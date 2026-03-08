"""
Phase 66 migration: create booking_financial_facts table.

Usage:
    cd "/Users/clawadmin/Antigravity Proj/ihouse-core"
    source .venv/bin/activate
    PYTHONPATH=src python3 scripts/migrate_phase66_financial_facts.py
"""
import os
import sys

# ---------------------------------------------------------------------------
# Load env
# ---------------------------------------------------------------------------
from pathlib import Path
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client  # noqa: E402

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
client = create_client(url, key)

# ---------------------------------------------------------------------------
# DDL statements — executed one by one via insert + RPC workaround
# Each statement uses Supabase's postgrest query builder can't run DDL.
# We'll use the pg_dump / supabase db approach instead.
# ---------------------------------------------------------------------------

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS booking_financial_facts (
      id                   BIGSERIAL PRIMARY KEY,
      booking_id           TEXT         NOT NULL,
      tenant_id            TEXT         NOT NULL,
      provider             TEXT         NOT NULL,
      total_price          NUMERIC(12,4),
      currency             CHAR(3),
      ota_commission       NUMERIC(12,4),
      taxes                NUMERIC(12,4),
      fees                 NUMERIC(12,4),
      net_to_property      NUMERIC(12,4),
      source_confidence    TEXT         NOT NULL,
      raw_financial_fields JSONB        NOT NULL DEFAULT '{}',
      event_kind           TEXT         NOT NULL,
      recorded_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
    )
    """,
    "ALTER TABLE booking_financial_facts ENABLE ROW LEVEL SECURITY",
    """
    DO $$ BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'booking_financial_facts'
        AND policyname = 'service_role_insert'
      ) THEN
        CREATE POLICY service_role_insert ON booking_financial_facts
          FOR INSERT TO service_role WITH CHECK (true);
      END IF;
    END $$
    """,
    """
    DO $$ BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'booking_financial_facts'
        AND policyname = 'service_role_select'
      ) THEN
        CREATE POLICY service_role_select ON booking_financial_facts
          FOR SELECT TO service_role USING (true);
      END IF;
    END $$
    """,
    "CREATE INDEX IF NOT EXISTS ix_bff_booking_id ON booking_financial_facts (booking_id)",
    "CREATE INDEX IF NOT EXISTS ix_bff_tenant_id  ON booking_financial_facts (tenant_id)",
]

print("Running Phase 66 migration: booking_financial_facts...")

# Supabase REST API doesn't support DDL via PostgREST.
# Use the management API via the db execute endpoint.
import urllib.request
import json

project_ref = url.split("//")[1].split(".")[0]
management_url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"

# Try Supabase management API (requires access token, not always available)
# Fallback: print SQL for manual execution

print("\n" + "="*60)
print("MIGRATION SQL (apply this in Supabase SQL Editor):")
print("="*60)

ddl = """
-- Phase 66: booking_financial_facts projection table
-- Run this in the Supabase SQL Editor

CREATE TABLE IF NOT EXISTS booking_financial_facts (
  id                   BIGSERIAL PRIMARY KEY,
  booking_id           TEXT         NOT NULL,
  tenant_id            TEXT         NOT NULL,
  provider             TEXT         NOT NULL,
  total_price          NUMERIC(12,4),
  currency             CHAR(3),
  ota_commission       NUMERIC(12,4),
  taxes                NUMERIC(12,4),
  fees                 NUMERIC(12,4),
  net_to_property      NUMERIC(12,4),
  source_confidence    TEXT         NOT NULL,
  raw_financial_fields JSONB        NOT NULL DEFAULT '{}',
  event_kind           TEXT         NOT NULL,
  recorded_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

ALTER TABLE booking_financial_facts ENABLE ROW LEVEL SECURITY;

CREATE POLICY service_role_insert ON booking_financial_facts
  FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY service_role_select ON booking_financial_facts
  FOR SELECT TO service_role USING (true);

CREATE INDEX IF NOT EXISTS ix_bff_booking_id ON booking_financial_facts (booking_id);
CREATE INDEX IF NOT EXISTS ix_bff_tenant_id  ON booking_financial_facts (tenant_id);
"""

print(ddl)

# ---------------------------------------------------------------------------
# Verify table exists after manual run
# ---------------------------------------------------------------------------
print("Verifying table exists...")
try:
    result = client.table("booking_financial_facts").select("id").limit(1).execute()
    print("✅ booking_financial_facts table exists and is accessible.")
except Exception as e:
    print(f"❌ Table not yet accessible: {e}")
    print("Please run the SQL above in Supabase Studio, then re-run this script.")
    sys.exit(1)
