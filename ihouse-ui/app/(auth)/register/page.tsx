'use client';

/**
 * Phase 871 — Standalone Sign Up
 * Route: /register
 *
 * Creates an identity-only Supabase Auth account.
 * Fields: full name, email, password (or Google OAuth).
 * After success → /welcome (identity-only surface).
 *
 * This is separate from /get-started, which is the property onboarding wizard.
 * A user who wants a basic account should not be forced into property onboarding.
 */

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import AuthCard from '../../../components/auth/AuthCard';
import GoogleSignInButton from '../../../components/auth/GoogleSignInButton';
import AuthDivider from '../../../components/auth/AuthDivider';
import PasswordInput from '../../../components/auth/PasswordInput';
import { supabase } from '@/lib/supabaseClient';
import { setToken } from '@/lib/api';
import { getRoleRoute } from '@/lib/roleRoute';
import { usePasswordRules } from '@/hooks/usePasswordRules';

export default function RegisterPage() {
    const router = useRouter();
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);
    const [passwordFocused, setPasswordFocused] = useState(false);
    // OTP verification state
    const [otpCode, setOtpCode] = useState('');
    const [otpLoading, setOtpLoading] = useState(false);
    const [otpError, setOtpError] = useState<string | null>(null);
    const [resendCooldown, setResendCooldown] = useState(0);
    // Guard: prevents the mount-time Supabase session check from competing
    // with the OTP verification handler's own navigation.
    const navigating = useRef(false);

    const pwRules = usePasswordRules(password);
    const allRulesPass = pwRules.every(r => r.pass);

    // If already authenticated with a valid iHouse token, redirect to /welcome.
    // Guard: skip if OTP handler is already driving navigation.
    useEffect(() => {
        if (!supabase) return;
        const token = document.cookie.split('; ').find(c => c.startsWith('ihouse_token='))?.split('=')[1];
        if (token) {
            router.replace('/welcome');
        }
    }, [router]);

    const handleSignUp = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        if (!fullName.trim()) { setError('Please enter your name'); return; }
        if (!email.trim()) { setError('Please enter your email'); return; }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) { setError('Please enter a valid email'); return; }
        if (!allRulesPass) { setError('Password does not meet all requirements'); return; }
        if (password !== confirmPassword) { setError('Passwords do not match'); return; }
        if (!supabase) { setError('Authentication is not configured yet.'); return; }

        setLoading(true);
        try {
            const { data, error: signUpError } = await supabase.auth.signUp({
                email: email.trim(),
                password,
                options: {
                    data: {
                        full_name: fullName.trim(),
                    },
                },
            });

            if (signUpError) {
                setError(signUpError.message);
                setLoading(false);
                return;
            }

            // Supabase may require email confirmation depending on project settings.
            // If the user object exists and identities array is empty, email is taken.
            if (data.user && data.user.identities && data.user.identities.length === 0) {
                setError('An account with this email already exists. Please sign in instead.');
                setLoading(false);
                return;
            }

            // Check if email confirmation is required
            if (data.user && !data.session) {
                // Email confirmation required — show success message
                setSuccess(true);
                setLoading(false);
                return;
            }

            // Session created immediately (no email confirmation required)
            // Exchange Supabase session for iHouse JWT before redirecting
            const session = data.session!;
            const BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
            try {
                const resp = await fetch(`${BASE_URL}/auth/google-callback`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: session.user.id,
                        email: session.user.email || email.trim(),
                        access_token: session.access_token,
                        full_name: fullName.trim(),
                    }),
                });
                const body = await resp.json();
                const result = body?.data || body;
                if (resp.ok && result.token) {
                    setToken(result.token);
                    document.cookie = `ihouse_token=${result.token}; path=/; max-age=${result.expires_in || 86400}; SameSite=Lax`;
                    if (result.language) localStorage.setItem('domaniqo_lang', result.language);
                    window.location.href = getRoleRoute(result.token);
                    return;
                }
            } catch { /* fall through to /welcome */ }
            // Fallback: redirect to /welcome without JWT (identity-only)
            router.push('/welcome');
        } catch {
            setError('Something went wrong. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    // OTP verification handler
    const handleVerifyOtp = async () => {
        if (!supabase || !otpCode.trim()) return;
        setOtpLoading(true);
        setOtpError(null);
        try {
            // Try 'email' type first (Supabase uses this for sign-up confirmation codes)
            let result = await supabase.auth.verifyOtp({
                email: email.trim(),
                token: otpCode.trim(),
                type: 'email',
            });
            // Fallback to 'signup' type if 'email' didn't work
            if (result.error) {
                result = await supabase.auth.verifyOtp({
                    email: email.trim(),
                    token: otpCode.trim(),
                    type: 'signup',
                });
            }
            if (result.error) {
                setOtpError(result.error.message || 'Invalid verification code. Please try again.');
                setOtpLoading(false);
                return;
            }
            if (result.data.session) {
                // Exchange Supabase session for iHouse JWT
                const session = result.data.session;
                const BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
                navigating.current = true;
                try {
                    const resp = await fetch(`${BASE_URL}/auth/google-callback`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            user_id: session.user.id,
                            email: session.user.email || email.trim(),
                            access_token: session.access_token,
                            full_name: fullName.trim(),
                        }),
                    });
                    const body = await resp.json();
                    const jwt = body?.data || body;
                    if (resp.ok && jwt.token) {
                        setToken(jwt.token);
                        // Write cookie synchronously, then yield a tick before
                        // navigating so the cookie is guaranteed committed to
                        // document.cookie before the next page's useIdentity reads it.
                        document.cookie = `ihouse_token=${jwt.token}; path=/; max-age=${jwt.expires_in || 86400}; SameSite=Lax`;
                        if (jwt.language) localStorage.setItem('domaniqo_lang', jwt.language);
                        await new Promise(r => setTimeout(r, 50));
                        window.location.href = getRoleRoute(jwt.token);
                        return;
                    }
                } catch { /* fall through to /welcome */ }
                // Fallback: redirect to /welcome (identity-only, no JWT exchange)
                await new Promise(r => setTimeout(r, 50));
                window.location.href = '/welcome';
            } else {
                setOtpError('Verification succeeded but no session was created. Please try logging in.');
                setOtpLoading(false);
            }
        } catch {
            setOtpError('Verification failed. Please try again.');
            setOtpLoading(false);
        }
    };

    // Resend OTP
    const handleResendCode = async () => {
        if (!supabase || resendCooldown > 0) return;
        try {
            await supabase.auth.resend({ type: 'signup', email: email.trim() });
            setResendCooldown(60);
            setOtpError(null);
            const interval = setInterval(() => {
                setResendCooldown(prev => {
                    if (prev <= 1) { clearInterval(interval); return 0; }
                    return prev - 1;
                });
            }, 1000);
        } catch {
            setOtpError('Failed to resend code. Please try again.');
        }
    };

    const handleGoogleSignUp = async () => {
        if (!supabase) { setError('Google sign-in is not configured yet.'); return; }
        setLoading(true);
        setError(null);
        try {
            const redirectTo = typeof window !== 'undefined'
                ? `${window.location.origin}/auth/callback`
                : '/auth/callback';
            const { error: oauthError } = await supabase.auth.signInWithOAuth({
                provider: 'google',
                options: { redirectTo },
            });
            if (oauthError) {
                setError('Google sign-up failed. Please try again.');
                setLoading(false);
            }
        } catch {
            setError('Google sign-up failed. Please try again.');
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

    const labelStyle: React.CSSProperties = {
        display: 'block', fontSize: 'var(--text-xs, 12px)', fontWeight: 600,
        color: 'rgba(234,229,222,0.5)', marginBottom: 'var(--space-2, 8px)',
        textTransform: 'uppercase', letterSpacing: '0.06em',
    };

    // Success: show OTP verification form
    if (success) {
        return (
            <AuthCard title="Verify your email" subtitle="Enter the code we sent to complete registration">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)', textAlign: 'center' }}>
                    <div style={{ fontSize: 48, marginBottom: 'var(--space-2, 8px)' }}>📧</div>
                    <p style={{
                        fontSize: 'var(--text-sm, 14px)',
                        color: 'rgba(234,229,222,0.5)',
                        lineHeight: 1.6,
                    }}>
                        We sent a verification code to <strong style={{ color: 'var(--color-stone, #EAE5DE)' }}>{email}</strong>.
                        Enter the code below to activate your account.
                    </p>

                    {/* OTP Input */}
                    <input
                        id="input-otp-code"
                        className="auth-input"
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        maxLength={8}
                        value={otpCode}
                        onChange={e => { setOtpCode(e.target.value.replace(/\D/g, '')); setOtpError(null); }}
                        placeholder="Enter 8-digit code"
                        autoFocus
                        disabled={otpLoading}
                        style={{
                            ...inputStyle,
                            textAlign: 'center',
                            fontSize: 'var(--text-lg, 20px)',
                            fontWeight: 700,
                            letterSpacing: '0.2em',
                            fontFamily: 'monospace',
                        }}
                    />

                    {/* OTP Error */}
                    {otpError && (
                        <div style={{
                            background: 'rgba(155,58,58,0.1)', border: '1px solid rgba(155,58,58,0.25)',
                            borderRadius: 'var(--radius-md, 12px)', padding: '10px 14px',
                            fontSize: 'var(--text-sm, 14px)', color: '#EF4444',
                        }}>
                            ⚠ {otpError}
                        </div>
                    )}

                    {/* Verify Button */}
                    <button
                        id="btn-verify-otp"
                        type="button"
                        className="auth-btn"
                        disabled={otpLoading || otpCode.length < 6}
                        onClick={handleVerifyOtp}
                        style={{
                            padding: '14px',
                            background: 'var(--color-moss, #334036)',
                            border: 'none',
                            borderRadius: 'var(--radius-md, 12px)',
                            color: 'var(--color-white, #F8F6F2)',
                            fontSize: 'var(--text-base, 16px)',
                            fontWeight: 600,
                            fontFamily: 'var(--font-brand, "Inter", sans-serif)',
                            cursor: otpLoading || otpCode.length < 6 ? 'not-allowed' : 'pointer',
                            opacity: otpLoading || otpCode.length < 6 ? 0.4 : 1,
                            transition: 'all 0.2s',
                            minHeight: 48,
                        }}
                    >
                        {otpLoading ? 'Verifying…' : 'Verify & Continue'}
                    </button>

                    {/* Resend + Back */}
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--space-4, 16px)', fontSize: 'var(--text-sm, 14px)' }}>
                        <button
                            type="button"
                            onClick={handleResendCode}
                            disabled={resendCooldown > 0}
                            style={{
                                background: 'none', border: 'none',
                                color: resendCooldown > 0 ? 'rgba(234,229,222,0.2)' : 'var(--color-copper, #B56E45)',
                                cursor: resendCooldown > 0 ? 'default' : 'pointer',
                                padding: 0, fontFamily: 'inherit', fontSize: 'inherit',
                                textDecoration: 'underline',
                            }}
                        >
                            {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend code'}
                        </button>
                        <button
                            type="button"
                            onClick={() => { setSuccess(false); setOtpCode(''); setOtpError(null); }}
                            style={{
                                background: 'none', border: 'none',
                                color: 'rgba(234,229,222,0.4)',
                                cursor: 'pointer',
                                padding: 0, fontFamily: 'inherit', fontSize: 'inherit',
                            }}
                        >
                            ← Back
                        </button>
                    </div>
                </div>
            </AuthCard>
        );
    }

    return (
        <AuthCard title="Create your account" subtitle="Sign up to get started with Domaniqo">
            <form onSubmit={handleSignUp} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                {/* Full Name */}
                <div>
                    <label style={labelStyle}>Full Name</label>
                    <input
                        id="input-full-name"
                        className="auth-input"
                        type="text"
                        value={fullName}
                        onChange={e => { setFullName(e.target.value); setError(null); }}
                        placeholder="Your full name"
                        autoComplete="name"
                        autoFocus
                        disabled={loading}
                        style={inputStyle}
                    />
                </div>

                {/* Email */}
                <div>
                    <label style={labelStyle}>Email</label>
                    <input
                        id="input-email"
                        className="auth-input"
                        type="email"
                        value={email}
                        onChange={e => { setEmail(e.target.value); setError(null); }}
                        placeholder="you@example.com"
                        autoComplete="email"
                        disabled={loading}
                        style={inputStyle}
                    />
                </div>

                {/* Password */}
                <div>
                    <label style={labelStyle}>Password</label>
                    <PasswordInput
                        id="input-password"
                        value={password}
                        onChange={e => { setPassword(e.target.value); setError(null); }}
                        placeholder="Create a password"
                        autoComplete="new-password"
                        disabled={loading}
                    />
                    {/* Password strength indicator */}
                    {(passwordFocused || password.length > 0) && (
                        <div style={{
                            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px',
                            marginTop: 8, fontSize: 12,
                        }}>
                            {pwRules.map(r => (
                                <div key={r.key} style={{
                                    color: r.pass ? 'var(--color-copper, #B56E45)' : 'rgba(234,229,222,0.25)',
                                    transition: 'color 0.2s',
                                }}>
                                    {r.pass ? '✓' : '○'} {r.label}
                                </div>
                            ))}
                        </div>
                    )}
                    {/* Hidden focus trigger */}
                    <input
                        type="hidden"
                        onFocus={() => setPasswordFocused(true)}
                        onBlur={() => setPasswordFocused(false)}
                    />
                </div>

                {/* Confirm Password */}
                <div>
                    <label style={labelStyle}>Confirm Password</label>
                    <PasswordInput
                        id="input-confirm-password"
                        value={confirmPassword}
                        onChange={e => { setConfirmPassword(e.target.value); setError(null); }}
                        placeholder="Confirm your password"
                        autoComplete="new-password"
                        disabled={loading}
                    />
                </div>

                {/* Error */}
                {error && (
                    <div style={{
                        background: 'rgba(155,58,58,0.1)', border: '1px solid rgba(155,58,58,0.25)',
                        borderRadius: 'var(--radius-md, 12px)', padding: '10px 14px',
                        fontSize: 'var(--text-sm, 14px)', color: '#EF4444',
                    }}>
                        ⚠ {error}
                    </div>
                )}

                {/* Sign Up Button */}
                <button
                    id="btn-signup"
                    type="submit"
                    className="auth-btn"
                    disabled={loading || !fullName.trim() || !email.trim() || !allRulesPass || password !== confirmPassword}
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
                        cursor: loading ? 'not-allowed' : 'pointer',
                        opacity: (loading || !fullName.trim() || !email.trim() || !allRulesPass || password !== confirmPassword) ? 0.4 : 1,
                        transition: 'all 0.2s',
                        marginTop: 'var(--space-1, 4px)',
                        minHeight: 48,
                    }}
                >
                    {loading ? 'Creating account…' : 'Create Account'}
                </button>
            </form>

            <AuthDivider />

            <GoogleSignInButton
                onClick={handleGoogleSignUp}
                label="Sign up with Google"
                disabled={loading}
            />

            {/* Bottom links */}
            <div style={{
                marginTop: 'var(--space-6, 24px)',
                textAlign: 'center',
            }}>
                <a href="/login" className="auth-link" style={{ fontSize: 'var(--text-sm, 14px)' }}>
                    Already have an account? <span style={{ textDecoration: 'underline' }}>Sign in</span>
                </a>
            </div>
        </AuthCard>
    );
}
