/*
 * Phase 369 — Outbound Sync Retry Dashboard
 *
 * Route: /admin/sync
 * Displays per-provider outbound sync health with failure rates,
 * last sync times, and log lag indicators.
 */
'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '../../../../lib/api';

interface SyncProvider {
    provider: string;
    last_sync_at: string | null;
    failure_rate_7d: number | null;
    log_lag_seconds: number | null;
    status: 'ok' | 'degraded' | 'idle' | 'error';
}

interface SyncHealth {
    status: string;
    providers: SyncProvider[];
}

const STATUS_COLOR: Record<string, string> = {
    ok: '#10b981',
    degraded: '#f59e0b',
    idle: '#64748b',
    error: '#ef4444',
};

const STATUS_ICON: Record<string, string> = {
    ok: '✓',
    degraded: '⚠',
    idle: '—',
    error: '✕',
};

export default function SyncDashboardPage() {
    const [health, setHealth] = useState<SyncHealth | null>(null);
    const [loading, setLoading] = useState(true);
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const resp = await api.getOutboundHealth();
            const data = resp as unknown as { outbound?: SyncHealth };
            setHealth(data.outbound ?? null);
            setLastRefresh(new Date());
        } catch {
            setHealth(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    // Auto-refresh every 60s
    useEffect(() => {
        const timer = setInterval(load, 60000);
        return () => clearInterval(timer);
    }, [load]);

    const formatLag = (seconds: number | null) => {
        if (seconds === null) return '—';
        if (seconds < 60) return `${Math.floor(seconds)}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
        return `${Math.floor(seconds / 86400)}d`;
    };

    const formatRate = (rate: number | null) => {
        if (rate === null) return '—';
        return `${(rate * 100).toFixed(1)}%`;
    };

    return (
        <div style={{
            minHeight: '100vh',
            background: 'linear-gradient(135deg, #0f0c29, #1a1255, #0f0c29)',
            fontFamily: "'Inter', system-ui, sans-serif",
            color: '#e2e8f0',
            padding: '32px 24px',
        }}>
            <style>{`@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');`}</style>

            <div style={{ maxWidth: 960, margin: '0 auto' }}>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
                    <div>
                        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, letterSpacing: '-0.02em' }}>
                            🔄 Outbound Sync Health
                        </h1>
                        <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 13 }}>
                            Per-provider sync status, failure rates, and lag indicators
                        </p>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        {lastRefresh && (
                            <span style={{ fontSize: 11, color: '#475569' }}>
                                Updated {lastRefresh.toLocaleTimeString()}
                            </span>
                        )}
                        <button
                            id="sync-refresh"
                            onClick={load}
                            style={{
                                padding: '6px 14px', borderRadius: 99,
                                border: '1px solid #1e293b', background: '#0f172a',
                                color: '#64748b', fontSize: 12, cursor: 'pointer',
                            }}
                        >↻ Refresh</button>
                    </div>
                </div>

                {/* Overall status badge */}
                {health && (
                    <div style={{
                        display: 'inline-flex', alignItems: 'center', gap: 8,
                        background: '#111827', borderRadius: 99, padding: '6px 16px',
                        marginBottom: 24, border: `1px solid ${STATUS_COLOR[health.status] ?? '#64748b'}30`,
                    }}>
                        <div style={{
                            width: 8, height: 8, borderRadius: '50%',
                            background: STATUS_COLOR[health.status] ?? '#64748b',
                        }} />
                        <span style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase' }}>
                            {health.status}
                        </span>
                    </div>
                )}

                {/* Loading */}
                {loading && !health && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {[...Array(5)].map((_, i) => (
                            <div key={i} style={{
                                height: 72, borderRadius: 14,
                                background: 'linear-gradient(90deg, #1e293b 25%, #293548 50%, #1e293b 75%)',
                                backgroundSize: '200% 100%',
                            }} />
                        ))}
                    </div>
                )}

                {/* Provider cards */}
                {health?.providers?.map(prov => {
                    const color = STATUS_COLOR[prov.status] ?? '#64748b';
                    const icon = STATUS_ICON[prov.status] ?? '?';
                    return (
                        <div
                            key={prov.provider}
                            style={{
                                background: '#111827',
                                border: `1px solid ${prov.status === 'error' ? '#ef444430' : '#ffffff0a'}`,
                                borderRadius: 14, padding: '16px 20px',
                                marginBottom: 10, display: 'flex', alignItems: 'center', gap: 16,
                            }}
                        >
                            {/* Status indicator */}
                            <div style={{
                                width: 36, height: 36, borderRadius: 10,
                                background: `${color}20`, display: 'flex',
                                alignItems: 'center', justifyContent: 'center',
                                fontSize: 16, fontWeight: 700, color,
                            }}>{icon}</div>

                            {/* Provider info */}
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontSize: 14, fontWeight: 600, textTransform: 'capitalize' }}>
                                    {prov.provider}
                                </div>
                                <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                                    Last sync: {prov.last_sync_at
                                        ? new Date(prov.last_sync_at).toLocaleString()
                                        : 'Never'}
                                </div>
                            </div>

                            {/* Metrics */}
                            <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{ fontSize: 16, fontWeight: 700, color: (prov.failure_rate_7d ?? 0) > 0.2 ? '#ef4444' : '#e2e8f0' }}>
                                        {formatRate(prov.failure_rate_7d)}
                                    </div>
                                    <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase' }}>Fail Rate</div>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{ fontSize: 16, fontWeight: 700, color: (prov.log_lag_seconds ?? 0) > 3600 ? '#f59e0b' : '#e2e8f0' }}>
                                        {formatLag(prov.log_lag_seconds)}
                                    </div>
                                    <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase' }}>Lag</div>
                                </div>
                            </div>
                        </div>
                    );
                })}

                {/* Empty state */}
                {!loading && (!health || health.providers.length === 0) && (
                    <div style={{ textAlign: 'center', padding: '60px 0', color: '#475569', fontSize: 14 }}>
                        No outbound sync data available.
                    </div>
                )}
            </div>
        </div>
    );
}
