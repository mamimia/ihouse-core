'use client';

/**
 * Login Screen 1 — Email First
 * Phase 839 — Full localization (EN / TH / HE)
 * Route: /login
 */

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AuthCard from '../../../components/auth/AuthCard';
import GoogleSignInButton from '../../../components/auth/GoogleSignInButton';
import AuthDivider from '../../../components/auth/AuthDivider';
import { supabase } from '../../../lib/supabaseClient';
import { getRoleRoute } from '../../../lib/roleRoute';
import { useLanguage } from '../../../lib/LanguageContext';

export default function LoginPage() {
    const router = useRouter();
    const { t } = useLanguage();
    const [email, setEmail] = useState('');
    const [remember, setRemember] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        if (typeof window !== 'undefined') {
            const token = localStorage.getItem('ihouse_token');
            // Only redirect if token exists in BOTH localStorage AND cookie.
            // If token is in localStorage but missing from cookies, the middleware
            // will redirect back to /login, creating an infinite loop.
            const hasCookie = document.cookie.includes('ihouse_token');
            if (token && hasCookie) {
                window.location.href = getRoleRoute(token);
            } else if (token && !hasCookie) {
                // Stale localStorage token — clear it to prevent future loops
                localStorage.removeItem('ihouse_token');
            }
        }
        const stored = localStorage.getItem('domaniqo_remember_email');
        if (stored) {
            setEmail(stored);
            setRemember(true);
        }
    }, []);

    const handleContinue = (e: React.FormEvent) => {
        e.preventDefault();
        if (!email.trim()) {
            setError(t('auth.err_email_required'));
            return;
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
            setError(t('auth.err_email_invalid'));
            return;
        }
        if (remember) {
            localStorage.setItem('domaniqo_remember_email', email.trim());
        } else {
            localStorage.removeItem('domaniqo_remember_email');
        }
        router.push(`/login/password?email=${encodeURIComponent(email.trim())}${remember ? '&remember=1' : ''}`);
    };

    const handleGoogleSignIn = async () => {
        if (!supabase) { setError(t('auth.err_google_fail')); return; }
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
                setError(t('auth.err_google_fail'));
                setLoading(false);
            }
        } catch {
            setError(t('auth.err_google_fail'));
            setLoading(false);
        }
    };

    if (!mounted) return null;

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
        <AuthCard titleKey="auth.welcome" subtitleKey="auth.subtitle">
            <form onSubmit={handleContinue} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                {/* Email */}
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
                        {t('auth.email')}
                    </label>
                    <input
                        id="input-email"
                        className="auth-input"
                        type="email"
                        value={email}
                        onChange={e => { setEmail(e.target.value); setError(null); }}
                        placeholder={t('auth.email_placeholder')}
                        autoComplete="email"
                        autoFocus
                        disabled={loading}
                        style={inputStyle}
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
                    {t('auth.remember_me')}
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

                {/* Continue */}
                <button
                    id="btn-continue"
                    type="submit"
                    className="auth-btn"
                    disabled={loading || !email.trim()}
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
                        cursor: loading || !email.trim() ? 'not-allowed' : 'pointer',
                        opacity: loading || !email.trim() ? 0.4 : 1,
                        transition: 'all 0.2s',
                        marginTop: 'var(--space-1, 4px)',
                        minHeight: 48,
                    }}
                >
                    {t('auth.continue')}
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
                <a href="/get-started" className="auth-link" style={{ fontSize: 'var(--text-sm, 14px)' }}>
                    {t('auth.host_link')} <span style={{ textDecoration: 'underline' }}>{t('auth.host_link_cta')}</span>
                </a>
                <a href="/get-started" className="auth-link" style={{ fontSize: 'var(--text-sm, 14px)' }}>
                    {t('auth.register_link')} <span style={{ textDecoration: 'underline' }}>{t('auth.register_link_cta')}</span>
                </a>
            </div>
        </AuthCard>
    );
}
