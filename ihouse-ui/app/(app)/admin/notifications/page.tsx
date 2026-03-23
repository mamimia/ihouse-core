'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface NotificationEntry {
    notification_delivery_id: string;
    channel_type: string;
    status: string;
    trigger_reason: string;
    dispatched_at: string;
    worker_id: string;
    error_message?: string;
}

export default function NotificationCenterPage() {
    const [entries, setEntries] = useState<NotificationEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<'all' | 'sent' | 'failed'>('all');

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getNotificationHistory?.({ limit: 100 }) || { notifications: [] };
            setEntries((res.notifications || []) as NotificationEntry[]);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const filtered = filter === 'all' ? entries : entries.filter(e => e.status === filter);
    const sentCount = entries.filter(e => e.status === 'sent').length;
    const failedCount = entries.filter(e => e.status === 'failed').length;

    const channelColor = (ch: string) => {
        if (ch === 'line') return '#00B900';
        if (ch === 'whatsapp') return '#25D366';
        if (ch === 'telegram') return '#229ED9';
        if (ch === 'email') return '#3b82f6';
        return 'var(--color-text-dim)';
    };

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Delivery log</p>
                    <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                        Notification <span style={{ color: 'var(--color-primary)' }}>Center</span>
                    </h1>
                </div>
                <button onClick={load} disabled={loading} style={{ background: loading ? 'var(--color-surface-3)' : 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer' }}>
                    {loading ? '⟳ Loading…' : '↺ Refresh'}
                </button>
            </div>

            <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
                {[
                    { id: 'all' as const, label: `All (${entries.length})` },
                    { id: 'sent' as const, label: `Sent (${sentCount})` },
                    { id: 'failed' as const, label: `Failed (${failedCount})` },
                ].map(f => (
                    <button key={f.id} onClick={() => setFilter(f.id)} style={{
                        padding: 'var(--space-2) var(--space-4)',
                        borderRadius: 'var(--radius-md)',
                        border: filter === f.id ? '1px solid var(--color-primary)' : '1px solid var(--color-border)',
                        background: filter === f.id ? 'rgba(59,130,246,0.08)' : 'var(--color-surface)',
                        color: filter === f.id ? 'var(--color-primary)' : 'var(--color-text-dim)',
                        fontSize: 'var(--text-xs)',
                        fontWeight: 600,
                        cursor: 'pointer',
                    }}>
                        {f.label}
                    </button>
                ))}
            </div>

            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                {!loading && filtered.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No notifications found.</p>}
                {filtered.map((e, i) => (
                    <div key={e.notification_delivery_id || i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, padding: '2px 8px', borderRadius: 'var(--radius-full)', background: `${channelColor(e.channel_type)}22`, color: channelColor(e.channel_type), textTransform: 'uppercase' }}>
                                {e.channel_type}
                            </span>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{e.trigger_reason || 'notification'}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: e.status === 'sent' ? 'var(--color-ok)' : 'var(--color-danger)' }}>
                                {e.status === 'sent' ? '✓ Sent' : '✗ Failed'}
                            </span>
                            {e.dispatched_at && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>{new Date(e.dispatched_at).toLocaleString()}</span>}
                        </div>
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                Domaniqo — Notification Center · Phase 529
            </div>
        </div>
    );
}
