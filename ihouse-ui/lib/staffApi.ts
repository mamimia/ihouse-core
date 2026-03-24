/**
 * Phase 864 — Shared Staff API Utilities
 *
 * Single source of truth for API helpers used by worker-facing ops surfaces:
 *   /ops/cleaner, /ops/maintenance, /ops/checkin, /ops/checkout
 *
 * Extracted to eliminate identical copies in each page file.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

/** Extract worker identity from JWT stored in localStorage. */
export function getWorkerId(): string {
    if (typeof window === 'undefined') return '';
    try {
        const token = localStorage.getItem('ihouse_token');
        if (!token) return '';
        const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
        return payload.user_id || payload.sub || payload.tenant_id || '';
    } catch { return ''; }
}

/** Get auth token from localStorage. */
function getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('ihouse_token');
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
