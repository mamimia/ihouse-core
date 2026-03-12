'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, OperationsToday, Task, OutboundHealthProvider, DlqSummaryEntry, PortfolioProperty } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DashboardData {
    today: OperationsToday | null;
    criticalTasks: Task[];
    syncProviders: OutboundHealthProvider[];
    dlqPending: DlqSummaryEntry[];
    portfolio: PortfolioProperty[];
}

// ---------------------------------------------------------------------------
// Section Card
// ---------------------------------------------------------------------------

function SectionCard({
    title,
    badge,
    badgeColor,
    children,
}: {
    title: string;
    badge?: string | number;
    badgeColor?: string;
    children: React.ReactNode;
}) {
    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-6)',
            transition: 'border-color var(--transition-base)',
        }}>
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                marginBottom: 'var(--space-5)',
            }}>
                <h2 style={{
                    fontSize: 'var(--text-sm)',
                    fontWeight: 600,
                    color: 'var(--color-text-dim)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                }}>{title}</h2>
                {badge !== undefined && (
                    <span style={{
                        fontSize: 'var(--text-xs)',
                        fontWeight: 700,
                        padding: '1px 8px',
                        borderRadius: 'var(--radius-full)',
                        background: badgeColor ? `${badgeColor}22` : 'var(--color-surface-3)',
                        color: badgeColor || 'var(--color-text-dim)',
                        border: `1px solid ${badgeColor ? `${badgeColor}44` : 'var(--color-border)'}`,
                    }}>{badge}</span>
                )}
            </div>
            {children}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Stat chip
// ---------------------------------------------------------------------------

function StatChip({
    label,
    value,
    accent,
}: {
    label: string;
    value: number | string;
    accent?: string;
}) {
    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-1)',
            background: 'var(--color-surface-2)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-4) var(--space-5)',
            border: '1px solid var(--color-border)',
        }}>
            <span style={{
                fontSize: 'var(--text-2xl)',
                fontWeight: 700,
                color: accent || 'var(--color-text)',
                lineHeight: 1.1,
                fontVariantNumeric: 'tabular-nums',
            }}>{value}</span>
            <span style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
            }}>{label}</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Sync badge
// ---------------------------------------------------------------------------

function SyncBadge({ status }: { status: 'ok' | 'warn' | 'fail' | 'idle' }) {
    const colors = {
        ok: { bg: '#10b98122', color: 'var(--color-ok)', label: 'OK' },
        warn: { bg: '#f59e0b22', color: 'var(--color-warn)', label: 'WARN' },
        fail: { bg: '#ef444422', color: 'var(--color-danger)', label: 'FAIL' },
        idle: { bg: '#6b728022', color: 'var(--color-muted)', label: 'IDLE' },
    }[status];
    return (
        <span style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: 'var(--radius-full)',
            background: colors.bg,
            color: colors.color,
            fontFamily: 'var(--font-mono)',
        }}>{colors.label}</span>
    );
}

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
    const [data, setData] = useState<DashboardData>({
        today: null,
        criticalTasks: [],
        syncProviders: [],
        dlqPending: [],
        portfolio: [],
    });
    const [loading, setLoading] = useState(true);
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [todayRes, tasksRes, healthRes, dlqRes, portfolioRes] = await Promise.allSettled([
                api.getOperationsToday(),
                api.getTasks({ status: 'pending', priority: 'critical', limit: 10 }),
                api.getOutboundHealth(),
                api.getDlq({ status: 'pending', limit: 50 }),
                api.getPortfolioDashboard(),
            ]);

            setData({
                today: todayRes.status === 'fulfilled' ? todayRes.value : null,
                criticalTasks: tasksRes.status === 'fulfilled' ? tasksRes.value.tasks : [],
                syncProviders: healthRes.status === 'fulfilled' ? healthRes.value.providers : [],
                dlqPending: dlqRes.status === 'fulfilled' ? dlqRes.value.entries : [],
                portfolio: portfolioRes.status === 'fulfilled' ? portfolioRes.value.properties : [],
            });
            setLastRefresh(new Date());
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
        // 60s auto-refresh
        timerRef.current = setInterval(load, 60_000);
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [load]);

    // SSE for real-time events (Phase 306/307)
    useEffect(() => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') ?? '' : '';
        const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
        const es = new EventSource(`${baseUrl}/events/stream?channels=bookings,tasks,alerts&token=${token}`);
        es.onmessage = (e) => {
            try {
                const evt = JSON.parse(e.data);
                // Auto-refresh dashboard on any real event
                if (evt.channel && evt.channel !== 'system') {
                    setTimeout(load, 1000);
                }
            } catch { /* ignore */ }
        };
        return () => es.close();
    }, [load]);

    const now = new Date();
    const hour = now.getHours();
    const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

    // Determine sync provider health status
    const syncStatus = (p: OutboundHealthProvider) => {
        if (!p.last_sync_at) return 'idle' as const;
        if (p.failure_rate_7d !== null && p.failure_rate_7d > 0.2) return 'fail' as const;
        if (p.failure_rate_7d !== null && p.failure_rate_7d > 0.05) return 'warn' as const;
        return 'ok' as const;
    };

    return (
        <div style={{ maxWidth: 1100 }}>

            {/* Header */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: 'var(--space-8)',
            }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-1)' }}>
                        {greeting} · {data.today?.date || now.toISOString().slice(0, 10)}
                    </p>
                    <h1 style={{
                        fontSize: 'var(--text-3xl)',
                        fontWeight: 700,
                        letterSpacing: '-0.03em',
                        color: 'var(--color-text)',
                        lineHeight: 1.1,
                    }}>
                        Operations <span style={{ color: 'var(--color-primary)' }}>Dashboard</span>
                    </h1>
                </div>
                <button
                    onClick={load}
                    disabled={loading}
                    style={{
                        background: loading ? 'var(--color-surface-3)' : 'var(--color-primary)',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-2) var(--space-5)',
                        fontSize: 'var(--text-sm)',
                        fontWeight: 600,
                        opacity: loading ? 0.7 : 1,
                        transition: 'all var(--transition-fast)',
                    }}
                >
                    {loading ? '⟳  Refreshing…' : '↺  Refresh'}
                </button>
            </div>

            {lastRefresh && (
                <p style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-faint)',
                    marginBottom: 'var(--space-8)',
                    marginTop: '-var(--space-4)',
                }}>
                    Last updated {lastRefresh.toLocaleTimeString()}
                </p>
            )}

            {/* Grid layout */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 'var(--space-6)',
            }}>

                {/* Section 1 — Urgent */}
                <SectionCard
                    title="Urgent tasks"
                    badge={data.criticalTasks.length || 0}
                    badgeColor={data.criticalTasks.length > 0 ? 'var(--color-danger)' : undefined}
                >
                    {data.criticalTasks.length === 0 ? (
                        <p style={{ color: 'var(--color-ok)', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <span>✓</span> No critical unacked tasks
                        </p>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {data.criticalTasks.map(task => (
                                <div key={task.task_id} style={{
                                    background: '#ef444411',
                                    border: '1px solid #ef444433',
                                    borderRadius: 'var(--radius-md)',
                                    padding: 'var(--space-3) var(--space-4)',
                                }}>
                                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-danger)' }}>
                                        {task.title}
                                    </div>
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 'var(--space-1)' }}>
                                        ACK SLA: {task.ack_sla_minutes}min · {task.property_id}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </SectionCard>

                {/* Section 2 — Today */}
                <SectionCard title="Today">
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-3)' }}>
                        <StatChip
                            label="Arrivals"
                            value={data.today?.arrivals_today ?? '—'}
                            accent="var(--color-accent)"
                        />
                        <StatChip
                            label="Departures"
                            value={data.today?.departures_today ?? '—'}
                            accent="var(--color-primary)"
                        />
                        <StatChip
                            label="Cleanings"
                            value={data.today?.cleanings_due_today ?? '—'}
                            accent="var(--color-warn)"
                        />
                    </div>
                </SectionCard>

                {/* Section 3 — Sync Health */}
                <SectionCard title="Sync health" badge={data.syncProviders.length}>
                    {data.syncProviders.length === 0 ? (
                        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>No sync data yet</p>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {data.syncProviders.map(p => (
                                <div key={p.provider} style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    padding: 'var(--space-3) var(--space-4)',
                                    background: 'var(--color-surface-2)',
                                    borderRadius: 'var(--radius-md)',
                                }}>
                                    <div>
                                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>
                                            {p.provider}
                                        </span>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                                            ✓{p.ok_count} ✗{p.failed_count}
                                            {p.last_sync_at ? ` · ${new Date(p.last_sync_at).toLocaleTimeString()}` : ''}
                                        </div>
                                    </div>
                                    <SyncBadge status={syncStatus(p)} />
                                </div>
                            ))}
                        </div>
                    )}
                </SectionCard>

                {/* Section 4 — Integration Alerts */}
                <SectionCard
                    title="Integration alerts"
                    badge={data.dlqPending.length || 0}
                    badgeColor={data.dlqPending.length > 0 ? 'var(--color-warn)' : undefined}
                >
                    {data.dlqPending.length === 0 ? (
                        <p style={{ color: 'var(--color-ok)', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <span>✓</span> DLQ clear — no pending events
                        </p>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                            {data.dlqPending.slice(0, 5).map(entry => (
                                <div key={entry.id} style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    padding: 'var(--space-2) var(--space-3)',
                                    background: '#f59e0b11',
                                    border: '1px solid #f59e0b22',
                                    borderRadius: 'var(--radius-sm)',
                                    fontSize: 'var(--text-xs)',
                                }}>
                                    <span style={{ color: 'var(--color-text)', fontWeight: 500 }}>
                                        {entry.provider} · {entry.event_type}
                                    </span>
                                    <span style={{ color: 'var(--color-warn)' }}>
                                        {entry.rejection_code}
                                    </span>
                                </div>
                            ))}
                            {data.dlqPending.length > 5 && (
                                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', textAlign: 'center' }}>
                                    +{data.dlqPending.length - 5} more
                                </p>
                            )}
                        </div>
                    )}
                </SectionCard>

            </div>

            {/* Section 5 — Portfolio Overview */}
            {data.portfolio.length > 0 && (
                <SectionCard
                    title="Portfolio overview"
                    badge={data.portfolio.length}
                >
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                        gap: 'var(--space-3)',
                    }}>
                        {data.portfolio.map(prop => (
                            <div key={prop.property_id} style={{
                                background: 'var(--color-surface-2)',
                                border: `1px solid ${prop.sync_health.stale ? '#f59e0b44' : 'var(--color-border)'}`,
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-3) var(--space-4)',
                            }}>
                                <div style={{
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 700,
                                    color: 'var(--color-text-dim)',
                                    marginBottom: 'var(--space-2)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.06em',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                }}>
                                    <span style={{
                                        maxWidth: 140,
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap',
                                    }}>{prop.property_id}</span>
                                    {prop.sync_health.stale && (
                                        <span style={{ color: 'var(--color-warn)', fontSize: 11 }}>STALE</span>
                                    )}
                                </div>
                                <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                        🛏 {prop.occupancy.active_bookings} active
                                    </span>
                                    <span style={{ fontSize: 'var(--text-xs)', color: prop.tasks.pending_tasks > 0 ? 'var(--color-warn)' : 'var(--color-text-dim)' }}>
                                        ✓ {prop.tasks.pending_tasks} tasks
                                    </span>
                                    {prop.revenue.gross_total && (
                                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-ok)' }}>
                                            {prop.revenue.currency} {prop.revenue.gross_total}
                                        </span>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </SectionCard>
            )}

            {/* Footer */}
            <div style={{
                marginTop: 'var(--space-10)',
                paddingTop: 'var(--space-6)',
                borderTop: '1px solid var(--color-border)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-faint)',
                display: 'flex',
                justifyContent: 'space-between',
            }}>
                <span>Domaniqo — Operations Dashboard · Phase 288</span>
                <span>Auto-refresh: 60s</span>
            </div>
        </div>
    );
}
