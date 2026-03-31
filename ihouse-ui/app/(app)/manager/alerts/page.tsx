'use client';

/**
 * Phase 1033 Step 3 — /manager/alerts
 *
 * Operational alerts surface. Pulls from audit stream, filters to
 * alert-class actions, groups by severity and status.
 *
 * No new backend endpoint needed — reuses /admin/audit already proven in Hub.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import DraftGuard from '@/components/DraftGuard';
import { api } from '@/lib/api';

// ---------------------------------------------------------------------------
// Alert classification
// ---------------------------------------------------------------------------

const ALERT_ACTIONS = new Set([
    'BOOKING_FLAGS_UPDATED',
    'TASK_ESCALATED',
    'SLA_BREACHED',
    'ALERT_RAISED',
    'TASK_OVERDUE',
    'MANAGER_TAKEOVER',
]);

type AlertSeverity = 'critical' | 'warning' | 'info';

type AlertItem = {
    id: number;
    action: string;
    entity_type: string;
    entity_id: string;
    occurred_at: string;
    payload: Record<string, unknown>;
    severity: AlertSeverity;
};

function classifySeverity(action: string, payload: Record<string, unknown>): AlertSeverity {
    if (action === 'SLA_BREACHED' || action === 'TASK_ESCALATED') return 'critical';
    if (action === 'BOOKING_FLAGS_UPDATED') {
        const flags = (payload.flags as string[] | undefined) || [];
        if (flags.includes('DND') || flags.includes('URGENT')) return 'warning';
        return 'info';
    }
    if (action === 'TASK_OVERDUE') return 'warning';
    return 'info';
}

function actionLabel(action: string): string {
    const MAP: Record<string, string> = {
        BOOKING_FLAGS_UPDATED: 'Booking Flag',
        TASK_ESCALATED: 'Task Escalated',
        SLA_BREACHED: 'SLA Breached',
        ALERT_RAISED: 'Alert',
        TASK_OVERDUE: 'Task Overdue',
        MANAGER_TAKEOVER: 'Manager Takeover',
    };
    return MAP[action] || action;
}

const SEVERITY_CONFIG: Record<AlertSeverity, { color: string; bg: string; icon: string; label: string }> = {
    critical: { color: '#ef4444', bg: 'rgba(239,68,68,0.10)',  icon: '🔴', label: 'Critical' },
    warning:  { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)', icon: '⚠️', label: 'Warning'  },
    info:     { color: '#6366f1', bg: 'rgba(99,102,241,0.10)', icon: 'ℹ️', label: 'Info'     },
};

function timeAgo(iso: string): string {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return `${Math.round(diff)}s ago`;
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    return `${Math.round(diff / 86400)}d ago`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type Filter = 'all' | 'critical' | 'warning' | 'info';

export default function AlertsPage() {
    const [allEvents, setAllEvents] = useState<AlertItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState('');
    const [filter, setFilter] = useState<Filter>('all');
    const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const load = useCallback(async () => {
        setLoading(true); setErr('');
        try {
            const res = await api.getManagerAuditEvents({ limit: 100 });
            const alerts: AlertItem[] = (res.events || [])
                .filter(e => ALERT_ACTIONS.has(e.action))
                .map(e => ({
                    ...e,
                    severity: classifySeverity(e.action, e.payload),
                }));
            setAllEvents(alerts);
            setLastRefresh(new Date());
        } catch (e: any) {
            setErr((e as any)?.message || 'Failed to load alerts');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
        timerRef.current = setInterval(load, 30_000);
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [load]);

    const filtered = filter === 'all' ? allEvents : allEvents.filter(a => a.severity === filter);
    const criticalCount = allEvents.filter(a => a.severity === 'critical').length;
    const warningCount  = allEvents.filter(a => a.severity === 'warning').length;

    const filterBtn = (active: boolean, color = 'var(--color-primary)'): React.CSSProperties => ({
        padding: '6px 14px',
        borderRadius: 'var(--radius-full)',
        border: active ? `1px solid ${color}` : '1px solid var(--color-border)',
        background: active ? `${color}15` : 'transparent',
        color: active ? color : 'var(--color-text-dim)',
        fontWeight: active ? 700 : 500,
        fontSize: 12,
        cursor: 'pointer',
        transition: 'all 120ms ease',
    });

    const alertCardStyle = (sev: AlertSeverity): React.CSSProperties => ({
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderLeft: `3px solid ${SEVERITY_CONFIG[sev].color}`,
        borderRadius: 'var(--radius-lg)',
        padding: '14px 18px',
        marginBottom: 10,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 14,
    });

    return (
        <DraftGuard>
            <div style={{ maxWidth: 900 }}>
                {/* Header */}
                <div style={{ marginBottom: 24 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
                        <div>
                            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.1em', marginBottom: 4 }}>
                                OPERATIONAL MANAGER
                            </div>
                            <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--color-text)', letterSpacing: '-0.04em', marginBottom: 4 }}>
                                Alerts
                            </h1>
                            <div style={{ fontSize: 13, color: 'var(--color-text-dim)' }}>
                                Escalations · Flags · SLA breaches · Takeovers
                            </div>
                        </div>
                        <button onClick={load} style={{ background: 'transparent', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '7px 14px', fontSize: 12, fontWeight: 600, color: 'var(--color-text-dim)', cursor: 'pointer' }}>
                            ↻ Refresh
                        </button>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginTop: 8 }}>
                        Last updated {lastRefresh.toLocaleTimeString()} · Auto-refreshes every 30s
                    </div>
                </div>

                {/* Stats */}
                <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
                    {[
                        { count: criticalCount, color: '#ef4444', bg: 'rgba(239,68,68,0.08)', icon: '🔴', label: 'CRITICAL' },
                        { count: warningCount,  color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', icon: '⚠️', label: 'WARNINGS' },
                        { count: allEvents.length, color: '#6366f1', bg: 'rgba(99,102,241,0.08)', icon: '📋', label: 'TOTAL' },
                    ].map(s => (
                        <div key={s.label} style={{ background: s.bg, border: `1px solid ${s.color}30`, borderRadius: 'var(--radius-lg)', padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 10, minWidth: 140 }}>
                            <span style={{ fontSize: 20 }}>{s.icon}</span>
                            <div>
                                <div style={{ fontSize: 22, fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.count}</div>
                                <div style={{ fontSize: 10, fontWeight: 700, color: s.color, opacity: 0.8, letterSpacing: '0.06em' }}>{s.label}</div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Filters */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
                    <button style={filterBtn(filter === 'all')} onClick={() => setFilter('all')}>All alerts</button>
                    <button style={filterBtn(filter === 'critical', '#ef4444')} onClick={() => setFilter('critical')}>Critical</button>
                    <button style={filterBtn(filter === 'warning', '#f59e0b')} onClick={() => setFilter('warning')}>Warning</button>
                    <button style={filterBtn(filter === 'info', '#6366f1')} onClick={() => setFilter('info')}>Info</button>
                </div>

                {/* List */}
                {loading && <div style={{ color: 'var(--color-text-faint)', padding: '24px 0', textAlign: 'center', fontSize: 13 }}>Loading alerts…</div>}
                {!loading && err && (
                    <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-lg)', padding: '16px 20px', color: '#ef4444', fontSize: 13 }}>⚠ {err}</div>
                )}
                {!loading && !err && filtered.length === 0 && (
                    <div style={{ background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.15)', borderRadius: 'var(--radius-xl)', padding: '40px', textAlign: 'center' }}>
                        <div style={{ fontSize: 28, marginBottom: 8 }}>✓</div>
                        <div style={{ fontWeight: 700, color: '#22c55e', fontSize: 15 }}>No active alerts</div>
                        <div style={{ fontSize: 12, color: 'var(--color-text-faint)', marginTop: 4 }}>Operations are running normally</div>
                    </div>
                )}
                {!loading && filtered.map(alert => {
                    const cfg = SEVERITY_CONFIG[alert.severity];
                    return (
                        <div key={alert.id} style={alertCardStyle(alert.severity)}>
                            <span style={{ fontSize: 18, marginTop: 1, flexShrink: 0 }}>{cfg.icon}</span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                                    <span style={{ fontSize: 11, fontWeight: 700, color: cfg.color, background: cfg.bg, padding: '2px 8px', borderRadius: 'var(--radius-full)', letterSpacing: '0.05em' }}>
                                        {actionLabel(alert.action)}
                                    </span>
                                    <span style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>
                                        {alert.entity_type} · {alert.entity_id.slice(0, 12)}…
                                    </span>
                                    <span style={{ fontSize: 11, color: 'var(--color-text-faint)', marginInlineStart: 'auto' }}>
                                        {timeAgo(alert.occurred_at)}
                                    </span>
                                </div>
                                {alert.payload && Object.keys(alert.payload).length > 0 && (
                                    <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>
                                        {Object.entries(alert.payload).slice(0, 2).map(([k, v]) => (
                                            <span key={k} style={{ marginInlineEnd: 12 }}>
                                                <span style={{ color: 'var(--color-text-faint)' }}>{k}:</span>{' '}
                                                {String(typeof v === 'object' ? JSON.stringify(v) : v).slice(0, 60)}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </DraftGuard>
    );
}
