'use client';

/**
 * Phase 388 — Guest QR Portal
 * Route: /guest/[token]
 *
 * Public route, token-authenticated. Shows property information
 * for check-in guests: Wi-Fi, house rules, check-in/out times,
 * emergency contact. No PII leakage on invalid tokens.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import DMonogram from '../../../../components/DMonogram';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GuestPortalData {
    property_name: string;
    property_address?: string;
    wifi_name?: string;
    wifi_password?: string;
    check_in_time?: string;
    check_out_time?: string;
    house_rules?: string[];
    emergency_contact?: string;
    welcome_message?: string;
}

// ---------------------------------------------------------------------------
// Info Card
// ---------------------------------------------------------------------------

function InfoCard({ icon, label, value, mono }: {
    icon: string; label: string; value: string; mono?: boolean;
}) {
    return (
        <div style={{
            background: 'var(--color-surface, #1a1f2e)',
            border: '1px solid var(--color-border, #ffffff12)',
            borderRadius: 'var(--radius-lg, 16px)',
            padding: 'var(--space-4, 16px)',
            display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3, 12px)',
        }}>
            <span style={{ fontSize: 24, flexShrink: 0 }}>{icon}</span>
            <div>
                <div style={{
                    fontSize: 'var(--text-xs, 11px)',
                    color: 'var(--color-text-dim, #6b7280)',
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                    marginBottom: 'var(--space-1, 4px)',
                }}>
                    {label}
                </div>
                <div style={{
                    fontSize: 'var(--text-base, 16px)',
                    fontWeight: 600,
                    color: 'var(--color-text, #f9fafb)',
                    fontFamily: mono ? 'var(--font-mono, monospace)' : 'inherit',
                    wordBreak: 'break-all',
                }}>
                    {value}
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function GuestPortalPage() {
    const params = useParams();
    const token = params?.token as string;
    const [data, setData] = useState<GuestPortalData | null>(null);
    const [error, setError] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!token) { setError(true); setLoading(false); return; }

        // Attempt to load guest portal data via token
        const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
        fetch(`${API_BASE}/guest/portal/${encodeURIComponent(token)}`)
            .then(r => {
                if (!r.ok) throw new Error('Invalid');
                return r.json();
            })
            .then(d => setData(d))
            .catch(() => setError(true))
            .finally(() => setLoading(false));
    }, [token]);

    // Invalid / expired token — graceful error, no PII leakage
    if (error) {
        return (
            <div style={{
                minHeight: '100vh',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column', gap: 'var(--space-4, 16px)',
                padding: 'var(--space-6, 24px)',
                textAlign: 'center',
            }}>
                <DMonogram size={48} />
                <h1 style={{
                    fontSize: 'var(--text-xl, 22px)', fontWeight: 800,
                    color: 'var(--color-text, #f9fafb)',
                    margin: 0,
                }}>
                    Link Expired or Invalid
                </h1>
                <p style={{
                    fontSize: 'var(--text-sm, 14px)',
                    color: 'var(--color-text-dim, #6b7280)',
                    maxWidth: 340,
                }}>
                    This guest access link is no longer valid. Please contact your host for a new link.
                </p>
                <div style={{
                    fontSize: 'var(--text-xs, 11px)',
                    color: 'var(--color-text-faint, #4b5563)',
                    marginTop: 'var(--space-4, 16px)',
                }}>
                    info@domaniqo.com
                </div>
            </div>
        );
    }

    if (loading) {
        return (
            <div style={{
                minHeight: '100vh',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column', gap: 'var(--space-3, 12px)',
            }}>
                <DMonogram size={40} />
                <div style={{
                    fontSize: 'var(--text-sm, 14px)',
                    color: 'var(--color-text-dim, #6b7280)',
                    animation: 'pulse 1.5s infinite',
                }}>
                    Loading your stay information…
                </div>
                <style>{`@keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }`}</style>
            </div>
        );
    }

    if (!data) return null;

    return (
        <>
            <style>{`
                @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
            `}</style>

            <div style={{
                maxWidth: 480, margin: '0 auto',
                padding: 'var(--space-5, 20px) var(--space-4, 16px)',
                minHeight: '100vh',
                animation: 'fadeIn 400ms ease',
            }}>
                {/* Header */}
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-6, 24px)' }}>
                    <DMonogram size={36} />
                    <h1 style={{
                        fontSize: 'var(--text-xl, 22px)', fontWeight: 800,
                        color: 'var(--color-text, #f9fafb)',
                        margin: 'var(--space-3, 12px) 0 var(--space-1, 4px)',
                        letterSpacing: '-0.03em',
                    }}>
                        Welcome
                    </h1>
                    <p style={{
                        fontSize: 'var(--text-lg, 18px)',
                        color: 'var(--color-primary, #3b82f6)',
                        fontWeight: 600, margin: 0,
                    }}>
                        {data.property_name}
                    </p>
                    {data.property_address && (
                        <p style={{
                            fontSize: 'var(--text-sm, 13px)',
                            color: 'var(--color-text-dim, #6b7280)',
                            marginTop: 'var(--space-1, 4px)',
                        }}>
                            📍 {data.property_address}
                        </p>
                    )}
                </div>

                {/* Welcome message */}
                {data.welcome_message && (
                    <div style={{
                        background: 'var(--color-surface, #1a1f2e)',
                        border: '1px solid var(--color-border, #ffffff12)',
                        borderRadius: 'var(--radius-lg, 16px)',
                        padding: 'var(--space-4, 16px)',
                        marginBottom: 'var(--space-4, 16px)',
                        fontSize: 'var(--text-sm, 15px)',
                        color: 'var(--color-text, #e5e7eb)',
                        lineHeight: 1.6,
                    }}>
                        {data.welcome_message}
                    </div>
                )}

                {/* Info cards */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3, 12px)' }}>
                    {data.wifi_name && (
                        <InfoCard icon="📶" label="Wi-Fi Network" value={data.wifi_name} mono />
                    )}
                    {data.wifi_password && (
                        <InfoCard icon="🔑" label="Wi-Fi Password" value={data.wifi_password} mono />
                    )}
                    {data.check_in_time && (
                        <InfoCard icon="🛬" label="Check-in Time" value={data.check_in_time} />
                    )}
                    {data.check_out_time && (
                        <InfoCard icon="🛫" label="Check-out Time" value={data.check_out_time} />
                    )}
                    {data.emergency_contact && (
                        <InfoCard icon="🆘" label="Emergency Contact" value={data.emergency_contact} />
                    )}
                </div>

                {/* House rules */}
                {data.house_rules && data.house_rules.length > 0 && (
                    <div style={{
                        marginTop: 'var(--space-5, 20px)',
                        background: 'var(--color-surface, #1a1f2e)',
                        border: '1px solid var(--color-border, #ffffff12)',
                        borderRadius: 'var(--radius-lg, 16px)',
                        padding: 'var(--space-4, 16px)',
                    }}>
                        <div style={{
                            fontSize: 'var(--text-xs, 11px)',
                            color: 'var(--color-text-dim, #6b7280)',
                            textTransform: 'uppercase', letterSpacing: '0.06em',
                            marginBottom: 'var(--space-3, 12px)',
                        }}>
                            📋 House Rules
                        </div>
                        {data.house_rules.map((rule, i) => (
                            <div key={i} style={{
                                display: 'flex', alignItems: 'flex-start', gap: 'var(--space-2, 8px)',
                                marginBottom: 'var(--space-2, 8px)',
                                fontSize: 'var(--text-sm, 14px)',
                                color: 'var(--color-text, #d1d5db)',
                                lineHeight: 1.5,
                            }}>
                                <span style={{ color: 'var(--color-text-dim, #6b7280)', flexShrink: 0 }}>•</span>
                                <span>{rule}</span>
                            </div>
                        ))}
                    </div>
                )}

                {/* Footer */}
                <div style={{
                    textAlign: 'center',
                    marginTop: 'var(--space-6, 24px)',
                    padding: 'var(--space-4, 16px)',
                }}>
                    <DMonogram size={20} />
                    <div style={{
                        fontSize: 'var(--text-xs, 11px)',
                        color: 'var(--color-text-faint, #4b5563)',
                        marginTop: 'var(--space-2, 8px)',
                    }}>
                        Powered by Domaniqo · info@domaniqo.com
                    </div>
                </div>
            </div>
        </>
    );
}
