'use client';

/**
 * Phase 388 — Staff Invitation Flow
 * Route: /invite/[token]
 *
 * Token-validated. Shows role, organization, CTA to complete profile.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import DMonogram from '../../../../components/DMonogram';

interface InviteData {
    role: string;
    organization_name: string;
    invited_by?: string;
    expires_at?: string;
}

export default function InvitePage() {
    const params = useParams();
    const token = params?.token as string;
    const [data, setData] = useState<InviteData | null>(null);
    const [error, setError] = useState(false);
    const [loading, setLoading] = useState(true);
    const [accepted, setAccepted] = useState(false);
    const [accepting, setAccepting] = useState(false);
    const [acceptError, setAcceptError] = useState<string | null>(null);
    // Phase 856A: actual input fields for account creation
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');

    useEffect(() => {
        if (!token) { setError(true); setLoading(false); return; }
        const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
        fetch(`${API_BASE}/invite/validate/${encodeURIComponent(token)}`)
            .then(r => { if (!r.ok) throw new Error('Invalid'); return r.json(); })
            .then(d => setData(d))
            .catch(() => setError(true))
            .finally(() => setLoading(false));
    }, [token]);

    if (error) {
        return (
            <div style={{
                minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column', gap: 'var(--space-4, 16px)', padding: 'var(--space-6, 24px)', textAlign: 'center',
            }}>
                <DMonogram size={48} />
                <h1 style={{ fontSize: 'var(--text-xl, 22px)', fontWeight: 800, color: 'var(--color-text, #f9fafb)', margin: 0 }}>
                    Invitation Expired or Invalid
                </h1>
                <p style={{ fontSize: 'var(--text-sm, 14px)', color: 'var(--color-text-dim, #6b7280)', maxWidth: 340 }}>
                    This invitation link is no longer valid. Please contact your administrator for a new invitation.
                </p>
                <div style={{ fontSize: 'var(--text-xs, 11px)', color: 'var(--color-text-faint, #4b5563)', marginTop: 'var(--space-4, 16px)' }}>
                    info@domaniqo.com
                </div>
            </div>
        );
    }

    if (loading) {
        return (
            <div style={{
                minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column', gap: 'var(--space-3, 12px)',
            }}>
                <DMonogram size={40} />
                <div style={{ fontSize: 'var(--text-sm, 14px)', color: 'var(--color-text-dim, #6b7280)', animation: 'pulse 1.5s infinite' }}>
                    Validating invitation…
                </div>
                <style>{`@keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }`}</style>
            </div>
        );
    }

    if (!data) return null;

    if (accepted) {
        return (
            <div style={{
                minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column', gap: 'var(--space-4, 16px)', padding: 'var(--space-6, 24px)', textAlign: 'center',
            }}>
                <div style={{ fontSize: 64, marginBottom: 'var(--space-2, 8px)' }}>🎉</div>
                <h1 style={{ fontSize: 'var(--text-xl, 22px)', fontWeight: 800, color: 'var(--color-text, #f9fafb)', margin: 0 }}>
                    Welcome to {data.organization_name}!
                </h1>
                <p style={{ fontSize: 'var(--text-sm, 14px)', color: 'var(--color-text-dim, #6b7280)', maxWidth: 340 }}>
                    Your account has been created. You can now log in to the platform.
                </p>
                <a
                    href="/login"
                    style={{
                        display: 'inline-block', padding: 'var(--space-3, 14px) var(--space-6, 32px)',
                        borderRadius: 'var(--radius-md, 14px)', border: 'none',
                        background: 'linear-gradient(135deg, var(--color-primary, #3b82f6), #2563eb)',
                        color: '#fff', fontWeight: 700, fontSize: 16, textDecoration: 'none',
                        boxShadow: '0 0 20px rgba(59,130,246,0.3)',
                    }}
                >
                    Go to Login →
                </a>
            </div>
        );
    }

    const canSubmit = password.length >= 8 && fullName.trim().length > 0 && !accepting;

    return (
        <>
            <style>{`@keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }`}</style>
            <div style={{
                maxWidth: 440, margin: '0 auto',
                padding: 'var(--space-6, 32px) var(--space-4, 16px)',
                minHeight: '100vh', animation: 'fadeIn 400ms ease',
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                justifyContent: 'center', textAlign: 'center',
            }}>
                <DMonogram size={48} />
                <h1 style={{
                    fontSize: 'var(--text-2xl, 28px)', fontWeight: 800,
                    color: 'var(--color-text, #f9fafb)', margin: 'var(--space-4, 16px) 0 var(--space-2, 8px)',
                    letterSpacing: '-0.03em',
                }}>
                    You&apos;re Invited
                </h1>
                <p style={{
                    fontSize: 'var(--text-base, 16px)',
                    color: 'var(--color-text-dim, #9ca3af)',
                    margin: '0 0 var(--space-6, 24px)',
                }}>
                    Join <strong style={{ color: 'var(--color-text, #f9fafb)' }}>{data.organization_name}</strong> as{' '}
                    <strong style={{ color: 'var(--color-primary, #3b82f6)' }}>{data.role.replace(/_/g, ' ')}</strong>
                </p>

                {data.invited_by && (
                    <div style={{
                        fontSize: 'var(--text-sm, 13px)',
                        color: 'var(--color-text-faint, #6b7280)',
                        marginBottom: 'var(--space-4, 16px)',
                    }}>
                        Invited by {data.invited_by}
                    </div>
                )}

                {/* Phase 856A: Account creation form */}
                <div style={{ width: '100%', textAlign: 'left', marginBottom: 'var(--space-4, 16px)' }}>
                    <label style={{
                        display: 'block', fontSize: 12, fontWeight: 600,
                        color: 'var(--color-text-faint, #6b7280)',
                        marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em',
                    }}>Full Name</label>
                    <input
                        type="text"
                        value={fullName}
                        onChange={e => setFullName(e.target.value)}
                        placeholder="Your full name"
                        disabled={accepting}
                        style={{
                            width: '100%', padding: '12px 14px',
                            background: 'var(--color-midnight, #171A1F)',
                            border: '1px solid rgba(234,229,222,0.1)',
                            borderRadius: 'var(--radius-md, 12px)',
                            color: 'var(--color-stone, #EAE5DE)',
                            fontSize: 14, boxSizing: 'border-box',
                        }}
                    />
                </div>

                <div style={{ width: '100%', textAlign: 'left', marginBottom: 'var(--space-5, 20px)' }}>
                    <label style={{
                        display: 'block', fontSize: 12, fontWeight: 600,
                        color: 'var(--color-text-faint, #6b7280)',
                        marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em',
                    }}>Password (min. 8 characters)</label>
                    <input
                        type="password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        placeholder="Choose a secure password"
                        disabled={accepting}
                        style={{
                            width: '100%', padding: '12px 14px',
                            background: 'var(--color-midnight, #171A1F)',
                            border: '1px solid rgba(234,229,222,0.1)',
                            borderRadius: 'var(--radius-md, 12px)',
                            color: 'var(--color-stone, #EAE5DE)',
                            fontSize: 14, boxSizing: 'border-box',
                        }}
                    />
                </div>

                {acceptError && (
                    <div style={{
                        width: '100%',
                        background: 'rgba(155,58,58,0.1)',
                        border: '1px solid rgba(155,58,58,0.25)',
                        borderRadius: 'var(--radius-md, 12px)',
                        padding: '10px 14px', marginBottom: 'var(--space-4, 16px)',
                        fontSize: 14, color: '#EF4444', textAlign: 'left',
                    }}>
                        ⚠ {acceptError}
                    </div>
                )}

                <button
                    id="accept-invite"
                    disabled={!canSubmit}
                    onClick={async () => {
                        const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
                        setAccepting(true);
                        setAcceptError(null);
                        try {
                            const r = await fetch(`${API_BASE}/invite/accept/${encodeURIComponent(token)}`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    password,
                                    full_name: fullName.trim(),
                                }),
                            });
                            if (!r.ok) {
                                const body = await r.json().catch(() => ({}));
                                setAcceptError(body.message || body.detail?.[0]?.msg || 'Failed to accept invitation');
                                return;
                            }
                            setAccepted(true);
                        } catch {
                            setAcceptError('Network error. Please try again.');
                        } finally {
                            setAccepting(false);
                        }
                    }}
                    style={{
                        padding: 'var(--space-4, 18px) var(--space-8, 48px)',
                        borderRadius: 'var(--radius-md, 14px)', border: 'none',
                        background: canSubmit
                            ? 'linear-gradient(135deg, var(--color-primary, #3b82f6), #2563eb)'
                            : 'rgba(59,130,246,0.3)',
                        color: '#fff', fontWeight: 700, fontSize: 18,
                        cursor: canSubmit ? 'pointer' : 'not-allowed',
                        boxShadow: canSubmit ? '0 0 24px rgba(59,130,246,0.3)' : 'none',
                        transition: 'all 0.15s',
                        opacity: canSubmit ? 1 : 0.5,
                        width: '100%',
                    }}
                >
                    {accepting ? 'Creating account…' : 'Accept Invitation'}
                </button>

                <div style={{
                    fontSize: 'var(--text-xs, 11px)', color: 'var(--color-text-faint, #4b5563)',
                    marginTop: 'var(--space-6, 24px)',
                }}>
                    Powered by Domaniqo · info@domaniqo.com
                </div>
            </div>
        </>
    );
}
