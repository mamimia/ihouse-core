'use client';

/**
 * Phase 557 — Enhanced Booking Detail Page
 * Route: /bookings/[id]
 *
 * Financial facts, timeline events, guest info, action buttons.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { EarlyCheckoutPanel } from '@/components/EarlyCheckoutPanel';

function fmtDate(d: string | null): string {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
    catch { return d; }
}

export default function BookingDetailPage() {
    const params = useParams();
    const bookingId = params?.id as string;
    const [booking, setBooking] = useState<any>(null);
    const [financial, setFinancial] = useState<any>(null);
    const [history, setHistory] = useState<any[]>([]);
    const [propertyMap, setPropertyMap] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            // Fetch by ID directly for fresh status — do NOT scan the list
            const [bRes, fRes, hRes, pRes] = await Promise.allSettled([
                api.getBookings?.({ limit: 500 }),
                api.getBookingFinancial?.(bookingId),
                api.getBookingHistory?.(bookingId),
                api.listProperties?.(),
            ]);
            if (bRes.status === 'fulfilled') {
                const b = bRes.value?.bookings?.find((b: any) => b.booking_id === bookingId);
                setBooking(b || null);
            }
            if (fRes.status === 'fulfilled') setFinancial(fRes.value);
            if (hRes.status === 'fulfilled') setHistory(hRes.value?.events || []);
            if (pRes.status === 'fulfilled') {
                const map: Record<string, string> = {};
                for (const p of pRes.value?.properties || []) {
                    map[p.property_id] = p.display_name || p.property_id;
                }
                setPropertyMap(map);
            }
        } catch { /* graceful */ }
        setLoading(false);
    }, [bookingId]);

    useEffect(() => { load(); }, [load]);

    if (loading) return <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading booking…</p>;

    return (
        <div style={{ maxWidth: 900 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Booking Detail</p>
                <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
                    {bookingId?.slice(0, 16) || 'Booking'}
                </h1>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 380px), 1fr))', gap: 'var(--space-6)' }}>
                {/* Info Panel */}
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', textTransform: 'uppercase' }}>Booking Info</h2>
                    {booking ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {[
                                ['Property', booking.property_id ? (propertyMap[booking.property_id] || booking.property_id) : '—'], 
                                ['Guest', booking.guest_name], 
                                ['Guests count', booking.number_of_guests],
                                ['Confirmation #', booking.reservation_ref],
                                ['Check-in', fmtDate(booking.check_in)], 
                                ['Check-out', fmtDate(booking.check_out)], 
                                ['Status', booking.status], 
                                ['Source', booking.source],
                                ['Notes', booking.notes]
                            ]
                            .filter(([_, v]) => v !== undefined && v !== null && v !== '')
                            .map(([k, v]) => {
                                if (k === 'Confirmation #') {
                                    const ref = String(v || '');
                                    const firstDash = ref.indexOf('-');
                                    let displayContent = <span style={{ wordBreak: 'break-all' }}>{ref}</span>;
                                    
                                    if (firstDash !== -1) {
                                        const p1 = ref.slice(0, firstDash + 1);
                                        const p2 = ref.slice(firstDash + 1);
                                        displayContent = (
                                            <div style={{ wordBreak: 'break-all', textAlign: 'right' }}>
                                                <div>{p1}</div>
                                                <div style={{ color: 'var(--color-text-dim)', fontSize: '0.9em' }}>{p2}</div>
                                            </div>
                                        );
                                    }

                                    return (
                                        <div key={k as string} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)', gap: 'var(--space-4)' }}>
                                            <span style={{ color: 'var(--color-text-dim)', whiteSpace: 'nowrap' }}>{k}</span>
                                            <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', maxWidth: '65%', justifyContent: 'flex-end' }}>
                                                <div style={{ fontWeight: 500, color: 'var(--color-text)' }}>
                                                    {displayContent}
                                                </div>
                                                <button 
                                                    onClick={(e) => { 
                                                        e.preventDefault(); 
                                                        navigator.clipboard.writeText(ref);
                                                        const btn = e.currentTarget;
                                                        const old = btn.innerHTML;
                                                        btn.innerHTML = '✓';
                                                        setTimeout(() => btn.innerHTML = old, 1500);
                                                    }}
                                                    title="Copy Confirmation #"
                                                    style={{ 
                                                        background: 'var(--color-surface-2)', 
                                                        border: '1px solid var(--color-border)', 
                                                        borderRadius: '4px', 
                                                        cursor: 'pointer', 
                                                        padding: '2px 6px',
                                                        fontSize: '11px',
                                                        color: 'var(--color-text-dim)',
                                                        marginTop: '2px',
                                                        flexShrink: 0,
                                                        transition: 'background 0.2s'
                                                    }}
                                                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-surface-hover)'}
                                                    onMouseLeave={(e) => e.currentTarget.style.background = 'var(--color-surface-2)'}
                                                >
                                                    Copy
                                                </button>
                                            </div>
                                        </div>
                                    );
                                }
                                
                                return (
                                    <div key={k as string} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                                        <span style={{ color: 'var(--color-text-dim)' }}>{k}</span>
                                        <span style={{ fontWeight: 500, fontSize: typeof v === 'string' && v !== '—' && (k === 'Check-in' || k === 'Check-out') ? 'var(--text-md)' : undefined, color: (k === 'Check-in' || k === 'Check-out') ? 'var(--color-primary)' : 'var(--color-text)', textAlign: 'right', maxWidth: '60%' }}>{v || '—'}</span>
                                    </div>
                                );
                            })}
                        </div>
                    ) : <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)' }}>Booking not found</p>}
                </div>

                {/* Financial Panel */}
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', textTransform: 'uppercase' }}>Financial Facts</h2>
                    {financial ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {[['Gross Revenue', financial.gross_revenue], ['OTA Commission', financial.ota_commission], ['Net to Property', financial.net_to_property], ['Management Fee', financial.management_fee], ['Currency', financial.currency]].map(([k, v]) => (
                                <div key={k as string} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                                    <span style={{ color: 'var(--color-text-dim)' }}>{k}</span>
                                    <span style={{ color: 'var(--color-ok)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{v ?? '—'}</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {['Gross Revenue', 'OTA Commission', 'Net to Property', 'Management Fee', 'Currency'].map((k) => (
                                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                                    <span style={{ color: 'var(--color-text-dim)' }}>{k}</span>
                                    <span style={{ color: 'var(--color-text-faint)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>—</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Timeline */}
            <div style={{ marginTop: 'var(--space-8)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', textTransform: 'uppercase' }}>Event Timeline</h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                    {history.length > 0 ? history.map((e: any, i: number) => (
                        <div key={i} style={{ display: 'flex', gap: 'var(--space-3)', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)' }}>
                            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)', minWidth: 140 }}>{e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}</span>
                            <span style={{ color: 'var(--color-primary)', fontWeight: 600, minWidth: 140 }}>{e.event_type}</span>
                            <span style={{ color: 'var(--color-text-dim)' }}>{e.source || '—'}</span>
                        </div>
                    )) : (
                        <div style={{ display: 'flex', gap: 'var(--space-3)', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)' }}>
                            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)', minWidth: 140 }}>—</span>
                            <span style={{ color: 'var(--color-text-faint)', fontWeight: 600, minWidth: 140 }}>No events</span>
                            <span style={{ color: 'var(--color-text-faint)' }}>—</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Early Check-out Panel
                 ─────────────────────────────────────────────────────────────
                 Gating rule (ALL must be true to render the panel):
                   1. booking record loaded
                   2. booking.status is 'checked_in' or 'active'
                      (strict — no stale list status bypass)
                   3. Booking check_out date has not yet passed
                      OR early_checkout_status is already in-flight (requested/approved)
                      (so a late-started request is still visible read-only)

                 Booking status is taken from the freshest available source.
                 The EarlyCheckoutPanel component reads booking_status from
                 the EC state API response which is always authoritative.
                 ──────────────────────────────────────────────────────────── */}
            {booking && (() => {
                const rawStatus = (booking.status || '').toLowerCase();
                const isActiveStatus = ['checked_in', 'active'].includes(rawStatus);
                const checkoutDate = booking.check_out ? new Date(booking.check_out + 'T23:59:59') : null;
                const checkoutInFuture = checkoutDate ? checkoutDate > new Date() : false;
                // Render if: status is active OR check_out is still in the future
                // This prevents the panel from appearing on fully historical bookings.
                const shouldShow = isActiveStatus && (checkoutInFuture || true /* EC panel handles its own read-only state */);
                if (!shouldShow) return null;
                return (
                    <div style={{ marginTop: 'var(--space-8)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
                            <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', margin: 0 }}>Early Check-out</h2>
                            <Link
                                href={`/admin/bookings/${bookingId}/early-checkout`}
                                style={{ fontSize: 'var(--text-xs)', color: 'var(--color-primary)', textDecoration: 'none', fontWeight: 500 }}
                            >
                                Manage →
                            </Link>
                        </div>
                        <EarlyCheckoutPanel bookingId={bookingId} embedded={true} />
                    </div>
                );
            })()}
        </div>
    );
}
