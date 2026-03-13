'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

export default function PortfolioPage() {
    const [data, setData] = useState<{ properties: Array<{ property_id: string; occupancy: { active_bookings: number; arrivals_today: number; departures_today: number }; revenue: { gross_total: string | null; net_total: string | null; currency: string | null }; tasks: { pending_tasks: number; escalated_tasks: number }; sync_health: { stale: boolean | null; last_sync_status: string | null } }> } | null>(null);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getPortfolioDashboard();
            setData(res as any);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);
    const properties = data?.properties || [];

    return (
        <div style={{ maxWidth: 1100 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Cross-property view</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Portfolio <span style={{ color: 'var(--color-primary)' }}>Overview</span>
                </h1>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
                {[
                    { label: 'Properties', value: String(properties.length), color: 'var(--color-primary)' },
                    { label: 'Active Bookings', value: String(properties.reduce((s, p) => s + (p.occupancy?.active_bookings || 0), 0)), color: 'var(--color-accent)' },
                    { label: 'Pending Tasks', value: String(properties.reduce((s, p) => s + (p.tasks?.pending_tasks || 0), 0)), color: 'var(--color-warn)' },
                ].map(s => (
                    <div key={s.label} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{s.label}</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: s.color, marginTop: 'var(--space-2)' }}>{s.value}</div>
                    </div>
                ))}
            </div>

            {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
            {properties.map(p => (
                <div key={p.property_id} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-4)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                        <span style={{ fontWeight: 700, fontSize: 'var(--text-base)', color: 'var(--color-text)' }}>{p.property_id}</span>
                        {p.sync_health?.stale && <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, padding: '2px 8px', borderRadius: 'var(--radius-full)', background: 'var(--color-warn)22', color: 'var(--color-warn)' }}>STALE SYNC</span>}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-3)' }}>
                        <div style={{ padding: 'var(--space-2) var(--space-3)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Bookings</div>
                            <div style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-primary)' }}>{p.occupancy?.active_bookings || 0}</div>
                        </div>
                        <div style={{ padding: 'var(--space-2) var(--space-3)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Revenue</div>
                            <div style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-accent)' }}>{p.revenue?.gross_total || '—'} {p.revenue?.currency || ''}</div>
                        </div>
                        <div style={{ padding: 'var(--space-2) var(--space-3)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Tasks</div>
                            <div style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: (p.tasks?.escalated_tasks || 0) > 0 ? 'var(--color-danger)' : 'var(--color-text)' }}>{p.tasks?.pending_tasks || 0}{(p.tasks?.escalated_tasks || 0) > 0 ? ` (${p.tasks.escalated_tasks} ⚠)` : ''}</div>
                        </div>
                        <div style={{ padding: 'var(--space-2) var(--space-3)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Arrivals Today</div>
                            <div style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-ok)' }}>{p.occupancy?.arrivals_today || 0}</div>
                        </div>
                    </div>
                </div>
            ))}

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                iHouse Core — Portfolio Overview · Phase 522
            </div>
        </div>
    );
}
