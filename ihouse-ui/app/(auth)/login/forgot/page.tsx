'use client';

/**
 * Forgot Password Page
 * Route: /login/forgot
 *
 * Sends Supabase password reset email.
 */

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import AuthCard from '../../../../components/auth/AuthCard';
import { supabase } from '@/lib/supabaseClient';

function ForgotPasswordForm() {
    const searchParams = useSearchParams();
    const [email, setEmail] = useState(searchParams.get('email') || '');
    const [loading, setLoading] = useState(false);
    const [sent, setSent] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSendReset = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!email.trim()) { setError('Please enter your email'); return; }
        setError(null);
        if (!supabase) { setError('Password reset is not configured yet.'); return; }
        setLoading(true);
        try {
            const { error: resetError } = await supabase!.auth.resetPasswordForEmail(email.trim(), {
                redirectTo: typeof window !== 'undefined' ? `${window.location.origin}/login/reset` : '/login/reset',
            });
            if (resetError) {
                setError(resetError.message);
            } else {
                setSent(true);
            }
        } catch {
            setError('Failed to send reset email. Please try again.');
        } finally {
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

    if (sent) {
        return (
            <AuthCard title="Check your email" subtitle="We sent you a password reset link">
                <div style={{
                    textAlign: 'center',
                    padding: 'var(--space-6, 24px) 0',
                }}>
                    <div style={{ fontSize: 48, marginBottom: 'var(--space-4, 16px)' }}>📧</div>
                    <p style={{
                        fontSize: 'var(--text-sm, 14px)',
                        color: 'rgba(234,229,222,0.5)',
                        lineHeight: 1.6,
                        marginBottom: 4,
                    }}>
                        If <strong style={{ color: 'var(--color-stone, #EAE5DE)' }}>{email}</strong> has an account,
                        you&apos;ll receive an email shortly.
                    </p>
                    <p style={{
                        fontSize: 12,
                        color: 'rgba(234,229,222,0.3)',
                        lineHeight: 1.6,
                        marginBottom: 'var(--space-6, 24px)',
                    }}>
                        Click the link in the email to set a new password.
                        Check your spam folder if it doesn&apos;t arrive within a few minutes.
                    </p>
                    <a
                        href={`/login/password?email=${encodeURIComponent(email)}`}
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
                        Back to sign in
                    </a>
                </div>
            </AuthCard>
        );
    }

    return (
        <AuthCard title="Reset your password" subtitle="Enter your email and we'll send a reset link">
            <form onSubmit={handleSendReset} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                <div>
                    <label style={{
                        display: 'block', fontSize: 'var(--text-xs, 12px)', fontWeight: 600,
                        color: 'rgba(234,229,222,0.5)', marginBottom: 'var(--space-2, 8px)',
                        textTransform: 'uppercase', letterSpacing: '0.06em',
                    }}>
                        Email
                    </label>
                    <input
                        className="auth-input"
                        type="email"
                        value={email}
                        onChange={e => { setEmail(e.target.value); setError(null); }}
                        placeholder="you@example.com"
                        autoComplete="email"
                        autoFocus
                        disabled={loading}
                        style={inputStyle}
                    />
                </div>

                {error && (
                    <div style={{
                        background: 'rgba(155,58,58,0.1)', border: '1px solid rgba(155,58,58,0.25)',
                        borderRadius: 'var(--radius-md, 12px)', padding: '10px 14px',
                        fontSize: 'var(--text-sm, 14px)', color: '#EF4444',
                    }}>
                        ⚠ {error}
                    </div>
                )}

                <button
                    type="submit"
                    className="auth-btn"
                    disabled={loading || !email.trim()}
                    style={{
                        padding: '14px', background: 'var(--color-moss, #334036)',
                        border: 'none', borderRadius: 'var(--radius-md, 12px)',
                        color: 'var(--color-white, #F8F6F2)', fontSize: 'var(--text-base, 16px)',
                        fontWeight: 600, fontFamily: 'var(--font-brand, "Inter", sans-serif)',
                        cursor: loading || !email.trim() ? 'not-allowed' : 'pointer',
                        opacity: loading || !email.trim() ? 0.4 : 1,
                        transition: 'all 0.2s', minHeight: 48,
                    }}
                >
                    {loading ? 'Sending…' : 'Send Reset Link'}
                </button>
            </form>

            <div style={{ marginTop: 'var(--space-6, 24px)', textAlign: 'center' }}>
                <a href="/login" className="auth-link" style={{ fontSize: 'var(--text-sm, 14px)' }}>
                    ← Back to login
                </a>
            </div>
        </AuthCard>
    );
}

export default function ForgotPasswordPage() {
    return (
        <Suspense fallback={null}>
            <ForgotPasswordForm />
        </Suspense>
    );
}
