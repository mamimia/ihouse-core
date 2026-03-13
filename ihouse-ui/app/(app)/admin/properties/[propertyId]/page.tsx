'use client';

/**
 * Phase 556 — Enhanced Property Detail Page
 * Route: /admin/properties/[propertyId]
 *
 * Tabbed view: Overview, Bookings, Financials, Tasks, Settings.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { useParams } from 'next/navigation';

type Tab = 'overview' | 'bookings' | 'financials' | 'tasks' | 'settings';

export default function PropertyDetailPage() {
    const params = useParams();
    const propertyId = params?.propertyId as string;
    const [tab, setTab] = useState<Tab>('overview');
    const [data, setData] = useState<any>({});
    const [bookings, setBookings] = useState<any[]>([]);
    const [tasks, setTasks] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [propRes, bookRes, taskRes] = await Promise.allSettled([
                api.getPortfolioDashboard?.(),
                api.getBookings?.({ property_id: propertyId, limit: 20 }),
                api.getTasks?.({ limit: 20 }),
            ]);
            if (propRes.status === 'fulfilled') {
                const prop = (propRes.value?.properties || []).find((p: any) => p.property_id === propertyId);
                setData(prop || {});
            }
            if (bookRes.status === 'fulfilled') setBookings(bookRes.value?.bookings || []);
            if (taskRes.status === 'fulfilled') setTasks((taskRes.value?.tasks || []).filter((t: any) => t.property_id === propertyId));
        } catch { /* graceful */ }
        setLoading(false);
    }, [propertyId]);

    useEffect(() => { load(); }, [load]);

    const tabStyle = (t: Tab) => ({
        padding: 'var(--space-2) var(--space-4)',
        fontSize: 'var(--text-sm)',
        fontWeight: tab === t ? 600 : 400,
        color: tab === t ? 'var(--color-primary)' : 'var(--color-text-dim)',
        borderBottom: tab === t ? '2px solid var(--color-primary)' : '2px solid transparent',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
    });

    return (
        <div style={{ maxWidth: 1100 }}>
            <div style={{ marginBottom: 'var(--space-6)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Property Detail</p>
                <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
                    {propertyId || 'Property'}
                </h1>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 'var(--space-1)', borderBottom: '1px solid var(--color-border)', marginBottom: 'var(--space-6)' }}>
                {(['overview', 'bookings', 'financials', 'tasks', 'settings'] as Tab[]).map(t => (
                    <button key={t} onClick={() => setTab(t)} style={tabStyle(t)}>{t.charAt(0).toUpperCase() + t.slice(1)}</button>
                ))}
            </div>

            {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}

            {/* Overview */}
            {tab === 'overview' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
                    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Active Bookings</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-primary)' }}>{data?.occupancy?.active_bookings ?? '—'}</div>
                    </div>
                    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Pending Tasks</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: data?.tasks?.pending_tasks > 0 ? 'var(--color-warn)' : 'var(--color-ok)' }}>{data?.tasks?.pending_tasks ?? '—'}</div>
                    </div>
                    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>Revenue</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-ok)' }}>{data?.revenue?.currency} {data?.revenue?.gross_total ?? '—'}</div>
                    </div>
                </div>
            )}

            {/* Bookings */}
            {tab === 'bookings' && (
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 100px 100px', gap: 'var(--space-2)', padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>
                        <div>Booking ID</div><div>Check-In</div><div>Check-Out</div><div>Status</div>
                    </div>
                    {bookings.length === 0 && <p style={{ padding: 'var(--space-6)', fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', textAlign: 'center' }}>No bookings</p>}
                    {bookings.slice(0, 20).map((b: any) => (
                        <div key={b.booking_id} style={{ display: 'grid', gridTemplateColumns: '1fr 100px 100px 100px', gap: 'var(--space-2)', padding: 'var(--space-2) var(--space-4)', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)' }}>
                            <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text)' }}>{b.booking_id?.slice(0, 12)}</div>
                            <div style={{ color: 'var(--color-text-dim)' }}>{b.check_in_date}</div>
                            <div style={{ color: 'var(--color-text-dim)' }}>{b.check_out_date}</div>
                            <div style={{ fontWeight: 600, color: b.status === 'confirmed' ? 'var(--color-ok)' : 'var(--color-text-dim)' }}>{b.status}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Financials */}
            {tab === 'financials' && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Use Financial Dashboard for detailed per-property breakdown →</p>}

            {/* Tasks */}
            {tab === 'tasks' && (
                <div>
                    {tasks.length === 0 && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>No tasks for this property</p>}
                    {tasks.map((t: any) => (
                        <div key={t.task_id} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-2)', fontSize: 'var(--text-sm)' }}>
                            <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>{t.title}</span>
                            <span style={{ marginLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{t.status} · {t.priority}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* Settings */}
            {tab === 'settings' && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Property settings will be available in a future update.</p>}
        </div>
    );
}
