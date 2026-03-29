'use client';

/**
 * Phase 190 — Manager Activity Feed
 * Route: /manager
 *
 * Real-time audit trail of all operator/worker mutations.
 * Reads from GET /admin/audit (Phase 189 audit_events table).
 *
 * Sections:
 *   - Live Activity Feed — all recent mutations, filterable by entity type
 *   - Quick Stats — mutation counts by action type
 *   - Booking Lookup — enter a booking_id to see its full audit trail
 */

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api, AuditEvent, MorningBriefingResponse, CopilotActionItem, apiFetch } from '@/lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtTime(iso: string): string {
    try {
        const d = new Date(iso);
        const now = new Date();
        const diffMs = now.getTime() - d.getTime();
        const diffMin = Math.floor(diffMs / 60000);
        if (diffMin < 1) return 'just now';
        if (diffMin < 60) return `${diffMin}m ago`;
        const diffH = Math.floor(diffMin / 60);
        if (diffH < 24) return `${diffH}h ago`;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
        return iso;
    }
}

function fmtFull(iso: string): string {
    try {
        return new Date(iso).toLocaleString('en-US', {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
        });
    } catch { return iso; }
}

// ---------------------------------------------------------------------------
// Action badge
// ---------------------------------------------------------------------------

const ACTION_STYLES: Record<string, { bg: string; color: string; icon: string }> = {
    TASK_ACKNOWLEDGED:          { bg: 'rgba(59,130,246,0.12)',  color: '#60a5fa', icon: '👁' },
    TASK_COMPLETED:             { bg: 'rgba(16,185,129,0.12)',  color: '#34d399', icon: '✓' },
    BOOKING_FLAGS_UPDATED:      { bg: 'rgba(245,158,11,0.12)',  color: '#fbbf24', icon: '⚑' },
    MANAGER_TAKEOVER_INITIATED: { bg: 'rgba(239,68,68,0.12)',   color: '#f87171', icon: '⚡' },
    MANAGER_TASK_COMPLETED:     { bg: 'rgba(16,185,129,0.12)',  color: '#34d399', icon: '✓' },
    MANAGER_TASK_REASSIGNED:    { bg: 'rgba(168,85,247,0.12)', color: '#c084fc', icon: '↩' },
};

function ActionBadge({ action }: { action: string }) {
    const s = ACTION_STYLES[action] ?? { bg: 'rgba(100,100,100,0.12)', color: 'var(--color-text-dim)', icon: '·' };
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            fontSize: 'var(--text-xs)', fontWeight: 700,
            padding: '2px 8px', borderRadius: 'var(--radius-full)',
            background: s.bg, color: s.color,
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.04em',
            whiteSpace: 'nowrap',
        }}>
            <span style={{ fontSize: 10 }}>{s.icon}</span>
            {action.replace(/_/g, ' ')}
        </span>
    );
}

function EntityChip({ type, id }: { type: string; id: string }) {
    const isTask = type === 'task';
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            fontSize: 'var(--text-xs)',
            color: isTask ? 'var(--color-primary)' : 'var(--color-accent)',
        }}>
            <span style={{ opacity: 0.6 }}>{isTask ? '⚙' : '📋'} {type}</span>
            <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.8 }}>
                {id.length > 16 ? id.slice(0, 16) + '…' : id}
            </span>
        </span>
    );
}

// ---------------------------------------------------------------------------
// Payload viewer
// ---------------------------------------------------------------------------

function PayloadBlock({ payload }: { payload: Record<string, unknown> }) {
    const keys = Object.keys(payload).filter(k => payload[k] !== null && payload[k] !== undefined);
    if (keys.length === 0) return <span style={{ color: 'var(--color-text-faint)', fontSize: 'var(--text-xs)' }}>—</span>;
    return (
        <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)' }}>
            {keys.map(k => (
                <span key={k} style={{ marginRight: 10 }}>
                    <span style={{ color: 'var(--color-text-faint)' }}>{k}:</span>
                    {' '}
                    <span style={{ color: 'var(--color-text)' }}>{String(payload[k])}</span>
                </span>
            ))}
        </span>
    );
}

// ---------------------------------------------------------------------------
// Stat metric
// ---------------------------------------------------------------------------

function MetricChip({ label, value, color }: { label: string; value: number; color: string }) {
    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-4) var(--space-5)',
            display: 'flex', flexDirection: 'column', gap: 'var(--space-1)',
            minWidth: 120,
        }}>
            <span style={{
                fontSize: 'var(--text-2xl)', fontWeight: 700,
                color, fontVariantNumeric: 'tabular-nums',
                lineHeight: 1.1,
            }}>{value}</span>
            <span style={{
                fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)',
                textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>{label}</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Audit row
// ---------------------------------------------------------------------------

function AuditRow({ ev, isNew }: { ev: AuditEvent; isNew: boolean }) {
    const [open, setOpen] = useState(false);
    return (
        <div
            onClick={() => setOpen(o => !o)}
            style={{
                borderBottom: '1px solid var(--color-border)',
                cursor: 'pointer',
                transition: 'background var(--transition-fast)',
                background: isNew ? 'rgba(99,102,241,0.04)' : 'transparent',
                borderLeft: isNew ? '2px solid var(--color-primary)' : '2px solid transparent',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
            onMouseLeave={e => (e.currentTarget.style.background = isNew ? 'rgba(99,102,241,0.04)' : 'transparent')}
        >
            {/* Main row */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: '160px 1fr 180px 80px',
                gap: 'var(--space-4)',
                padding: 'var(--space-3) var(--space-5)',
                alignItems: 'center',
            }}>
                <ActionBadge action={ev.action} />
                <EntityChip type={ev.entity_type} id={ev.entity_id} />
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
                    {ev.actor_id.length > 20 ? ev.actor_id.slice(0, 20) + '…' : ev.actor_id}
                </span>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textAlign: 'right' }}
                    title={fmtFull(ev.occurred_at)}>
                    {fmtTime(ev.occurred_at)}
                </span>
            </div>

            {/* Expanded payload */}
            {open && (
                <div style={{
                    padding: 'var(--space-2) var(--space-5) var(--space-3)',
                    background: 'var(--color-surface-2)',
                    borderTop: '1px solid var(--color-border)',
                }}>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-1)' }}>
                        Payload · {fmtFull(ev.occurred_at)}
                    </div>
                    <PayloadBlock payload={ev.payload} />
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Booking audit lookup panel
// ---------------------------------------------------------------------------

function BookingAuditLookup() {
    const [bookingId, setBookingId] = useState('');
    const [events, setEvents] = useState<AuditEvent[] | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const lookup = async () => {
        if (!bookingId.trim()) return;
        setLoading(true); setError(null); setEvents(null);
        try {
            const res = await api.getAuditEvents({ entity_type: 'booking', entity_id: bookingId.trim(), limit: 50 });
            setEvents(res.events);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to load');
        } finally {
            setLoading(false);
        }
    };

    const inputStyle: React.CSSProperties = {
        background: 'var(--color-bg)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        color: 'var(--color-text)',
        padding: 'var(--space-2) var(--space-3)',
        fontSize: 'var(--text-sm)',
        fontFamily: 'var(--font-mono)',
        outline: 'none',
        flex: 1,
    };

    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-6)',
        }}>
            <h2 style={{
                fontSize: 'var(--text-sm)', fontWeight: 600,
                color: 'var(--color-text-dim)', textTransform: 'uppercase',
                letterSpacing: '0.08em', marginBottom: 'var(--space-4)',
            }}>Booking Audit Lookup</h2>

            <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                <input
                    id="audit-lookup-booking-id"
                    placeholder="Enter booking_id…"
                    value={bookingId}
                    onChange={e => setBookingId(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && lookup()}
                    style={inputStyle}
                />
                <button
                    id="audit-lookup-submit"
                    onClick={lookup}
                    disabled={loading || !bookingId.trim()}
                    style={{
                        background: 'var(--color-primary)',
                        color: '#fff', border: 'none',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-2) var(--space-5)',
                        fontSize: 'var(--text-sm)', fontWeight: 600,
                        opacity: loading || !bookingId.trim() ? 0.6 : 1,
                        cursor: loading || !bookingId.trim() ? 'not-allowed' : 'pointer',
                        transition: 'opacity var(--transition-fast)',
                    }}
                >
                    {loading ? '…' : 'Look up'}
                </button>
            </div>

            {error && (
                <div style={{ color: 'var(--color-danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-3)' }}>
                    ⚠ {error}
                </div>
            )}

            {events !== null && (
                events.length === 0
                    ? <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>No audit events found for this booking.</p>
                    : (
                        <div style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                            {/* Header */}
                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: '160px 1fr 180px 80px',
                                gap: 'var(--space-4)',
                                padding: 'var(--space-2) var(--space-5)',
                                background: 'var(--color-surface-2)',
                                borderBottom: '1px solid var(--color-border)',
                            }}>
                                {['Action', 'Entity', 'Actor', 'When'].map(h => (
                                    <span key={h} style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</span>
                                ))}
                            </div>
                            {events.map(ev => <AuditRow key={ev.id} ev={ev} isNew={false} />)}
                        </div>
                    )
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Phase 1022-E: Takeover Modal
// ---------------------------------------------------------------------------

const TAKEOVER_REASONS = [
    { value: 'worker_unavailable', label: 'Worker unavailable' },
    { value: 'worker_sick',        label: 'Worker sick / unable to attend' },
    { value: 'emergency',          label: 'Emergency situation' },
    { value: 'other',              label: 'Other' },
];

interface ManagerTask {
    id: string;
    task_kind: string;
    status: string;
    priority: string;
    property_id: string;
    booking_id?: string;
    assigned_to?: string;
    original_worker_id?: string;
    taken_over_by?: string;
    taken_over_reason?: string;
    taken_over_at?: string;
    due_date: string;
    title: string;
    created_at: string;
}

function TakeoverModal({
    task,
    onClose,
    onSuccess,
}: {
    task: ManagerTask;
    onClose: () => void;
    onSuccess: (taskId: string) => void;
}) {
    const router = useRouter();
    const [reason, setReason] = useState('');
    const [notes, setNotes]   = useState('');
    const [busy, setBusy]     = useState(false);
    const [err, setErr]       = useState('');

    const handleTakeover = async () => {
        if (!reason) { setErr('Please select a reason.'); return; }
        setBusy(true); setErr('');
        try {
            await apiFetch(`/tasks/${task.id}/take-over`, {
                method: 'POST',
                body: JSON.stringify({ reason, notes: notes.trim() || undefined }),
            });
            onSuccess(task.id);
            onClose();
            // Phase 1022-F: route manager into the real worker execution flow
            router.push('/worker');
        } catch (e: any) {
            setErr(e?.message || 'Takeover failed. Please try again.');
        } finally {
            setBusy(false);
        }
    };

    const iStyle: React.CSSProperties = {
        width: '100%', boxSizing: 'border-box',
        background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-sm)', color: 'var(--color-text)',
        fontSize: 'var(--text-sm)', padding: '8px 12px',
    };
    const lStyle: React.CSSProperties = {
        fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)',
        fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
        marginBottom: 4, display: 'block',
    };

    return (
        <div
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)', zIndex: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            onClick={onClose}
        >
            <div
                onClick={e => e.stopPropagation()}
                style={{
                    background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-xl)', padding: 'var(--space-6)',
                    width: '100%', maxWidth: 480, boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
                }}
            >
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-5)' }}>
                    <div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 4 }}>
                            ⚡ Take Over Task
                        </div>
                        <div style={{
                            display: 'inline-flex', alignItems: 'center', gap: 6,
                            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
                            borderRadius: 'var(--radius-sm)', padding: '3px 10px',
                            fontSize: 'var(--text-xs)', color: '#f87171', fontWeight: 600,
                        }}>
                            {task.task_kind} · {task.property_id}
                        </div>
                    </div>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: 'var(--color-text-dim)' }}>✕</button>
                </div>

                {/* Task info */}
                <div style={{
                    background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)',
                    fontSize: 'var(--text-sm)', marginBottom: 'var(--space-5)',
                    display: 'flex', flexDirection: 'column', gap: 4,
                }}>
                    <div style={{ fontWeight: 600, color: 'var(--color-text)' }}>{task.title || task.task_kind}</div>
                    <div style={{ color: 'var(--color-text-dim)', fontSize: 12 }}>
                        Status: <strong style={{ color: 'var(--color-warn)' }}>{task.status}</strong>
                        {task.assigned_to && <span style={{ marginLeft: 12 }}>Currently: <strong>{task.assigned_to.slice(0, 12)}…</strong></span>}
                        {task.due_date && <span style={{ marginLeft: 12 }}>Due: <strong>{task.due_date}</strong></span>}
                    </div>
                </div>

                <div style={{ fontSize: 11, color: 'var(--color-text-faint)', marginBottom: 'var(--space-5)', lineHeight: 1.5 }}>
                    You are taking over this task as the active executor.
                    The original worker will be notified. You will be routed to the full task execution flow.
                </div>

                {/* Reason */}
                <div style={{ marginBottom: 'var(--space-4)' }}>
                    <label style={lStyle}>Reason <span style={{ color: 'var(--color-danger)' }}>*</span></label>
                    <select
                        value={reason}
                        onChange={e => setReason(e.target.value)}
                        style={iStyle}
                    >
                        <option value="">— Select reason —</option>
                        {TAKEOVER_REASONS.map(r => (
                            <option key={r.value} value={r.value}>{r.label}</option>
                        ))}
                    </select>
                </div>

                {/* Notes */}
                <div style={{ marginBottom: 'var(--space-5)' }}>
                    <label style={lStyle}>Notes (optional)</label>
                    <textarea
                        value={notes}
                        onChange={e => setNotes(e.target.value)}
                        placeholder="Additional context about why you are taking over…"
                        rows={3}
                        style={{ ...iStyle, resize: 'vertical', fontFamily: 'inherit' }}
                    />
                </div>

                {err && (
                    <div style={{ color: 'var(--color-danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)' }}>⚠ {err}</div>
                )}

                <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end' }}>
                    <button
                        onClick={onClose}
                        disabled={busy}
                        style={{
                            background: 'transparent', border: '1px solid var(--color-border)',
                            color: 'var(--color-text-dim)', borderRadius: 'var(--radius-md)',
                            padding: '8px 18px', fontSize: 'var(--text-sm)', cursor: 'pointer',
                        }}
                    >Cancel</button>
                    <button
                        id="confirm-takeover-btn"
                        onClick={handleTakeover}
                        disabled={busy || !reason}
                        style={{
                            background: busy || !reason ? 'var(--color-surface-3)' : 'linear-gradient(135deg,#ef4444,#dc2626)',
                            color: '#fff', border: 'none',
                            borderRadius: 'var(--radius-md)',
                            padding: '8px 20px', fontSize: 'var(--text-sm)', fontWeight: 700,
                            cursor: busy || !reason ? 'not-allowed' : 'pointer',
                            opacity: busy || !reason ? 0.6 : 1,
                            transition: 'all 0.15s',
                            boxShadow: '0 2px 12px rgba(239,68,68,0.35)',
                        }}
                    >
                        {busy ? 'Taking over…' : '⚡ Confirm Takeover'}
                    </button>
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Phase 1022-E: Manager Task Board
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
    PENDING:           { label: 'Pending',           color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' },
    ACKNOWLEDGED:      { label: 'Acknowledged',      color: '#60a5fa', bg: 'rgba(59,130,246,0.1)' },
    IN_PROGRESS:       { label: 'In Progress',       color: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
    MANAGER_EXECUTING: { label: 'Manager Executing', color: '#f87171', bg: 'rgba(239,68,68,0.1)' },
};

const PRIORITY_DOT: Record<string, string> = {
    CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#f59e0b', LOW: '#94a3b8',
};

function TaskRow({
    task,
    onTakeover,
}: {
    task: ManagerTask;
    onTakeover: (t: ManagerTask) => void;
}) {
    const sc = STATUS_CONFIG[task.status] ?? STATUS_CONFIG['PENDING'];
    const isTakenOver = task.status === 'MANAGER_EXECUTING';
    const canTakeover = ['PENDING', 'ACKNOWLEDGED', 'IN_PROGRESS'].includes(task.status);
    const dot = PRIORITY_DOT[task.priority] ?? '#94a3b8';

    return (
        <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 140px 110px 90px',
            gap: 'var(--space-4)',
            padding: 'var(--space-3) var(--space-4)',
            alignItems: 'center',
            borderBottom: '1px solid var(--color-border)',
            background: isTakenOver ? 'rgba(239,68,68,0.03)' : 'transparent',
            transition: 'background 0.15s',
        }}>
            {/* Title + property */}
            <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: dot, flexShrink: 0 }} />
                    <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {task.title || task.task_kind}
                    </span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-dim)', paddingLeft: 15 }}>
                    {task.property_id}
                    {task.due_date && <span style={{ marginLeft: 8, color: 'var(--color-text-faint)' }}>Due {task.due_date}</span>}
                    {isTakenOver && task.original_worker_id && (
                        <span style={{ marginLeft: 8, color: '#f87171' }}>↩ was: {task.original_worker_id.slice(0, 10)}…</span>
                    )}
                </div>
            </div>

            {/* Kind */}
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
                {task.task_kind}
            </div>

            {/* Status badge */}
            <div>
                <span style={{
                    display: 'inline-block',
                    background: sc.bg, color: sc.color,
                    fontSize: 10, fontWeight: 700,
                    padding: '2px 8px', borderRadius: 'var(--radius-full)',
                    letterSpacing: '0.04em', whiteSpace: 'nowrap',
                }}>
                    {sc.label}
                </span>
            </div>

            {/* Action */}
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                {canTakeover ? (
                    <button
                        id={`takeover-btn-${task.id}`}
                        onClick={() => onTakeover(task)}
                        title="Take over this task"
                        style={{
                            background: 'linear-gradient(135deg,#ef4444,#dc2626)',
                            color: '#fff', border: 'none',
                            borderRadius: 'var(--radius-sm)',
                            padding: '5px 12px', fontSize: 11, fontWeight: 700,
                            cursor: 'pointer',
                            boxShadow: '0 1px 6px rgba(239,68,68,0.3)',
                            transition: 'all 0.15s',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        ⚡ Take Over
                    </button>
                ) : isTakenOver ? (
                    <span style={{ fontSize: 10, color: '#f87171', fontWeight: 600 }}>You're executing</span>
                ) : null}
            </div>
        </div>
    );
}

function TaskBoard() {
    const [groups, setGroups] = useState<Record<string, ManagerTask[]> | null>(null);
    const [total, setTotal]   = useState(0);
    const [loading, setLoading] = useState(true);
    const [err, setErr]       = useState('');
    const [takeoverTask, setTakeoverTask] = useState<ManagerTask | null>(null);

    const load = useCallback(async () => {
        setLoading(true); setErr('');
        try {
            const res = await apiFetch<{ groups: Record<string, ManagerTask[]>; total: number }>('/manager/tasks');
            setGroups(res.groups);
            setTotal(res.total);
        } catch (e: any) {
            setErr(e?.message || 'Failed to load task board.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleTakeoverSuccess = () => { load(); };

    const allTasks: ManagerTask[] = groups
        ? [
            ...(groups.manager_executing || []),
            ...(groups.pending || []),
            ...(groups.acknowledged || []),
            ...(groups.in_progress || []),
          ]
        : [];

    const managerExecutingCount = groups?.manager_executing?.length ?? 0;

    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            marginBottom: 'var(--space-8)',
        }}>
            {/* Header */}
            <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: 'var(--space-4) var(--space-5)',
                borderBottom: '1px solid var(--color-border)',
                background: 'linear-gradient(135deg, rgba(239,68,68,0.05), rgba(245,158,11,0.03))',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 16 }}>⚡</span>
                    <h2 style={{
                        fontSize: 'var(--text-sm)', fontWeight: 600,
                        color: 'var(--color-text-dim)', textTransform: 'uppercase',
                        letterSpacing: '0.08em', margin: 0,
                    }}>Task Board</h2>
                    <span style={{
                        fontSize: 'var(--text-xs)', fontWeight: 700,
                        padding: '1px 8px', borderRadius: 'var(--radius-full)',
                        background: total > 0 ? 'rgba(239,68,68,0.15)' : 'var(--color-surface-3)',
                        color: total > 0 ? '#f87171' : 'var(--color-text-dim)',
                    }}>{total} open</span>
                    {managerExecutingCount > 0 && (
                        <span style={{
                            fontSize: 'var(--text-xs)', fontWeight: 700,
                            padding: '1px 8px', borderRadius: 'var(--radius-full)',
                            background: 'rgba(239,68,68,0.12)', color: '#f87171',
                        }}>⚡ {managerExecutingCount} you're executing</span>
                    )}
                </div>
                <button
                    id="task-board-refresh"
                    onClick={load}
                    disabled={loading}
                    style={{
                        background: 'transparent', border: '1px solid var(--color-border)',
                        color: 'var(--color-text-dim)', borderRadius: 'var(--radius-md)',
                        padding: '4px 12px', fontSize: 'var(--text-xs)', cursor: 'pointer',
                        opacity: loading ? 0.5 : 1,
                    }}
                >↺ Refresh</button>
            </div>

            {/* Column header */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 140px 110px 90px',
                gap: 'var(--space-4)',
                padding: 'var(--space-2) var(--space-4)',
                background: 'var(--color-surface-2)',
                borderBottom: '1px solid var(--color-border)',
            }}>
                {['Task', 'Kind', 'Status', ''].map(h => (
                    <span key={h} style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</span>
                ))}
            </div>

            {/* Error */}
            {err && (
                <div style={{ padding: 'var(--space-4)', color: 'var(--color-danger)', fontSize: 'var(--text-sm)', background: 'rgba(239,68,68,0.06)' }}>⚠ {err}</div>
            )}

            {/* Loading */}
            {loading && allTasks.length === 0 && (
                Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} style={{
                        display: 'grid', gridTemplateColumns: '1fr 140px 110px 90px',
                        gap: 'var(--space-4)', padding: 'var(--space-3) var(--space-4)',
                        borderBottom: '1px solid var(--color-border)', alignItems: 'center',
                    }}>
                        {[240, 80, 90, 80].map((w, j) => (
                            <div key={j} style={{ height: 11, width: w, background: 'var(--color-surface-3)', borderRadius: 4 }} />
                        ))}
                    </div>
                ))
            )}

            {/* Empty */}
            {!loading && allTasks.length === 0 && !err && (
                <div style={{ padding: 'var(--space-10)', textAlign: 'center', color: 'var(--color-text-dim)' }}>
                    <div style={{ fontSize: '1.8rem', marginBottom: 8 }}>✓</div>
                    <div style={{ fontWeight: 600 }}>All clear</div>
                    <div style={{ fontSize: 'var(--text-sm)', marginTop: 4 }}>No open tasks for your properties right now.</div>
                </div>
            )}

            {/* Task rows */}
            {allTasks.map(t => (
                <TaskRow key={t.id} task={t} onTakeover={setTakeoverTask} />
            ))}

            {/* Takeover modal */}
            {takeoverTask && (
                <TakeoverModal
                    task={takeoverTask}
                    onClose={() => setTakeoverTask(null)}
                    onSuccess={handleTakeoverSuccess}
                />
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Morning Briefing widget (Phase 312)
// ---------------------------------------------------------------------------

function MorningBriefingWidget() {
    const [data, setData] = useState<MorningBriefingResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [language, setLanguage] = useState('en');

    const doFetch = useCallback(async () => {
        setLoading(true); setError(null);
        try {
            const res = await api.getMorningBriefing(language);
            setData(res);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to load briefing');
        } finally {
            setLoading(false);
        }
    }, [language]);

    const ops = data?.context_signals?.operations;
    const tasks = data?.context_signals?.tasks;

    const priorityColor: Record<string, string> = {
        CRITICAL: '#ef4444', HIGH: '#f97316', NORMAL: '#3b82f6',
    };

    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            marginBottom: 'var(--space-8)',
            overflow: 'hidden',
        }}>
            <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: 'var(--space-4) var(--space-5)',
                borderBottom: '1px solid var(--color-border)',
                background: 'linear-gradient(135deg, rgba(99,102,241,0.06), rgba(168,85,247,0.04))',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 18 }}>&#129504;</span>
                    <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        Copilot &middot; Morning Briefing
                    </h2>
                    {data && (
                        <span style={{
                            fontSize: 10, fontWeight: 700,
                            padding: '2px 8px', borderRadius: 'var(--radius-full)',
                            background: data.generated_by === 'llm' ? 'rgba(99,102,241,0.15)' : 'rgba(245,158,11,0.15)',
                            color: data.generated_by === 'llm' ? '#818cf8' : '#f59e0b',
                        }}>
                            {data.generated_by.toUpperCase()}
                        </span>
                    )}
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <select
                        value={language}
                        onChange={e => setLanguage(e.target.value)}
                        style={{
                            background: 'var(--color-bg)', border: '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-md)', color: 'var(--color-text)',
                            fontSize: 'var(--text-xs)', padding: '4px 8px', cursor: 'pointer',
                        }}
                    >
                        <option value="en">EN</option>
                        <option value="th">TH</option>
                        <option value="ja">JA</option>
                    </select>
                    <button
                        id="generate-briefing"
                        onClick={doFetch}
                        disabled={loading}
                        style={{
                            background: loading ? 'var(--color-surface-3)' : 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                            color: '#fff', border: 'none', borderRadius: 'var(--radius-md)',
                            padding: '6px 16px', fontSize: 'var(--text-xs)', fontWeight: 600,
                            cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1,
                            boxShadow: '0 0 12px rgba(99,102,241,0.25)',
                        }}
                    >
                        {loading ? 'Generating...' : data ? 'Refresh' : 'Generate Briefing'}
                    </button>
                </div>
            </div>

            <div style={{ padding: 'var(--space-5)' }}>
                {error && (
                    <div style={{ color: 'var(--color-danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)' }}>
                        {error}
                    </div>
                )}

                {!data && !loading && !error && (
                    <div style={{ textAlign: 'center', padding: 'var(--space-8) 0', color: 'var(--color-text-dim)' }}>
                        <div style={{ fontSize: '2rem', marginBottom: 8 }}>&#9728;</div>
                        <div style={{ fontSize: 'var(--text-sm)' }}>Click Generate Briefing to get today&#39;s morning summary.</div>
                    </div>
                )}

                {loading && !data && (
                    <div style={{ padding: 'var(--space-4) 0' }}>
                        {[1, 2, 3].map(i => (
                            <div key={i} style={{
                                height: 14, width: `${80 - i * 15}%`, background: 'var(--color-surface-3)',
                                borderRadius: 4, marginBottom: 12, animation: 'pulse 1.5s infinite',
                            }} />
                        ))}
                    </div>
                )}

                {data && (
                    <>
                        <div style={{
                            fontSize: 'var(--text-sm)', color: 'var(--color-text)',
                            lineHeight: 1.7, whiteSpace: 'pre-wrap',
                            marginBottom: 'var(--space-5)',
                        }}>
                            {data.briefing_text}
                        </div>

                        {data.action_items && data.action_items.length > 0 && (
                            <div style={{ marginBottom: 'var(--space-5)' }}>
                                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)' }}>
                                    Action Items
                                </div>
                                {data.action_items.map((item: CopilotActionItem, i: number) => (
                                    <div key={i} style={{
                                        display: 'flex', alignItems: 'center', gap: 10,
                                        padding: 'var(--space-2) var(--space-3)',
                                        borderLeft: `3px solid ${priorityColor[item.priority] || '#6b7280'}`,
                                        background: 'var(--color-surface-2)',
                                        borderRadius: '0 var(--radius-md) var(--radius-md) 0',
                                        marginBottom: 6,
                                        fontSize: 'var(--text-sm)',
                                    }}>
                                        <span style={{
                                            fontSize: 10, fontWeight: 700,
                                            padding: '1px 7px', borderRadius: 4,
                                            background: (priorityColor[item.priority] || '#6b7280') + '20',
                                            color: priorityColor[item.priority] || '#6b7280',
                                        }}>{item.priority}</span>
                                        <span style={{ color: 'var(--color-text)' }}>{item.description}</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        {ops && (
                            <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                                {[
                                    { label: 'Check-ins', value: ops.arrivals_count || 0, color: '#22c55e' },
                                    { label: 'Check-outs', value: ops.departures_count || 0, color: '#3b82f6' },
                                    { label: 'Cleanings', value: ops.cleanings_due || 0, color: '#f59e0b' },
                                    { label: 'Open Tasks', value: tasks?.total_open || 0, color: '#8b5cf6' },
                                ].map(s => (
                                    <div key={s.label} style={{
                                        background: 'var(--color-surface-2)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: 'var(--radius-md)',
                                        padding: 'var(--space-3) var(--space-4)',
                                        minWidth: 90,
                                    }}>
                                        <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: s.color }}>{s.value}</div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{s.label}</div>
                                    </div>
                                ))}
                            </div>
                        )}

                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-4)', textAlign: 'right' }}>
                            Generated {new Date(data.generated_at).toLocaleTimeString()} via {data.generated_by}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ManagerPage() {
    const [events, setEvents] = useState<AuditEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [entityFilter, setEntityFilter] = useState<'all' | 'task' | 'booking'>('all');
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
    const [prevIds, setPrevIds] = useState<Set<number>>(new Set());

    const load = useCallback(async () => {
        setLoading(true); setError(null);
        try {
            const params: Parameters<typeof api.getAuditEvents>[0] = { limit: 100 };
            if (entityFilter !== 'all') params.entity_type = entityFilter;
            const res = await api.getAuditEvents(params);
            setEvents(res.events);
            setLastRefresh(new Date());
            setPrevIds(prev => new Set([...prev, ...res.events.map(e => e.id)]));
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to load audit events');
        } finally {
            setLoading(false);
        }
    }, [entityFilter]);

    useEffect(() => { load(); }, [load]);

    // Derived stats
    const acknowledged = events.filter(e => e.action === 'TASK_ACKNOWLEDGED').length;
    const completed = events.filter(e => e.action === 'TASK_COMPLETED').length;
    const flagged = events.filter(e => e.action === 'BOOKING_FLAGS_UPDATED').length;

    const btnBase: React.CSSProperties = {
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-full)',
        padding: 'var(--space-1) var(--space-4)',
        fontSize: 'var(--text-xs)',
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all var(--transition-fast)',
        letterSpacing: '0.04em',
    };

    return (
        <div style={{ maxWidth: 1100 }}>
            <style>{`
                @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
            `}</style>

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-8)' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-1)' }}>
                        Manager view · {lastRefresh ? lastRefresh.toLocaleTimeString() : 'loading…'}
                    </p>
                    <h1 style={{
                        fontSize: 'var(--text-3xl)', fontWeight: 700,
                        letterSpacing: '-0.03em', lineHeight: 1.1,
                    }}>
                        Activity <span style={{ color: 'var(--color-primary)' }}>Feed</span>
                    </h1>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                        Every operator and worker mutation — who did what, when.
                    </p>
                </div>
                <button
                    id="manager-refresh"
                    onClick={load}
                    disabled={loading}
                    style={{
                        background: loading ? 'var(--color-surface-3)' : 'var(--color-primary)',
                        color: '#fff', border: 'none',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-2) var(--space-5)',
                        fontSize: 'var(--text-sm)', fontWeight: 600,
                        opacity: loading ? 0.7 : 1,
                        cursor: loading ? 'not-allowed' : 'pointer',
                        transition: 'all var(--transition-fast)',
                    }}
                >
                    {loading ? '⟳  Refreshing…' : '↺  Refresh'}
                </button>
            </div>

            {/* Stat row */}
            <div style={{ display: 'flex', gap: 'var(--space-4)', marginBottom: 'var(--space-8)', flexWrap: 'wrap' }}>
                <MetricChip label="Total events" value={events.length} color="var(--color-text)" />
                <MetricChip label="Task acked" value={acknowledged} color="#60a5fa" />
                <MetricChip label="Task completed" value={completed} color="#34d399" />
                <MetricChip label="Flags updated" value={flagged} color="#fbbf24" />
            </div>

            {/* Phase 1022-E: Task Board */}
            <TaskBoard />

            {/* Copilot Briefing (Phase 312) */}
            <MorningBriefingWidget />

            {/* Activity feed */}
            <div style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
                marginBottom: 'var(--space-8)',
            }}>
                {/* Feed header */}
                <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: 'var(--space-4) var(--space-5)',
                    borderBottom: '1px solid var(--color-border)',
                    background: 'var(--color-surface-2)',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                        <h2 style={{
                            fontSize: 'var(--text-sm)', fontWeight: 600,
                            color: 'var(--color-text-dim)', textTransform: 'uppercase',
                            letterSpacing: '0.08em',
                        }}>Live Mutations</h2>
                        <span style={{
                            fontSize: 'var(--text-xs)', fontWeight: 700,
                            padding: '1px 8px', borderRadius: 'var(--radius-full)',
                            background: 'var(--color-surface-3)',
                            color: 'var(--color-text-dim)',
                        }}>{events.length}</span>
                    </div>
                    {/* Entity filter pills */}
                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                        {(['all', 'task', 'booking'] as const).map(f => (
                            <button
                                key={f}
                                id={`filter-${f}`}
                                onClick={() => setEntityFilter(f)}
                                style={{
                                    ...btnBase,
                                    background: entityFilter === f ? 'var(--color-primary)' : 'transparent',
                                    color: entityFilter === f ? '#fff' : 'var(--color-text-dim)',
                                    borderColor: entityFilter === f ? 'var(--color-primary)' : 'var(--color-border)',
                                }}
                            >
                                {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1) + 's'}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Column headers */}
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: '160px 1fr 180px 80px',
                    gap: 'var(--space-4)',
                    padding: 'var(--space-2) var(--space-5)',
                    borderBottom: '1px solid var(--color-border)',
                    background: 'var(--color-surface-2)',
                }}>
                    {['Action', 'Entity', 'Actor', 'When'].map(h => (
                        <span key={h} style={{
                            fontSize: 'var(--text-xs)', fontWeight: 600,
                            color: 'var(--color-text-dim)', textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                        }}>{h}</span>
                    ))}
                </div>

                {/* Error */}
                {error && (
                    <div style={{
                        padding: 'var(--space-4) var(--space-5)',
                        color: 'var(--color-danger)',
                        fontSize: 'var(--text-sm)',
                        background: 'rgba(239,68,68,0.06)',
                        borderBottom: '1px solid var(--color-border)',
                    }}>⚠ {error}</div>
                )}

                {/* Loading skeletons */}
                {loading && events.length === 0 && (
                    Array.from({ length: 6 }).map((_, i) => (
                        <div key={i} style={{
                            display: 'grid', gridTemplateColumns: '160px 1fr 180px 80px',
                            gap: 'var(--space-4)', padding: 'var(--space-3) var(--space-5)',
                            borderBottom: '1px solid var(--color-border)',
                            alignItems: 'center',
                        }}>
                            {[100, 200, 140, 50].map((w, j) => (
                                <div key={j} style={{
                                    height: 12, width: w, background: 'var(--color-surface-3)',
                                    borderRadius: 4, animation: 'pulse 1.5s infinite',
                                }} />
                            ))}
                        </div>
                    ))
                )}

                {/* Empty */}
                {!loading && events.length === 0 && !error && (
                    <div style={{ padding: 'var(--space-16)', textAlign: 'center', color: 'var(--color-text-dim)' }}>
                        <div style={{ fontSize: '2rem', marginBottom: 'var(--space-3)' }}>📋</div>
                        <div style={{ fontWeight: 600 }}>No mutations yet</div>
                        <div style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-2)' }}>
                            Audit events will appear here as operators take actions.
                        </div>
                    </div>
                )}

                {/* Rows */}
                {events.map(ev => (
                    <AuditRow
                        key={ev.id}
                        ev={ev}
                        isNew={!prevIds.has(ev.id)}
                    />
                ))}
            </div>

            {/* Booking Audit Lookup */}
            <BookingAuditLookup />

            {/* Footer */}
            <div style={{
                marginTop: 'var(--space-10)',
                paddingTop: 'var(--space-6)',
                borderTop: '1px solid var(--color-border)',
                fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)',
                display: 'flex', justifyContent: 'space-between',
            }}>
                <span>Domaniqo — Manager Copilot · Phase 1022 (Takeover Gate)</span>
                <span>Source: audit_events table · actor_id = JWT sub</span>
            </div>
        </div>
    );
}
