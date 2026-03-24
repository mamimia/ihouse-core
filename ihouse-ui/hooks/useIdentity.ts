'use client';

/**
 * Phase 862 P23 — useIdentity Hook
 *
 * Client-side hook to fetch the canonical identity surface from GET /auth/identity.
 * Used by pages that need to know:
 *   - whether the user has a tenant membership
 *   - what role they have
 *   - whether they have pending intake requests
 *
 * This replaces ad-hoc JWT decoding in individual page components.
 */

import { useState, useEffect, useCallback } from 'react';

export interface Identity {
    user_id: string;
    email: string;
    full_name: string;
    has_membership: boolean;
    tenant_id: string | null;
    role: string | null;
    is_active: boolean | null;
    intake_status: string | null;
}

export interface UseIdentityResult {
    identity: Identity | null;
    loading: boolean;
    error: string | null;
    refetch: () => void;
}

function getToken(): string | null {
    if (typeof document === 'undefined') return null;
    const match = document.cookie
        .split('; ')
        .find(c => c.startsWith('ihouse_token='));
    return match?.split('=')[1] || null;
}

export function useIdentity(): UseIdentityResult {
    const [identity, setIdentity] = useState<Identity | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchIdentity = useCallback(async () => {
        setLoading(true);
        setError(null);

        const token = getToken();
        if (!token) {
            setIdentity(null);
            setLoading(false);
            setError('NO_TOKEN');
            return;
        }

        try {
            const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
            const res = await fetch(`${apiBase}/auth/identity`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });

            if (!res.ok) {
                // Phase 877: Active Token Purge on 401/403
                // If we get an auth error, we MUST clear the token from browser state.
                // Otherwise, the page redirects to /login, but /login sees the token
                // and bounces us back here, causing an infinite redirect loop.
                if (res.status === 401 || res.status === 403) {
                    if (typeof document !== 'undefined') {
                        document.cookie = 'ihouse_token=; path=/; max-age=0; SameSite=Lax';
                    }
                    if (typeof window !== 'undefined') {
                        localStorage.removeItem('ihouse_token');
                    }
                }

                setError(`HTTP_${res.status}`);
                setIdentity(null);
                setLoading(false);
                return;
            }

            const data = await res.json();
            const payload = data.data || data;
            setIdentity(payload as Identity);
        } catch (e) {
            setError('FETCH_FAILED');
            setIdentity(null);
        }

        setLoading(false);
    }, []);

    useEffect(() => {
        fetchIdentity();
    }, [fetchIdentity]);

    return { identity, loading, error, refetch: fetchIdentity };
}
