'use client';

/**
 * Phase 178 — Worker Mobile UI
 * Route: /worker
 *
 * Dedicated mobile-first app for field workers.
 * Distinct from /tasks (manager view).
 *
 * Features:
 *  - Bottom navigation (mobile-native, no sidebar)
 *  - My Tasks tab: role-scoped, priority-sorted
 *  - Active tab: in_progress + acknowledged only
 *  - Done tab: completed (read-only)
 *  - Per-task bottom sheet detail with full info
 *  - Acknowledge → Complete flow with notes
 *  - SLA countdown for CRITICAL pending tasks
 *  - Overdue badge + haptic-style shake animation
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, WorkerTask } from '../../lib/api';

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------

function priorityBg(p: string) {
    switch (p?.toUpperCase()) {
        case 'CRITICAL': return '#ef4444';
        case 'HIGH': return '#f97316';
        case 'MEDIUM': return '#3b82f6';
        default: return '#6b7280';
    }
}

function statusLabel(s: string) {
    const m: Record<string, string> = {
        pending: 'Pending',
        acknowledged: 'Acknowledged',
        in_progress: 'In Progress',
        completed: 'Completed',
        canceled: 'Canceled',
    };
    return m[s] ?? s;
}

function kindEmoji(k: string) {
    const m: Record<string, string> = {
        CLEANING: '🧹',
        CHECKIN_PREP: '🏠',
        CHECKOUT_PREP: '📦',
        MAINTENANCE: '🔧',
        INSPECTION: '🔍',
    };
    return m[k] ?? '📋';
}

function isOverdue(task: WorkerTask): boolean {
    if (!task.due_date || task.status === 'completed' || task.status === 'canceled') return false;
    const due = new Date(task.due_time
        ? `${task.due_date}T${task.due_time}`
        : `${task.due_date}T23:59:59`);
    return new Date() > due;
}

function fmtTime(iso: string) {
    try { return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }); }
    catch { return iso; }
}

function fmtDate(d: string) {
    try {
        return new Date(d).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    } catch { return d; }
}

// ---------------------------------------------------------------------------
// SLA Countdown
// ---------------------------------------------------------------------------

function SlaCountdown({ task }: { task: WorkerTask }) {
    const [ms, setMs] = useState<number | null>(null);

    useEffect(() => {
        if (task.priority !== 'CRITICAL' || task.status !== 'pending') return;
        const calc = () => {
            const deadline = new Date(task.created_at).getTime() + (task.ack_sla_minutes ?? 5) * 60_000;
            return Math.max(0, deadline - Date.now());
        };
        setMs(calc());
        const t = setInterval(() => setMs(calc()), 1000);
        return () => clearInterval(t);
    }, [task]);

    if (ms === null) return null;
    const secs = Math.floor(ms / 1000);
    const mins = Math.floor(secs / 60);
    const s = secs % 60;
    const hot = ms < 60_000;
    const gone = ms === 0;

    return (
        <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            fontSize: 13, fontFamily: 'monospace',
            color: gone ? '#9ca3af' : hot ? '#ef4444' : '#f97316',
            animation: hot && !gone ? 'pulse 1s infinite' : 'none',
            marginTop: 6,
        }}>
            <span>⏱</span>
            <span>{gone ? 'SLA EXPIRED' : `${mins}:${String(s).padStart(2, '0')} to acknowledge`}</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Task Card (list item)
// ---------------------------------------------------------------------------

interface CardProps { task: WorkerTask; onTap: () => void; }

function TaskCard({ task, onTap }: CardProps) {
    const overdue = isOverdue(task);
    const isCrit = task.priority === 'CRITICAL';

    return (
        <div
            id={`worker-task-${task.task_id}`}
            onClick={onTap}
            style={{
                background: '#1a1f2e',
                border: `1px solid ${overdue ? '#ef444480' : isCrit ? '#ef444430' : '#ffffff12'}`,
                borderRadius: 16,
                padding: '16px 16px 16px 20px',
                position: 'relative',
                overflow: 'hidden',
                cursor: 'pointer',
                boxShadow: overdue
                    ? '0 0 18px rgba(239,68,68,0.2)'
                    : isCrit ? '0 0 10px rgba(239,68,68,0.1)' : '0 2px 8px rgba(0,0,0,0.3)',
                transition: 'transform 0.1s ease, box-shadow 0.15s ease',
            }}
            onTouchStart={e => (e.currentTarget.style.transform = 'scale(0.98)')}
            onTouchEnd={e => (e.currentTarget.style.transform = 'scale(1)')}
        >
            {/* Priority left bar */}
            <div style={{
                position: 'absolute', left: 0, top: 0, bottom: 0, width: 4,
                background: priorityBg(task.priority),
                borderRadius: '16px 0 0 16px',
            }} />

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <div>
                    <div style={{ fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>
                        {kindEmoji(task.kind)} {task.kind?.replace('_', ' ')}
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: '#f9fafb', lineHeight: 1.3 }}>
                        {task.title}
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0, marginLeft: 8 }}>
                    <span style={{
                        fontSize: 11, fontWeight: 700,
                        color: '#fff', background: priorityBg(task.priority),
                        borderRadius: 99, padding: '2px 9px',
                    }}>{task.priority}</span>
                    <span style={{
                        fontSize: 11, color: task.status === 'completed' ? '#22c55e' : '#9ca3af',
                        background: task.status === 'completed' ? '#22c55e18' : '#ffffff0a',
                        borderRadius: 99, padding: '2px 9px',
                    }}>{statusLabel(task.status)}</span>
                </div>
            </div>

            {/* Property + time */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13, color: '#9ca3af' }}>
                <span>🏡 <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{task.property_id}</span></span>
                <span style={{ color: overdue ? '#ef4444' : '#9ca3af', fontFamily: 'monospace', fontSize: 12 }}>
                    {overdue && <span style={{ fontWeight: 700, marginRight: 6 }}>⚠ OVERDUE</span>}
                    {task.due_time ? fmtTime(`${task.due_date}T${task.due_time}`) : fmtDate(task.due_date)}
                </span>
            </div>

            {task.priority === 'CRITICAL' && task.status === 'pending' && (
                <SlaCountdown task={task} />
            )}

            {/* Chevron */}
            <div style={{ position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)', color: '#4b5563', fontSize: 18 }}>›</div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Detail Bottom Sheet
// ---------------------------------------------------------------------------

interface SheetProps {
    task: WorkerTask;
    onClose: () => void;
    onAck: (id: string) => Promise<void>;
    onComplete: (id: string, notes: string) => Promise<void>;
    loading: boolean;
}

function DetailSheet({ task, onClose, onAck, onComplete, loading }: SheetProps) {
    const [notes, setNotes] = useState('');
    const [view, setView] = useState<'detail' | 'complete'>('detail');
    const overdue = isOverdue(task);
    const isPending = task.status === 'pending';
    const isAcked = task.status === 'acknowledged' || task.status === 'in_progress';
    const isDone = task.status === 'completed' || task.status === 'canceled';

    return (
        <>
            {/* Backdrop */}
            <div
                onClick={onClose}
                style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
                    zIndex: 100, backdropFilter: 'blur(4px)',
                }}
            />
            {/* Sheet */}
            <div style={{
                position: 'fixed', bottom: 0, left: 0, right: 0,
                background: '#111827',
                borderRadius: '24px 24px 0 0',
                zIndex: 101,
                padding: '0 0 env(safe-area-inset-bottom,24px)',
                maxHeight: '85vh',
                overflowY: 'auto',
                animation: 'slideUp 240ms cubic-bezier(0.32,0.72,0,1)',
            }}>
                {/* Handle */}
                <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 12, paddingBottom: 4 }}>
                    <div style={{ width: 40, height: 4, background: '#374151', borderRadius: 99 }} />
                </div>

                <div style={{ padding: '12px 20px 28px' }}>
                    {/* Priority strip */}
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        marginBottom: 16,
                    }}>
                        <div style={{
                            width: 6, height: 40, background: priorityBg(task.priority),
                            borderRadius: 99, flexShrink: 0,
                        }} />
                        <div>
                            <div style={{ fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                                {kindEmoji(task.kind)} {task.kind?.replace(/_/g, ' ')}
                            </div>
                            <div style={{ fontSize: 20, fontWeight: 700, color: '#f9fafb', lineHeight: 1.2 }}>
                                {task.title}
                            </div>
                        </div>
                    </div>

                    {/* Info grid */}
                    <div style={{
                        display: 'grid', gridTemplateColumns: '1fr 1fr',
                        gap: 10, marginBottom: 20,
                    }}>
                        {[
                            ['Property', task.property_id],
                            ['Due', task.due_time ? fmtTime(`${task.due_date}T${task.due_time}`) : fmtDate(task.due_date)],
                            ['Priority', task.priority],
                            ['Status', statusLabel(task.status)],
                            ['Role', task.worker_role?.replace(/_/g, ' ')],
                            ['Booking', task.booking_id ?? '—'],
                        ].map(([label, value]) => (
                            <div key={label} style={{
                                background: '#1a1f2e', borderRadius: 12,
                                padding: '10px 12px',
                                border: '1px solid #ffffff0d',
                            }}>
                                <div style={{ fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>{label}</div>
                                <div style={{ fontSize: 13, color: '#e5e7eb', fontWeight: 600, fontFamily: label === 'Property' || label === 'Booking' ? 'monospace' : 'inherit', wordBreak: 'break-all' }}>{value}</div>
                            </div>
                        ))}
                    </div>

                    {/* Description */}
                    {task.description && (
                        <div style={{
                            background: '#1a1f2e', borderRadius: 12, padding: '12px 14px',
                            marginBottom: 20, border: '1px solid #ffffff0d',
                        }}>
                            <div style={{ fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Notes</div>
                            <div style={{ fontSize: 14, color: '#d1d5db', lineHeight: 1.5 }}>{task.description}</div>
                        </div>
                    )}

                    {overdue && !isDone && (
                        <div style={{
                            background: '#ef444415', border: '1px solid #ef444440',
                            borderRadius: 12, padding: '10px 14px', marginBottom: 16,
                            fontSize: 13, color: '#ef4444', fontWeight: 600,
                            animation: 'pulse 2s infinite',
                        }}>
                            ⚠ This task is overdue — action required immediately
                        </div>
                    )}

                    {/* CRITICAL SLA */}
                    {task.priority === 'CRITICAL' && task.status === 'pending' && (
                        <div style={{ marginBottom: 16 }}>
                            <SlaCountdown task={task} />
                        </div>
                    )}

                    {/* Actions */}
                    {!isDone && view === 'detail' && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                            {isPending && (
                                <button
                                    id={`sheet-ack-${task.task_id}`}
                                    disabled={loading}
                                    onClick={() => onAck(task.task_id)}
                                    style={{
                                        padding: '16px', borderRadius: 14, border: 'none',
                                        background: task.priority === 'CRITICAL'
                                            ? 'linear-gradient(135deg,#ef4444,#dc2626)'
                                            : 'linear-gradient(135deg,#3b82f6,#2563eb)',
                                        color: '#fff', fontWeight: 700, fontSize: 16,
                                        cursor: loading ? 'not-allowed' : 'pointer',
                                        opacity: loading ? 0.6 : 1,
                                        boxShadow: task.priority === 'CRITICAL'
                                            ? '0 0 20px rgba(239,68,68,0.35)'
                                            : '0 0 16px rgba(59,130,246,0.3)',
                                    }}
                                >
                                    {loading ? 'Processing…' : task.priority === 'CRITICAL' ? '⚡ Acknowledge Now' : '✓ Acknowledge'}
                                </button>
                            )}

                            {isAcked && (
                                <button
                                    id={`sheet-complete-${task.task_id}`}
                                    disabled={loading}
                                    onClick={() => setView('complete')}
                                    style={{
                                        padding: '16px', borderRadius: 14, border: 'none',
                                        background: 'linear-gradient(135deg,#22c55e,#16a34a)',
                                        color: '#fff', fontWeight: 700, fontSize: 16,
                                        cursor: 'pointer',
                                        boxShadow: '0 0 16px rgba(34,197,94,0.3)',
                                    }}
                                >
                                    ✅ Mark as Complete
                                </button>
                            )}
                        </div>
                    )}

                    {/* Complete form */}
                    {view === 'complete' && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            <div style={{ fontSize: 15, fontWeight: 600, color: '#f9fafb', marginBottom: 4 }}>
                                Add completion notes (optional)
                            </div>
                            <textarea
                                id={`notes-${task.task_id}`}
                                value={notes}
                                onChange={e => setNotes(e.target.value)}
                                placeholder="E.g. All rooms cleaned, keys returned, gate locked…"
                                rows={4}
                                style={{
                                    width: '100%', background: '#1a1f2e',
                                    border: '1px solid #374151', borderRadius: 12,
                                    color: '#f9fafb', fontSize: 14, padding: '12px',
                                    resize: 'none', outline: 'none',
                                    boxSizing: 'border-box',
                                }}
                            />
                            <button
                                id={`confirm-complete-${task.task_id}`}
                                disabled={loading}
                                onClick={() => onComplete(task.task_id, notes)}
                                style={{
                                    padding: '16px', borderRadius: 14, border: 'none',
                                    background: 'linear-gradient(135deg,#22c55e,#16a34a)',
                                    color: '#fff', fontWeight: 700, fontSize: 16,
                                    cursor: loading ? 'not-allowed' : 'pointer',
                                    opacity: loading ? 0.6 : 1,
                                    boxShadow: '0 0 16px rgba(34,197,94,0.3)',
                                }}
                            >
                                {loading ? 'Saving…' : '✅ Confirm Complete'}
                            </button>
                            <button
                                onClick={() => setView('detail')}
                                style={{
                                    padding: '12px', borderRadius: 12, border: '1px solid #374151',
                                    background: 'transparent', color: '#9ca3af', fontSize: 14, cursor: 'pointer',
                                }}
                            >
                                Cancel
                            </button>
                        </div>
                    )}

                    {isDone && (
                        <div style={{
                            background: '#22c55e18', border: '1px solid #22c55e40',
                            borderRadius: 12, padding: '14px', textAlign: 'center',
                            fontSize: 15, color: '#22c55e', fontWeight: 600,
                        }}>
                            ✅ Task {task.status}
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Bottom Nav
// ---------------------------------------------------------------------------

type Tab = 'todo' | 'active' | 'done';

function BottomNav({ tab, setTab, counts }: { tab: Tab; setTab: (t: Tab) => void; counts: Record<Tab, number> }) {
    const tabs: { id: Tab; label: string; icon: string }[] = [
        { id: 'todo', label: 'To Do', icon: '📋' },
        { id: 'active', label: 'Active', icon: '🔄' },
        { id: 'done', label: 'Done', icon: '✅' },
    ];

    return (
        <nav style={{
            position: 'fixed', bottom: 0, left: 0, right: 0,
            background: '#111827',
            borderTop: '1px solid #1f2937',
            display: 'flex',
            padding: '8px 0 env(safe-area-inset-bottom,8px)',
            zIndex: 50,
        }}>
            {tabs.map(t => (
                <button
                    key={t.id}
                    id={`tab-${t.id}`}
                    onClick={() => setTab(t.id)}
                    style={{
                        flex: 1, display: 'flex', flexDirection: 'column',
                        alignItems: 'center', gap: 3,
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: tab === t.id ? '#3b82f6' : '#6b7280',
                        transition: 'color 0.15s',
                        position: 'relative',
                        padding: '6px 0',
                    }}
                >
                    <span style={{ fontSize: 22 }}>{t.icon}</span>
                    <span style={{ fontSize: 11, fontWeight: tab === t.id ? 700 : 400 }}>{t.label}</span>
                    {counts[t.id] > 0 && (
                        <span style={{
                            position: 'absolute', top: 2, right: '50%', transform: 'translate(18px, 0)',
                            background: t.id === 'todo' ? '#ef4444' : '#3b82f6',
                            color: '#fff', borderRadius: 99,
                            fontSize: 10, fontWeight: 700,
                            padding: '1px 5px', minWidth: 16, textAlign: 'center',
                        }}>
                            {counts[t.id]}
                        </span>
                    )}
                </button>
            ))}
        </nav>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function WorkerPage() {
    const [tasks, setTasks] = useState<WorkerTask[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [selected, setSelected] = useState<WorkerTask | null>(null);
    const [tab, setTab] = useState<Tab>('todo');
    const [error, setError] = useState<string | null>(null);
    const [toast, setToast] = useState<string | null>(null);

    const showToast = (msg: string) => {
        setToast(msg);
        setTimeout(() => setToast(null), 2500);
    };

    const load = useCallback(async () => {
        try {
            setError(null);
            const resp = await api.getWorkerTasks({ limit: 100 });
            setTasks(resp.tasks ?? []);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        setLoading(true);
        load();

        // Phase 181 — SSE live refresh
        // EventSource cannot set Authorization header in browsers,
        // so we pass the token as a query param.
        const token = typeof window !== 'undefined'
            ? localStorage.getItem('ihouse_token') ?? ''
            : '';

        const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
        let es: EventSource | null = null;
        let fallbackIv: ReturnType<typeof setInterval> | null = null;
        let sseAlive = false;

        if (typeof EventSource !== 'undefined') {
            es = new EventSource(`${API_BASE}/events/stream?token=${encodeURIComponent(token)}`);

            es.onopen = () => {
                sseAlive = true;
                // Once SSE is live, cancel any fallback polling
                if (fallbackIv) { clearInterval(fallbackIv); fallbackIv = null; }
            };

            es.onmessage = (e) => {
                try {
                    const evt = JSON.parse(e.data ?? '{}');
                    // Reload on any task mutation event
                    if (evt.type === 'task_update' || evt.type === 'task_created') {
                        load();
                    }
                } catch { /* ignore malformed event */ }
            };

            es.onerror = () => {
                sseAlive = false;
                // SSE dropped — start fallback polling at 60s
                if (!fallbackIv) {
                    fallbackIv = setInterval(load, 60_000);
                }
            };
        } else {
            // No EventSource support — fall back to 60s polling
            fallbackIv = setInterval(load, 60_000);
        }

        return () => {
            es?.close();
            if (fallbackIv) clearInterval(fallbackIv);
        };
    }, [load]);

    const handleAck = async (id: string) => {
        setActionLoading(true);
        try {
            await api.acknowledgeTask(id);
            showToast('✓ Task acknowledged');
            setSelected(null);
            await load();
        } catch {
            showToast('⚠ Acknowledge failed');
        } finally {
            setActionLoading(false);
        }
    };

    const handleComplete = async (id: string, notes: string) => {
        setActionLoading(true);
        try {
            await api.completeTask(id, notes || undefined);
            showToast('✅ Task completed!');
            setSelected(null);
            await load();
        } catch {
            showToast('⚠ Complete failed');
        } finally {
            setActionLoading(false);
        }
    };

    // Tab filters
    const todo = tasks
        .filter(t => t.status === 'pending')
        .sort((a, b) => {
            const pm: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
            return (pm[a.priority] ?? 9) - (pm[b.priority] ?? 9);
        });

    const active = tasks
        .filter(t => t.status === 'acknowledged' || t.status === 'in_progress')
        .sort((a, b) => (a.due_time ?? '').localeCompare(b.due_time ?? ''));

    const done = tasks
        .filter(t => t.status === 'completed' || t.status === 'canceled')
        .slice(0, 30);

    const visible = tab === 'todo' ? todo : tab === 'active' ? active : done;

    const criticalCount = todo.filter(t => t.priority === 'CRITICAL').length;
    const overdueCount = tasks.filter(t => isOverdue(t) && t.status !== 'completed').length;

    return (
        <>
            <style>{`
        @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.5 } }
        @keyframes slideUp { from { opacity:0; transform:translateY(24px) } to { opacity:1; transform:translateY(0) } }
        @keyframes fadeIn { from { opacity:0 } to { opacity:1 } }
        @keyframes toastIn { from { opacity:0; transform:translateX(-50%) translateY(12px) } to { opacity:1; transform:translateX(-50%) translateY(0) } }
        * { box-sizing:border-box }
        body { background:#0d1117 !important; }
        /* Override desktop sidebar for this route */
        nav[style*="sidebar"] { display:none !important }
        main { margin-left:0 !important; padding:0 !important; max-width:100% !important; }
      `}</style>

            <div style={{
                background: '#0d1117', minHeight: '100vh',
                color: '#f9fafb', fontFamily: "'Inter', -apple-system, sans-serif",
                paddingBottom: 80,
            }}>
                {/* Header */}
                <div style={{
                    padding: '20px 20px 12px',
                    background: 'linear-gradient(180deg, #111827 0%, transparent 100%)',
                    position: 'sticky', top: 0, zIndex: 30,
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <h1 style={{ fontSize: 24, fontWeight: 800, color: '#f9fafb', margin: 0, letterSpacing: '-0.03em' }}>
                                My Tasks
                            </h1>
                            <p style={{ fontSize: 13, color: '#6b7280', margin: '2px 0 0' }}>
                                {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
                            </p>
                        </div>
                        <div style={{ display: 'flex', gap: 8 }}>
                            {criticalCount > 0 && (
                                <div style={{
                                    background: '#ef4444', color: '#fff',
                                    borderRadius: 99, padding: '4px 10px',
                                    fontSize: 12, fontWeight: 700,
                                    animation: 'pulse 1.5s infinite',
                                    boxShadow: '0 0 16px rgba(239,68,68,0.4)',
                                }}>
                                    {criticalCount} CRITICAL
                                </div>
                            )}
                            {overdueCount > 0 && (
                                <div style={{
                                    background: '#ef444420', color: '#ef4444',
                                    border: '1px solid #ef444460',
                                    borderRadius: 99, padding: '4px 10px',
                                    fontSize: 12, fontWeight: 600,
                                }}>
                                    {overdueCount} overdue
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div style={{
                        margin: '0 20px 16px',
                        background: '#ef444415', border: '1px solid #ef444430',
                        borderRadius: 12, padding: '12px 14px',
                        fontSize: 14, color: '#ef4444',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    }}>
                        <span>⚠ {error}</span>
                        <button onClick={load} style={{
                            background: 'none', border: '1px solid #ef4444', color: '#ef4444',
                            borderRadius: 8, padding: '4px 10px', fontSize: 12, cursor: 'pointer',
                        }}>Retry</button>
                    </div>
                )}

                {/* Loading skeletons */}
                {loading && (
                    <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                        {[1, 2, 3].map(i => (
                            <div key={i} style={{
                                height: 100, background: '#1a1f2e', borderRadius: 16,
                                animation: 'pulse 1.5s infinite',
                            }} />
                        ))}
                    </div>
                )}

                {/* Task list */}
                {!loading && (
                    <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                        {visible.length === 0 && (
                            <div style={{
                                textAlign: 'center', padding: '60px 20px',
                                color: '#4b5563',
                            }}>
                                <div style={{ fontSize: 48, marginBottom: 12 }}>
                                    {tab === 'done' ? '✅' : '🎉'}
                                </div>
                                <div style={{ fontSize: 18, fontWeight: 600, color: '#6b7280' }}>
                                    {tab === 'done' ? 'No completed tasks yet' : 'All clear!'}
                                </div>
                                <div style={{ fontSize: 14, marginTop: 6 }}>
                                    {tab === 'todo' ? 'No pending tasks assigned to you.' : tab === 'active' ? 'No tasks in progress.' : ''}
                                </div>
                            </div>
                        )}
                        {visible.map(task => (
                            <div key={task.task_id} style={{ animation: 'fadeIn 200ms ease' }}>
                                <TaskCard task={task} onTap={() => setSelected(task)} />
                            </div>
                        ))}
                        {visible.length > 0 && (
                            <div style={{ textAlign: 'center', fontSize: 12, color: '#374151', padding: '12px 0' }}>
                                {visible.length} task{visible.length !== 1 ? 's' : ''} · live updates
                            </div>
                        )}
                    </div>
                )}

                {/* Detail Sheet */}
                {selected && (
                    <DetailSheet
                        task={selected}
                        onClose={() => setSelected(null)}
                        onAck={handleAck}
                        onComplete={handleComplete}
                        loading={actionLoading}
                    />
                )}

                {/* Toast */}
                {toast && (
                    <div style={{
                        position: 'fixed', bottom: 88, left: '50%',
                        transform: 'translateX(-50%)',
                        background: '#1f2937', color: '#f9fafb',
                        borderRadius: 99, padding: '10px 20px',
                        fontSize: 14, fontWeight: 600,
                        boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
                        zIndex: 200,
                        animation: 'toastIn 200ms ease',
                        whiteSpace: 'nowrap',
                        border: '1px solid #374151',
                    }}>
                        {toast}
                    </div>
                )}

                {/* Bottom Nav */}
                <BottomNav
                    tab={tab}
                    setTab={setTab}
                    counts={{ todo: todo.length, active: active.length, done: done.length }}
                />
            </div>
        </>
    );
}
