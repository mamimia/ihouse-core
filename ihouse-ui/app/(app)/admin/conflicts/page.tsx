'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface Conflict {
    property_id: string;
    booking_a: string;
    booking_b: string;
    overlap_start: string;
    overlap_end: string;
    status: string;
}

export default function ConflictDashboardPage() {
    const [conflicts, setConflicts] = useState<Conflict[]>([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await (api as any).getConflicts?.() || { conflicts: [] };
            setConflicts((res.conflicts || []) as Conflict[]);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Booking overlap management</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Conflict <span style={{ color: 'var(--color-danger)' }}>Dashboard</span>
                </h1>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Active Conflicts</div>
                    <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: conflicts.length > 0 ? 'var(--color-danger)' : 'var(--color-ok)', marginTop: 'var(--space-2)' }}>{conflicts.length}</div>
                </div>
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Properties Affected</div>
                    <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-warn)', marginTop: 'var(--space-2)' }}>{new Set(conflicts.map(c => c.property_id)).size}</div>
                </div>
            </div>

            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                {!loading && conflicts.length === 0 && <p style={{ color: 'var(--color-ok)', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>✓ No active conflicts</p>}
                {conflicts.map((c, i) => (
                    <div key={i} style={{ padding: 'var(--space-3) var(--space-4)', background: '#ef444408', border: '1px solid #ef444422', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-1)' }}>
                            <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{c.property_id}</span>
                            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, padding: '2px 8px', borderRadius: 'var(--radius-full)', background: 'var(--color-danger)22', color: 'var(--color-danger)' }}>{(c.status || 'active').toUpperCase()}</span>
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                            {c.booking_a} ↔ {c.booking_b} · Overlap: {c.overlap_start} to {c.overlap_end}
                        </div>
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                Domaniqo — Conflict Dashboard · Phase 522
            </div>
        </div>
    );
}
