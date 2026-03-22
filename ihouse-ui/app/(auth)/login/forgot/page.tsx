'use client';

/**
 * Phase 876 — Forgot Password (Code-Based In-App Reset)
 * Route: /login/forgot
 *
 * Canonical password reset flow — the user never leaves the app.
 *
 * State A: Enter email (prefilled from ?email= query param)
 *   → signInWithOtp({ email, shouldCreateUser: false })
 *   → Always shows "code sent" (doesn't reveal whether email exists)
 *
 * State B: Enter 8-digit verification code
 *   → verifyOtp({ email, token, type: 'email' })
 *   → On success: session established → move to State C
 *
 * State C: Set new password + confirm
 *   → updateUser({ password })
 *   → On success → show success → "Continue to sign in"
 *
 * Security:
 *   - shouldCreateUser: false prevents accidental account creation
 *   - Always shows "code sent" regardless of whether email exists
 *   - OTP is one-time use & time-limited (Supabase-enforced)
 *   - Rate limiting is Supabase-enforced
 */

import { useState, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import AuthCard from '../../../../components/auth/AuthCard';
import PasswordInput from '../../../../components/auth/PasswordInput';
import { supabase } from '@/lib/supabaseClient';
import { usePasswordRules } from '@/hooks/usePasswordRules';

type ResetStep = 'email' | 'code' | 'password' | 'success';

function ForgotPasswordForm() {
    const searchParams = useSearchParams();
    const [step, setStep] = useState<ResetStep>('email');
    const [email, setEmail] = useState(searchParams.get('email') || '');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Code step
    const [code, setCode] = useState('');
    const codeInputRef = useRef<HTMLInputElement>(null);

    // Password step
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [passwordFocused, setPasswordFocused] = useState(false);
    const pwRules = usePasswordRules(password);
    const allRulesPass = pwRules.every(r => r.pass);

    // Resend cooldown
    const [resendCooldown, setResendCooldown] = useState(0);

    /* ─── Shared styles ─── */
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

    const btnStyle = (disabled: boolean): React.CSSProperties => ({
        width: '100%',
        padding: '14px', background: 'var(--color-moss, #334036)',
        border: 'none', borderRadius: 'var(--radius-md, 12px)',
        color: 'var(--color-white, #F8F6F2)', fontSize: 'var(--text-base, 16px)',
        fontWeight: 600, fontFamily: 'var(--font-brand, "Inter", sans-serif)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        transition: 'all 0.2s', minHeight: 48,
    });

    const errorBox = (
        <div style={{
            background: 'rgba(155,58,58,0.1)', border: '1px solid rgba(155,58,58,0.25)',
            borderRadius: 'var(--radius-md, 12px)', padding: '10px 14px',
            fontSize: 'var(--text-sm, 14px)', color: '#EF4444',
        }}>
            ⚠ {error}
        </div>
    );

    /* ─── Step A: Send OTP code ─── */
    const handleSendCode = async (e?: React.FormEvent) => {
        if (e) e.preventDefault();
        if (!email.trim()) { setError('Please enter your email'); return; }
        if (!supabase) { setError('Password reset is not configured yet.'); return; }
        setError(null);
        setLoading(true);
        try {
            // Use signInWithOtp with shouldCreateUser: false
            // This sends an OTP for existing users only.
            // If the user doesn't exist, Supabase returns success but sends nothing.
            // We ALWAYS show "code sent" to avoid revealing whether the email exists.
            await supabase.auth.signInWithOtp({
                email: email.trim(),
                options: {
                    shouldCreateUser: false,
                },
            });
            setStep('code');
            // Start resend cooldown (60 seconds)
            setResendCooldown(60);
            const timer = setInterval(() => {
                setResendCooldown(prev => {
                    if (prev <= 1) { clearInterval(timer); return 0; }
                    return prev - 1;
                });
            }, 1000);
            // Focus code input after render
            setTimeout(() => codeInputRef.current?.focus(), 100);
        } catch {
            // Even on network error, show "code sent" to avoid leaking info.
            // Only show real errors for clearly non-user-related issues.
            setStep('code');
        } finally {
            setLoading(false);
        }
    };

    /* ─── Step B: Verify code ─── */
    const handleVerifyCode = async () => {
        if (code.length !== 8) return;
        if (!supabase) return;
        setError(null);
        setLoading(true);
        try {
            const { error: verifyError, data } = await supabase.auth.verifyOtp({
                email: email.trim(),
                token: code.trim(),
                type: 'email',
            });
            if (verifyError) {
                if (verifyError.message.toLowerCase().includes('expired')) {
                    setError('This code has expired. Please request a new one.');
                } else if (verifyError.message.toLowerCase().includes('invalid')) {
                    setError('Invalid code. Please check and try again.');
                } else {
                    setError(verifyError.message);
                }
            } else if (data?.session) {
                // Session established — user is now authenticated
                setStep('password');
                setError(null);
            } else {
                setError('Verification failed. Please try again.');
            }
        } catch {
            setError('Network error. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    /* ─── Step C: Set new password ─── */
    const handleSetPassword = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!allRulesPass) { setError('Password does not meet all requirements'); return; }
        if (password !== confirmPassword) { setError('Passwords do not match'); return; }
        if (!supabase) { setError('Not configured.'); return; }
        setError(null);
        setLoading(true);
        try {
            const { error: updateError } = await supabase.auth.updateUser({ password });
            if (updateError) {
                setError(updateError.message);
            } else {
                // Sign out after password change so user logs in fresh
                await supabase.auth.signOut();
                setStep('success');
            }
        } catch {
            setError('Failed to reset password. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    /* ─── Resend handler ─── */
    const handleResend = async () => {
        if (resendCooldown > 0) return;
        setError(null);
        await handleSendCode();
    };

    /* ═══════ Render ═══════ */

    // ── State A: Email entry ──
    if (step === 'email') {
        return (
            <AuthCard title="Reset your password" subtitle="Enter your email and we'll send a verification code">
                <form onSubmit={handleSendCode} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                    <div>
                        <label style={labelStyle}>Email</label>
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

                    {error && errorBox}

                    <button
                        type="submit"
                        className="auth-btn"
                        disabled={loading || !email.trim()}
                        style={btnStyle(loading || !email.trim())}
                    >
                        {loading ? 'Sending…' : 'Send Reset Code'}
                    </button>
                </form>

                <div style={{ marginTop: 'var(--space-6, 24px)', textAlign: 'center' }}>
                    <a href={`/login/password${email ? `?email=${encodeURIComponent(email)}` : ''}`} className="auth-link" style={{ fontSize: 'var(--text-sm, 14px)' }}>
                        ← Back to sign in
                    </a>
                </div>
            </AuthCard>
        );
    }

    // ── State B: Code verification ──
    if (step === 'code') {
        return (
            <AuthCard title="Check your email" subtitle="Enter the verification code to continue">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                    <div style={{
                        fontSize: 'var(--text-sm, 14px)',
                        color: 'rgba(234,229,222,0.5)',
                        lineHeight: 1.6,
                        padding: '12px 16px',
                        background: 'rgba(74,124,89,0.06)',
                        borderRadius: 'var(--radius-md, 12px)',
                        border: '1px solid rgba(74,124,89,0.1)',
                    }}>
                        <div style={{ marginBottom: 4 }}>
                            ✉️ If <strong style={{ color: 'var(--color-stone, #EAE5DE)' }}>{email}</strong> has an account,
                            we sent a verification code.
                        </div>
                        <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.3)' }}>
                            Do not close this page. Check your spam folder if the email doesn&apos;t arrive.
                        </div>
                    </div>

                    <div>
                        <label style={labelStyle}>8-Digit Verification Code</label>
                        <input
                            ref={codeInputRef}
                            className="auth-input"
                            value={code}
                            onChange={e => { setCode(e.target.value.replace(/\D/g, '').slice(0, 8)); setError(null); }}
                            onKeyDown={e => e.key === 'Enter' && code.length === 8 && handleVerifyCode()}
                            placeholder="· · · · · · · ·"
                            style={{
                                ...inputStyle,
                                textAlign: 'center',
                                fontSize: 22,
                                letterSpacing: '0.3em',
                                fontWeight: 300,
                                color: 'var(--color-stone)',
                            }}
                            maxLength={8}
                            inputMode="numeric"
                            autoComplete="one-time-code"
                            autoFocus
                        />
                        <div style={{ fontSize: 11, color: 'rgba(234,229,222,0.2)', marginTop: 6, textAlign: 'center' }}>
                            Enter the 8-digit code from your email
                        </div>
                    </div>

                    {error && errorBox}

                    <button
                        onClick={handleVerifyCode}
                        disabled={loading || code.length !== 8}
                        style={btnStyle(loading || code.length !== 8)}
                    >
                        {loading ? 'Verifying…' : 'Verify Code'}
                    </button>

                    {/* Resend + change email */}
                    <div style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        marginTop: 4,
                    }}>
                        <button
                            onClick={handleResend}
                            disabled={resendCooldown > 0}
                            style={{
                                background: 'none', border: 'none',
                                color: resendCooldown > 0 ? 'rgba(234,229,222,0.15)' : 'rgba(234,229,222,0.4)',
                                fontSize: 13, cursor: resendCooldown > 0 ? 'default' : 'pointer',
                                fontFamily: 'var(--font-sans, inherit)', padding: 0,
                            }}
                        >
                            {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend code'}
                        </button>
                        <button
                            onClick={() => { setCode(''); setStep('email'); setError(null); }}
                            style={{
                                background: 'none', border: 'none',
                                color: 'rgba(234,229,222,0.3)',
                                fontSize: 13, cursor: 'pointer',
                                fontFamily: 'var(--font-sans, inherit)', padding: 0,
                                textDecoration: 'underline',
                            }}
                        >
                            Use a different email
                        </button>
                    </div>
                </div>
            </AuthCard>
        );
    }

    // ── State C: Set new password ──
    if (step === 'password') {
        return (
            <AuthCard title="Set new password" subtitle="Choose a new password for your account">
                <form onSubmit={handleSetPassword} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                    <div style={{
                        fontSize: 13, color: 'rgba(234,229,222,0.4)',
                        padding: '10px 14px',
                        background: 'rgba(74,124,89,0.06)',
                        borderRadius: 'var(--radius-md, 12px)',
                        border: '1px solid rgba(74,124,89,0.1)',
                    }}>
                        ✅ Code verified for <strong style={{ color: 'var(--color-stone)' }}>{email}</strong>
                    </div>

                    <div>
                        <label style={labelStyle}>New Password</label>
                        <PasswordInput
                            id="input-new-password"
                            value={password}
                            onChange={e => { setPassword(e.target.value); setError(null); }}
                            onFocus={() => setPasswordFocused(true)}
                            onBlur={() => setPasswordFocused(false)}
                            placeholder="Create a strong password"
                            autoComplete="new-password"
                            autoFocus
                            disabled={loading}
                        />
                    </div>

                    {/* Live password rules */}
                    {(passwordFocused || password.length > 0) && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', fontSize: 11, lineHeight: 1.8 }}>
                            {pwRules.map(r => (
                                <span key={r.key} style={{
                                    color: password.length === 0
                                        ? 'rgba(234,229,222,0.25)'
                                        : r.pass ? '#4A7C59' : 'rgba(234,229,222,0.3)',
                                    transition: 'color 0.2s',
                                }}>
                                    {password.length > 0 && r.pass ? '✓' : '○'} {r.label}
                                </span>
                            ))}
                        </div>
                    )}

                    <div>
                        <label style={labelStyle}>Confirm Password</label>
                        <PasswordInput
                            id="input-confirm-password"
                            value={confirmPassword}
                            onChange={e => { setConfirmPassword(e.target.value); setError(null); }}
                            placeholder="Re-enter your new password"
                            autoComplete="new-password"
                            disabled={loading}
                        />
                    </div>

                    {/* Match indicators */}
                    {confirmPassword.length > 0 && password !== confirmPassword && (
                        <div style={{ fontSize: 12, color: '#D64545' }}>✗ Passwords do not match</div>
                    )}
                    {confirmPassword.length > 0 && password === confirmPassword && password.length > 0 && (
                        <div style={{ fontSize: 12, color: '#4A7C59' }}>✓ Passwords match</div>
                    )}

                    {error && errorBox}

                    <button
                        type="submit"
                        className="auth-btn"
                        disabled={loading || !allRulesPass || password !== confirmPassword}
                        style={btnStyle(loading || !allRulesPass || password !== confirmPassword)}
                    >
                        {loading ? 'Updating…' : 'Reset Password'}
                    </button>
                </form>
            </AuthCard>
        );
    }

    // ── State D: Success ──
    return (
        <AuthCard title="Password updated" subtitle="Your password has been reset successfully">
            <div style={{ textAlign: 'center', padding: 'var(--space-6, 24px) 0' }}>
                <div style={{ fontSize: 48, marginBottom: 'var(--space-4, 16px)' }}>✅</div>
                <p style={{
                    fontSize: 'var(--text-sm, 14px)',
                    color: 'rgba(234,229,222,0.5)',
                    lineHeight: 1.6,
                    marginBottom: 'var(--space-6, 24px)',
                }}>
                    Your password has been changed. You can now sign in with your new password.
                </p>
                <a
                    href={`/login/password?email=${encodeURIComponent(email)}`}
                    style={{
                        display: 'inline-block',
                        padding: '14px 32px',
                        background: 'var(--color-moss, #334036)',
                        borderRadius: 'var(--radius-md, 12px)',
                        color: 'var(--color-white, #F8F6F2)',
                        fontSize: 'var(--text-base, 16px)',
                        fontWeight: 600,
                        textDecoration: 'none',
                    }}
                >
                    Continue to sign in
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
