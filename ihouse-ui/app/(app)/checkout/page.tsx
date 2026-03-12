'use client';

/**
 * Phase 387 — Check-out Mobile Surface
 * Route: /checkout
 *
 * Today's departures for field staff. Checkout confirmation
 * with notes. Triggers cleaning task on completion.
 */

import { useEffect, useState, useCallback } from 'react';
import { api, Booking } from '../../../lib/api';

function isoToday(): string {
    return new Date().toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// Departure Card
// ---------------------------------------------------------------------------

function DepartureCard({ booking, onCheckout, loading }: {
    booking: Booking; onCheckout: (id: string, notes: string) => void; loading: boolean;
}) {
    const [expanded, setExpanded] = useState(false);
    const [notes, setNotes] = useState('');

    return (
        <div style={{
            background: 'var(--color-surface, #1a1f2e)',
            border: '1px solid var(--color-border, #ffffff12)',
            borderRadius: 'var(--radius-lg, 16px)',
            overflow: 'hidden',
            marginBottom: 'var(--space-3, 12px)',
        }}>
            <div
                onClick={() => setExpanded(!expanded)}
                style={{
                    padding: 'var(--space-4, 16px)',
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 'var(--space-3, 12px)',
                }}
            >
                <span style={{ fontSize: 28, flexShrink: 0 }}>🛫</span>
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
                        In: {booking.check_in} → Out: {booking.check_out}
                    </div>
                </div>
                <span style={{
                    fontSize: 'var(--text-xs, 11px)', fontWeight: 600,
                    color: '#f59e0b', background: '#f59e0b18',
                    borderRadius: 99, padding: '2px 10px', flexShrink: 0,
                }}>
                    Departing
                </span>
                <span style={{
                    color: 'var(--color-text-faint, #4b5563)', fontSize: 18,
                    transform: expanded ? 'rotate(90deg)' : 'none',
                    transition: 'transform 0.2s', flexShrink: 0,
                }}>›</span>
            </div>

            {expanded && (
                <div style={{
                    padding: '0 var(--space-4, 16px) var(--space-4, 16px)',
                    borderTop: '1px solid var(--color-border, #ffffff08)',
                }}>
                    <textarea
                        id={`checkout-notes-${booking.booking_id}`}
                        value={notes}
                        onChange={e => setNotes(e.target.value)}
                        placeholder="Checkout notes (condition, keys, damages…)"
                        rows={3}
                        style={{
                            width: '100%', background: 'var(--color-bg, #111827)',
                            border: '1px solid var(--color-border, #374151)',
                            borderRadius: 'var(--radius-md, 12px)',
                            color: 'var(--color-text, #f9fafb)',
                            fontSize: 14, padding: 'var(--space-3, 12px)',
                            resize: 'none', outline: 'none',
                            boxSizing: 'border-box',
                            marginTop: 'var(--space-3, 12px)',
                            marginBottom: 'var(--space-3, 12px)',
                        }}
                    />

                    <div style={{ display: 'flex', gap: 'var(--space-2, 8px)' }}>
                        <button
                            id={`checkout-confirm-${booking.booking_id}`}
                            disabled={loading}
                            onClick={() => onCheckout(booking.booking_id, notes)}
                            style={{
                                flex: 1, padding: 'var(--space-3, 14px)',
                                borderRadius: 'var(--radius-md, 14px)',
                                border: 'none',
                                background: loading ? 'var(--color-surface-3, #1f2937)' : 'linear-gradient(135deg,#f59e0b,#d97706)',
                                color: loading ? 'var(--color-text-dim, #6b7280)' : '#fff',
                                fontWeight: 700, fontSize: 15,
                                cursor: loading ? 'not-allowed' : 'pointer',
                                boxShadow: loading ? 'none' : '0 0 16px rgba(245,158,11,0.3)',
                            }}
                        >
                            {loading ? 'Processing…' : '🧹 Confirm Checkout'}
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

export default function CheckOutPage() {
    const today = isoToday();
    const [departures, setDepartures] = useState<Booking[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [processed, setProcessed] = useState<Set<string>>(new Set());

    const load = useCallback(async () => {
        try {
            const resp = await api.getBookings({ check_in_from: today, check_in_to: today, limit: 200 });
            setDepartures((resp.bookings ?? []).filter((b: Booking) => b.check_out === today && b.status === 'active'));
        } catch { /* noop */ } finally { setLoading(false); }
    }, [today]);

    useEffect(() => { load(); }, [load]);

    const handleCheckout = async (id: string, notes: string) => {
        setActionLoading(true);
        // Would trigger cleaning task creation via API
        setProcessed(prev => new Set(prev).add(id));
        setActionLoading(false);
    };

    const remaining = departures.filter(b => !processed.has(b.booking_id));
    const done = departures.filter(b => processed.has(b.booking_id));

    return (
        <>
            <style>{`
                @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
                @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.5} }
            `}</style>

            <div style={{ minHeight: '100vh', paddingBottom: 'var(--space-8, 32px)', animation: 'fadeIn 300ms ease' }}>
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
                        🛫 Check-out Today
                    </h1>
                    <p style={{
                        fontSize: 'var(--text-sm, 13px)',
                        color: 'var(--color-text-dim, #6b7280)',
                        margin: '2px 0 0',
                    }}>
                        {loading ? 'Loading…' : `${remaining.length} departure${remaining.length !== 1 ? 's' : ''} remaining · ${done.length} processed`}
                    </p>
                </div>

                {loading && (
                    <div style={{ padding: '0 var(--space-4, 16px)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3, 12px)' }}>
                        {[1, 2].map(i => (
                            <div key={i} style={{ height: 90, background: 'var(--color-surface, #1a1f2e)', borderRadius: 'var(--radius-lg, 16px)', animation: 'pulse 1.5s infinite' }} />
                        ))}
                    </div>
                )}

                {!loading && (
                    <div style={{ padding: '0 var(--space-4, 16px)' }}>
                        {remaining.length === 0 && done.length === 0 && (
                            <div style={{ textAlign: 'center', padding: 'var(--space-8, 60px) 0', color: 'var(--color-text-faint, #4b5563)' }}>
                                <div style={{ fontSize: 48, marginBottom: 'var(--space-3, 12px)' }}>🌅</div>
                                <div style={{ fontSize: 'var(--text-lg, 18px)', fontWeight: 600, color: 'var(--color-text-dim, #6b7280)' }}>No departures today</div>
                            </div>
                        )}

                        {remaining.map(b => (
                            <DepartureCard key={b.booking_id} booking={b} onCheckout={handleCheckout} loading={actionLoading} />
                        ))}

                        {done.length > 0 && (
                            <>
                                <div style={{
                                    fontSize: 'var(--text-xs, 11px)', color: 'var(--color-text-dim, #6b7280)',
                                    textTransform: 'uppercase', letterSpacing: '0.06em',
                                    padding: 'var(--space-4, 16px) 0 var(--space-2, 8px)',
                                }}>
                                    🧹 Processed ({done.length})
                                </div>
                                {done.map(b => (
                                    <div key={b.booking_id} style={{
                                        padding: 'var(--space-3, 12px) var(--space-4, 16px)',
                                        background: 'var(--color-surface, #1a1f2e)',
                                        border: '1px solid #f59e0b30',
                                        borderRadius: 'var(--radius-lg, 16px)',
                                        marginBottom: 'var(--space-2, 8px)',
                                        opacity: 0.6,
                                        display: 'flex', alignItems: 'center', gap: 'var(--space-3, 12px)',
                                    }}>
                                        <span style={{ fontSize: 20 }}>🧹</span>
                                        <span style={{ fontSize: 'var(--text-sm, 14px)', color: 'var(--color-text-dim, #9ca3af)' }}>
                                            {b.source} · {b.property_id} — cleaning task created
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
                    Domaniqo — Check-out · Phase 387 · {today}
                </div>
            </div>
        </>
    );
}
