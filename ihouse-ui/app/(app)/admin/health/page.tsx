'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface HealthMetrics {
    uptime_seconds: number;
    process_start_utc: string;
    request_counts: Record<string, number>;
    error_counts: Record<string, { '4xx': number; '5xx': number }>;
    latency: Record<string, { count: number; min_ms: number | null; max_ms: number | null; avg_ms: number | null; p95_ms: number | null }>;
}

export default function SystemHealthPage() {
    const [data, setData] = useState<HealthMetrics | null>(null);
    const [jobData, setJobData] = useState<{ total_jobs: number; jobs: Record<string, { description: string; interval_hours: number }> } | null>(null);
    const [dlqCount, setDlqCount] = useState<number>(0);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [metricsRes, jobsRes, dlqRes] = await Promise.allSettled([
                api.getHealthDetailed(),
                api.getSchedulerStatus?.() || Promise.resolve({ total_jobs: 0, jobs: {} }),
                api.getDlqEntries({ limit: 1 }),
            ]);
            if (metricsRes.status === 'fulfilled') setData(metricsRes.value as any);
            if (jobsRes.status === 'fulfilled') setJobData(jobsRes.value as any);
            if (dlqRes.status === 'fulfilled') setDlqCount((dlqRes.value as any)?.total || 0);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const fmtUptime = (s: number) => {
        const h = Math.floor(s / 3600);
        const m = Math.floor((s % 3600) / 60);
        return `${h}h ${m}m`;
    };

    const totalRequests = data ? Object.values(data.request_counts).reduce((a, b) => a + b, 0) : 0;
    const total5xx = data ? Object.values(data.error_counts).reduce((a, v) => a + (v['5xx'] || 0), 0) : 0;
    const total4xx = data ? Object.values(data.error_counts).reduce((a, v) => a + (v['4xx'] || 0), 0) : 0;

    return (
        <div style={{ maxWidth: 1000 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>System monitoring</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    System <span style={{ color: 'var(--color-ok)' }}>Health</span>
                </h1>
            </div>

            {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}

            {/* Key metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
                {[
                    { label: 'Uptime', value: data ? fmtUptime(data.uptime_seconds) : '—', color: 'var(--color-ok)' },
                    { label: 'Total Requests', value: totalRequests.toLocaleString(), color: 'var(--color-primary)' },
                    { label: '5xx Errors', value: String(total5xx), color: total5xx > 0 ? 'var(--color-danger)' : 'var(--color-ok)' },
                    { label: 'DLQ Entries', value: String(dlqCount), color: dlqCount > 0 ? 'var(--color-warn)' : 'var(--color-ok)' },
                ].map(s => (
                    <div key={s.label} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{s.label}</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: s.color, marginTop: 'var(--space-2)' }}>{s.value}</div>
                    </div>
                ))}
            </div>

            {/* Request breakdown */}
            {data && Object.keys(data.request_counts).length > 0 && (
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Requests by Route</h2>
                    {Object.entries(data.request_counts).sort((a, b) => b[1] - a[1]).map(([route, count]) => {
                        const pct = totalRequests > 0 ? (count / totalRequests) * 100 : 0;
                        const errs = data.error_counts[route] || { '4xx': 0, '5xx': 0 };
                        return (
                            <div key={route} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                                <span style={{ minWidth: 80, fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)' }}>{route}</span>
                                <div style={{ flex: 1, height: 12, background: 'var(--color-surface-2)', borderRadius: 4, overflow: 'hidden' }}>
                                    <div style={{ height: '100%', width: `${pct}%`, background: 'var(--color-primary)', borderRadius: 4, transition: 'width .4s ease' }} />
                                </div>
                                <span style={{ minWidth: 50, fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text)', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{count}</span>
                                {(errs['5xx'] > 0) && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-danger)', fontWeight: 700 }}>⚠ {errs['5xx']}</span>}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Latency */}
            {data && Object.keys(data.latency).length > 0 && (
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Latency (ms)</h2>
                    <div style={{ display: 'grid', gridTemplateColumns: 'auto repeat(4, 1fr)', gap: 'var(--space-2)', fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)' }}>
                        <div style={{ color: 'var(--color-text-faint)', fontWeight: 600 }}>Route</div>
                        <div style={{ color: 'var(--color-text-faint)', fontWeight: 600, textAlign: 'right' }}>Avg</div>
                        <div style={{ color: 'var(--color-text-faint)', fontWeight: 600, textAlign: 'right' }}>P95</div>
                        <div style={{ color: 'var(--color-text-faint)', fontWeight: 600, textAlign: 'right' }}>Min</div>
                        <div style={{ color: 'var(--color-text-faint)', fontWeight: 600, textAlign: 'right' }}>Max</div>
                        {Object.entries(data.latency).map(([route, stats]) => (
                            <>
                                <div key={`${route}-name`} style={{ color: 'var(--color-text-dim)' }}>{route}</div>
                                <div key={`${route}-avg`} style={{ textAlign: 'right', color: 'var(--color-text)' }}>{stats.avg_ms?.toFixed(1) ?? '—'}</div>
                                <div key={`${route}-p95`} style={{ textAlign: 'right', color: (stats.p95_ms || 0) > 500 ? 'var(--color-warn)' : 'var(--color-text)' }}>{stats.p95_ms?.toFixed(1) ?? '—'}</div>
                                <div key={`${route}-min`} style={{ textAlign: 'right', color: 'var(--color-text-dim)' }}>{stats.min_ms?.toFixed(1) ?? '—'}</div>
                                <div key={`${route}-max`} style={{ textAlign: 'right', color: 'var(--color-text-dim)' }}>{stats.max_ms?.toFixed(1) ?? '—'}</div>
                            </>
                        ))}
                    </div>
                </div>
            )}

            {/* Jobs */}
            {jobData && (
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-4)' }}>Scheduled Jobs ({jobData.total_jobs})</h2>
                    {Object.entries(jobData.jobs).map(([name, job]) => (
                        <div key={name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2) var(--space-3)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-1)' }}>
                            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text)' }}>{name.replace(/_/g, ' ')}</span>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>every {job.interval_hours}h</span>
                        </div>
                    ))}
                </div>
            )}

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                iHouse Core — System Health · Phase 527
            </div>
        </div>
    );
}
