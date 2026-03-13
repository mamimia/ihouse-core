'use client';

/**
 * Phase 555 — Analytics & Reporting Page
 * Route: /admin/analytics
 *
 * Occupancy trends, revenue per property, booking sources, satisfaction.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface AnalyticsData {
    occupancy_rate?: number;
    avg_daily_rate?: number;
    revpar?: number;
    total_bookings?: number;
    total_revenue?: number;
    booking_sources?: Record<string, number>;
    property_revenue?: Record<string, number>;
    monthly_trend?: { month: string; bookings: number; revenue: number }[];
}

export default function AnalyticsPage() {
    const [data, setData] = useState<AnalyticsData>({});
    const [loading, setLoading] = useState(true);
    const [period, setPeriod] = useState('30d');

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getAnalyticsSummary?.(period) || {};
            setData(res as AnalyticsData);
        } catch { /* graceful */ }
        setLoading(false);
    }, [period]);

    useEffect(() => { load(); }, [load]);

    const metricCard = (label: string, value: string | number | undefined, suffix = '', color = 'var(--color-primary)') => (
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-2)' }}>{label}</div>
            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{value ?? '—'}{suffix}</div>
        </div>
    );

    const sources = data.booking_sources || {};
    const sourceEntries = Object.entries(sources).sort(([, a], [, b]) => b - a);
    const maxSource = Math.max(...Object.values(sources), 1);

    const propRevenue = data.property_revenue || {};
    const propEntries = Object.entries(propRevenue).sort(([, a], [, b]) => b - a).slice(0, 10);
    const maxRev = Math.max(...Object.values(propRevenue), 1);

    return (
        <div style={{ maxWidth: 1100 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-8)', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Insights</p>
                    <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                        Analytics <span style={{ color: 'var(--color-primary)' }}>Dashboard</span>
                    </h1>
                </div>
                <select value={period} onChange={e => setPeriod(e.target.value)} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)' }}>
                    <option value="7d">Last 7 days</option>
                    <option value="30d">Last 30 days</option>
                    <option value="90d">Last 90 days</option>
                    <option value="365d">Last year</option>
                </select>
            </div>

            {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading analytics…</p>}

            {/* KPIs */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--space-4)', marginBottom: 'var(--space-8)' }}>
                {metricCard('Occupancy Rate', data.occupancy_rate, '%', 'var(--color-ok)')}
                {metricCard('Avg Daily Rate', data.avg_daily_rate, '', 'var(--color-primary)')}
                {metricCard('RevPAR', data.revpar, '', 'var(--color-accent)')}
                {metricCard('Total Bookings', data.total_bookings)}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 400px), 1fr))', gap: 'var(--space-6)' }}>
                {/* Booking Sources */}
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Booking Sources</h2>
                    {sourceEntries.length === 0 && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)' }}>No data</p>}
                    {sourceEntries.map(([source, count]) => (
                        <div key={source} style={{ marginBottom: 'var(--space-3)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--color-text)', marginBottom: 4 }}>
                                <span style={{ fontWeight: 500 }}>{source}</span>
                                <span style={{ fontFamily: 'var(--font-mono)' }}>{count}</span>
                            </div>
                            <div style={{ height: 6, background: 'var(--color-surface-2)', borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{ height: '100%', width: `${(count / maxSource) * 100}%`, background: 'var(--color-primary)', borderRadius: 3, transition: 'width 0.3s' }} />
                            </div>
                        </div>
                    ))}
                </div>

                {/* Revenue by Property */}
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Revenue by Property (Top 10)</h2>
                    {propEntries.length === 0 && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)' }}>No data</p>}
                    {propEntries.map(([prop, rev]) => (
                        <div key={prop} style={{ marginBottom: 'var(--space-3)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-xs)', color: 'var(--color-text)', marginBottom: 4 }}>
                                <span style={{ fontWeight: 500, maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{prop}</span>
                                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-ok)' }}>{rev.toLocaleString()}</span>
                            </div>
                            <div style={{ height: 6, background: 'var(--color-surface-2)', borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{ height: '100%', width: `${(rev / maxRev) * 100}%`, background: 'var(--color-ok)', borderRadius: 3, transition: 'width 0.3s' }} />
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>iHouse Core — Analytics · Phase 555</div>
        </div>
    );
}
