'use client';

/**
 * Phase 870 — Act As Context
 *
 * Manages the client-side state for Act As sessions:
 *   - Token swap (preserves original admin token, uses scoped act_as token)
 *   - Session metadata (role, email, remaining time, session ID)
 *   - Countdown timer
 *   - Clean start/end lifecycle
 *
 * Trust model: The act_as token comes from the backend (POST /auth/act-as/start).
 * The original admin token is saved in sessionStorage for restoration on session end.
 *
 * Important: Act As is only available in non-production environments.
 * The backend returns 404 when IHOUSE_ENV=production.
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
    remainingSeconds: number;    // updated every second
}

interface ActAsContextType {
    /** Current active session, or null if not acting */
    session: ActAsSession | null;
    /** True when an acting session is active */
    isActing: boolean;
    /** Start an acting session with the given role */
    startActAs: (role: string, ttlSeconds?: number) => Promise<{ ok: boolean; error?: string }>;
    /** End the current acting session */
    endActAs: () => Promise<void>;
    /** Whether Act As is available (non-production, admin user) */
    isAvailable: boolean;
}

const ActAsContext = createContext<ActAsContextType | undefined>(undefined);

// Storage keys
const ORIGINAL_TOKEN_KEY = 'ihouse_act_as_original_token';
const ACT_AS_SESSION_KEY = 'ihouse_act_as_session';

// ---------------------------------------------------------------------------
// Helper: raw fetch with token
// ---------------------------------------------------------------------------

async function actAsFetch(path: string, token: string, init?: RequestInit) {
    const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...(init?.headers as Record<string, string> || {}),
        },
    });
    return res;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ActAsProvider({ children }: { children: React.ReactNode }) {
    const [session, setSession] = useState<ActAsSession | null>(null);
    const [isAvailable, setIsAvailable] = useState(false);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    // Check if user is admin and Act As is available
    useEffect(() => {
        if (typeof window === 'undefined') return;
        try {
            const token = localStorage.getItem('ihouse_token');
            if (!token) return;
            const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
            // Act As available only for admin users (non-acting, non-preview)
            if (payload.role === 'admin' && payload.token_type !== 'act_as') {
                setIsAvailable(true);
            }
        } catch {}

        // Restore session from sessionStorage if page reloads during act-as
        try {
            const saved = sessionStorage.getItem(ACT_AS_SESSION_KEY);
            if (saved) {
                const parsed = JSON.parse(saved) as ActAsSession;
                const expiresAt = new Date(parsed.expiresAt).getTime();
                const remaining = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000));
                if (remaining > 0) {
                    setSession({ ...parsed, remainingSeconds: remaining });
                } else {
                    // Session expired — clean up
                    cleanupActAs();
                }
            }
        } catch {}
    }, []);

    // Countdown timer
    useEffect(() => {
        if (!session) {
            if (timerRef.current) clearInterval(timerRef.current);
            return;
        }

        timerRef.current = setInterval(() => {
            setSession(prev => {
                if (!prev) return null;
                const remaining = prev.remainingSeconds - 1;
                if (remaining <= 0) {
                    // Session expired
                    cleanupActAs();
                    return null;
                }
                // Update sessionStorage
                const updated = { ...prev, remainingSeconds: remaining };
                try { sessionStorage.setItem(ACT_AS_SESSION_KEY, JSON.stringify(updated)); } catch {}
                return updated;
            });
        }, 1000);

        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [session?.sessionId]); // Only restart timer when session changes

    const cleanupActAs = useCallback(() => {
        // Restore original admin token
        try {
            const originalToken = sessionStorage.getItem(ORIGINAL_TOKEN_KEY);
            if (originalToken) {
                setToken(originalToken);
                sessionStorage.removeItem(ORIGINAL_TOKEN_KEY);
            }
        } catch {}
        sessionStorage.removeItem(ACT_AS_SESSION_KEY);
        setSession(null);
        setIsAvailable(true); // Re-enable Act As selector
    }, []);

    const startActAs = useCallback(async (role: string, ttlSeconds = 3600): Promise<{ ok: boolean; error?: string }> => {
        const currentToken = getToken();
        if (!currentToken) return { ok: false, error: 'Not authenticated' };

        try {
            const res = await actAsFetch('/auth/act-as/start', currentToken, {
                method: 'POST',
                body: JSON.stringify({ target_role: role, ttl_seconds: ttlSeconds }),
            });

            const body = await res.json();

            if (!res.ok) {
                const errorMsg = body?.error?.message || body?.detail || 'Failed to start Act As';
                return { ok: false, error: errorMsg };
            }

            const data = body?.data || body;

            // Save original admin token before swapping
            sessionStorage.setItem(ORIGINAL_TOKEN_KEY, currentToken);

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
            setIsAvailable(false); // Hide selector while acting

            return { ok: true };
        } catch (exc) {
            return { ok: false, error: `Network error: ${exc}` };
        }
    }, []);

    const endActAs = useCallback(async () => {
        if (!session) return;

        // Try to end server-side (best-effort)
        try {
            const originalToken = sessionStorage.getItem(ORIGINAL_TOKEN_KEY);
            const tokenToUse = originalToken || getToken() || '';
            await actAsFetch('/auth/act-as/end', tokenToUse, {
                method: 'POST',
                body: JSON.stringify({ session_id: session.sessionId }),
            });
        } catch {}

        // Always clean up client-side
        cleanupActAs();

        // Reload to restore admin context
        window.location.reload();
    }, [session, cleanupActAs]);

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
