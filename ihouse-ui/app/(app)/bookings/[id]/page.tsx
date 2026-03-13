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

export default function BookingDetailPage() {
    const params = useParams();
    const bookingId = params?.id as string;
    const [booking, setBooking] = useState<any>(null);
    const [financial, setFinancial] = useState<any>(null);
    const [history, setHistory] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [bRes, fRes, hRes] = await Promise.allSettled([
                api.getBookings?.({ limit: 100 }),
                api.getBookingFinancial?.(bookingId),
                api.getBookingHistory?.(bookingId),
            ]);
            if (bRes.status === 'fulfilled') {
                const b = bRes.value?.bookings?.find((b: any) => b.booking_id === bookingId);
                setBooking(b || null);
            }
            if (fRes.status === 'fulfilled') setFinancial(fRes.value);
            if (hRes.status === 'fulfilled') setHistory(hRes.value?.events || []);
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
                            {[['Property', booking.property_id], ['Guest', booking.guest_name], ['Check-in', booking.check_in_date], ['Check-out', booking.check_out_date], ['Status', booking.status], ['Source', booking.source]].map(([k, v]) => (
                                <div key={k as string} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-sm)' }}>
                                    <span style={{ color: 'var(--color-text-dim)' }}>{k}</span>
                                    <span style={{ color: 'var(--color-text)', fontWeight: 500 }}>{v || '—'}</span>
                                </div>
                            ))}
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
                    ) : <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)' }}>No financial data</p>}
                </div>
            </div>

            {/* Timeline */}
            <div style={{ marginTop: 'var(--space-8)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', textTransform: 'uppercase' }}>Event Timeline</h2>
                {history.length === 0 && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)' }}>No events recorded</p>}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                    {history.map((e: any, i: number) => (
                        <div key={i} style={{ display: 'flex', gap: 'var(--space-3)', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)' }}>
                            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)', minWidth: 140 }}>{e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}</span>
                            <span style={{ color: 'var(--color-primary)', fontWeight: 600, minWidth: 140 }}>{e.event_type}</span>
                            <span style={{ color: 'var(--color-text-dim)' }}>{e.source || '—'}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
