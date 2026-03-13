'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface WebhookEvent {
    id: number;
    provider: string;
    event_type: string;
    status: string;
    received_at: string;
    payload_preview: string;
    source?: string | null;
    replay_result?: string | null;
}

export default function WebhookLogPage() {
    const [events, setEvents] = useState<WebhookEvent[]>([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getDlqEntries({ limit: 50 });
            setEvents((res.entries || []) as unknown as WebhookEvent[]);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const statusColor = (s: string) => {
        if (s === 'applied' || s === 'ok') return 'var(--color-ok)';
        if (s === 'pending') return 'var(--color-warn)';
        if (s === 'error' || s === 'failed') return 'var(--color-danger)';
        return 'var(--color-text-dim)';
    };

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Integration events</p>
                    <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                        Webhook <span style={{ color: 'var(--color-primary)' }}>Event Log</span>
                    </h1>
                </div>
                <button onClick={load} disabled={loading} style={{ background: loading ? 'var(--color-surface-3)' : 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer' }}>
                    {loading ? '⟳ Loading…' : '↺ Refresh'}
                </button>
            </div>

            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                {!loading && events.length === 0 && <p style={{ color: 'var(--color-ok)', fontSize: 'var(--text-sm)' }}>✓ No webhook events in queue</p>}
                {events.map((e, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                        <div>
                            <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{e.source || e.provider || '—'}</span>
                            <span style={{ margin: '0 var(--space-2)', color: 'var(--color-text-dim)' }}>·</span>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{e.replay_result || e.event_type || '—'}</span>
                        </div>
                        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, padding: '2px 8px', borderRadius: 'var(--radius-full)', background: `${statusColor(e.status)}22`, color: statusColor(e.status) }}>
                            {(e.status || 'unknown').toUpperCase()}
                        </span>
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                iHouse Core — Webhook Event Log · Phase 521
            </div>
        </div>
    );
}
