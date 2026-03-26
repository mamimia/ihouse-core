'use client';

/**
 * Auth Callback — handles both Google OAuth and Magic Link/Invite returns.
 * Route: /auth/callback
 *
 * TWO distinct flows arrive here:
 *
 * A) Google OAuth: Supabase redirects here after Google sign-in.
 *    The hash may or may not contain tokens. We use getSession().
 *
 * B) Magic Link / Invite Link (worker first-time access):
 *    Supabase verifies the OTP server-side, then redirects here with
 *    #access_token=JWT&refresh_token=...
 *    We extract the worker identity DIRECTLY from the JWT in the hash.
 *    This avoids any dependency on Supabase's cached session (which may
 *    belong to the admin who was previously logged in on the same device).
 *
 * CRITICAL: The hash fragment is captured at MODULE LOAD TIME (line below)
 * because Supabase's detectSessionInUrl will consume and remove it from the
 * URL before React's useEffect fires.
 */

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabaseClient';
import { setToken } from '@/lib/api';
import { getRoleRoute } from '@/lib/roleRoute';
import AuthCard from '@/components/auth/AuthCard';

// ── Capture hash IMMEDIATELY at module load, before Supabase consumes it ──
const _capturedHash = typeof window !== 'undefined' ? window.location.hash : '';

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
            const linkingProvider = sessionStorage.getItem('ihouse_linking_provider');
            if (linkingProvider) {
                const { data: linkCheck } = await supabase!.auth.getSession();
                if (linkCheck?.session) {
                    sessionStorage.removeItem('ihouse_linking_provider');
                    const returnRoute = sessionStorage.getItem('ihouse_linking_return') || '/profile';
                    sessionStorage.removeItem('ihouse_linking_return');
                    window.location.href = returnRoute;
                    return;
                } else {
                    sessionStorage.removeItem('ihouse_linking_provider');
                    sessionStorage.removeItem('ihouse_linking_return');
                }
            }

            // ── Phase 946: Determine identity source ──────────────────────────
            //
            // Parse _capturedHash for magic link tokens.
            // If present → decode the access_token JWT directly to get the
            //               worker's user_id and email. No Supabase session needed.
            // If absent  → this is a Google OAuth callback; use getSession().
            //
            let userId: string;
            let userEmail: string;
            let accessToken: string;
            let fullName: string;

            const hashParams = new URLSearchParams(
                _capturedHash.replace(/^#/, '')
            );
            const hashAccessToken = hashParams.get('access_token');

            if (hashAccessToken) {
                // ─── Magic Link / Invite Link flow ───────────────────────
                // The access_token IS a Supabase JWT. Decode it to get the
                // worker's identity directly. No reliance on cached sessions.
                try {
                    const jwtPayload = JSON.parse(atob(hashAccessToken.split('.')[1]));
                    userId = jwtPayload.sub || '';
                    userEmail = jwtPayload.email || '';
                    accessToken = hashAccessToken;
                    fullName = jwtPayload.user_metadata?.full_name || '';
                } catch (decodeErr) {
                    setStatus('error');
                    setErrorMsg('Invalid access link. Please request a new one.');
                    return;
                }

                if (!userId || !userEmail) {
                    setStatus('error');
                    setErrorMsg('Access link is missing identity information. Please request a new one.');
                    return;
                }
            } else {
                // ─── Google OAuth flow ────────────────────────────────────
                // No hash tokens → Supabase handled the OAuth code exchange.
                // getSession() returns the freshly authenticated Google user.
                const { data, error } = await supabase.auth.getSession();
                if (error || !data.session) {
                    setStatus('error');
                    setErrorMsg('Failed to complete sign-in. Please try again.');
                    return;
                }
                userId = data.session.user.id;
                userEmail = data.session.user.email || '';
                accessToken = data.session.access_token;
                fullName = data.session.user.user_metadata?.full_name || '';
            }

            // Call backend to resolve tenant/role and get iHouse JWT
            const BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
            const resp = await fetch(`${BASE_URL}/auth/google-callback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    email: userEmail,
                    access_token: accessToken,
                    full_name: fullName,
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
            // Phase 948h: ALWAYS set language from the authenticated worker's identity.
            // This prevents cross-user leakage on shared devices. If Worker A (th)
            // logs out and Worker B (en) logs in, we must reset to 'en', not inherit 'th'.
            localStorage.setItem('domaniqo_lang', result.language || 'en');
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
