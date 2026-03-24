'use client';

/**
 * Google OAuth Callback
 * Route: /auth/callback
 *
 * Supabase redirects here after Google sign-in.
 * Exchanges code for session, then resolves tenant/role via backend.
 */

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabaseClient';
import { setToken } from '@/lib/api';
import { getRoleRoute } from '@/lib/roleRoute';
import AuthCard from '@/components/auth/AuthCard';

export default function AuthCallbackPage() {
    const [status, setStatus] = useState<'loading' | 'error'>('loading');
    const [errorMsg, setErrorMsg] = useState('');

    useEffect(() => {
        handleCallback();
    }, []);

    async function handleCallback() {
        try {
            if (!supabase) {
                setStatus('error');
                setErrorMsg('Authentication is not configured. Please contact your administrator.');
                return;
            }

            // Phase 865: Check if this is a return from identity linking (not login).
            // Guard: only treat this as a linking callback if Supabase already has a
            // fresh session on the page (i.e. we actually returned from Google OAuth
            // mid-linking).  If there is no Supabase session yet the key is a stale
            // leftover from a previous browser restart — clear it and fall through to
            // the normal login flow so we don't loop back to /profile without a token.
            const linkingProvider = sessionStorage.getItem('ihouse_linking_provider');
            if (linkingProvider) {
                const { data: linkCheck } = await supabase!.auth.getSession();
                if (linkCheck?.session) {
                    // Real linking return — go back to the initiating route
                    sessionStorage.removeItem('ihouse_linking_provider');
                    const returnRoute = sessionStorage.getItem('ihouse_linking_return') || '/profile';
                    sessionStorage.removeItem('ihouse_linking_return');
                    window.location.href = returnRoute;
                    return;
                } else {
                    // Stale key leftover from a previous session — clear and continue
                    sessionStorage.removeItem('ihouse_linking_provider');
                    sessionStorage.removeItem('ihouse_linking_return');
                }
            }

            // Supabase handles the code exchange automatically via the URL hash/params
            const { data, error } = await supabase.auth.getSession();
            if (error || !data.session) {
                setStatus('error');
                setErrorMsg('Failed to complete sign-in. Please try again.');
                return;
            }

            const session = data.session;
            const userId = session.user.id;
            const userEmail = session.user.email || '';

            // Call backend to resolve tenant/role and get iHouse JWT
            const BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
            const resp = await fetch(`${BASE_URL}/auth/google-callback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    email: userEmail,
                    access_token: session.access_token,
                    full_name: session.user.user_metadata?.full_name || '',
                }),
            });

            const body = await resp.json();
            const result = body?.data || body;

            if (!resp.ok || !result.token) {
                setStatus('error');
                setErrorMsg(result?.error || 'Failed to complete sign-in.');
                return;
            }

            // Store token and redirect
            setToken(result.token);
            if (result.language) {
                localStorage.setItem('domaniqo_lang', result.language);
            }
            // Secure flag required so Chrome accepts the cookie on HTTPS (staging/production).
            const isHttps = typeof window !== 'undefined' && window.location.protocol === 'https:';
            document.cookie = `ihouse_token=${result.token}; path=/; max-age=${result.expires_in || 86400}; SameSite=Lax${isHttps ? '; Secure' : ''}`;
            window.location.href = getRoleRoute(result.token);
        } catch (err) {
            setStatus('error');
            setErrorMsg('An unexpected error occurred. Please try again.');
        }
    }

    if (status === 'error') {
        return (
            <AuthCard title="Sign-in failed" subtitle={errorMsg}>
                <div style={{ textAlign: 'center', padding: 'var(--space-4, 16px) 0' }}>
                    <a
                        href="/login"
                        style={{
                            display: 'inline-block',
                            padding: '12px 24px',
                            background: 'var(--color-moss, #334036)',
                            borderRadius: 'var(--radius-md, 12px)',
                            color: 'var(--color-white, #F8F6F2)',
                            fontSize: 'var(--text-sm, 14px)',
                            fontWeight: 600,
                            textDecoration: 'none',
                        }}
                    >
                        Back to login
                    </a>
                </div>
            </AuthCard>
        );
    }

    // Loading state
    return (
        <AuthCard title="Signing you in…" subtitle="Please wait while we complete your sign-in">
            <div style={{ textAlign: 'center', padding: 'var(--space-8, 32px) 0' }}>
                <div style={{
                    width: 40, height: 40, margin: '0 auto',
                    border: '3px solid rgba(234,229,222,0.1)',
                    borderTopColor: 'var(--color-copper, #B56E45)',
                    borderRadius: '50%',
                    animation: 'authSpin 0.8s linear infinite',
                }} />
                <style>{`@keyframes authSpin { to { transform: rotate(360deg) } }`}</style>
            </div>
        </AuthCard>
    );
}
