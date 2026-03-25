/**
 * Phase 865 — Canonical Tab-Aware Token Store
 *
 * PRODUCT MODEL:
 *   Admin tab:     logs in via normal flow → token stored in localStorage + cookie
 *   Act As tab:    receives scoped JWT via /act-as?token=... landing page
 *                  → token stored in sessionStorage (tab-scoped, isolated)
 *                  → does NOT touch localStorage → admin tab is never mutated
 *   Parallel tabs: each Act As tab has its own sessionStorage → tokens never collide
 *
 * READ PRIORITY:
 *   sessionStorage.ihouse_token  ← Act As tab scoped token (if present)
 *   localStorage.ihouse_token    ← normal login token (fallback)
 *
 * EXPLICIT PRODUCT RULES enforced here:
 *   1. Act As tokens ONLY live in sessionStorage (setActAsTabToken)
 *   2. clearTabToken removes ONLY sessionStorage — never the admin's localStorage token
 *   3. Admin logout (which clears localStorage + cookie) propagates into Act As tabs
 *      because the middleware cookie will no longer be valid on their next navigation
 *   4. No consumer should call localStorage.getItem('ihouse_token') directly —
 *      all reads must go through getTabToken() for correct tab-aware behavior
 *
 * WHAT THIS DOES NOT DO:
 *   - Does not manage cookies (login/logout flows own that)
 *   - Does not call setToken() from lib/api.ts (admin-only path, unchanged)
 *   - Does not persist act_as tokens to localStorage (by design)
 */

const TOKEN_KEY = 'ihouse_token';

/**
 * Read the token for the current tab.
 * sessionStorage wins (Act As tab) → falls back to localStorage (admin / normal login).
 */
export function getTabToken(): string | null {
    if (typeof window === 'undefined') return null;
    return (
        sessionStorage.getItem(TOKEN_KEY) ??
        localStorage.getItem(TOKEN_KEY)
    );
}

/**
 * Store a scoped Act As JWT in sessionStorage for this tab only.
 * Must only be called by the /act-as landing page.
 * Does NOT touch localStorage — admin tab token is never modified.
 */
export function setActAsTabToken(token: string): void {
    if (typeof window === 'undefined') return;
    sessionStorage.setItem(TOKEN_KEY, token);
}

/**
 * Clear the Act As token for this tab.
 * Only removes from sessionStorage — the admin's localStorage token is intentionally
 * left intact so the admin tab continues operating after the worker tab is ended.
 *
 * After calling this, getTabToken() will fall back to localStorage.
 * If localStorage is also empty (admin logged out), the tab will be unauthenticated.
 */
export function clearTabToken(): void {
    if (typeof window === 'undefined') return;
    sessionStorage.removeItem(TOKEN_KEY);
}

/**
 * Returns true if the current tab has an Act As scoped token in sessionStorage.
 * Used to detect Act As context without decoding the JWT.
 */
export function isActAsTab(): boolean {
    if (typeof window === 'undefined') return false;
    return sessionStorage.getItem(TOKEN_KEY) !== null;
}

/**
 * Decode the tab-scoped token's payload without signature verification.
 * Returns null if no token or decode fails.
 */
export function decodeTabTokenPayload(): Record<string, unknown> | null {
    const token = getTabToken();
    if (!token) return null;
    try {
        const parts = token.split('.');
        if (parts.length !== 3) return null;
        return JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
    } catch {
        return null;
    }
}
