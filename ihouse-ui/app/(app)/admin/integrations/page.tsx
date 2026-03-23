'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface IntegrationProperty {
    property_id: string;
    property_name: string;
    channels: Array<{
        provider: string;
        channel_id: string;
        enabled: boolean;
        last_sync_at: string | null;
        status: string;
    }>;
}

export default function IntegrationManagementPage() {
    const [properties, setProperties] = useState<IntegrationProperty[]>([]);
    const [summary, setSummary] = useState<{ enabled: number; disabled: number; stale: number; failed: number }>({ enabled: 0, disabled: 0, stale: 0, failed: 0 });
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [intRes, sumRes] = await Promise.allSettled([
                api.getIntegrations(),
                api.getIntegrationsSummary(),
            ]);
            if (intRes.status === 'fulfilled') setProperties(intRes.value.properties as IntegrationProperty[]);
            if (sumRes.status === 'fulfilled') setSummary(sumRes.value);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const statusColor = (status: string) => {
        if (status === 'ok' || status === 'active') return 'var(--color-ok)';
        if (status === 'stale') return 'var(--color-warn)';
        if (status === 'failed' || status === 'error') return 'var(--color-danger)';
        return 'var(--color-text-dim)';
    };

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>OTA channel health</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Integration <span style={{ color: 'var(--color-primary)' }}>Management</span>
                </h1>
            </div>

            {/* Summary stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
                {[
                    { label: 'Enabled', value: summary.enabled, color: 'var(--color-ok)' },
                    { label: 'Disabled', value: summary.disabled, color: 'var(--color-text-dim)' },
                    { label: 'Stale', value: summary.stale, color: 'var(--color-warn)' },
                    { label: 'Failed', value: summary.failed, color: 'var(--color-danger)' },
                ].map(s => (
                    <div key={s.label} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{s.label}</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: s.color, marginTop: 'var(--space-2)' }}>{s.value}</div>
                    </div>
                ))}
            </div>

            {/* Per-property integrations */}
            {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
            {!loading && properties.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No integrations configured.</p>}
            {properties.map(prop => (
                <div key={prop.property_id} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-4)' }}>
                    <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)', marginBottom: 'var(--space-3)' }}>
                        {prop.property_name || prop.property_id}
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--space-3)' }}>
                        {(prop.channels || []).map((ch, i) => (
                            <div key={i} style={{ padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{ch.provider}</div>
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>{ch.last_sync_at ? new Date(ch.last_sync_at).toLocaleDateString() : 'Never synced'}</div>
                                </div>
                                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, padding: '2px 8px', borderRadius: 'var(--radius-full)', background: `${statusColor(ch.status)}22`, color: statusColor(ch.status) }}>
                                    {(ch.status || 'unknown').toUpperCase()}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            ))}

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                Domaniqo — Integration Management · Phase 513
            </div>
        </div>
    );
}
