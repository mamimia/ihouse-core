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

                <button
                    id="accept-invite"
                    onClick={async () => {
                        const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
                        try {
                            const r = await fetch(`${API_BASE}/invite/accept/${encodeURIComponent(token)}`, { method: 'POST' });
                            if (!r.ok) {
                                const body = await r.json().catch(() => ({}));
                                alert(body.message || 'Failed to accept invitation');
                                return;
                            }
                            setAccepted(true);
                        } catch {
                            alert('Network error. Please try again.');
                        }
                    }}
                    style={{
                        padding: 'var(--space-4, 18px) var(--space-8, 48px)',
                        borderRadius: 'var(--radius-md, 14px)', border: 'none',
                        background: 'linear-gradient(135deg, var(--color-primary, #3b82f6), #2563eb)',
                        color: '#fff', fontWeight: 700, fontSize: 18,
                        cursor: 'pointer',
                        boxShadow: '0 0 24px rgba(59,130,246,0.3)',
                        transition: 'transform 0.15s',
                    }}
                >
                    Accept Invitation
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
