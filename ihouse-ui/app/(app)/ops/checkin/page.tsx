'use client';

/**
 * Phase 531 — Check-In Readiness Dashboard
 * Route: /ops/checkin
 *
 * Shows today's arrivals with readiness status per property.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface Arrival {
    booking_ref: string;
    property_id: string;
    guest_name: string;
    check_in_date: string;
    check_in_time: string;
    status: string;
    cleaning_done: boolean;
    keys_ready: boolean;
    welcome_sent: boolean;
    nights: number;
}

export default function CheckInDashboardPage() {
    const [arrivals, setArrivals] = useState<Arrival[]>([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getTodaysArrivals?.() || { arrivals: [] };
            setArrivals((res.arrivals || []) as Arrival[]);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const today = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
    const readyCount = arrivals.filter(a => a.cleaning_done && a.keys_ready).length;

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>{today}</p>
                    <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                        Check-In <span style={{ color: 'var(--color-primary)' }}>Readiness</span>
                    </h1>
                </div>
                <button onClick={load} disabled={loading} style={{ background: loading ? 'var(--color-surface-3)' : 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer' }}>↺</button>
            </div>

            {/* Summary */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
                {[
                    { label: 'Arrivals Today', value: arrivals.length, color: 'var(--color-primary)' },
                    { label: 'Ready', value: readyCount, color: 'var(--color-ok)' },
                    { label: 'Not Ready', value: arrivals.length - readyCount, color: arrivals.length - readyCount > 0 ? 'var(--color-warn)' : 'var(--color-ok)' },
                ].map(s => (
                    <div key={s.label} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{s.label}</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: s.color, marginTop: 'var(--space-2)' }}>{s.value}</div>
                    </div>
                ))}
            </div>

            {/* Arrivals list */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Arrivals</h2>
                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                {!loading && arrivals.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No arrivals today 🎉</p>}
                {arrivals.map(a => {
                    const isReady = a.cleaning_done && a.keys_ready;
                    return (
                        <div key={a.booking_ref} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                            <div>
                                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{a.guest_name}</div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                    <span style={{ fontFamily: 'var(--font-mono)' }}>{a.property_id}</span> · {a.nights} nights · {a.check_in_time}
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
                                <span title="Cleaning" style={{ fontSize: 16 }}>{a.cleaning_done ? '🧹✅' : '🧹❌'}</span>
                                <span title="Keys" style={{ fontSize: 16 }}>{a.keys_ready ? '🔑✅' : '🔑❌'}</span>
                                <span title="Welcome msg" style={{ fontSize: 16 }}>{a.welcome_sent ? '💬✅' : '💬❌'}</span>
                                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, padding: '2px 8px', borderRadius: 'var(--radius-full)', background: isReady ? 'rgba(34,197,94,0.1)' : 'rgba(245,158,11,0.1)', color: isReady ? 'var(--color-ok)' : 'var(--color-warn)' }}>
                                    {isReady ? 'READY' : 'NOT READY'}
                                </span>
                            </div>
                        </div>
                    );
                })}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                iHouse Core — Check-In Readiness · Phase 531
            </div>
        </div>
    );
}
