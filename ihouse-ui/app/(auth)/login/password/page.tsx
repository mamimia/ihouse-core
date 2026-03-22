'use client';

/**
 * Login Screen 2 — Password Step
 * Route: /login/password
 *
 * Receives email from Screen 1 via query param.
 * Shows: email (with Change link), password field, Remember me, Sign In, Google, links.
 */

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import AuthCard from '../../../../components/auth/AuthCard';
import GoogleSignInButton from '../../../../components/auth/GoogleSignInButton';
import AuthDivider from '../../../../components/auth/AuthDivider';
import PasswordInput from '../../../../components/auth/PasswordInput';
import { supabase } from '@/lib/supabaseClient';
import { api, setToken } from '../../../../lib/api';
import { getRoleRoute } from '../../../../lib/roleRoute';

function PasswordForm() {
    const searchParams = useSearchParams();
    const emailParam = searchParams.get('email') || '';
    const rememberParam = searchParams.get('remember') === '1';

    const [password, setPassword] = useState('');
    const [remember, setRemember] = useState(rememberParam);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSignIn = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!password) {
            setError('Please enter your password');
            return;
        }
        setError(null);
        setLoading(true);
        try {
            const resp = await api.loginWithEmail(emailParam, password);
            setToken(resp.token);
            // Set cookie with appropriate maxAge
            const maxAge = remember ? 30 * 24 * 3600 : resp.expires_in; // 30 days if remember, else default
            document.cookie = `ihouse_token=${resp.token}; path=/; max-age=${maxAge}; SameSite=Lax`;
            // Persist language on successful login
            if (resp.language) {
                localStorage.setItem('domaniqo_lang', resp.language);
            }
            // Persist email if remember
            if (remember) {
                localStorage.setItem('domaniqo_remember_email', emailParam);
            }
            window.location.href = getRoleRoute(resp.token);
        } catch (err: unknown) {
            if (err instanceof Error && err.message.includes('401')) {
                setError('Invalid email or password.');
            } else if (err instanceof Error && err.message.includes('403')) {
                setError('Your account is not assigned to any organization. Contact your administrator.');
            } else if (err instanceof Error && err.message.includes('503')) {
                setError('Authentication not configured. Contact your administrator.');
            } else if (err instanceof Error && (err.message.includes('500') || err.message.includes('[object Object]'))) {
                setError('Login failed. Please try again.');
            } else {
                setError(err instanceof Error ? err.message : 'Login failed');
            }
        } finally {
            setLoading(false);
        }
    };

    const handleGoogleSignIn = async () => {
        if (!supabase) { setError('Google sign-in is not configured yet.'); return; }
        setLoading(true);
        setError(null);
        try {
            const redirectTo = typeof window !== 'undefined'
                ? `${window.location.origin}/auth/callback`
                : '/auth/callback';
            const { error: oauthError } = await supabase!.auth.signInWithOAuth({
                provider: 'google',
                options: { redirectTo },
            });
            if (oauthError) {
                setError('Google sign-in failed. Please try again.');
                setLoading(false);
            }
        } catch {
            setError('Google sign-in failed. Please try again.');
            setLoading(false);
        }
    };

    const inputStyle: React.CSSProperties = {
        width: '100%',
        padding: '12px 14px',
        background: 'var(--color-midnight, #171A1F)',
        border: '1px solid rgba(234,229,222,0.1)',
        borderRadius: 'var(--radius-md, 12px)',
        color: 'var(--color-stone, #EAE5DE)',
        fontSize: 'var(--text-sm, 14px)',
        transition: 'border-color 0.2s, box-shadow 0.2s',
        fontFamily: 'var(--font-sans, inherit)',
        boxSizing: 'border-box',
    };

    return (
        <AuthCard title="Welcome" subtitle="Enter your password to continue">
            <form onSubmit={handleSignIn} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                {/* Email display + Change link */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    background: 'rgba(234,229,222,0.03)',
                    border: '1px solid rgba(234,229,222,0.06)',
                    borderRadius: 'var(--radius-md, 12px)',
                }}>
                    <span style={{
                        fontSize: 'var(--text-sm, 14px)',
                        color: 'var(--color-stone, #EAE5DE)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                    }}>
                        {emailParam}
                    </span>
                    <a
                        href="/login"
                        style={{
                            fontSize: 'var(--text-xs, 12px)',
                            color: 'var(--color-copper, #B56E45)',
                            textDecoration: 'none',
                            fontWeight: 600,
                            flexShrink: 0,
                            marginLeft: 12,
                        }}
                    >
                        Change
                    </a>
                </div>

                <div>
                    <label style={{
                        display: 'block',
                        fontSize: 'var(--text-xs, 12px)',
                        fontWeight: 600,
                        color: 'rgba(234,229,222,0.5)',
                        marginBottom: 'var(--space-2, 8px)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                    }}>
                        Password
                    </label>
                    <PasswordInput
                        id="input-password"
                        value={password}
                        onChange={e => { setPassword(e.target.value); setError(null); }}
                        autoFocus
                        disabled={loading}
                        autoComplete="current-password"
                    />
                </div>

                {/* Remember me */}
                <label style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    cursor: 'pointer',
                    fontSize: 'var(--text-sm, 14px)',
                    color: 'rgba(234,229,222,0.5)',
                }}>
                    <input
                        type="checkbox"
                        checked={remember}
                        onChange={e => setRemember(e.target.checked)}
                        style={{ accentColor: 'var(--color-copper, #B56E45)', width: 16, height: 16 }}
                    />
                    Remember me
                </label>

                {/* Error */}
                {error && (
                    <div style={{
                        background: 'rgba(155,58,58,0.1)',
                        border: '1px solid rgba(155,58,58,0.25)',
                        borderRadius: 'var(--radius-md, 12px)',
                        padding: '10px 14px',
                        fontSize: 'var(--text-sm, 14px)',
                        color: '#EF4444',
                    }}>
                        ⚠ {error}
                    </div>
                )}

                {/* Sign In */}
                <button
                    id="btn-signin"
                    type="submit"
                    className="auth-btn"
                    disabled={loading || !password}
                    style={{
                        padding: '14px',
                        background: 'var(--color-moss, #334036)',
                        border: 'none',
                        borderRadius: 'var(--radius-md, 12px)',
                        color: 'var(--color-white, #F8F6F2)',
                        fontSize: 'var(--text-base, 16px)',
                        fontWeight: 600,
                        fontFamily: 'var(--font-brand, "Inter", sans-serif)',
                        letterSpacing: '-0.01em',
                        cursor: loading || !password ? 'not-allowed' : 'pointer',
                        opacity: loading || !password ? 0.4 : 1,
                        transition: 'all 0.2s',
                        marginTop: 'var(--space-1, 4px)',
                        minHeight: 48,
                    }}
                >
                    {loading ? 'Signing in…' : 'Sign In'}
                </button>
            </form>

            <AuthDivider />

            <GoogleSignInButton
                onClick={handleGoogleSignIn}
                disabled={loading}
            />

            {/* Bottom links */}
            <div style={{
                marginTop: 'var(--space-6, 24px)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-3, 12px)',
                textAlign: 'center',
            }}>
                <a href="/login/forgot" className="auth-link" style={{ fontSize: 'var(--text-sm, 14px)' }}>
                    Forgot password?
                </a>
                <div style={{ height: 1, background: 'rgba(234,229,222,0.04)', margin: '4px 0' }} />
                <a href="/login?role=host" className="auth-link" style={{ fontSize: 'var(--text-sm, 14px)' }}>
                    Domaniqo for Host users? <span style={{ textDecoration: 'underline' }}>Log in here</span>
                </a>
                <a href="/register" className="auth-link" style={{ fontSize: 'var(--text-sm, 14px)' }}>
                    New to Domaniqo? <span style={{ textDecoration: 'underline' }}>Create an account</span>
                </a>
            </div>
        </AuthCard>
    );
}

export default function PasswordPage() {
    return (
        <Suspense fallback={null}>
            <PasswordForm />
        </Suspense>
    );
}
