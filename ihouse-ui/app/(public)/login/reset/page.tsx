'use client';

/**
 * Password Reset Page
 * Route: /login/reset
 *
 * Full recovery flow:
 * 1. User clicks "Forgot password?" → goes to /login/forgot
 * 2. Enters email → Supabase sends reset email with link to /login/reset
 * 3. User clicks link → arrives here with access_token in URL hash
 * 4. Enters new password → supabase.auth.updateUser({ password })
 * 5. Success → redirected to /login with success message
 *
 * Edge cases:
 * - Expired link: Supabase returns error → show "link expired"
 * - No token in URL: show error + link back to forgot page
 */

import { useState, useEffect } from 'react';
import AuthCard from '../../../../components/auth/AuthCard';
import { supabase } from '@/lib/supabaseClient';

export default function ResetPasswordPage() {
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);
    const [hasToken, setHasToken] = useState(false);
    const [checking, setChecking] = useState(true);

    // Check for access token in URL on mount
    useEffect(() => {
        const hash = window.location.hash;
        if (hash && hash.includes('access_token')) {
            setHasToken(true);
        }
        setChecking(false);
    }, []);

    const handleReset = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!password || password.length < 6) {
            setError('Password must be at least 6 characters');
            return;
        }
        if (password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }
        if (!supabase) {
            setError('Password reset is not configured yet.');
            return;
        }
        setError(null);
        setLoading(true);
        try {
            const { error: updateError } = await supabase.auth.updateUser({
                password,
            });
            if (updateError) {
                if (updateError.message.includes('expired') || updateError.message.includes('invalid')) {
                    setError('This reset link has expired. Please request a new one.');
                } else {
                    setError(updateError.message);
                }
            } else {
                setSuccess(true);
                // Redirect to login after a brief delay
                setTimeout(() => {
                    window.location.href = '/login';
                }, 3000);
            }
        } catch {
            setError('Failed to reset password. Please try again.');
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

    const labelStyle: React.CSSProperties = {
        display: 'block', fontSize: 'var(--text-xs, 12px)', fontWeight: 600,
        color: 'rgba(234,229,222,0.5)', marginBottom: 'var(--space-2, 8px)',
        textTransform: 'uppercase', letterSpacing: '0.06em',
    };

    if (checking) return null;

    // Success state
    if (success) {
        return (
            <AuthCard title="Password updated" subtitle="Your password has been reset successfully">
                <div style={{ textAlign: 'center', padding: 'var(--space-6, 24px) 0' }}>
                    <div style={{ fontSize: 48, marginBottom: 'var(--space-4, 16px)' }}>✅</div>
                    <p style={{
                        fontSize: 'var(--text-sm, 14px)',
                        color: 'rgba(234,229,222,0.5)',
                        lineHeight: 1.6,
                        marginBottom: 'var(--space-4, 16px)',
                    }}>
                        You'll be redirected to the login page in a moment.
                    </p>
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
                        Go to login
                    </a>
                </div>
            </AuthCard>
        );
    }

    // No token — invalid access
    if (!hasToken) {
        return (
            <AuthCard title="Invalid reset link" subtitle="This link is missing or has expired">
                <div style={{ textAlign: 'center', padding: 'var(--space-6, 24px) 0' }}>
                    <div style={{ fontSize: 48, marginBottom: 'var(--space-4, 16px)' }}>⚠️</div>
                    <p style={{
                        fontSize: 'var(--text-sm, 14px)',
                        color: 'rgba(234,229,222,0.5)',
                        lineHeight: 1.6,
                        marginBottom: 'var(--space-4, 16px)',
                    }}>
                        The password reset link is invalid or has expired.
                        Please request a new one.
                    </p>
                    <a
                        href="/login/forgot"
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
                        Request new reset link
                    </a>
                </div>
            </AuthCard>
        );
    }

    // Reset form
    return (
        <AuthCard title="Set new password" subtitle="Choose a new password for your account">
            <form onSubmit={handleReset} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                <div>
                    <label style={labelStyle}>New Password</label>
                    <input
                        className="auth-input"
                        type="password"
                        value={password}
                        onChange={e => { setPassword(e.target.value); setError(null); }}
                        placeholder="At least 6 characters"
                        autoComplete="new-password"
                        autoFocus
                        disabled={loading}
                        style={inputStyle}
                    />
                </div>
                <div>
                    <label style={labelStyle}>Confirm Password</label>
                    <input
                        className="auth-input"
                        type="password"
                        value={confirmPassword}
                        onChange={e => { setConfirmPassword(e.target.value); setError(null); }}
                        placeholder="Re-enter password"
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
                    disabled={loading || !password || !confirmPassword}
                    style={{
                        width: '100%', padding: '14px',
                        background: 'var(--color-moss, #334036)', border: 'none',
                        borderRadius: 'var(--radius-md, 12px)', color: 'var(--color-white, #F8F6F2)',
                        fontSize: 'var(--text-base, 16px)', fontWeight: 600,
                        fontFamily: 'var(--font-brand, "Inter", sans-serif)',
                        cursor: loading || !password || !confirmPassword ? 'not-allowed' : 'pointer',
                        opacity: loading || !password || !confirmPassword ? 0.4 : 1,
                        transition: 'all 0.2s', minHeight: 48,
                    }}
                >
                    {loading ? 'Updating…' : 'Reset Password'}
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
