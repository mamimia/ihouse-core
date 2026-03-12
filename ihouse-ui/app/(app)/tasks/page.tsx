'use client';

/**
 * Phase 157 — Worker Task Mobile View
 * Route: /tasks
 *
 * Mobile-first task list for cleaners, check-in staff, maintenance workers.
 * Features:
 *  - Live SLA countdown for CRITICAL tasks (5-min ack window)
 *  - Priority chips with colour coding
 *  - One-tap Acknowledge action
 *  - Overdue indicator
 *  - Tap task card to go to detail view
 */

import { useEffect, useState, useCallback } from 'react';
import { api, WorkerTask } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function priorityColor(priority: string): string {
    switch (priority?.toUpperCase()) {
        case 'CRITICAL': return 'var(--color-danger)';
        case 'HIGH': return 'var(--color-warn)';
        case 'MEDIUM': return 'var(--color-primary)';
        default: return 'var(--color-muted)';
    }
}

function statusColor(status: string): string {
    switch (status?.toLowerCase()) {
        case 'completed': return 'var(--color-ok)';
        case 'in_progress': return 'var(--color-primary)';
        case 'acknowledged': return 'var(--color-accent)';
        default: return 'var(--color-muted)';
    }
}

function kindLabel(kind: string): string {
    const map: Record<string, string> = {
        CLEANING: '🧹 Cleaning',
        CHECKIN_PREP: '🏠 Check-in Prep',
        CHECKOUT_PREP: '📦 Checkout Prep',
        MAINTENANCE: '🔧 Maintenance',
    };
    return map[kind] ?? kind;
}

function formatTime(iso: string | undefined): string {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch { return iso; }
}

function isOverdue(task: WorkerTask): boolean {
    if (!task.due_date) return false;
    const due = new Date(task.due_time ? `${task.due_date}T${task.due_time}` : `${task.due_date}T23:59:59`);
    return new Date() > due && task.status !== 'completed';
}

function SlaCountdown({ task }: { task: WorkerTask }) {
    const [remaining, setRemaining] = useState<number | null>(null);

    useEffect(() => {
        if (task.priority !== 'CRITICAL' || task.status !== 'pending') return;
        const computeRemaining = () => {
            const created = new Date(task.created_at).getTime();
            const deadline = created + (task.ack_sla_minutes ?? 5) * 60_000;
            return Math.max(0, deadline - Date.now());
        };
        setRemaining(computeRemaining());
        const timer = setInterval(() => setRemaining(computeRemaining()), 1000);
        return () => clearInterval(timer);
    }, [task]);

    if (remaining === null) return null;

    const secs = Math.floor(remaining / 1000);
    const mins = Math.floor(secs / 60);
    const s = secs % 60;
    const isHot = remaining < 60_000;
    const expired = remaining === 0;

    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-1)',
            fontSize: 'var(--text-xs)',
            fontFamily: 'var(--font-mono)',
            color: expired ? 'var(--color-muted)' : isHot ? 'var(--color-danger)' : 'var(--color-warn)',
            animation: isHot && !expired ? 'pulse 1s infinite' : 'none',
        }}>
            <span>⏱</span>
            <span>{expired ? 'SLA EXPIRED' : `${mins}:${String(s).padStart(2, '0')} left`}</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Task Card
// ---------------------------------------------------------------------------

interface TaskCardProps {
    task: WorkerTask;
    onAcknowledge: (id: string) => void;
    onOpen: (id: string) => void;
    loading: string | null;
}

function TaskCard({ task, onAcknowledge, onOpen, loading }: TaskCardProps) {
    const overdue = isOverdue(task);
    const isCritical = task.priority === 'CRITICAL';
    const isPending = task.status === 'pending';
    const isLoading = loading === task.task_id;

    return (
        <div
            onClick={() => onOpen(task.task_id)}
            style={{
                background: 'var(--color-surface)',
                border: `1px solid ${overdue ? 'var(--color-danger)' : isCritical ? 'rgba(239,68,68,0.4)' : 'var(--color-border)'}`,
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-4)',
                cursor: 'pointer',
                transition: 'all var(--transition-fast)',
                boxShadow: overdue ? 'var(--shadow-glow-red)' : isCritical ? '0 0 12px rgba(239,68,68,0.15)' : 'var(--shadow-sm)',
                position: 'relative',
                overflow: 'hidden',
            }}
        >
            {/* Priority left strip */}
            <div style={{
                position: 'absolute',
                left: 0,
                top: 0,
                bottom: 0,
                width: '3px',
                background: priorityColor(task.priority),
                borderRadius: 'var(--radius-lg) 0 0 var(--radius-lg)',
            }} />

            <div style={{ marginLeft: 'var(--space-4)' }}>
                {/* Header row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                        {/* Kind label */}
                        <span style={{
                            fontSize: 'var(--text-xs)',
                            color: 'var(--color-text-dim)',
                            fontWeight: 500,
                            letterSpacing: '0.05em',
                            textTransform: 'uppercase',
                        }}>
                            {kindLabel(task.kind)}
                        </span>
                        {/* Title */}
                        <span style={{
                            fontSize: 'var(--text-base)',
                            fontWeight: 600,
                            color: 'var(--color-text)',
                            lineHeight: 1.3,
                        }}>
                            {task.title}
                        </span>
                    </div>

                    {/* Priority + Status chips */}
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 'var(--space-1)', flexShrink: 0 }}>
                        <span style={{
                            fontSize: 'var(--text-xs)',
                            fontWeight: 600,
                            color: priorityColor(task.priority),
                            background: `${priorityColor(task.priority)}18`,
                            borderRadius: 'var(--radius-full)',
                            padding: '2px 8px',
                            border: `1px solid ${priorityColor(task.priority)}40`,
                        }}>
                            {task.priority}
                        </span>
                        <span style={{
                            fontSize: 'var(--text-xs)',
                            color: statusColor(task.status),
                            background: `${statusColor(task.status)}12`,
                            borderRadius: 'var(--radius-full)',
                            padding: '2px 8px',
                        }}>
                            {task.status.replace('_', ' ')}
                        </span>
                    </div>
                </div>

                {/* Property + due time row */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: isCritical || overdue ? 'var(--space-3)' : 0,
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                        <span style={{ fontSize: '0.85em' }}>🏡</span>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>
                            {task.property_id}
                        </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        {overdue && (
                            <span style={{
                                fontSize: 'var(--text-xs)',
                                fontWeight: 700,
                                color: 'var(--color-danger)',
                                animation: 'pulse 1.5s infinite',
                            }}>
                                ⚠ OVERDUE
                            </span>
                        )}
                        <span style={{ fontSize: 'var(--text-sm)', color: overdue ? 'var(--color-danger)' : 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
                            {task.due_time ? formatTime(`${task.due_date}T${task.due_time}`) : task.due_date}
                        </span>
                    </div>
                </div>

                {/* SLA countdown for CRITICAL pending */}
                {isCritical && isPending && (
                    <div style={{ marginBottom: 'var(--space-3)' }}>
                        <SlaCountdown task={task} />
                    </div>
                )}

                {/* Acknowledge action (only for pending tasks) */}
                {isPending && (
                    <button
                        id={`ack-btn-${task.task_id}`}
                        onClick={(e) => { e.stopPropagation(); onAcknowledge(task.task_id); }}
                        disabled={isLoading}
                        style={{
                            width: '100%',
                            padding: 'var(--space-3)',
                            borderRadius: 'var(--radius-md)',
                            border: 'none',
                            background: isCritical
                                ? 'linear-gradient(135deg, var(--color-danger), #dc2626)'
                                : 'linear-gradient(135deg, var(--color-primary), var(--color-primary-dim))',
                            color: '#fff',
                            fontWeight: 600,
                            fontSize: 'var(--text-sm)',
                            cursor: isLoading ? 'not-allowed' : 'pointer',
                            opacity: isLoading ? 0.7 : 1,
                            transition: 'all var(--transition-fast)',
                            boxShadow: isCritical ? 'var(--shadow-glow-red)' : 'var(--shadow-glow-blue)',
                        }}
                    >
                        {isLoading ? '...' : isCritical ? '⚡ Acknowledge Now' : '✓ Acknowledge'}
                    </button>
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function EmptyState() {
    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 'var(--space-16)',
            gap: 'var(--space-4)',
            textAlign: 'center',
        }}>
            <div style={{ fontSize: '3rem' }}>✅</div>
            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text)' }}>
                All clear!
            </div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                No tasks assigned to you right now.
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Status filter tabs
// ---------------------------------------------------------------------------

const FILTERS = [
    { label: 'All', value: '' },
    { label: 'Pending', value: 'pending' },
    { label: 'In Progress', value: 'in_progress' },
    { label: 'Done', value: 'completed' },
];

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function TasksPage() {
    const [tasks, setTasks] = useState<WorkerTask[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [filter, setFilter] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [detailId, setDetailId] = useState<string | null>(null);

    const loadTasks = useCallback(async () => {
        try {
            setError(null);
            const resp = await api.getWorkerTasks({ status: filter || undefined, limit: 50 });
            setTasks(resp.tasks ?? []);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to load tasks');
        } finally {
            setLoading(false);
        }
    }, [filter]);

    // Poll every 30s as fallback
    useEffect(() => {
        setLoading(true);
        loadTasks();
        const interval = setInterval(loadTasks, 30_000);
        return () => clearInterval(interval);
    }, [loadTasks]);

    // SSE for real-time task events (Phase 308)
    useEffect(() => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') ?? '' : '';
        const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
        const es = new EventSource(`${baseUrl}/events/stream?channels=tasks,alerts&token=${token}`);
        es.onmessage = (e) => {
            try {
                const evt = JSON.parse(e.data);
                if (evt.channel === 'tasks' || evt.channel === 'alerts') {
                    setTimeout(loadTasks, 500);
                }
            } catch { /* ignore */ }
        };
        return () => es.close();
    }, [loadTasks]);

    const handleAcknowledge = async (id: string) => {
        setActionLoading(id);
        try {
            await api.acknowledgeTask(id);
            await loadTasks();
        } catch (err: unknown) {
            console.error('Acknowledge failed:', err);
        } finally {
            setActionLoading(null);
        }
    };

    // Sort: CRITICAL first, then by due_time
    const sorted = [...tasks].sort((a, b) => {
        const pMap: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
        const pa = pMap[a.priority] ?? 9;
        const pb = pMap[b.priority] ?? 9;
        if (pa !== pb) return pa - pb;
        return (a.due_time ?? '').localeCompare(b.due_time ?? '');
    });

    const criticalCount = tasks.filter(t => t.priority === 'CRITICAL' && t.status === 'pending').length;
    const overdueCount = tasks.filter(t => isOverdue(t)).length;

    return (
        <>
            <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .task-card-enter {
          animation: slideUp 220ms ease forwards;
        }
        /* Mobile: hide sidebar, full-width */
        @media (max-width: 768px) {
          .tasks-main {
            margin-left: 0 !important;
            padding: var(--space-4) !important;
          }
          .tasks-nav-desktop {
            display: none !important;
          }
        }
      `}</style>

            {/* Mobile-aware outer wrapper */}
            <div className="tasks-main" style={{ maxWidth: 680, margin: '0 auto' }}>

                {/* Header */}
                <div style={{ marginBottom: 'var(--space-6)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                            <h1 style={{
                                fontSize: 'var(--text-2xl)',
                                fontWeight: 700,
                                color: 'var(--color-text)',
                                letterSpacing: '-0.02em',
                                lineHeight: 1.2,
                            }}>
                                My Tasks
                            </h1>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-1)' }}>
                                Today • {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
                            </p>
                        </div>

                        {/* Badges */}
                        <div style={{ display: 'flex', gap: 'var(--space-2)', flexShrink: 0 }}>
                            {criticalCount > 0 && (
                                <div style={{
                                    background: 'var(--color-danger)',
                                    color: '#fff',
                                    borderRadius: 'var(--radius-full)',
                                    padding: '4px 10px',
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 700,
                                    animation: 'pulse 2s infinite',
                                    boxShadow: 'var(--shadow-glow-red)',
                                }}>
                                    {criticalCount} CRITICAL
                                </div>
                            )}
                            {overdueCount > 0 && (
                                <div style={{
                                    background: 'rgba(239,68,68,0.15)',
                                    color: 'var(--color-danger)',
                                    border: '1px solid var(--color-danger)',
                                    borderRadius: 'var(--radius-full)',
                                    padding: '4px 10px',
                                    fontSize: 'var(--text-xs)',
                                    fontWeight: 600,
                                }}>
                                    {overdueCount} overdue
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Filter tabs */}
                <div style={{
                    display: 'flex',
                    gap: 'var(--space-2)',
                    marginBottom: 'var(--space-5)',
                    background: 'var(--color-surface)',
                    borderRadius: 'var(--radius-lg)',
                    padding: 'var(--space-1)',
                    border: '1px solid var(--color-border)',
                }}>
                    {FILTERS.map(f => (
                        <button
                            key={f.value}
                            id={`filter-${f.value || 'all'}`}
                            onClick={() => { setFilter(f.value); setLoading(true); }}
                            style={{
                                flex: 1,
                                padding: 'var(--space-2) var(--space-3)',
                                borderRadius: 'var(--radius-md)',
                                border: 'none',
                                background: filter === f.value ? 'var(--color-primary)' : 'transparent',
                                color: filter === f.value ? '#fff' : 'var(--color-text-dim)',
                                fontWeight: filter === f.value ? 600 : 400,
                                fontSize: 'var(--text-sm)',
                                transition: 'all var(--transition-fast)',
                                cursor: 'pointer',
                            }}
                        >
                            {f.label}
                        </button>
                    ))}
                </div>

                {/* Error state */}
                {error && (
                    <div style={{
                        background: 'rgba(239,68,68,0.1)',
                        border: '1px solid rgba(239,68,68,0.3)',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-4)',
                        marginBottom: 'var(--space-4)',
                        color: 'var(--color-danger)',
                        fontSize: 'var(--text-sm)',
                    }}>
                        ⚠ {error}
                        <button
                            onClick={loadTasks}
                            style={{
                                marginLeft: 'var(--space-3)',
                                background: 'none',
                                border: '1px solid var(--color-danger)',
                                color: 'var(--color-danger)',
                                borderRadius: 'var(--radius-sm)',
                                padding: '2px 8px',
                                fontSize: 'var(--text-xs)',
                                cursor: 'pointer',
                            }}
                        >
                            Retry
                        </button>
                    </div>
                )}

                {/* Loading skeleton */}
                {loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        {[1, 2, 3].map(i => (
                            <div key={i} style={{
                                height: 120,
                                background: 'var(--color-surface)',
                                borderRadius: 'var(--radius-lg)',
                                animation: 'pulse 1.5s infinite',
                                border: '1px solid var(--color-border)',
                            }} />
                        ))}
                    </div>
                )}

                {/* Task list */}
                {!loading && sorted.length === 0 && <EmptyState />}

                {!loading && sorted.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        {sorted.map((task, idx) => (
                            <div key={task.task_id} className="task-card-enter" style={{ animationDelay: `${idx * 40}ms` }}>
                                <TaskCard
                                    task={task}
                                    onAcknowledge={handleAcknowledge}
                                    onOpen={setDetailId}
                                    loading={actionLoading}
                                />
                            </div>
                        ))}
                    </div>
                )}

                {/* Task count footer */}
                {!loading && sorted.length > 0 && (
                    <div style={{
                        textAlign: 'center',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-text-faint)',
                        marginTop: 'var(--space-6)',
                    }}>
                        {sorted.length} task{sorted.length !== 1 ? 's' : ''} · refreshes every 30s
                    </div>
                )}
            </div>
        </>
    );
}
