from __future__ import annotations

import os
import logging
from typing import Any

from dotenv import load_dotenv
from core.api import CoreAPI

logger = logging.getLogger("ihouse-api")


def build_core() -> CoreAPI:
    """
    Phase 17A – Supabase-only canonical runtime.

    Invariants:
    - Single composition root
    - Supabase is the only event + state backend
    - Fail fast if required env vars are missing
    """

    load_dotenv(dotenv_path=".env")

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
        )

    from supabase import create_client
    from core.supabase_event_log import SupabaseEventLog
    from core.supabase_state_store import SupabaseStateStore

    sb = create_client(supabase_url, supabase_key)

    db_port: Any = SupabaseEventLog(client=sb)
    state_store = SupabaseStateStore(client=sb)

    logger.info("Using Supabase canonical runtime")

    return CoreAPI(
        db=db_port,
        event_log_applier=db_port,
        state_store=state_store,
    )
