"""
Phase 495 — Scheduled Job Runner

Central scheduler that runs periodic jobs:
- Pre-arrival scan (every 6 hours)
- Conflict scan (daily)
- Financial reconciliation (daily)
- SLA escalation check (every 15 minutes)
- Guest token cleanup (daily — remove expired)

Uses a simple interval-based runner that can be triggered
by a cron job, Supabase pg_cron, or manual API call.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.job_runner")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ---------------------------------------------------------------------------
# Job definitions
# ---------------------------------------------------------------------------

JOBS: Dict[str, Dict[str, Any]] = {
    "pre_arrival_scan": {
        "interval_hours": 6,
        "description": "Scan for upcoming check-ins and create pre-arrival tasks",
    },
    "conflict_scan": {
        "interval_hours": 24,
        "description": "Scan all properties for booking date overlaps",
    },
    "sla_escalation": {
        "interval_hours": 0.25,  # 15 minutes
        "description": "Check for SLA breaches and escalate",
    },
    "token_cleanup": {
        "interval_hours": 24,
        "description": "Remove expired guest tokens",
    },
    "financial_recon": {
        "interval_hours": 24,
        "description": "Run financial reconciliation against OTA data",
    },
}


def _should_run(db: Any, job_name: str, interval_hours: float) -> bool:
    """Check if a job should run based on last execution time."""
    try:
        result = (
            db.table("scheduled_job_log")
            .select("completed_at")
            .eq("job_name", job_name)
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return True  # Never run before

        last_run = result.data[0].get("completed_at", "")
        if not last_run:
            return True

        from datetime import timedelta
        last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - last_dt).total_seconds() > interval_hours * 3600
    except Exception:
        return True  # On error, run the job


def _log_job_start(db: Any, job_name: str, job_id: str) -> None:
    """Record job start in scheduled_job_log."""
    try:
        db.table("scheduled_job_log").insert({
            "job_id": job_id,
            "job_name": job_name,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as exc:
        logger.warning("Job log start failed for %s: %s", job_name, exc)


def _log_job_complete(
    db: Any,
    job_id: str,
    status: str,
    result_summary: Dict,
) -> None:
    """Update job log with completion status."""
    try:
        db.table("scheduled_job_log").update({
            "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result_json": result_summary,
        }).eq("job_id", job_id).execute()
    except Exception as exc:
        logger.warning("Job log complete failed: %s", exc)


def _run_job(job_name: str, db: Any) -> Dict[str, Any]:
    """Execute a single job and return its result."""
    try:
        if job_name == "pre_arrival_scan":
            from services.pre_arrival_scanner import run_pre_arrival_scan
            return run_pre_arrival_scan(db=db)

        elif job_name == "conflict_scan":
            from services.conflict_scanner import run_full_scan
            return run_full_scan(dry_run=False)

        elif job_name == "sla_escalation":
            try:
                from services.sla_engine import check_escalations
                return check_escalations(db)
            except ImportError:
                return {"status": "skipped", "reason": "sla_engine not available"}

        elif job_name == "token_cleanup":
            return _cleanup_expired_tokens(db)

        elif job_name == "financial_recon":
            try:
                from services.financial_reconciler import run_reconciliation
                return run_reconciliation(db=db)
            except ImportError:
                return {"status": "skipped", "reason": "financial_reconciler not available"}

        else:
            return {"status": "unknown_job", "job_name": job_name}

    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _cleanup_expired_tokens(db: Any) -> Dict[str, Any]:
    """Remove expired guest tokens from guest_tokens table."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        result = (
            db.table("guest_tokens")
            .delete()
            .lt("expires_at", now)
            .execute()
        )
        deleted = len(result.data) if result.data else 0
        return {"status": "completed", "tokens_cleaned": deleted}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_all_due_jobs(
    *,
    force: bool = False,
    dry_run: bool = False,
    jobs_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run all scheduled jobs that are due.

    Args:
        force: Run all jobs regardless of interval.
        dry_run: Report which jobs would run without executing.
        jobs_filter: Optional list of job names to check.

    Returns:
        Summary of jobs run.
    """
    import uuid
    db = _get_db()

    results = {
        "total_jobs": 0,
        "executed": 0,
        "skipped": 0,
        "errors": 0,
        "dry_run": dry_run,
        "jobs": {},
    }

    jobs_to_check = jobs_filter or list(JOBS.keys())

    for job_name in jobs_to_check:
        if job_name not in JOBS:
            continue

        job_def = JOBS[job_name]
        results["total_jobs"] += 1

        should_run = force or _should_run(db, job_name, job_def["interval_hours"])

        if not should_run:
            results["skipped"] += 1
            results["jobs"][job_name] = {"status": "skipped", "reason": "not_due"}
            continue

        if dry_run:
            results["executed"] += 1
            results["jobs"][job_name] = {"status": "would_run"}
            continue

        job_id = str(uuid.uuid4())
        _log_job_start(db, job_name, job_id)

        try:
            result = _run_job(job_name, db)
            status = result.get("status", "completed")
            _log_job_complete(db, job_id, status, result)
            results["executed"] += 1
            results["jobs"][job_name] = result
        except Exception as exc:
            _log_job_complete(db, job_id, "error", {"error": str(exc)})
            results["errors"] += 1
            results["jobs"][job_name] = {"status": "error", "error": str(exc)}

    logger.info("Job runner complete: executed=%d skipped=%d errors=%d",
                results["executed"], results["skipped"], results["errors"])
    return results
