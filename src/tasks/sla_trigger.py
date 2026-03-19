"""
Phase 843 — SLA Trigger Integration
Scheduled job to evaluate SLA rules over open tasks and trigger dispatch.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from tasks.sla_engine import evaluate
from channels.sla_dispatch_bridge import dispatch_escalations

logger = logging.getLogger(__name__)

def check_escalations(db: Any) -> Dict[str, Any]:
    """
    Called by job_runner periodically to sweep active tasks via sla_engine.
    """
    now_utc_dt = datetime.now(timezone.utc)
    now_utc_str = now_utc_dt.isoformat()
    
    # Query non-terminal tasks
    # We do a direct string match just like task_writer.py
    try:
        res = db.table("tasks").select("*").not_.in_("status", ["COMPLETED", "CANCELED"]).execute()
        tasks = res.data or []
    except Exception as e:
        logger.error("Failed to query open tasks for SLA sweep: %s", e)
        return {"status": "error", "error": str(e)}
    
    if not tasks:
        return {"status": "completed", "escalations_triggered": 0}
        
    escalations = 0
    
    # Standard SLA Policy
    policy = {
        "notify_ops_on": ["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
        "notify_admin_on": ["COMPLETION_SLA_BREACH"]
    }
    
    for row in tasks:
        tenant_id = row.get("tenant_id")
        created_at_str = row.get("created_at")
        ack_sla_minutes = row.get("ack_sla_minutes", 0)
        
        # Calculate ack_due_str based on created_at
        ack_due_str = ""
        if created_at_str and ack_sla_minutes:
            dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            ack_due_str = (dt + timedelta(minutes=ack_sla_minutes)).isoformat()
        
        # Calculate completed_due_str based on due_date (naively 18:00 UTC for now)
        completed_due_str = ""
        if row.get("due_date"):
            completed_due_str = f"{row['due_date']}T18:00:00+00:00"
            
        is_acked = row["status"] in ("ACKNOWLEDGED", "IN_PROGRESS")
            
        payload = {
            "idempotency": {"request_id": f"sla-sweep-{row['task_id']}-{int(now_utc_dt.timestamp())}"},
            "actor": {"actor_id": "system", "role": "system"},
            "context": {
                "run_id": f"sweep-{int(now_utc_dt.timestamp())}",
                "timers_utc": {
                    "now_utc": now_utc_str,
                    "task_ack_due_utc": ack_due_str,
                    "task_completed_due_utc": completed_due_str
                }
            },
            "task": {
                "task_id": row["task_id"],
                "property_id": row["property_id"],
                "task_type": row["kind"],
                "state": row["status"],
                "priority": row["priority"],
                "ack_state": "Acked" if is_acked else "Unacked"
            },
            "policy": policy
        }
        
        try:
            result = evaluate(payload)
            if result.actions:
                dispatch_escalations(db, tenant_id, result.actions)
                escalations += len(result.actions)
                
                # Write the audit event
                try:
                    db.table("audit_events").insert({
                        "tenant_id": tenant_id,
                        "entity_id": row["task_id"],
                        "entity_type": "task",
                        "event_type": "sla_escalation",
                        "actor_id": "system",
                        "payload": result.audit_event
                    }).execute()
                except Exception as audit_exc:
                    logger.warning("Failed to write audit event for task=%s: %s", row["task_id"], audit_exc)
                    
        except Exception as exc:
            logger.error("SLA Sweep failed for task=%s: %s", row.get("task_id"), exc)
            
    return {"status": "completed", "escalations_triggered": escalations}
