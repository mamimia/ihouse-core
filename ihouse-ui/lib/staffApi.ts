/**
 * Phase 864 — Shared Staff API Utilities
 * Phase 865 — Tab-aware token reads via tokenStore (sessionStorage-first)
 *
 * Single source of truth for API helpers used by worker-facing ops surfaces:
 *   /ops/cleaner, /ops/maintenance, /ops/checkin, /ops/checkout
 *
 * Token reads use getTabToken() which prioritizes sessionStorage (Act As tab)
 * over localStorage (normal login), enabling true parallel tab isolation.
 */

import { getTabToken, decodeTabTokenPayload } from './tokenStore';

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

/** Extract worker identity from the tab-scoped token. */
export function getWorkerId(): string {
    if (typeof window === 'undefined') return '';
    try {
        const payload = decodeTabTokenPayload();
        if (!payload) return '';
        return (payload.user_id || payload.sub || payload.tenant_id || '') as string;
    } catch { return ''; }
}

/** Get auth token for the current tab (Act As or normal). */
function getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return getTabToken();
}

/** Authenticated fetch wrapper for staff API calls. */
export async function apiFetch<T = any>(path: string, init?: RequestInit): Promise<T> {
    const token = getToken();
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers as Record<string, string> || {}),
    };

    // Phase 866 — Propagate preview role for server-enforced read-only
    if (typeof window !== 'undefined') {
        const previewRole = sessionStorage.getItem('ihouse_preview_role');
        if (previewRole) {
            headers['X-Preview-Role'] = previewRole;
        }
    }

    const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers,
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
}

/** Base URL for direct fetch calls (e.g. FormData uploads that skip apiFetch). */
export { BASE as API_BASE };
export { getToken };

