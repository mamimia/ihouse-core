'use client';

/**
 * Phase 1033 Step 3 — /manager/stream
 * Phase 1034 (OM-1) — Task event expand → ManagerTaskDrawer intervention layer.
 *
 * Full-width live event stream. Full-screen version of the Hub's LiveStream
 * widget, with richer filtering and no size constraints.
 *
 * Data: /admin/audit (existing endpoint, proven in Hub).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import DraftGuard from '@/components/DraftGuard';
import { api, AuditEvent, apiFetch } from '@/lib/api';
import { ManagerTaskDrawer, type ManagerTaskCardTask } from '@/components/ManagerTaskCard';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ACTION_CONFIG: Record<string, { color: string; bg: string; icon: string }> = {
    TASK_COMPLETED:         { color: '#22c55e', bg: 'rgba(34,197,94,0.12)',   icon: '✓' },
    TASK_ACKNOWLEDGED:      { color: '#3b82f6', bg: 'rgba(59,130,246,0.12)',  icon: '👁' },
    TASK_IN_PROGRESS:       { color: '#6366f1', bg: 'rgba(99,102,241,0.12)',  icon: '▶' },
    TASK_ESCALATED:         { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',   icon: '↑' },
    MANAGER_TAKEOVER:       { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',  icon: '⚡' },
    BOOKING_FLAGS_UPDATED:  { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', icon: '⚑' },
    BOOKING_CREATED:        { color: '#22c55e', bg: 'rgba(34,197,94,0.12)',   icon: '+' },
    BOOKING_CANCELLED:      { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',   icon: '×' },
    ACT_AS_STARTED:         { color: '#a855f7', bg: 'rgba(168,85,247,0.12)', icon: '🔴' },
    PREVIEW_OPENED:         { color: '#6366f1', bg: 'rgba(99,102,241,0.12)', icon: '👁' },
};

const DEFAULT_CONFIG = { color: '#6b7280', bg: 'rgba(107,114,128,0.08)', icon: '·' };

function getActionConfig(action: string) {
    return ACTION_CONFIG[action] || DEFAULT_CONFIG;
}

function formatAction(action: string): string {
    return action.replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase());
}

function timeAgo(iso: string): string {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return `${Math.round(diff)}s ago`;
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    return new Date(iso).toLocaleDateString();
}

// ---------------------------------------------------------------------------
// Filter types
// ---------------------------------------------------------------------------

type StreamFilter = 'all' | 'tasks' | 'bookings' | 'sessions';

function matchesFilter(ev: AuditEvent, filter: StreamFilter): boolean {
    if (filter === 'all') return true;
    if (filter === 'tasks') return ev.entity_type === 'task' || ev.action.startsWith('TASK_') || ev.action === 'MANAGER_TAKEOVER';
    if (filter === 'bookings') return ev.entity_type === 'booking' || ev.action.startsWith('BOOKING_');
    if (filter === 'sessions') return ev.action.startsWith('ACT_AS') || ev.action.startsWith('PREVIEW_');
    return true;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function StreamPage() {
    const [events, setEvents] = useState<AuditEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState('');
    const [filter, setFilter] = useState<StreamFilter>('all');
    const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
    const [newIds, setNewIds] = useState<Set<number>>(new Set());
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const prevIdsRef = useRef<Set<number>>(new Set());

    // Phase 1034: task event expand → ManagerTaskDrawer
    const [drawerTask, setDrawerTask] = useState<ManagerTaskCardTask | null>(null);
    const [loadingTask, setLoadingTask] = useState(false);

    const openTaskDrawer = useCallback(async (entityId: string) => {
        setLoadingTask(true);
        try {
            // Phase 1034: use GET /tasks/{id} — full task with timing + notes
            const res = await apiFetch<{ task: ManagerTaskCardTask }>(`/tasks/detail/${entityId}`);
            setDrawerTask(res.task);
        } catch {
            // Fallback — open with minimal shell so manager can still see the panel
            setDrawerTask({ id: entityId, task_kind: 'GENERAL', status: 'UNKNOWN', priority: 'NORMAL', property_id: '' });
        } finally {
            setLoadingTask(false);
        }
    }, []);

    const load = useCallback(async (isAuto = false) => {
        if (!isAuto) setLoading(true);
        setErr('');
        try {
            const res = await api.getManagerAuditEvents({ limit: 100 });
            const incoming = res.events || [];
            if (isAuto) {
                const fresh = new Set(incoming.filter(e => !prevIdsRef.current.has(e.id)).map(e => e.id));
                setNewIds(fresh);
                setTimeout(() => setNewIds(new Set()), 3000);
            }
            prevIdsRef.current = new Set(incoming.map(e => e.id));
            setEvents(incoming);
            setLastRefresh(new Date());
        } catch (e: any) {
            setErr((e as any)?.message || 'Failed to load stream');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
        timerRef.current = setInterval(() => load(true), 20_000);
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [load]);

    const filtered = events.filter(e => matchesFilter(e, filter));

    const tabBtn = (active: boolean): React.CSSProperties => ({
        padding: '6px 16px',
        borderRadius: 'var(--radius-full)',
        border: active ? '1px solid var(--color-primary)' : '1px solid var(--color-border)',
        background: active ? 'var(--color-primary)15' : 'transparent',
        color: active ? 'var(--color-primary)' : 'var(--color-text-dim)',
        fontWeight: active ? 700 : 500,
        fontSize: 12,
        cursor: 'pointer',
        transition: 'all 120ms ease',
    });

    return (
        <DraftGuard>
            <div style={{ maxWidth: 960 }}>
                {/* Header */}
                <div style={{ marginBottom: 24 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
                        <div>
                            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.1em', marginBottom: 4 }}>
                                OPERATIONAL MANAGER
                            </div>
                            <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--color-text)', letterSpacing: '-0.04em', marginBottom: 4 }}>
                                Live Stream
                            </h1>
                            <div style={{ fontSize: 13, color: 'var(--color-text-dim)' }}>
                                Real-time operational events · Tasks · Bookings · Sessions
                            </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>
                                {filtered.length} events
                            </span>
                            <button onClick={() => load()} style={{ background: 'transparent', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '7px 14px', fontSize: 12, fontWeight: 600, color: 'var(--color-text-dim)', cursor: 'pointer' }}>
                                ↻ Refresh
                            </button>
                        </div>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginTop: 8 }}>
                        Last updated {lastRefresh.toLocaleTimeString()} · Auto-refreshes every 20s
                    </div>
                </div>

                {/* Filter tabs */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
                    <button style={tabBtn(filter === 'all')} onClick={() => setFilter('all')}>All</button>
                    <button style={tabBtn(filter === 'tasks')} onClick={() => setFilter('tasks')}>Tasks</button>
                    <button style={tabBtn(filter === 'bookings')} onClick={() => setFilter('bookings')}>Bookings</button>
                    <button style={tabBtn(filter === 'sessions')} onClick={() => setFilter('sessions')}>Sessions</button>
                </div>

                {/* Stream */}
                {loading && <div style={{ color: 'var(--color-text-faint)', padding: '24px 0', textAlign: 'center', fontSize: 13 }}>Loading stream…</div>}
                {!loading && err && (
                    <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-lg)', padding: '16px 20px', color: '#ef4444', fontSize: 13 }}>⚠ {err}</div>
                )}
                {!loading && !err && filtered.length === 0 && (
                    <div style={{ color: 'var(--color-text-faint)', padding: '32px 0', textAlign: 'center', fontSize: 13 }}>No events in this filter</div>
                )}

                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xl)', overflow: 'hidden' }}>
                    {/* Column header */}
                    {filtered.length > 0 && (
                        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr 2fr 1fr', gap: 12, padding: '10px 20px', borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg)' }}>
                            {['ACTION', 'ENTITY', 'ACTOR', 'WHEN'].map(h => (
                                <div key={h} style={{ fontSize: 9, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.1em' }}>{h}</div>
                            ))}
                        </div>
                    )}

                    {filtered.map((ev, idx) => {
                        const cfg = getActionConfig(ev.action);
                        const isNew = newIds.has(ev.id);
                        const isTaskEvent = ev.entity_type === 'task';
                        return (
                            <div
                                key={ev.id}
                                onClick={isTaskEvent ? () => openTaskDrawer(ev.entity_id) : undefined}
                                title={isTaskEvent ? 'Click to open intervention panel' : undefined}
                                style={{
                                    display: 'grid',
                                    gridTemplateColumns: '2fr 1.2fr 2fr 1fr',
                                    gap: 12,
                                    padding: '12px 20px',
                                    borderBottom: idx < filtered.length - 1 ? '1px solid var(--color-border)' : 'none',
                                    background: isNew ? `${cfg.color}08` : 'transparent',
                                    transition: 'background 180ms ease',
                                    alignItems: 'center',
                                    cursor: isTaskEvent ? 'pointer' : 'default',
                                }}
                                onMouseEnter={e => { if (isTaskEvent) (e.currentTarget as HTMLElement).style.background = 'var(--color-surface-2)'; }}
                                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = isNew ? `${cfg.color}08` : 'transparent'; }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                                    <span style={{ fontSize: 11, fontWeight: 700, color: cfg.color, background: cfg.bg, width: 22, height: 22, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                        {cfg.icon}
                                    </span>
                                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                        {formatAction(ev.action)}
                                    </span>
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--color-text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    <span style={{ color: 'var(--color-text-faint)', marginInlineEnd: 4 }}>{ev.entity_type}</span>
                                    {ev.entity_id.slice(0, 10)}…
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--color-text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {ev.actor_id.slice(0, 18)}…
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--color-text-faint)', whiteSpace: 'nowrap' }}>
                                    {timeAgo(ev.occurred_at)}
                                </div>
                            </div>
                            );
                    })}
                </div>
            </div>

            {/* Phase 1034: ManagerTaskDrawer — intervention panel from stream */}
            {drawerTask && (
                <ManagerTaskDrawer
                    task={drawerTask}
                    onClose={() => setDrawerTask(null)}
                    onMutated={() => { setDrawerTask(null); load(); }}
                />
            )}
            {loadingTask && (
                <div style={{
                    position: 'fixed', bottom: 24, right: 24,
                    background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                    borderRadius: 8, padding: '10px 16px', fontSize: 12, color: 'var(--color-text-dim)',
                    zIndex: 400, boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                }}>Loading task…</div>
            )}
        </DraftGuard>
    );
}
