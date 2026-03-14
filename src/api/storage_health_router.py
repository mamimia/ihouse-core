"""
Phase 765 — Storage E2E Verification Router
==============================================

Provides GET /admin/storage-health that tests upload → read → delete
on each configured storage bucket. Used to verify storage is functional
before going to staging.

No JWT required (ops surface, no sensitive data — just tests connectivity).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

_BUCKETS = ["pii-documents", "property-photos", "guest-uploads", "exports"]

# Test file content — tiny text file for each bucket
_TEST_CONTENT = b"ihouse-storage-health-probe"
_TEST_MIME = "text/plain"


def _get_db() -> Any:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


def _test_bucket(db: Any, bucket_name: str) -> dict:
    """
    Test a single bucket: upload → read → delete.

    Returns dict with {bucket, upload, read, delete, error} status.
    """
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    test_path = f"_health_probe/{ts}.txt"
    result = {
        "bucket": bucket_name,
        "upload": False,
        "read": False,
        "delete": False,
        "error": None,
    }

    try:
        # Upload
        db.storage.from_(bucket_name).upload(
            test_path,
            _TEST_CONTENT,
            file_options={"content-type": _TEST_MIME},
        )
        result["upload"] = True

        # List (verify exists)
        files = db.storage.from_(bucket_name).list("_health_probe")
        found = any(f.get("name", "").endswith(".txt") for f in (files or []))
        result["read"] = found

        # Delete
        db.storage.from_(bucket_name).remove([test_path])
        result["delete"] = True

    except Exception as exc:
        result["error"] = str(exc)
        logger.warning("storage-health: bucket=%s error=%s", bucket_name, exc)

        # Try cleanup even on error
        try:
            db.storage.from_(bucket_name).remove([test_path])
        except Exception:
            pass

    return result


@router.get(
    "/admin/storage-health",
    tags=["admin", "ops"],
    summary="Storage E2E health check (Phase 765)",
    description=(
        "Tests upload → read → delete on each storage bucket. "
        "Returns per-bucket status. No auth required (ops surface)."
    ),
    responses={
        200: {"description": "All buckets healthy"},
        503: {"description": "One or more buckets unhealthy or Supabase not configured"},
    },
)
async def storage_health() -> JSONResponse:
    db = _get_db()
    if not db:
        return JSONResponse(status_code=503, content={
            "status": "unconfigured",
            "message": "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set",
            "buckets": [],
        })

    results = []
    for bucket in _BUCKETS:
        results.append(_test_bucket(db, bucket))

    all_ok = all(r["upload"] and r["read"] and r["delete"] for r in results)

    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "healthy" if all_ok else "degraded",
            "buckets": results,
            "bucket_count": len(results),
            "healthy_count": sum(1 for r in results if r["upload"] and r["read"] and r["delete"]),
        },
    )
