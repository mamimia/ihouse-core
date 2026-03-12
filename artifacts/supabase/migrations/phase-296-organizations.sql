-- Phase 296 — Multi-Tenant Organization Foundation
-- Creates: organizations, org_members, tenant_org_map
-- These tables establish the org layer above individual tenant_ids,
-- enabling multi-user, multi-property management scenarios.
--
-- Invariant: tenant_id (JWT sub) remains the single authority for all
-- existing booking/financial/task operations. The org layer adds a
-- grouping abstraction on top — it never replaces tenant_id lookups.

-- ---------------------------------------------------------------------------
-- organizations
-- ---------------------------------------------------------------------------
-- An organization is a named group that owns one or more tenant_ids.
-- Created by any authenticated user; that user becomes the first org_admin.

CREATE TABLE IF NOT EXISTS public.organizations (
    org_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT        NOT NULL,
    slug            TEXT        UNIQUE NOT NULL,     -- URL-safe identifier, lowercase az09-_
    description     TEXT,
    created_by      TEXT        NOT NULL,            -- tenant_id of the creator
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_organizations_created_by
    ON public.organizations(created_by);

-- ---------------------------------------------------------------------------
-- org_members
-- ---------------------------------------------------------------------------
-- Maps individual tenant_ids (= Supabase Auth user UUIDs) to an org.
-- A tenant_id can belong to at most one organization.
-- role: 'org_admin' | 'manager' | 'member'

CREATE TABLE IF NOT EXISTS public.org_members (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    tenant_id       TEXT        NOT NULL,            -- JWT sub claim of the member
    role            TEXT        NOT NULL DEFAULT 'member'
                    CHECK (role IN ('org_admin', 'manager', 'member')),
    invited_by      TEXT,                            -- tenant_id of the inviting admin
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_org_members_tenant_id
    ON public.org_members(tenant_id);

CREATE INDEX IF NOT EXISTS idx_org_members_org_id
    ON public.org_members(org_id);

-- ---------------------------------------------------------------------------
-- tenant_org_map
-- ---------------------------------------------------------------------------
-- Lightweight lookup: given a tenant_id, what org does it belong to?
-- Kept in sync with org_members. Read-optimized. No write path from users.

CREATE TABLE IF NOT EXISTS public.tenant_org_map (
    tenant_id       TEXT        PRIMARY KEY,
    org_id          UUID        NOT NULL REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    role            TEXT        NOT NULL DEFAULT 'member',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenant_org_map_org_id
    ON public.tenant_org_map(org_id);

-- ---------------------------------------------------------------------------
-- Trigger: keep tenant_org_map in sync with org_members
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.sync_tenant_org_map()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF (TG_OP = 'DELETE') THEN
        DELETE FROM public.tenant_org_map WHERE tenant_id = OLD.tenant_id;
        RETURN OLD;
    ELSIF (TG_OP = 'INSERT' OR TG_OP = 'UPDATE') THEN
        INSERT INTO public.tenant_org_map (tenant_id, org_id, role, updated_at)
        VALUES (NEW.tenant_id, NEW.org_id, NEW.role, NOW())
        ON CONFLICT (tenant_id) DO UPDATE
            SET org_id = EXCLUDED.org_id,
                role   = EXCLUDED.role,
                updated_at = NOW();
        RETURN NEW;
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_tenant_org_map ON public.org_members;

CREATE TRIGGER trg_sync_tenant_org_map
AFTER INSERT OR UPDATE OR DELETE ON public.org_members
FOR EACH ROW EXECUTE FUNCTION public.sync_tenant_org_map();
