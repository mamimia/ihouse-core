'use client';

/**
 * Registration Step 2 — Email
 * Route: /register/email
 *
 * Email field + "Get started" button → Supabase signUp
 * OR "Sign up with Google" → Supabase OAuth
 */

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import AuthCard from '../../../../components/auth/AuthCard';
import ProgressBar from '../../../../components/auth/ProgressBar';
import GoogleSignInButton from '../../../../components/auth/GoogleSignInButton';
import AuthDivider from '../../../../components/auth/AuthDivider';
import { supabase } from '@/lib/supabaseClient';

function RegisterEmailForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const portfolio = searchParams.get('portfolio') || '';

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSignUp = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!email.trim()) { setError('Please enter your email'); return; }
        if (!password || password.length < 6) { setError('Password must be at least 6 characters'); return; }
        setError(null);
        if (!supabase) { setError('Registration is not configured yet.'); return; }
        setLoading(true);
        try {
            const { data, error: signUpError } = await supabase!.auth.signUp({
                email: email.trim(),
                password,
                options: {
                    data: {
                        portfolio_size: portfolio,
                    },
                },
            });
            if (signUpError) {
                setError(signUpError.message);
                return;
            }
            // Move to profile step
            router.push(`/register/profile?email=${encodeURIComponent(email.trim())}&portfolio=${portfolio}`);
        } catch {
            setError('Registration failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleGoogleSignUp = async () => {
        if (!supabase) { setError('Google sign-up is not configured yet.'); return; }
        setLoading(true);
        try {
            const redirectTo = typeof window !== 'undefined'
                ? `${window.location.origin}/auth/callback`
                : '/auth/callback';
            await supabase!.auth.signInWithOAuth({
                provider: 'google',
                options: { redirectTo },
            });
        } catch {
            setError('Google sign-up failed.');
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
        <AuthCard title="Create your account" subtitle="Enter your email to get started">
            <ProgressBar current={2} total={3} />

            <form onSubmit={handleSignUp} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                <div>
                    <label style={{
                        display: 'block', fontSize: 'var(--text-xs, 12px)', fontWeight: 600,
                        color: 'rgba(234,229,222,0.5)', marginBottom: 'var(--space-2, 8px)',
                        textTransform: 'uppercase', letterSpacing: '0.06em',
                    }}>Email</label>
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
                <div>
                    <label style={{
                        display: 'block', fontSize: 'var(--text-xs, 12px)', fontWeight: 600,
                        color: 'rgba(234,229,222,0.5)', marginBottom: 'var(--space-2, 8px)',
                        textTransform: 'uppercase', letterSpacing: '0.06em',
                    }}>Password</label>
                    <input
                        className="auth-input"
                        type="password"
                        value={password}
                        onChange={e => { setPassword(e.target.value); setError(null); }}
                        placeholder="At least 6 characters"
                        autoComplete="new-password"
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
                    disabled={loading || !email.trim() || !password}
                    style={{
                        width: '100%', padding: '14px',
                        background: 'var(--color-moss, #334036)', border: 'none',
                        borderRadius: 'var(--radius-md, 12px)', color: 'var(--color-white, #F8F6F2)',
                        fontSize: 'var(--text-base, 16px)', fontWeight: 600,
                        fontFamily: 'var(--font-brand, "Inter", sans-serif)',
                        cursor: loading || !email.trim() || !password ? 'not-allowed' : 'pointer',
                        opacity: loading || !email.trim() || !password ? 0.4 : 1,
                        transition: 'all 0.2s', minHeight: 48,
                    }}
                >
                    {loading ? 'Creating account…' : 'Get started'}
                </button>
            </form>

            <AuthDivider />
            <GoogleSignInButton onClick={handleGoogleSignUp} label="Sign up with Google" disabled={loading} />

            <div style={{ marginTop: 'var(--space-6, 24px)', textAlign: 'center' }}>
                <a href="/login" className="auth-link" style={{ fontSize: 'var(--text-sm, 14px)' }}>
                    Already a Domaniqo user? <span style={{ textDecoration: 'underline' }}>Login here</span>
                </a>
            </div>
        </AuthCard>
    );
}

export default function RegisterEmailPage() {
    return (
        <Suspense fallback={null}>
            <RegisterEmailForm />
        </Suspense>
    );
}
