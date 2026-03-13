'use client';

/**
 * Phase 532 — Check-Out & Turnover Page
 * Route: /ops/checkout
 *
 * Shows today's departures with inspection/turnover status.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface Departure {
    booking_ref: string;
    property_id: string;
    guest_name: string;
    check_out_date: string;
    check_out_time: string;
    checkout_done: boolean;
    inspection_done: boolean;
    cleaning_scheduled: boolean;
    damage_reported: boolean;
}

export default function CheckOutPage() {
    const [departures, setDepartures] = useState<Departure[]>([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getTodaysDepartures?.() || { departures: [] };
            setDepartures((res.departures || []) as Departure[]);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const today = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>{today}</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Check-Out & <span style={{ color: 'var(--color-warn)' }}>Turnover</span>
                </h1>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
                {[
                    { label: 'Departures', value: departures.length, color: 'var(--color-primary)' },
                    { label: 'Inspected', value: departures.filter(d => d.inspection_done).length, color: 'var(--color-ok)' },
                    { label: 'Damages', value: departures.filter(d => d.damage_reported).length, color: departures.some(d => d.damage_reported) ? 'var(--color-danger)' : 'var(--color-ok)' },
                ].map(s => (
                    <div key={s.label} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{s.label}</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: s.color, marginTop: 'var(--space-2)' }}>{s.value}</div>
                    </div>
                ))}
            </div>

            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Departures</h2>
                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                {!loading && departures.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No departures today 🎉</p>}
                {departures.map(d => (
                    <div key={d.booking_ref} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                        <div>
                            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{d.guest_name}</div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                <span style={{ fontFamily: 'var(--font-mono)' }}>{d.property_id}</span> · checkout {d.check_out_time}
                            </div>
                        </div>
                        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
                            <span title="Checkout done" style={{ fontSize: 14 }}>{d.checkout_done ? '✅' : '⏳'}</span>
                            <span title="Inspected" style={{ fontSize: 14 }}>{d.inspection_done ? '🔍✅' : '🔍⏳'}</span>
                            <span title="Cleaning scheduled" style={{ fontSize: 14 }}>{d.cleaning_scheduled ? '🧹✅' : '🧹⏳'}</span>
                            {d.damage_reported && <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-danger)', background: 'rgba(239,68,68,0.1)', padding: '2px 6px', borderRadius: 'var(--radius-full)' }}>⚠ DAMAGE</span>}
                        </div>
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                iHouse Core — Check-Out & Turnover · Phase 532
            </div>
        </div>
    );
}
