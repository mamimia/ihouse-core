'use client';

/**
 * Phase 533 — Operations Today Page
 * Route: /ops
 *
 * Full real-time picture: arrivals, departures, active tasks, SLA alerts.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { toast } from '@/components/Toast';
import Link from 'next/link';

export default function OperationsTodayPage() {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getOperationsToday?.() || {} as any;
            setData(res);
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to load operations');
        }
        setLoading(false);
    }, []);

    useEffect(() => { load(); const t = setInterval(load, 60_000); return () => clearInterval(t); }, [load]);

    const today = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
    const arrivals = data?.arrivals_count ?? 0;
    const departures = data?.departures_count ?? 0;
    const activeTasks = data?.active_tasks_count ?? 0;
    const slaBreaches = data?.sla_breaches_count ?? 0;
    const criticalTasks = data?.critical_pending_count ?? 0;

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>{today}</p>
                    <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                        Operations <span style={{ color: 'var(--color-primary)' }}>Today</span>
                    </h1>
                </div>
                <button onClick={load} disabled={loading} style={{ background: loading ? 'var(--color-surface-3)' : 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer' }}>
                    {loading ? '⟳' : '↺ Refresh'}
                </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
                {[
                    { label: 'Arrivals', value: arrivals, icon: '🛬', color: 'var(--color-primary)' },
                    { label: 'Departures', value: departures, icon: '🛫', color: 'var(--color-warn)' },
                    { label: 'Active Tasks', value: activeTasks, icon: '⚡', color: 'var(--color-text)' },
                    { label: 'Critical Pending', value: criticalTasks, icon: '🔴', color: criticalTasks > 0 ? 'var(--color-danger)' : 'var(--color-ok)' },
                    { label: 'SLA Breaches', value: slaBreaches, icon: '⏰', color: slaBreaches > 0 ? 'var(--color-danger)' : 'var(--color-ok)' },
                ].map(s => (
                    <div key={s.label} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{s.label}</span>
                            <span style={{ fontSize: 18 }}>{s.icon}</span>
                        </div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: s.color, marginTop: 'var(--space-2)' }}>{s.value}</div>
                    </div>
                ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
                {[
                    { label: 'Check-In Dashboard', href: '/ops/checkin', icon: '🛬', desc: 'Arrival readiness status' },
                    { label: 'Check-Out Turnover', href: '/ops/checkout', icon: '🛫', desc: 'Departure & inspection' },
                    { label: 'Task Board', href: '/tasks', icon: '✓', desc: 'All tasks & assignments' },
                    { label: 'Calendar', href: '/calendar', icon: '📆', desc: 'Booking timeline' },
                ].map(a => (
                    <Link key={a.href} href={a.href} style={{
                        background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)',
                        textDecoration: 'none', transition: 'all var(--transition-fast)', display: 'block',
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
                            <span style={{ fontSize: 20 }}>{a.icon}</span>
                            <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{a.label}</span>
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{a.desc}</div>
                    </Link>
                ))}
            </div>

            {slaBreaches > 0 && (
                <div style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-danger)', marginBottom: 'var(--space-3)' }}>⚠ SLA Breaches</h2>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                        {slaBreaches} task(s) have exceeded their SLA. Check the task board for details.
                    </p>
                </div>
            )}

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                iHouse Core — Operations Today · Phase 533 · Auto-refresh: 60s
            </div>
        </div>
    );
}
