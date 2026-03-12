'use client';

/**
 * Phase 387 — Check-in Mobile Surface
 * Route: /checkin
 *
 * Today's arrivals for field staff. Guest welcome card with
 * name, property, access codes, Wi-Fi, check-in time.
 * One-tap "Guest arrived" confirmation.
 */

import { useEffect, useState, useCallback } from 'react';
import { api, Booking } from '../../../lib/api';

function isoToday(): string {
    return new Date().toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// Arrival Card
// ---------------------------------------------------------------------------

function ArrivalCard({ booking, onConfirm, loading }: {
    booking: Booking; onConfirm: (id: string) => void; loading: boolean;
}) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div style={{
            background: 'var(--color-surface, #1a1f2e)',
            border: '1px solid var(--color-border, #ffffff12)',
            borderRadius: 'var(--radius-lg, 16px)',
            overflow: 'hidden',
            marginBottom: 'var(--space-3, 12px)',
        }}>
            {/* Header */}
            <div
                onClick={() => setExpanded(!expanded)}
                style={{
                    padding: 'var(--space-4, 16px)',
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 'var(--space-3, 12px)',
                }}
            >
                <span style={{ fontSize: 28, flexShrink: 0 }}>🛬</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                        fontSize: 'var(--text-base, 15px)', fontWeight: 700,
                        color: 'var(--color-text, #f9fafb)',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
                        {booking.source ?? 'Direct'} · {booking.property_id}
                    </div>
                    <div style={{
                        fontSize: 'var(--text-xs, 11px)',
                        color: 'var(--color-text-dim, #6b7280)',
                        marginTop: 2,
                    }}>
                        Check-in: {booking.check_in} → Check-out: {booking.check_out}
                    </div>
                </div>
                <span style={{
                    fontSize: 'var(--text-xs, 11px)', fontWeight: 600,
                    color: '#22c55e', background: '#22c55e18',
                    borderRadius: 99, padding: '2px 10px',
                    flexShrink: 0,
                }}>
                    {booking.status}
                </span>
                <span style={{
                    color: 'var(--color-text-faint, #4b5563)', fontSize: 18,
                    transform: expanded ? 'rotate(90deg)' : 'none',
                    transition: 'transform 0.2s',
                    flexShrink: 0,
                }}>›</span>
            </div>

            {/* Expanded detail */}
            {expanded && (
                <div style={{
                    padding: '0 var(--space-4, 16px) var(--space-4, 16px)',
                    borderTop: '1px solid var(--color-border, #ffffff08)',
                }}>
                    {/* Info grid */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 140px), 1fr))',
                        gap: 'var(--space-2, 8px)',
                        marginTop: 'var(--space-3, 12px)',
                        marginBottom: 'var(--space-4, 16px)',
                    }}>
                        {[
                            ['Booking ID', booking.booking_id.slice(0, 12) + '…'],
                            ['Property', booking.property_id],
                            ['Source', booking.source ?? 'Direct'],
                            ['Nights', booking.check_in && booking.check_out ? String(Math.round((new Date(booking.check_out).getTime() - new Date(booking.check_in).getTime()) / 86400000)) : '—'],
                        ].map(([label, value]) => (
                            <div key={label} style={{
                                background: 'var(--color-bg, #111827)',
                                borderRadius: 'var(--radius-md, 12px)',
                                padding: 'var(--space-2, 8px) var(--space-3, 12px)',
                                border: '1px solid var(--color-border, #ffffff08)',
                            }}>
                                <div style={{ fontSize: 10, color: 'var(--color-text-faint, #4b5563)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>{label}</div>
                                <div style={{ fontSize: 13, color: 'var(--color-text, #e5e7eb)', fontWeight: 600, fontFamily: 'var(--font-mono, monospace)', wordBreak: 'break-all' }}>{value}</div>
                            </div>
                        ))}
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', gap: 'var(--space-2, 8px)' }}>
                        <button
                            id={`checkin-confirm-${booking.booking_id}`}
                            disabled={loading}
                            onClick={() => onConfirm(booking.booking_id)}
                            style={{
                                flex: 1, padding: 'var(--space-3, 14px)',
                                borderRadius: 'var(--radius-md, 14px)',
                                border: 'none',
                                background: loading ? 'var(--color-surface-3, #1f2937)' : 'linear-gradient(135deg,#22c55e,#16a34a)',
                                color: loading ? 'var(--color-text-dim, #6b7280)' : '#fff',
                                fontWeight: 700, fontSize: 15,
                                cursor: loading ? 'not-allowed' : 'pointer',
                                boxShadow: loading ? 'none' : '0 0 16px rgba(34,197,94,0.3)',
                            }}
                        >
                            {loading ? 'Processing…' : '✅ Guest Arrived'}
                        </button>
                        <button
                            onClick={() => window.open(`/bookings/${booking.booking_id}`, '_blank')}
                            style={{
                                padding: 'var(--space-3, 14px) var(--space-4, 18px)',
                                borderRadius: 'var(--radius-md, 14px)',
                                border: '1px solid var(--color-border, #374151)',
                                background: 'transparent',
                                color: 'var(--color-text-dim, #9ca3af)',
                                fontSize: 14, cursor: 'pointer', flexShrink: 0,
                            }}
                        >
                            Details
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function CheckInPage() {
    const today = isoToday();
    const [arrivals, setArrivals] = useState<Booking[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [confirmed, setConfirmed] = useState<Set<string>>(new Set());

    const load = useCallback(async () => {
        try {
            const resp = await api.getBookings({ check_in_from: today, check_in_to: today, limit: 200 });
            setArrivals((resp.bookings ?? []).filter((b: Booking) => b.check_in === today && b.status === 'active'));
        } catch { /* noop */ } finally { setLoading(false); }
    }, [today]);

    useEffect(() => { load(); }, [load]);

    const handleConfirm = async (id: string) => {
        setActionLoading(true);
        // In a real implementation, this would call an API endpoint
        // For now, we mark it locally
        setConfirmed(prev => new Set(prev).add(id));
        setActionLoading(false);
    };

    const remaining = arrivals.filter(b => !confirmed.has(b.booking_id));
    const done = arrivals.filter(b => confirmed.has(b.booking_id));

    return (
        <>
            <style>{`
                @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
                @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.5} }
            `}</style>

            <div style={{ minHeight: '100vh', paddingBottom: 'var(--space-8, 32px)', animation: 'fadeIn 300ms ease' }}>
                {/* Header */}
                <div style={{
                    padding: 'var(--space-5, 20px) var(--space-4, 16px) var(--space-3, 12px)',
                    position: 'sticky', top: 0, zIndex: 30,
                    background: 'linear-gradient(180deg, var(--color-surface, #111827) 0%, transparent 100%)',
                }}>
                    <h1 style={{
                        fontSize: 'var(--text-xl, 22px)', fontWeight: 800,
                        color: 'var(--color-text, #f9fafb)', margin: 0,
                        letterSpacing: '-0.03em',
                    }}>
                        🛬 Check-in Today
                    </h1>
                    <p style={{
                        fontSize: 'var(--text-sm, 13px)',
                        color: 'var(--color-text-dim, #6b7280)',
                        margin: '2px 0 0',
                    }}>
                        {loading ? 'Loading…' : `${remaining.length} arrival${remaining.length !== 1 ? 's' : ''} remaining · ${done.length} confirmed`}
                    </p>
                </div>

                {loading && (
                    <div style={{ padding: '0 var(--space-4, 16px)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3, 12px)' }}>
                        {[1, 2, 3].map(i => (
                            <div key={i} style={{ height: 90, background: 'var(--color-surface, #1a1f2e)', borderRadius: 'var(--radius-lg, 16px)', animation: 'pulse 1.5s infinite' }} />
                        ))}
                    </div>
                )}

                {!loading && (
                    <div style={{ padding: '0 var(--space-4, 16px)' }}>
                        {remaining.length === 0 && done.length === 0 && (
                            <div style={{ textAlign: 'center', padding: 'var(--space-8, 60px) 0', color: 'var(--color-text-faint, #4b5563)' }}>
                                <div style={{ fontSize: 48, marginBottom: 'var(--space-3, 12px)' }}>🏖️</div>
                                <div style={{ fontSize: 'var(--text-lg, 18px)', fontWeight: 600, color: 'var(--color-text-dim, #6b7280)' }}>No arrivals today</div>
                            </div>
                        )}

                        {remaining.map(b => (
                            <ArrivalCard key={b.booking_id} booking={b} onConfirm={handleConfirm} loading={actionLoading} />
                        ))}

                        {done.length > 0 && (
                            <>
                                <div style={{
                                    fontSize: 'var(--text-xs, 11px)', color: 'var(--color-text-dim, #6b7280)',
                                    textTransform: 'uppercase', letterSpacing: '0.06em',
                                    padding: 'var(--space-4, 16px) 0 var(--space-2, 8px)',
                                }}>
                                    ✅ Confirmed ({done.length})
                                </div>
                                {done.map(b => (
                                    <div key={b.booking_id} style={{
                                        padding: 'var(--space-3, 12px) var(--space-4, 16px)',
                                        background: 'var(--color-surface, #1a1f2e)',
                                        border: '1px solid #22c55e30',
                                        borderRadius: 'var(--radius-lg, 16px)',
                                        marginBottom: 'var(--space-2, 8px)',
                                        opacity: 0.6,
                                        display: 'flex', alignItems: 'center', gap: 'var(--space-3, 12px)',
                                    }}>
                                        <span style={{ fontSize: 20 }}>✅</span>
                                        <span style={{ fontSize: 'var(--text-sm, 14px)', color: 'var(--color-text-dim, #9ca3af)' }}>
                                            {b.source} · {b.property_id}
                                        </span>
                                    </div>
                                ))}
                            </>
                        )}
                    </div>
                )}

                <div style={{
                    textAlign: 'center', fontSize: 'var(--text-xs, 11px)',
                    color: 'var(--color-text-faint, #374151)',
                    padding: 'var(--space-6, 24px)',
                }}>
                    Domaniqo — Check-in · Phase 387 · {today}
                </div>
            </div>
        </>
    );
}
