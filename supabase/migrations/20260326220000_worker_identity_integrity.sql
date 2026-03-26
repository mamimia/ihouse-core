-- Phase 947: Worker Identity Integrity Guardrails
-- Migration: 20260326220000_worker_identity_integrity.sql
--
-- Adds a database-level function that can be called to audit identity mismatches
-- between tenant_permissions.user_id and auth.users.email vs comm_preference.email.
-- This cannot be a hard constraint (auth.users is in a separate schema) but the
-- function can be called by admin tools and monitoring jobs.

-- ── 1. Identity audit function ─────────────────────────────────────────────
-- Returns all tenant_permissions rows where the auth email diverges from
-- the comm_preference email. Safe read-only function, no side effects.
CREATE OR REPLACE FUNCTION public.audit_worker_identity_mismatches(p_tenant_id text DEFAULT NULL)
RETURNS TABLE (
    user_id         text,
    tenant_id       text,
    display_name    text,
    auth_email      text,
    comm_email      text,
    mismatch        boolean,
    created_at      timestamptz
)
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
    SELECT
        tp.user_id::text,
        tp.tenant_id,
        tp.display_name,
        au.email AS auth_email,
        (tp.comm_preference->>'email') AS comm_email,
        (
            (tp.comm_preference->>'email') IS NOT NULL
            AND lower(trim(au.email)) IS DISTINCT FROM lower(trim(tp.comm_preference->>'email'))
        ) AS mismatch,
        tp.created_at
    FROM public.tenant_permissions tp
    LEFT JOIN auth.users au ON au.id = tp.user_id::uuid
    WHERE
        (p_tenant_id IS NULL OR tp.tenant_id = p_tenant_id)
        AND tp.role = 'worker'
    ORDER BY mismatch DESC, tp.created_at DESC;
$$;

COMMENT ON FUNCTION public.audit_worker_identity_mismatches IS
'Phase 947: Returns worker identity chain state. Call with no args to audit all tenants, or pass tenant_id to scope. Rows with mismatch=true indicate a broken identity linkage where the auth account email differs from the comm_preference email. These workers will be blocked from receiving access links until repaired.';

-- ── 2. Quick-view: only mismatched rows ────────────────────────────────────
CREATE OR REPLACE VIEW public.v_worker_identity_mismatches AS
    SELECT * FROM public.audit_worker_identity_mismatches()
    WHERE mismatch = true;

COMMENT ON VIEW public.v_worker_identity_mismatches IS
'Phase 947: Live view of all workers with a broken identity linkage. Monitored by the identity preflight check in the resend-access endpoint.';

-- ── 3. Repair audit log table ──────────────────────────────────────────────
-- Records every identity repair action for auditability.
CREATE TABLE IF NOT EXISTS public.identity_repair_log (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id       text NOT NULL,
    user_id_from    text NOT NULL,       -- old (wrong) user_id
    user_id_to      text NOT NULL,       -- new (correct) user_id
    auth_email_from text,
    auth_email_to   text,
    repaired_by     text NOT NULL,       -- admin user_id who performed the repair
    repair_method   text NOT NULL,       -- 'manual_db' | 'admin_ui' | 'api'
    notes           text,
    repaired_at     timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.identity_repair_log IS
'Phase 947: Immutable audit trail for every worker identity repair. Each row records who changed which user_id FK to what, and why.';
