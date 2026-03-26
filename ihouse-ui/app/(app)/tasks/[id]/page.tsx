'use client';

/**
 * Phase 157 — Worker Task Detail View
 * Route: /tasks/[id]
 *
 * Full task detail with:
 *  - Task metadata (kind, status, priority, property, booking)
 *  - SLA countdown for CRITICAL pending
 *  - Single-tap action flow: Acknowledge → Start → Complete
 *  - Notes textarea on completion
 *  - Back navigation to task list
 */

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api, WorkerTask, WorkerTaskListResponse } from '../../../../lib/api';

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

function statusLabel(status: string): string {
    const map: Record<string, string> = {
        pending: 'Pending',
        acknowledged: 'Acknowledged',
        in_progress: 'In Progress',
        completed: 'Completed',
    };
    return map[status] ?? status;
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

function SlaCountdown({ task }: { task: WorkerTask }) {
    const [remaining, setRemaining] = useState<number>(0);

    useEffect(() => {
        if (task.priority !== 'CRITICAL' || task.status !== 'pending') return;
        const compute = () => {
            const created = new Date(task.created_at).getTime();
            const deadline = created + (task.ack_sla_minutes ?? 5) * 60_000;
            return Math.max(0, deadline - Date.now());
        };
        setRemaining(compute());
        const t = setInterval(() => setRemaining(compute()), 1000);
        return () => clearInterval(t);
    }, [task]);

    if (task.priority !== 'CRITICAL' || task.status !== 'pending') return null;

    const secs = Math.floor(remaining / 1000);
    const mins = Math.floor(secs / 60);
    const s = secs % 60;
    const isHot = remaining < 60_000;
    const expired = remaining === 0;

    return (
        <div style={{
            background: expired ? 'rgba(107,114,128,0.15)' : isHot ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.12)',
            border: `1px solid ${expired ? 'var(--color-muted)' : isHot ? 'var(--color-danger)' : 'var(--color-warn)'}`,
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-3) var(--space-4)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-3)',
        }}>
            <span style={{ fontSize: '1.5rem' }}>{expired ? '🔴' : isHot ? '🔥' : '⏱'}</span>
            <div>
                <div style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-dim)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                }}>
                    Critical SLA — Acknowledge Required
                </div>
                <div style={{
                    fontSize: 'var(--text-xl)',
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                    color: expired ? 'var(--color-muted)' : isHot ? 'var(--color-danger)' : 'var(--color-warn)',
                    animation: isHot && !expired ? 'pulse 1s infinite' : 'none',
                }}>
                    {expired ? 'SLA EXPIRED' : `${mins}:${String(s).padStart(2, '0')}`}
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Field row
// ---------------------------------------------------------------------------

function Field({ label, value, mono }: { label: string; value: string | undefined; mono?: boolean }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
            <span style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                color: 'var(--color-text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
            }}>
                {label}
            </span>
            <span style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text)',
                fontFamily: mono ? 'var(--font-mono)' : 'inherit',
            }}>
                {value ?? '—'}
            </span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Action button
// ---------------------------------------------------------------------------

interface ActionButtonProps {
    label: string;
    onClick: () => void;
    disabled?: boolean;
    danger?: boolean;
    id: string;
}

function ActionButton({ label, onClick, disabled, danger, id }: ActionButtonProps) {
    return (
        <button
            id={id}
            onClick={onClick}
            disabled={disabled}
            style={{
                width: '100%',
                padding: 'var(--space-4)',
                borderRadius: 'var(--radius-lg)',
                border: 'none',
                background: danger
                    ? 'linear-gradient(135deg, var(--color-danger), #dc2626)'
                    : 'linear-gradient(135deg, var(--color-primary), var(--color-primary-dim))',
                color: '#fff',
                fontWeight: 700,
                fontSize: 'var(--text-base)',
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.6 : 1,
                transition: 'all var(--transition-fast)',
                boxShadow: danger ? 'var(--shadow-glow-red)' : 'var(--shadow-glow-blue)',
            }}
        >
            {label}
        </button>
    );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function Skeleton() {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {[100, 60, 80, 120].map((h, i) => (
                <div key={i} style={{
                    height: h,
                    background: 'var(--color-surface)',
                    borderRadius: 'var(--radius-lg)',
                    animation: 'pulse 1.5s infinite',
                    border: '1px solid var(--color-border)',
                }} />
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function TaskDetailPage() {
    const params = useParams();
    const router = useRouter();
    const id = params?.id as string;

    const [task, setTask] = useState<WorkerTask | null>(null);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [notes, setNotes] = useState('');
    const [showNotes, setShowNotes] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [ackMsg, setAckMsg] = useState('');

    useEffect(() => {
        if (!id) return;
        api.getWorkerTasks({ limit: 200 })
            .then((resp: WorkerTaskListResponse) => {
                const found = resp.tasks.find((t: WorkerTask) => t.task_id === id);
                setTask(found ?? null);
            })
            .catch((err: unknown) => setError((err instanceof Error ? err.message : null) ?? 'Failed to load task'))
            .finally(() => setLoading(false));
    }, [id]);

    const doAction = async (action: 'acknowledge' | 'start' | 'complete') => {
        if (!task) return;
        setActionLoading(true);
        setError(null);
        try {
            let updated: WorkerTask;
            if (action === 'acknowledge') updated = await api.acknowledgeTask(id);
            else if (action === 'start') updated = await api.startTask(id);
            else updated = await api.completeTask(id, notes);
            setTask(updated);
            setSuccess(`Task ${action === 'acknowledge' ? 'acknowledged' : action === 'start' ? 'started' : 'completed'}!`);
            setTimeout(() => setSuccess(null), 3000);
            if (action === 'complete') {
                setTimeout(() => router.push('/tasks'), 1500);
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : `Failed to ${action} task`);
        } finally {
            setActionLoading(false);
        }
    };

    return (
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
            <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        textarea:focus { outline: none; }
        @media (max-width: 768px) {
          .tasks-main { margin-left: 0 !important; }
        }
      `}</style>

            {/* Back nav */}
            <button
                id="back-to-tasks"
                onClick={() => router.push('/tasks')}
                style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--color-primary)',
                    fontSize: 'var(--text-sm)',
                    cursor: 'pointer',
                    padding: 'var(--space-2) 0',
                    marginBottom: 'var(--space-5)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                }}
            >
                ← Back to tasks
            </button>

            {loading && <Skeleton />}

            {!loading && !task && (
                <div style={{
                    textAlign: 'center',
                    padding: 'var(--space-16)',
                    color: 'var(--color-text-dim)',
                }}>
                    <div style={{ fontSize: '2rem', marginBottom: 'var(--space-4)' }}>🔍</div>
                    Task not found.
                </div>
            )}

            {task && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', animation: 'slideUp 220ms ease' }}>

                    {/* Title block */}
                    <div style={{
                        background: 'var(--color-surface)',
                        borderRadius: 'var(--radius-xl)',
                        padding: 'var(--space-6)',
                        border: `1px solid ${task.priority === 'CRITICAL' ? 'rgba(239,68,68,0.4)' : 'var(--color-border)'}`,
                        position: 'relative',
                        overflow: 'hidden',
                    }}>
                        {/* Priority bar */}
                        <div style={{
                            position: 'absolute',
                            top: 0, left: 0, right: 0,
                            height: 3,
                            background: `linear-gradient(90deg, ${priorityColor(task.priority)}, transparent)`,
                        }} />

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-3)' }}>
                            <span style={{
                                fontSize: 'var(--text-xs)',
                                color: 'var(--color-text-dim)',
                                fontWeight: 600,
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em',
                            }}>
                                {kindLabel(task.kind)}
                            </span>
                            <span style={{
                                fontSize: 'var(--text-xs)',
                                fontWeight: 700,
                                color: priorityColor(task.priority),
                                background: `${priorityColor(task.priority)}18`,
                                borderRadius: 'var(--radius-full)',
                                padding: '3px 10px',
                                border: `1px solid ${priorityColor(task.priority)}40`,
                            }}>
                                {task.priority}
                            </span>
                        </div>

                        <h1 style={{
                            fontSize: 'var(--text-xl)',
                            fontWeight: 700,
                            color: 'var(--color-text)',
                            lineHeight: 1.3,
                            marginBottom: 'var(--space-3)',
                            letterSpacing: '-0.02em',
                        }}>
                            {task.title}
                        </h1>

                        {task.description && (
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', lineHeight: 1.6 }}>
                                {task.description}
                            </p>
                        )}
                    </div>

                    {/* SLA countdown */}
                    <SlaCountdown task={task} />

                    {/* Metadata grid */}
                    <div style={{
                        background: 'var(--color-surface)',
                        borderRadius: 'var(--radius-lg)',
                        padding: 'var(--space-5)',
                        border: '1px solid var(--color-border)',
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))',
                        gap: 'var(--space-4)',
                    }}>
                        <Field label="Status" value={statusLabel(task.status)} />
                        <Field label="Due Date" value={task.due_date} />
                        <Field label="Property" value={task.property_id} mono />
                        <Field label="Booking" value={task.booking_id} mono />
                        <Field label="Assigned Role" value={task.worker_role} />
                        {task.due_time && <Field label="Due Time" value={task.due_time} />}
                    </div>

                    {/* Success toast */}
                    {success && (
                        <div style={{
                            background: 'rgba(16,185,129,0.12)',
                            border: '1px solid rgba(16,185,129,0.35)',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-3) var(--space-4)',
                            color: 'var(--color-ok)',
                            fontSize: 'var(--text-sm)',
                            fontWeight: 500,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-2)',
                        }}>
                            ✓ {success}
                        </div>
                    )}

                    {/* Error */}
                    {error && (
                        <div style={{
                            background: 'rgba(239,68,68,0.1)',
                            border: '1px solid rgba(239,68,68,0.3)',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-3) var(--space-4)',
                            color: 'var(--color-danger)',
                            fontSize: 'var(--text-sm)',
                        }}>
                            ⚠ {error}
                        </div>
                    )}

                    {/* Action area */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        {task.status === 'pending' && (
                            <ActionButton
                                id="action-acknowledge"
                                label={ackMsg || (task.priority === 'CRITICAL' ? '⚡ Acknowledge Now' : '✓ Acknowledge Task')}
                                onClick={() => {
                                    if (ackMsg) return;
                                    const date = task.due_date;
                                    const time = task.due_time || '12:00';
                                    const parsedDate = date && date !== 'Unknown' ? date : new Date().toISOString().split('T')[0];
                                    const target = new Date(`${parsedDate}T${time.length === 5 ? time + ':00' : time}`).getTime();
                                    
                                    if (!isNaN(target)) {
                                        const diff = target - Date.now();
                                        const twentyFourHours = 24 * 60 * 60 * 1000;
                                        if (diff > twentyFourHours) {
                                            const h = Math.floor(diff / 3600000);
                                            const m = Math.floor((diff % 3600000) / 60000);
                                            const days = Math.floor(h / 24);
                                            const remainingH = h % 24;
                                            
                                            let timeStr = days > 0 ? `${days}d ${remainingH}h` : `${h}h ${m}m`;
                                            setAckMsg(`Available in ${timeStr}`);
                                            setTimeout(() => setAckMsg(''), 5000);
                                            return;
                                        }
                                    }
                                    doAction('acknowledge');
                                }}
                                disabled={actionLoading || !!ackMsg}
                                danger={task.priority === 'CRITICAL' && !ackMsg}
                            />
                        )}

                        {task.status === 'acknowledged' && (
                            <ActionButton
                                id="action-start"
                                label="▶ Start Task"
                                onClick={() => doAction('start')}
                                disabled={actionLoading}
                            />
                        )}

                        {task.status === 'in_progress' && (
                            <>
                                {!showNotes ? (
                                    <ActionButton
                                        id="action-complete"
                                        label="✓ Mark as Complete"
                                        onClick={() => setShowNotes(true)}
                                        disabled={actionLoading}
                                    />
                                ) : (
                                    <div style={{
                                        background: 'var(--color-surface)',
                                        borderRadius: 'var(--radius-lg)',
                                        padding: 'var(--space-5)',
                                        border: '1px solid var(--color-border)',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        gap: 'var(--space-3)',
                                    }}>
                                        <label style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)' }}>
                                            Completion Notes (optional)
                                        </label>
                                        <textarea
                                            id="completion-notes"
                                            value={notes}
                                            onChange={e => setNotes(e.target.value)}
                                            placeholder="e.g., completed all items, replaced towels"
                                            rows={3}
                                            style={{
                                                width: '100%',
                                                background: 'var(--color-bg)',
                                                border: '1px solid var(--color-border)',
                                                borderRadius: 'var(--radius-md)',
                                                color: 'var(--color-text)',
                                                padding: 'var(--space-3)',
                                                fontSize: 'var(--text-sm)',
                                                fontFamily: 'var(--font-sans)',
                                                resize: 'vertical',
                                                lineHeight: 1.6,
                                            }}
                                        />
                                        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
                                            <button
                                                onClick={() => setShowNotes(false)}
                                                style={{
                                                    flex: 1,
                                                    padding: 'var(--space-3)',
                                                    borderRadius: 'var(--radius-md)',
                                                    border: '1px solid var(--color-border)',
                                                    background: 'transparent',
                                                    color: 'var(--color-text-dim)',
                                                    cursor: 'pointer',
                                                    fontSize: 'var(--text-sm)',
                                                }}
                                            >
                                                Cancel
                                            </button>
                                            <ActionButton
                                                id="action-confirm-complete"
                                                label={actionLoading ? 'Completing...' : '✓ Confirm Complete'}
                                                onClick={() => doAction('complete')}
                                                disabled={actionLoading}
                                            />
                                        </div>
                                    </div>
                                )}
                            </>
                        )}

                        {task.status === 'completed' && (
                            <div style={{
                                background: 'rgba(16,185,129,0.08)',
                                border: '1px solid rgba(16,185,129,0.25)',
                                borderRadius: 'var(--radius-lg)',
                                padding: 'var(--space-5)',
                                textAlign: 'center',
                                color: 'var(--color-ok)',
                            }}>
                                <div style={{ fontSize: '2rem', marginBottom: 'var(--space-2)' }}>✅</div>
                                <div style={{ fontWeight: 600 }}>Task Completed</div>
                                {task.notes && (
                                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                                        {task.notes}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Task ID footer */}
                    <div style={{
                        textAlign: 'center',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-text-faint)',
                        fontFamily: 'var(--font-mono)',
                        marginTop: 'var(--space-2)',
                    }}>
                        {task.task_id}
                    </div>
                </div>
            )}
        </div>
    );
}
