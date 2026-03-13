'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface Worker {
    worker_id: string;
    name?: string;
    tasks_completed: number;
    avg_ack_minutes: number;
    sla_compliance_pct: number;
    tasks_per_day: number;
    channel?: string;
}

export default function StaffPerformancePage() {
    const [workers, setWorkers] = useState<Worker[]>([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getStaffPerformance();
            setWorkers((res.workers || []) as Worker[]);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Team operations</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Staff <span style={{ color: 'var(--color-primary)' }}>Performance</span>
                </h1>
            </div>

            {/* Summary stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
                {[
                    { label: 'Total Workers', value: String(workers.length), color: 'var(--color-primary)' },
                    { label: 'Avg SLA Compliance', value: workers.length ? `${(workers.reduce((s, w) => s + (w.sla_compliance_pct || 0), 0) / workers.length).toFixed(0)}%` : '—', color: 'var(--color-ok)' },
                    { label: 'Avg ACK Time', value: workers.length ? `${(workers.reduce((s, w) => s + (w.avg_ack_minutes || 0), 0) / workers.length).toFixed(1)}m` : '—', color: 'var(--color-accent)' },
                ].map(s => (
                    <div key={s.label} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{s.label}</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: s.color, marginTop: 'var(--space-2)' }}>{s.value}</div>
                    </div>
                ))}
            </div>

            {/* Worker table */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Worker Metrics</h2>

                {/* Header */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 100px 100px 100px', gap: 'var(--space-3)', padding: '0 var(--space-4)', marginBottom: 'var(--space-2)' }}>
                    {['Worker', 'Tasks', 'ACK Time', 'SLA %', 'Tasks/Day'].map(h => (
                        <span key={h} style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</span>
                    ))}
                </div>

                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>Loading…</p>}
                {!loading && workers.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>No worker data yet.</p>}

                {workers.map((w, i) => (
                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 100px 100px 100px 100px', gap: 'var(--space-3)', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)', alignItems: 'center' }}>
                        <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{w.name || w.worker_id}</span>
                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', fontFamily: 'var(--font-mono)' }}>{w.tasks_completed}</span>
                        <span style={{ fontSize: 'var(--text-sm)', color: (w.avg_ack_minutes || 0) > 5 ? 'var(--color-danger)' : 'var(--color-ok)', fontFamily: 'var(--font-mono)' }}>{(w.avg_ack_minutes || 0).toFixed(1)}m</span>
                        <span style={{
                            fontSize: 'var(--text-xs)', fontWeight: 700, padding: '2px 8px', borderRadius: 'var(--radius-full)',
                            background: (w.sla_compliance_pct || 0) >= 90 ? 'var(--color-ok)22' : 'var(--color-danger)22',
                            color: (w.sla_compliance_pct || 0) >= 90 ? 'var(--color-ok)' : 'var(--color-danger)',
                        }}>{(w.sla_compliance_pct || 0).toFixed(0)}%</span>
                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>{(w.tasks_per_day || 0).toFixed(1)}</span>
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', borderTop: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                iHouse Core — Staff Performance · Phase 511
            </div>
        </div>
    );
}
