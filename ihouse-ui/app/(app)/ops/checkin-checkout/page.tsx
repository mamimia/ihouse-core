'use client';

/**
 * Phase 865 — Combined Check-in & Check-out Hub
 *
 * Surface for staff members who handle BOTH arrivals and departures.
 * This is a navigation hub, not a re-implementation of either flow.
 *
 * Product distinction:
 *   - Check-in Staff  → /ops/checkin  (arrivals only)
 *   - Check-out Staff → /ops/checkout (departures only)
 *   - Check-in & Check-out → THIS PAGE (hub → links to both)
 *
 * This is a preview/act-as target, not a deep persistence role.
 */

import { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '@/lib/staffApi';
import { STAFF_BOTTOM_NAV } from '@/components/BottomNav';
import MobileStaffShell from '@/components/MobileStaffShell';
import Link from 'next/link';

export default function CheckinCheckoutHub() {
    const [arrivals, setArrivals] = useState(0);
    const [activeStays, setActiveStays] = useState(0);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            // Today's arrivals (same query as checkin page)
            const today = new Date().toISOString().slice(0, 10);
            const arrRes = await apiFetch<any>(`/bookings?check_in_from=${today}&check_in_to=${today}&limit=50`);
            const arrList = arrRes.bookings || arrRes.data?.bookings || arrRes.data || [];
            const arrBookings = Array.isArray(arrList) ? arrList : [];
            setArrivals(arrBookings.filter((b: any) => b.status !== 'checked_in' && b.status !== 'Completed' && b.status !== 'completed').length);
        } catch { setArrivals(0); }

        try {
            // Active stays for checkout (same query as checkout page)
            const coRes = await apiFetch<any>('/bookings?status=checked_in&limit=50');
            const coList = coRes.bookings || coRes.data?.bookings || coRes.data || [];
            setActiveStays(Array.isArray(coList) ? coList.length : 0);
        } catch { setActiveStays(0); }

        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const today = new Date();
    const dateStr = today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

    const card = {
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
        transition: 'border-color 0.2s',
    };

    return (
        <MobileStaffShell title="Check-in & Check-out" bottomNavItems={STAFF_BOTTOM_NAV}>
        <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--space-4)' }}>
            {/* Date + title */}
            <div style={{ marginBottom: 'var(--space-5)' }}>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {dateStr}
                </p>
                <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
                    Your Shifts Today
                </h1>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                    Combined check-in & check-out assignments
                </p>
            </div>

            {loading && (
                <div style={{ ...card, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading…</div>
            )}

            {!loading && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                    {/* Arrivals card */}
                    <Link href="/ops/checkin" style={{ textDecoration: 'none' }}>
                        <div
                            style={card}
                            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                    <span style={{ fontSize: 'var(--text-2xl)' }}>📋</span>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>
                                            Check-in
                                        </div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                                            Today&apos;s arrivals
                                        </div>
                                    </div>
                                </div>
                                <div style={{
                                    fontSize: 'var(--text-2xl)', fontWeight: 800,
                                    color: arrivals > 0 ? 'var(--color-accent)' : 'var(--color-text-faint)',
                                }}>
                                    {arrivals}
                                </div>
                            </div>
                            <div style={{
                                width: '100%', padding: '10px', borderRadius: 'var(--radius-sm)',
                                background: 'var(--color-primary)', color: '#fff',
                                fontSize: 'var(--text-xs)', fontWeight: 600, textAlign: 'center',
                            }}>
                                {arrivals > 0 ? `Start Check-ins (${arrivals} pending) →` : 'View Arrivals →'}
                            </div>
                        </div>
                    </Link>

                    {/* Departures card */}
                    <Link href="/ops/checkout" style={{ textDecoration: 'none' }}>
                        <div
                            style={card}
                            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                    <span style={{ fontSize: 'var(--text-2xl)' }}>🚪</span>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>
                                            Check-out
                                        </div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                                            Active stays for departure
                                        </div>
                                    </div>
                                </div>
                                <div style={{
                                    fontSize: 'var(--text-2xl)', fontWeight: 800,
                                    color: activeStays > 0 ? 'var(--color-accent)' : 'var(--color-text-faint)',
                                }}>
                                    {activeStays}
                                </div>
                            </div>
                            <div style={{
                                width: '100%', padding: '10px', borderRadius: 'var(--radius-sm)',
                                background: 'rgba(248,81,73,0.08)', color: 'var(--color-alert)',
                                border: '1px solid rgba(248,81,73,0.2)',
                                fontSize: 'var(--text-xs)', fontWeight: 600, textAlign: 'center',
                            }}>
                                {activeStays > 0 ? `Start Check-outs (${activeStays} active) →` : 'View Stays →'}
                            </div>
                        </div>
                    </Link>

                    {/* Summary strip */}
                    <div style={{
                        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)',
                    }}>
                        <div style={card}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Arrivals</div>
                            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-sage)', marginTop: 4 }}>{arrivals}</div>
                        </div>
                        <div style={card}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Departures</div>
                            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-alert)', marginTop: 4 }}>{activeStays}</div>
                        </div>
                    </div>
                </div>
            )}
        </div>
        </MobileStaffShell>
    );
}
