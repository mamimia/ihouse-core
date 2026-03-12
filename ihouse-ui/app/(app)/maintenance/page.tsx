'use client';

/**
 * Phase 387 — Maintenance Mobile Surface
 * Route: /maintenance
 *
 * Filtered task view (MAINTENANCE kind only) with
 * claim → in-progress → completed flow and issue notes.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '../../../lib/api';

interface MTask {
    task_id: string;
    title: string;
    kind: string;
    priority: string;
    status: string;
    property_id: string;
    due_date: string;
    due_time?: string;
    description?: string;
    created_at: string;
}

function priorityColor(p: string): string {
    switch (p?.toUpperCase()) {
        case 'CRITICAL': return '#ef4444';
        case 'HIGH': return '#f97316';
        case 'MEDIUM': return '#3b82f6';
        default: return '#6b7280';
    }
}

function isOverdue(t: MTask): boolean {
    if (!t.due_date || t.status === 'completed' || t.status === 'canceled') return false;
    const due = new Date(t.due_time ? `${t.due_date}T${t.due_time}` : `${t.due_date}T23:59:59`);
    return new Date() > due;
}

// ---------------------------------------------------------------------------
// Maintenance Card
// ---------------------------------------------------------------------------

function MaintenanceCard({ task, onAction, loading }: {
    task: MTask;
    onAction: (id: string, action: 'acknowledge' | 'complete', notes?: string) => void;
    loading: boolean;
}) {
    const [expanded, setExpanded] = useState(false);
    const [notes, setNotes] = useState('');
    const overdue = isOverdue(task);
    const isPending = task.status === 'pending';
    const isInProgress = task.status === 'acknowledged' || task.status === 'in_progress';
    const isDone = task.status === 'completed' || task.status === 'canceled';

    return (
        <div style={{
            background: 'var(--color-surface, #1a1f2e)',
            border: `1px solid ${overdue ? 'rgba(239,68,68,0.3)' : 'var(--color-border, #ffffff12)'}`,
            borderRadius: 'var(--radius-lg, 16px)',
            overflow: 'hidden',
            marginBottom: 'var(--space-3, 12px)',
            boxShadow: overdue ? '0 0 12px rgba(239,68,68,0.15)' : 'none',
        }}>
            <div
                onClick={() => setExpanded(!expanded)}
                style={{
                    padding: 'var(--space-4, 16px)',
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 'var(--space-3, 12px)',
                }}
            >
                {/* Priority bar */}
                <div style={{
                    width: 4, height: 40, borderRadius: 99,
                    background: priorityColor(task.priority),
                    flexShrink: 0,
                }} />

                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                        fontSize: 'var(--text-base, 15px)', fontWeight: 700,
                        color: 'var(--color-text, #f9fafb)',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
                        🔧 {task.title}
                    </div>
                    <div style={{
                        fontSize: 'var(--text-xs, 11px)',
                        color: 'var(--color-text-dim, #6b7280)',
                        display: 'flex', gap: 'var(--space-2, 8px)', marginTop: 2,
                    }}>
                        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{task.property_id}</span>
                        {overdue && <span style={{ color: '#ef4444', fontWeight: 700 }}>⚠ OVERDUE</span>}
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
                    <span style={{
                        fontSize: 10, fontWeight: 700, color: '#fff',
                        background: priorityColor(task.priority),
                        borderRadius: 99, padding: '2px 8px',
                    }}>{task.priority}</span>
                    <span style={{
                        fontSize: 10,
                        color: isDone ? '#22c55e' : 'var(--color-text-dim, #9ca3af)',
                    }}>{task.status.replace(/_/g, ' ')}</span>
                </div>

                <span style={{
                    color: 'var(--color-text-faint, #4b5563)', fontSize: 18,
                    transform: expanded ? 'rotate(90deg)' : 'none',
                    transition: 'transform 0.2s', flexShrink: 0,
                }}>›</span>
            </div>

            {expanded && (
                <div style={{
                    padding: '0 var(--space-4, 16px) var(--space-4, 16px)',
                    borderTop: '1px solid var(--color-border, #ffffff08)',
                }}>
                    {task.description && (
                        <div style={{
                            background: 'var(--color-bg, #111827)',
                            borderRadius: 'var(--radius-md, 12px)',
                            padding: 'var(--space-3, 12px)',
                            marginTop: 'var(--space-3, 12px)',
                            marginBottom: 'var(--space-3, 12px)',
                            fontSize: 'var(--text-sm, 14px)',
                            color: 'var(--color-text-dim, #d1d5db)',
                            lineHeight: 1.5,
                            border: '1px solid var(--color-border, #ffffff08)',
                        }}>
                            {task.description}
                        </div>
                    )}

                    {!isDone && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2, 8px)', marginTop: 'var(--space-3, 12px)' }}>
                            {isPending && (
                                <button
                                    id={`maint-claim-${task.task_id}`}
                                    disabled={loading}
                                    onClick={() => onAction(task.task_id, 'acknowledge')}
                                    style={{
                                        padding: 'var(--space-3, 14px)',
                                        borderRadius: 'var(--radius-md, 14px)',
                                        border: 'none',
                                        background: loading ? 'var(--color-surface-3, #1f2937)' : 'linear-gradient(135deg,#3b82f6,#2563eb)',
                                        color: '#fff', fontWeight: 700, fontSize: 15,
                                        cursor: loading ? 'not-allowed' : 'pointer',
                                        boxShadow: '0 0 16px rgba(59,130,246,0.3)',
                                    }}
                                >
                                    {loading ? '…' : '🔧 Claim this job'}
                                </button>
                            )}

                            {isInProgress && (
                                <>
                                    <textarea
                                        id={`maint-notes-${task.task_id}`}
                                        value={notes}
                                        onChange={e => setNotes(e.target.value)}
                                        placeholder="Issue notes, parts used, time spent…"
                                        rows={3}
                                        style={{
                                            width: '100%', background: 'var(--color-bg, #111827)',
                                            border: '1px solid var(--color-border, #374151)',
                                            borderRadius: 'var(--radius-md, 12px)',
                                            color: 'var(--color-text, #f9fafb)',
                                            fontSize: 14, padding: 'var(--space-3, 12px)',
                                            resize: 'none', outline: 'none', boxSizing: 'border-box',
                                        }}
                                    />
                                    <button
                                        id={`maint-complete-${task.task_id}`}
                                        disabled={loading}
                                        onClick={() => onAction(task.task_id, 'complete', notes)}
                                        style={{
                                            padding: 'var(--space-3, 14px)',
                                            borderRadius: 'var(--radius-md, 14px)',
                                            border: 'none',
                                            background: loading ? 'var(--color-surface-3, #1f2937)' : 'linear-gradient(135deg,#22c55e,#16a34a)',
                                            color: '#fff', fontWeight: 700, fontSize: 15,
                                            cursor: loading ? 'not-allowed' : 'pointer',
                                            boxShadow: '0 0 16px rgba(34,197,94,0.3)',
                                        }}
                                    >
                                        {loading ? '…' : '✅ Mark Complete'}
                                    </button>
                                </>
                            )}
                        </div>
                    )}

                    {isDone && (
                        <div style={{
                            background: '#22c55e18', border: '1px solid #22c55e40',
                            borderRadius: 'var(--radius-md, 12px)',
                            padding: 'var(--space-3, 14px)',
                            textAlign: 'center', marginTop: 'var(--space-3, 12px)',
                            fontSize: 'var(--text-sm, 15px)', color: '#22c55e', fontWeight: 600,
                        }}>
                            ✅ {task.status}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type Filter = 'open' | 'done' | 'all';

export default function MaintenancePage() {
    const [tasks, setTasks] = useState<MTask[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [filter, setFilter] = useState<Filter>('open');

    const load = useCallback(async () => {
        try {
            const resp = await api.getTasks({ limit: 100 });
            const all = (resp.tasks ?? []) as MTask[];
            setTasks(all.filter(t => t.kind === 'MAINTENANCE'));
        } catch { /* noop */ } finally { setLoading(false); }
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleAction = async (id: string, action: 'acknowledge' | 'complete', notes?: string) => {
        setActionLoading(true);
        try {
            if (action === 'acknowledge') {
                await api.acknowledgeTask(id);
            } else {
                await api.completeTask(id, notes || undefined);
            }
            await load();
        } catch { /* noop */ } finally { setActionLoading(false); }
    };

    const open = tasks.filter(t => t.status !== 'completed' && t.status !== 'canceled');
    const done = tasks.filter(t => t.status === 'completed' || t.status === 'canceled');
    const visible = filter === 'open' ? open : filter === 'done' ? done : tasks;

    return (
        <>
            <style>{`
                @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
                @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.5} }
            `}</style>

            <div style={{ minHeight: '100vh', paddingBottom: 'var(--space-8, 32px)', animation: 'fadeIn 300ms ease' }}>
                <div style={{
                    padding: 'var(--space-5, 20px) var(--space-4, 16px) var(--space-3, 12px)',
                    position: 'sticky', top: 0, zIndex: 30,
                    background: 'linear-gradient(180deg, var(--color-surface, #111827) 0%, transparent 100%)',
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-2, 8px)' }}>
                        <div>
                            <h1 style={{
                                fontSize: 'var(--text-xl, 22px)', fontWeight: 800,
                                color: 'var(--color-text, #f9fafb)', margin: 0,
                                letterSpacing: '-0.03em',
                            }}>
                                🔧 Maintenance
                            </h1>
                            <p style={{
                                fontSize: 'var(--text-sm, 13px)',
                                color: 'var(--color-text-dim, #6b7280)',
                                margin: '2px 0 0',
                            }}>
                                {loading ? 'Loading…' : `${open.length} open · ${done.length} done`}
                            </p>
                        </div>

                        {/* Filter */}
                        <div style={{
                            display: 'flex', border: '1px solid var(--color-border, #374151)',
                            borderRadius: 'var(--radius-md, 10px)', overflow: 'hidden',
                        }}>
                            {(['open', 'done', 'all'] as Filter[]).map(f => (
                                <button
                                    key={f}
                                    id={`maint-filter-${f}`}
                                    onClick={() => setFilter(f)}
                                    style={{
                                        padding: 'var(--space-2, 6px) var(--space-3, 12px)',
                                        fontSize: 'var(--text-xs, 12px)',
                                        border: 'none',
                                        borderRight: '1px solid var(--color-border, #374151)',
                                        cursor: 'pointer',
                                        background: filter === f ? 'var(--color-primary, #3b82f6)' : 'transparent',
                                        color: filter === f ? '#fff' : 'var(--color-text-dim, #6b7280)',
                                        fontWeight: filter === f ? 700 : 400,
                                        fontFamily: 'var(--font-sans, inherit)',
                                    }}
                                >
                                    {f.charAt(0).toUpperCase() + f.slice(1)}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                {loading && (
                    <div style={{ padding: '0 var(--space-4, 16px)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3, 12px)' }}>
                        {[1, 2, 3].map(i => (
                            <div key={i} style={{ height: 80, background: 'var(--color-surface, #1a1f2e)', borderRadius: 'var(--radius-lg, 16px)', animation: 'pulse 1.5s infinite' }} />
                        ))}
                    </div>
                )}

                {!loading && (
                    <div style={{ padding: '0 var(--space-4, 16px)' }}>
                        {visible.length === 0 && (
                            <div style={{ textAlign: 'center', padding: 'var(--space-8, 60px) 0', color: 'var(--color-text-faint, #4b5563)' }}>
                                <div style={{ fontSize: 48, marginBottom: 'var(--space-3, 12px)' }}>🔧</div>
                                <div style={{ fontSize: 'var(--text-lg, 18px)', fontWeight: 600, color: 'var(--color-text-dim, #6b7280)' }}>
                                    {filter === 'open' ? 'No open maintenance jobs' : filter === 'done' ? 'No completed jobs' : 'No maintenance tasks'}
                                </div>
                            </div>
                        )}

                        {visible.map(t => (
                            <MaintenanceCard key={t.task_id} task={t} onAction={handleAction} loading={actionLoading} />
                        ))}
                    </div>
                )}

                <div style={{
                    textAlign: 'center', fontSize: 'var(--text-xs, 11px)',
                    color: 'var(--color-text-faint, #374151)',
                    padding: 'var(--space-6, 24px)',
                }}>
                    Domaniqo — Maintenance · Phase 387
                </div>
            </div>
        </>
    );
}
