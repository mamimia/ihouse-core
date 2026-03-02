from __future__ import annotations

import os
import logging
from typing import Any

from dotenv import load_dotenv

from core.api import CoreAPI
from core.db.config import db_path
from core.db.sqlite_event_log_adapter import SqliteEventLogAdapter
from core.sqlite_event_log import SqliteEventLog
from core.sqlite_state_store import SqliteStateStore


logger = logging.getLogger("ihouse-api")


def build_core() -> CoreAPI:
    load_dotenv(dotenv_path=".env")

    adapter_type = os.getenv("DB_ADAPTER", "supabase").strip().lower()

    if adapter_type == "supabase":
        from supabase import create_client
        from core.supabase_event_log import SupabaseEventLog
        from core.supabase_state_store import SupabaseStateStore

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not supabase_url or not supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

        sb = create_client(supabase_url, supabase_key)

        db_port: Any = SupabaseEventLog(client=sb)
        state_store = SupabaseStateStore(client=sb)

        logger.info("Using Supabase adapter (log-only mode)")
        return CoreAPI(
            db=db_port,
            event_log_applier=db_port,
            state_store=state_store,
        )

    # SQLite canonical Phase 14 wiring
    dbp = db_path()

    db_port = SqliteEventLogAdapter(dbp)
    applier = SqliteEventLog(db_path=dbp)
    state_store = SqliteStateStore(db_path=dbp)

    logger.info("Using SQLite adapter (canonical executor enabled)")

    return CoreAPI(
        db=db_port,
        event_log_applier=applier,
        state_store=state_store,
    )
