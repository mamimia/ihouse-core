"""
Phase 221 — Scheduled Job Runner

Pure scheduler module using APScheduler 3.x AsyncIOScheduler.
Wired into FastAPI lifespan in main.py.

Scheduled jobs:
    1. sla_sweep          — every 2 minutes
       Queries open/in-progress tasks for the whole tenant,
       evaluates each against sla_engine.evaluate(), logs any
       SLA breaches. Best-effort, non-raising.

    2. dlq_threshold_alert — every 10 minutes
       Counts unprocessed DLQ entries (ota_dead_letter where
       replay_result IS NULL). Logs a WARNING if count exceeds
       DLQ_ALERT_THRESHOLD (default: 5).

    3. health_log          — every 15 minutes
       Runs run_health_checks() and logs the result. Degraded/
       unhealthy status logged at WARNING level. Useful for
       monitoring pipelines that tail structured logs.

Design invariants:
    - All jobs are best-effort: exceptions are caught and logged,
      never propagated to the ASGI event loop.
    - No job modifies canonical state (apply_envelope not called).
    - No job blocks the event loop (sync calls run in thread pool).
    - Scheduler is DISABLED if IHOUSE_SCHEDULER_ENABLED=false.
    - All intervals are overridable via env vars (testing/ops use).
    - Supabase client is created lazily per job run (connection pooling
      is handled by the supabase-py library).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional
import asyncio

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (overridable via env vars)
# ---------------------------------------------------------------------------

def _int_env(name: str, default: int) -> int:
    """Read an integer env var with a safe fallback."""
    try:
        return int(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name, "").lower()
    if val in ("0", "false", "no", "off"):
        return False
    if val in ("1", "true", "yes", "on"):
        return True
    return default


# Intervals in seconds
SLA_SWEEP_INTERVAL_S: int = _int_env("IHOUSE_SLA_SWEEP_INTERVAL_S", 120)      # 2 min
DLQ_CHECK_INTERVAL_S: int = _int_env("IHOUSE_DLQ_CHECK_INTERVAL_S", 600)     # 10 min
HEALTH_LOG_INTERVAL_S: int = _int_env("IHOUSE_HEALTH_LOG_INTERVAL_S", 900)   # 15 min
DLQ_ALERT_THRESHOLD: int = _int_env("IHOUSE_DLQ_ALERT_THRESHOLD", 5)

SCHEDULER_ENABLED: bool = _bool_env("IHOUSE_SCHEDULER_ENABLED", True)


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    """Create a fresh Supabase service-role client. Non-caching — per-job."""
    from supabase import create_client  # type: ignore[import]
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Job 1: SLA sweep
# ---------------------------------------------------------------------------

def _run_sla_sweep() -> None:
    """
    Queries all open/in-progress tasks and evaluates SLA state for each.

    Flow:
        1. Fetch tasks with status in (PENDING, ACKNOWLEDGED, IN_PROGRESS).
        2. For each task, build the sla_engine payload with now_utc +
           task-level ACK and completion SLA times.
        3. Call sla_engine.evaluate().
        4. If any triggers fire, log at WARNING level.

    ACK SLA: CRITICAL_ACK_SLA_MINUTES = 5 minutes from created_at.
    Completion SLA: task-type dependent — CLEANING/GENERAL = 24h,
                    CHECKIN_PREP/CHECKOUT_VERIFY = 2h, MAINTENANCE = 48h.
    """
    try:
        db = _get_db()
    except RuntimeError as exc:
        logger.debug("sla_sweep: skipping — %s", exc)
        return

    try:
        result = (
            db.table("tasks")
            .select(
                "task_id, tenant_id, property_id, kind, status, priority, "
                "created_at, acknowledged_at"
            )
            .in_("status", ["PENDING", "ACKNOWLEDGED", "IN_PROGRESS"])
            .limit(500)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("sla_sweep: DB query failed: %s", exc)
        return

    if not rows:
        return

    from tasks.sla_engine import evaluate, CRITICAL_ACK_SLA_MINUTES
    import uuid

    now = datetime.now(tz=timezone.utc)
    now_str = now.isoformat()

    # Completion SLA windows by task kind (hours)
    _COMPLETION_HOURS: dict[str, int] = {
        "CLEANING": 24,
        "GENERAL": 24,
        "MAINTENANCE": 48,
        "CHECKIN_PREP": 2,
        "CHECKOUT_VERIFY": 2,
        "GUEST_WELCOME": 4,
    }

    breaches = 0
    for row in rows:
        try:
            task_id = row.get("task_id") or ""
            kind = str(row.get("kind") or "GENERAL").upper()
            status = str(row.get("status") or "PENDING")
            priority = str(row.get("priority") or "NORMAL").capitalize()
            created_at_str = row.get("created_at") or now_str

            # Compute ACK due (CRITICAL_ACK_SLA_MINUTES from created_at)
            try:
                created_dt = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
            except Exception:
                created_dt = now

            from datetime import timedelta
            ack_due = (
                created_dt + timedelta(minutes=CRITICAL_ACK_SLA_MINUTES)
            ).isoformat()

            # Completion SLA
            completion_hours = _COMPLETION_HOURS.get(kind, 24)
            completion_due = (
                created_dt + timedelta(hours=completion_hours)
            ).isoformat()

            # Derive sla_engine state
            ack_state = "Unacked" if status in ("PENDING",) else "Acked"
            engine_state = {
                "PENDING": "Open",
                "ACKNOWLEDGED": "InProgress",
                "IN_PROGRESS": "InProgress",
            }.get(status, "Open")

            payload = {
                "actor": {"actor_id": "scheduler", "role": "system"},
                "context": {
                    "run_id": str(uuid.uuid4()),
                    "timers_utc": {
                        "now_utc": now_str,
                        "task_ack_due_utc": ack_due,
                        "task_completed_due_utc": completion_due,
                    },
                },
                "task": {
                    "task_id": task_id,
                    "property_id": str(row.get("property_id") or ""),
                    "task_type": kind,
                    "state": engine_state,
                    "priority": priority,
                    "ack_state": ack_state,
                },
                "policy": {
                    "notify_ops_on": ["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
                    "notify_admin_on": ["COMPLETION_SLA_BREACH"],
                },
                "idempotency": {"request_id": str(uuid.uuid4())},
            }

            result_obj = evaluate(payload)

            if result_obj.actions:
                triggers = result_obj.audit_event.get("triggers_fired", [])
                logger.warning(
                    "sla_sweep: SLA breach task_id=%s kind=%s triggers=%s",
                    task_id,
                    kind,
                    triggers,
                )
                breaches += 1

        except Exception as exc:  # noqa: BLE001
            logger.warning("sla_sweep: error evaluating task=%s: %s", row.get("task_id"), exc)

    logger.info(
        "sla_sweep: evaluated %d open tasks, %d SLA breaches",
        len(rows),
        breaches,
    )


# ---------------------------------------------------------------------------
# Job 2: DLQ threshold alert
# ---------------------------------------------------------------------------

def _run_dlq_check() -> None:
    """
    Counts unprocessed DLQ entries and alerts if count >= DLQ_ALERT_THRESHOLD.

    Reads: ota_dead_letter where replay_result IS NULL.
    Logs WARNING if count meets or exceeds threshold.
    """
    try:
        db = _get_db()
    except RuntimeError as exc:
        logger.debug("dlq_check: skipping — %s", exc)
        return

    try:
        result = (
            db.table("ota_dead_letter")
            .select("id", count="exact")
            .is_("replay_result", "null")
            .execute()
        )
        count = result.count if result.count is not None else len(result.data or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("dlq_check: DB query failed: %s", exc)
        return

    if count >= DLQ_ALERT_THRESHOLD:
        logger.warning(
            "dlq_check: %d unprocessed DLQ entries (threshold=%d) — "
            "review /admin/dlq for details",
            count,
            DLQ_ALERT_THRESHOLD,
        )
    else:
        logger.info("dlq_check: %d unprocessed DLQ entries (ok)", count)


# ---------------------------------------------------------------------------
# Job 3: Health log
# ---------------------------------------------------------------------------

def _run_health_log() -> None:
    """
    Runs run_health_checks() and logs the result.

    Logs INFO on ok, WARNING on degraded/unhealthy.
    Useful for monitoring pipelines that tail structured logs.
    """
    try:
        from api.health import run_health_checks
        result = run_health_checks(
            version=os.environ.get("APP_VERSION", "0.1.0"),
            env=os.environ.get("IHOUSE_ENV", "production"),
        )
        log_fn = logger.warning if result.status != "ok" else logger.info
        log_fn(
            "health_log: status=%s checks=%s",
            result.status,
            {k: v.get("status") for k, v in result.checks.items()},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_log: check failed: %s", exc)


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

_scheduler: Optional[Any] = None


def build_scheduler() -> Any:
    """
    Build and return a configured AsyncIOScheduler.

    Does NOT start the scheduler — caller must call .start().
    Returns None if IHOUSE_SCHEDULER_ENABLED=false.
    """
    if not SCHEDULER_ENABLED:
        logger.info("Scheduler disabled (IHOUSE_SCHEDULER_ENABLED=false)")
        return None

    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import]

    sched = AsyncIOScheduler()

    sched.add_job(
        _run_sla_sweep,
        "interval",
        seconds=SLA_SWEEP_INTERVAL_S,
        id="sla_sweep",
        name="SLA Sweep",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )

    sched.add_job(
        _run_dlq_check,
        "interval",
        seconds=DLQ_CHECK_INTERVAL_S,
        id="dlq_threshold_alert",
        name="DLQ Threshold Alert",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    sched.add_job(
        _run_health_log,
        "interval",
        seconds=HEALTH_LOG_INTERVAL_S,
        id="health_log",
        name="Health Log",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    logger.info(
        "Scheduler built: sla_sweep=%ds, dlq_check=%ds, health_log=%ds",
        SLA_SWEEP_INTERVAL_S,
        DLQ_CHECK_INTERVAL_S,
        HEALTH_LOG_INTERVAL_S,
    )
    return sched


def start_scheduler() -> None:
    """Start the global scheduler. Safe to call multiple times."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is not None:
        return
    _scheduler = build_scheduler()
    if _scheduler is not None:
        _scheduler.start()
        logger.info("Scheduler started with %d jobs", len(_scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Stop the global scheduler cleanly. Called on app shutdown."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scheduler shutdown error: %s", exc)
        _scheduler = None


def get_scheduler_status() -> dict:
    """
    Return a status dict for the scheduler and its jobs.
    Used by GET /admin/scheduler-status endpoint.
    """
    if not SCHEDULER_ENABLED:
        return {"enabled": False, "running": False, "jobs": []}

    if _scheduler is None:
        return {"enabled": True, "running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_utc": next_run.isoformat() if next_run else None,
        })

    return {
        "enabled": True,
        "running": _scheduler.running,
        "jobs": jobs,
        "config": {
            "sla_sweep_interval_s": SLA_SWEEP_INTERVAL_S,
            "dlq_check_interval_s": DLQ_CHECK_INTERVAL_S,
            "health_log_interval_s": HEALTH_LOG_INTERVAL_S,
            "dlq_alert_threshold": DLQ_ALERT_THRESHOLD,
        },
    }
