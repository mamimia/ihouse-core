'use client';

/**
 * Phase 870/871 — Act As Context (Revised: Multi-Tab State Reconstruction)
 *
 * State reconstruction priority (on every tab load):
 *   1. If ihouse_token in localStorage has token_type === 'act_as':
 *      → Acting is in progress. Reconstruct from JWT claims + call GET /auth/act-as/status
 *        for authoritative remaining time.
 *      → Banner appears. End Session control appears. No silent acting state possible.
 *   2. If sessionStorage has ACT_AS_SESSION_KEY but token is not act_as:
 *      → Stale sessionStorage (prior session ended externally). Clean up.
 *   3. Neither → Not acting. Show selector if admin.
 *
 * This ensures:
 *   - New tabs: banner always reconstructed from token (not sessionStorage alone)
 *   - Page reloads: same
 *   - Expiry: consistent with manual end (cleanup only, no page reload on timer expiry)
 *   - No silent acting state is possible
 *
 * sessionStorage is now used only as a fast-path cache (avoids /status fetch on same tab).
 * It is never the sole source of truth for whether acting is active.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { setToken, getToken } from './api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ActAsSession {
    sessionId: string;
    actingAsRole: string;
    realAdminId: string;
    realAdminEmail: string;
    expiresAt: string;           // ISO timestamp
    remainingSeconds: number;    // updated every second by timer
}

interface ActAsContextType {
    session: ActAsSession | null;
    isActing: boolean;
    startActAs: (role: string, ttlSeconds?: number) => Promise<{ ok: boolean; error?: string }>;
    endActAs: () => Promise<void>;
    isAvailable: boolean;
}

const ActAsContext = createContext<ActAsContextType | undefined>(undefined);

// Storage keys
const ORIGINAL_TOKEN_KEY = 'ihouse_act_as_original_token';
const ACT_AS_SESSION_KEY = 'ihouse_act_as_session';   // sessionStorage cache (same-tab fast path)

// Role label map for display
export const ROLE_LABELS: Record<string, string> = {
    manager: 'Ops Manager',
    owner: 'Owner',
    cleaner: 'Cleaner',
    checkin: 'Check-in Staff',
    checkout: 'Check-out Staff',
    checkin_checkout: 'Check-in & Check-out',
    maintenance: 'Maintenance',
    worker: 'Staff',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function decodeJwtPayload(token: string): Record<string, unknown> | null {
    try {
        return JSON.parse(atob(token.split('.')[1] || '{}'));
    } catch {
        return null;
    }
}

async function apiFetch(path: string, token: string, init?: RequestInit): Promise<Response> {
    return fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...(init?.headers as Record<string, string> || {}),
        },
    });
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ActAsProvider({ children }: { children: React.ReactNode }) {
    const [session, setSession] = useState<ActAsSession | null>(null);
    const [isAvailable, setIsAvailable] = useState(false);
    const [initializing, setInitializing] = useState(true);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    // -----------------------------------------------------------------------
    // cleanupActAs — restore original token, clear state, clear storage
    // -----------------------------------------------------------------------
    const cleanupActAs = useCallback((opts?: { reload?: boolean }) => {
        if (timerRef.current) clearInterval(timerRef.current);

        // Restore original admin token
        try {
            const originalToken = sessionStorage.getItem(ORIGINAL_TOKEN_KEY)
                ?? localStorage.getItem('ihouse_act_as_original_token');
            if (originalToken) {
                setToken(originalToken);
                sessionStorage.removeItem(ORIGINAL_TOKEN_KEY);
                localStorage.removeItem('ihouse_act_as_original_token');
            }
        } catch {}

        sessionStorage.removeItem(ACT_AS_SESSION_KEY);
        setSession(null);
        setIsAvailable(true);

        if (opts?.reload) {
            window.location.reload();
        }
    }, []);

    // -----------------------------------------------------------------------
    // Reconstruct session from token + /status on every tab load
    // This is the source-of-truth path. sessionStorage is only a fast-path cache.
    // -----------------------------------------------------------------------
    useEffect(() => {
        if (typeof window === 'undefined') return;

        async function reconstruct() {
            const storedToken = localStorage.getItem('ihouse_token');
            if (!storedToken) {
                setInitializing(false);
                return;
            }

            const payload = decodeJwtPayload(storedToken);
            if (!payload) {
                setInitializing(false);
                return;
            }

            const isActAsToken = payload.token_type === 'act_as';

            if (!isActAsToken) {
                // Not acting. Clean up any stale sessionStorage.
                sessionStorage.removeItem(ACT_AS_SESSION_KEY);
                // Re-enable selector only if this is a real admin token
                if (payload.role === 'admin') setIsAvailable(true);
                setInitializing(false);
                return;
            }

            // ----------------------------------------------------------------
            // act_as token detected. Must show banner regardless of sessionStorage.
            // Call /status for authoritative remaining time.
            // ----------------------------------------------------------------
            const sessionIdFromJwt = String(payload.acting_session_id || '');
            const realAdminId = String(payload.real_admin_id || payload.sub || '');
            const realAdminEmail = String(payload.real_admin_email || '');
            const actingAsRole = String(payload.role || '');

            // Check sessionStorage fast-path first (saves a round-trip on same-tab reload)
            let remainingSeconds: number | null = null;
            let expiresAt: string | null = null;
            let sessionId = sessionIdFromJwt;

            try {
                const cached = sessionStorage.getItem(ACT_AS_SESSION_KEY);
                if (cached) {
                    const parsed = JSON.parse(cached) as ActAsSession;
                    if (parsed.sessionId === sessionIdFromJwt) {
                        const exp = new Date(parsed.expiresAt).getTime();
                        const rem = Math.floor((exp - Date.now()) / 1000);
                        if (rem > 0) {
                            remainingSeconds = rem;
                            expiresAt = parsed.expiresAt;
                        }
                    }
                }
            } catch {}

            // If no valid cache, call /status
            if (remainingSeconds === null) {
                try {
                    const res = await apiFetch('/auth/act-as/status', storedToken);
                    if (res.ok) {
                        const body = await res.json();
                        const active = body?.data?.active_session ?? body?.active_session;
                        if (active) {
                            remainingSeconds = active.remaining_seconds ?? 0;
                            expiresAt = active.expires_at ?? '';
                            sessionId = active.session_id ?? sessionIdFromJwt;
                        } else {
                            // Server says no active session — JWT may be orphaned/expired
                            cleanupActAs();
                            setInitializing(false);
                            return;
                        }
                    } else {
                        // /status unreachable (backend down) — fall back to JWT exp claim
                        const jwtExp = typeof payload.exp === 'number' ? payload.exp : 0;
                        remainingSeconds = Math.max(0, jwtExp - Math.floor(Date.now() / 1000));
                        expiresAt = new Date(jwtExp * 1000).toISOString();
                    }
                } catch {
                    // Network error — fall back to JWT exp claim
                    const jwtExp = typeof payload.exp === 'number' ? payload.exp : 0;
                    remainingSeconds = Math.max(0, jwtExp - Math.floor(Date.now() / 1000));
                    expiresAt = new Date(jwtExp * 1000).toISOString();
                }
            }

            if (!remainingSeconds || remainingSeconds <= 0) {
                cleanupActAs();
                setInitializing(false);
                return;
            }

            // Restore original token into sessionStorage if not present
            // (in a new tab ORIGINAL_TOKEN_KEY won't be in sessionStorage)
            const hasOriginal = !!sessionStorage.getItem(ORIGINAL_TOKEN_KEY);
            if (!hasOriginal) {
                // We can't know the original token in a new tab.
                // Store a sentinel so we at least don't try to use the act_as token as "original".
                // endActAs in a new tab will call /end but restoration requires re-login.
                // This is the honest limitation for new-tab end-session.
                sessionStorage.setItem(ORIGINAL_TOKEN_KEY, '__new_tab__');
            }

            const reconstructed: ActAsSession = {
                sessionId,
                actingAsRole,
                realAdminId,
                realAdminEmail,
                expiresAt: expiresAt ?? '',
                remainingSeconds,
            };

            // Update sessionStorage cache
            try {
                sessionStorage.setItem(ACT_AS_SESSION_KEY, JSON.stringify(reconstructed));
            } catch {}

            setSession(reconstructed);
            setIsAvailable(false);
            setInitializing(false);
        }

        reconstruct();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // -----------------------------------------------------------------------
    // Countdown timer
    // -----------------------------------------------------------------------
    useEffect(() => {
        if (!session) {
            if (timerRef.current) clearInterval(timerRef.current);
            return;
        }

        if (timerRef.current) clearInterval(timerRef.current);

        timerRef.current = setInterval(() => {
            setSession(prev => {
                if (!prev) return null;
                const remaining = prev.remainingSeconds - 1;
                if (remaining <= 0) {
                    // Expired — clean up without page reload (consistent, non-jarring)
                    cleanupActAs({ reload: false });
                    return null;
                }
                const updated = { ...prev, remainingSeconds: remaining };
                try {
                    sessionStorage.setItem(ACT_AS_SESSION_KEY, JSON.stringify(updated));
                } catch {}
                return updated;
            });
        }, 1000);

        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [session?.sessionId, cleanupActAs]);

    // -----------------------------------------------------------------------
    // startActAs
    // -----------------------------------------------------------------------
    const startActAs = useCallback(async (
        role: string,
        ttlSeconds = 3600,
    ): Promise<{ ok: boolean; error?: string }> => {
        const currentToken = getToken();
        if (!currentToken) return { ok: false, error: 'Not authenticated' };

        try {
            const res = await apiFetch('/auth/act-as/start', currentToken, {
                method: 'POST',
                body: JSON.stringify({ target_role: role, ttl_seconds: ttlSeconds }),
            });
            const body = await res.json();

            if (!res.ok) {
                const msg = body?.error?.message || body?.detail || 'Failed to start Act As';
                return { ok: false, error: msg };
            }

            const data = body?.data ?? body;

            // Save original token in both sessionStorage and localStorage
            // so new tabs opened AFTER session start can attempt restoration
            sessionStorage.setItem(ORIGINAL_TOKEN_KEY, currentToken);
            localStorage.setItem('ihouse_act_as_original_token', currentToken);

            // Swap to act_as token
            setToken(data.token);

            const newSession: ActAsSession = {
                sessionId: data.session_id,
                actingAsRole: data.acting_as_role,
                realAdminId: data.real_admin_id,
                realAdminEmail: data.real_admin_email,
                expiresAt: data.expires_at,
                remainingSeconds: data.ttl_seconds,
            };

            sessionStorage.setItem(ACT_AS_SESSION_KEY, JSON.stringify(newSession));
            setSession(newSession);
            setIsAvailable(false);

            return { ok: true };
        } catch (exc) {
            return { ok: false, error: `Network error: ${exc}` };
        }
    }, []);

    // -----------------------------------------------------------------------
    // endActAs
    // -----------------------------------------------------------------------
    const endActAs = useCallback(async () => {
        if (!session) return;

        // Use original token if available; otherwise fall back to current (act_as) token
        const originalToken = sessionStorage.getItem(ORIGINAL_TOKEN_KEY)
            ?? localStorage.getItem('ihouse_act_as_original_token');
        const tokenForEnd = (originalToken && originalToken !== '__new_tab__')
            ? originalToken
            : getToken() ?? '';

        // Best-effort server-side end
        try {
            await apiFetch('/auth/act-as/end', tokenForEnd, {
                method: 'POST',
                body: JSON.stringify({ session_id: session.sessionId }),
            });
        } catch {}

        // If new tab (no original token), must redirect to login after cleanup
        const isNewTab = originalToken === '__new_tab__' || !originalToken;

        cleanupActAs({ reload: !isNewTab });

        if (isNewTab) {
            // Can't restore admin session in this tab — force re-login
            localStorage.removeItem('ihouse_token');
            window.location.href = '/login';
        }
    }, [session, cleanupActAs]);

    // Don't render children during init to avoid flash of wrong state
    if (initializing) return <>{children}</>;

    return (
        <ActAsContext.Provider value={{
            session,
            isActing: session !== null,
            startActAs,
            endActAs,
            isAvailable,
        }}>
            {children}
        </ActAsContext.Provider>
    );
}

export function useActAs() {
    const ctx = useContext(ActAsContext);
    if (!ctx) return {
        session: null,
        isActing: false,
        startActAs: async () => ({ ok: false, error: 'No provider' }),
        endActAs: async () => {},
        isAvailable: false,
    };
    return ctx;
}
