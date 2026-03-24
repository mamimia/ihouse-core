'use client';

/**
 * Phase 865 — Combined Check-in & Check-out Hub
 * Phase 884 fixes:
 *   C: Arrivals now sourced from CHECKIN tasks (same as /tasks),
 *      not bookings. Bookings can return 0 even when tasks exist.
 *   D: Added Home/Profile link so combined role has full worker world access.
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
import { useCountdown } from '@/lib/useCountdown';
import { CHECKIN_CHECKOUT_BOTTOM_NAV } from '@/components/BottomNav';
import MobileStaffShell from '@/components/MobileStaffShell';
import Link from 'next/link';

export default function CheckinCheckoutHub() {
    const [arrivals, setArrivals] = useState(0);

    const [nextArrivalIso, setNextArrivalIso] = useState<string | null>(null);
    const [activeCheckouts, setActiveCheckouts] = useState(0);
    const [overdueCheckouts, setOverdueCheckouts] = useState(0);
    const [nextCheckoutIso, setNextCheckoutIso] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);

        // Phase 884 fix (C): Query CHECKIN tasks directly — same source as /tasks.
        // Previously we used the booking API which returned 0 when the booking
        // window query found nothing, even though real CHECKIN tasks existed.
        try {
            const today = new Date().toISOString().slice(0, 10);
            const checkinRes = await apiFetch<any>('/worker/tasks?worker_role=CHECKIN&limit=100');
            const checkinList = checkinRes.tasks || checkinRes.data?.tasks || checkinRes.data || [];
            const checkinTasks: any[] = Array.isArray(checkinList) ? checkinList : [];
            const pendingCheckins = checkinTasks.filter((t: any) =>
                t.status !== 'COMPLETED' && t.status !== 'CANCELED' &&
                (!t.due_date || t.due_date >= today)
            );
            setArrivals(pendingCheckins.length);
            const sortedArrivals = [...pendingCheckins].sort((a: any, b: any) =>
                (a.due_date || '').localeCompare(b.due_date || '')
            );
            setNextArrivalIso(sortedArrivals[0]?.due_date || null);
        } catch { setArrivals(0); setNextArrivalIso(null); }

        try {
            // Phase 886: Count ALL non-completed checkout tasks (overdue + today + upcoming).
            // Previously only counted "pending" (future) tasks, which understated the workload
            // vs the 19 check-in tasks. The checkout page itself shows all three buckets.
            const today = new Date().toISOString().slice(0, 10);
            const coRes = await apiFetch<any>('/worker/tasks?worker_role=CHECKOUT&limit=100');
            const coList = coRes.tasks || coRes.data?.tasks || coRes.data || [];
            const coTasks: any[] = Array.isArray(coList)
                ? coList.filter((t: any) => t.status !== 'COMPLETED' && t.status !== 'CANCELED')
                : [];
            const overdue = coTasks.filter((t: any) => t.due_date && t.due_date < today).length;
            const active  = coTasks.filter((t: any) => !t.due_date || t.due_date >= today).length;
            setOverdueCheckouts(overdue);
            setActiveCheckouts(active);
            const sortedCo = [...coTasks].sort((a: any, b: any) => (a.due_date || '').localeCompare(b.due_date || ''));
            setNextCheckoutIso(sortedCo[0]?.due_date || null);
        } catch { setActiveCheckouts(0); setOverdueCheckouts(0); setNextCheckoutIso(null); }

        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const today = new Date();
    const dateStr = today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

    // Countdown hooks for each section
    const arrivalCountdown = useCountdown(nextArrivalIso, '14:00');
    const checkoutCountdown = useCountdown(nextCheckoutIso, '11:00');

    const card = {
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
        transition: 'border-color 0.2s',
    };

    return (
        <MobileStaffShell title="Check-in & Check-out" bottomNavItems={CHECKIN_CHECKOUT_BOTTOM_NAV}>
        <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--space-4)' }}>
            {/* Date + title */}
            <div style={{ marginBottom: 'var(--space-5)' }}>
                <p style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {dateStr}
                </p>
                <h1 style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--color-text)', letterSpacing: '-0.03em', marginTop: 4 }}>
                    Your Shifts
                </h1>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                    Check-ins (7 days) &amp; Check-outs (task world)
                </p>
            </div>

            {loading && (
                <div style={{ ...card, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading…</div>
            )}

            {!loading && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                    {/* Arrivals card — sourced from CHECKIN tasks */}
                    <Link href="/ops/checkin" style={{ textDecoration: 'none' }}>
                        <div
                            style={{ ...card, borderColor: arrivalCountdown.isUrgent ? 'rgba(88,166,255,0.35)' : 'var(--color-border)' }}
                            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                            onMouseLeave={e => (e.currentTarget.style.borderColor = arrivalCountdown.isUrgent ? 'rgba(88,166,255,0.35)' : 'var(--color-border)')}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                    <span style={{ fontSize: 'var(--text-2xl)' }}>📋</span>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>Check-in</div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>Next 7 days · task world</div>
                                    </div>
                                </div>
                                <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: arrivals > 0 ? 'var(--color-accent)' : 'var(--color-text-faint)' }}>
                                    {arrivals}
                                </div>
                            </div>
                            {nextArrivalIso && arrivals > 0 && (
                                <div style={{ fontSize: 'var(--text-xs)', color: arrivalCountdown.isUrgent ? 'var(--color-warn)' : 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>
                                    ⏱ Next arrival: {arrivalCountdown.label}
                                </div>
                            )}
                            <div style={{
                                width: '100%', padding: '10px', borderRadius: 'var(--radius-sm)',
                                background: 'var(--color-primary)', color: '#fff',
                                fontSize: 'var(--text-xs)', fontWeight: 600, textAlign: 'center',
                            }}>
                                {arrivals > 0 ? `Start Check-ins (${arrivals} pending) →` : 'No check-in tasks — View →'}
                            </div>
                        </div>
                    </Link>

                    {/* Departures card */}
                    <Link href="/ops/checkout" style={{ textDecoration: 'none' }}>
                        <div
                            style={{ ...card, borderColor: overdueCheckouts > 0 ? 'rgba(196,91,74,0.4)' : checkoutCountdown.isUrgent ? 'rgba(212,149,106,0.35)' : 'var(--color-border)' }}
                            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                            onMouseLeave={e => (e.currentTarget.style.borderColor = overdueCheckouts > 0 ? 'rgba(196,91,74,0.4)' : 'var(--color-border)')}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                    <span style={{ fontSize: 'var(--text-2xl)' }}>🚩</span>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>Check-out</div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: overdueCheckouts > 0 ? 'var(--color-alert)' : 'var(--color-text-dim)', marginTop: 2 }}>
                                            {overdueCheckouts > 0 ? `⚠ ${overdueCheckouts} overdue` : 'Task world'}
                                        </div>
                                    </div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    {overdueCheckouts > 0 && (
                                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 800, color: 'var(--color-alert)' }}>{overdueCheckouts}</div>
                                    )}
                                    <div style={{ fontSize: overdueCheckouts > 0 ? 'var(--text-sm)' : 'var(--text-2xl)', fontWeight: 800, color: activeCheckouts > 0 ? 'var(--color-accent)' : 'var(--color-text-faint)' }}>
                                        {activeCheckouts} upcoming
                                    </div>
                                </div>
                            </div>
                            {nextCheckoutIso && (
                                <div style={{ fontSize: 'var(--text-xs)', color: checkoutCountdown.isOverdue ? 'var(--color-alert)' : checkoutCountdown.isUrgent ? 'var(--color-warn)' : 'var(--color-text-dim)', marginBottom: 'var(--space-2)', fontWeight: checkoutCountdown.isOverdue ? 700 : 400 }}>
                                    {checkoutCountdown.isOverdue ? '⚠ ' : '⏱ '}Next checkout: {checkoutCountdown.label}
                                </div>
                            )}
                            <div style={{
                                width: '100%', padding: '10px', borderRadius: 'var(--radius-sm)',
                                background: overdueCheckouts > 0 ? 'rgba(248,81,73,0.12)' : 'var(--color-primary)',
                                color: overdueCheckouts > 0 ? 'var(--color-alert)' : '#fff',
                                border: overdueCheckouts > 0 ? '1px solid rgba(248,81,73,0.3)' : 'none',
                                fontSize: 'var(--text-xs)', fontWeight: 600, textAlign: 'center',
                            }}>
                                {activeCheckouts + overdueCheckouts > 0 ? `Process Check-outs (${activeCheckouts + overdueCheckouts}) →` : 'No checkouts — View →'}
                            </div>
                        </div>
                    </Link>

                    {/* Phase 886: Profile & Settings — use window.location for reliable
                        navigation inside the Preview/iframe context where router.push
                        may be intercepted and fall back to the same page. */}
                    <div style={{
                        ...card,
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        opacity: 0.8, cursor: 'pointer',
                    }}
                        onClick={() => { window.location.href = '/worker'; }}
                        onMouseEnter={e => {
                            (e.currentTarget as HTMLDivElement).style.opacity = '1';
                            (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--color-primary)';
                        }}
                        onMouseLeave={e => {
                            (e.currentTarget as HTMLDivElement).style.opacity = '0.8';
                            (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--color-border)';
                        }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                            <span style={{ fontSize: 'var(--text-xl)' }}>👤</span>
                            <div>
                                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>Profile &amp; Settings</div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 1 }}>Home · Sign out · Language</div>
                            </div>
                        </div>
                        <span style={{ fontSize: 'var(--text-lg)', color: 'var(--color-text-faint)' }}>›</span>
                    </div>
                </div>
            )}
        </div>
        </MobileStaffShell>
    );
}
