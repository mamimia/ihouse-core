'use client';

/**
 * Phase 190 — Manager Activity Feed + Phase 1022 — Operational Takeover Gate
 * Route: /manager
 *
 * Phase 1022-G: Manager execution surface — responsive in-place drawer.
 * Mobile: full-screen overlay.  Desktop: slide-in side drawer.
 * Manager/admin stays inside their surface throughout the entire takeover → execute → complete flow.
 */

import { useEffect, useState, useCallback } from 'react';
import { api, AuditEvent, MorningBriefingResponse, CopilotActionItem, apiFetch } from '@/lib/api';

// Phase 1022-H: Real worker execution wizards — embedded directly in the manager drawer.
// These are the canonical worker flows, identical to what workers see on /ops/*.
// MobileStaffShell wrapper removed; logic and UX are 100% identical.
import { CheckinWizard } from '@/app/(app)/ops/checkin/page';
import { CheckoutWizard } from '@/app/(app)/ops/checkout/page';
import { CleanerWizard } from '@/app/(app)/ops/cleaner/page';
import { MaintenanceWizard } from '@/app/(app)/ops/maintenance/page';

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
// Phase 1022-G: Responsive desktop/mobile detection
// ---------------------------------------------------------------------------

function useIsDesktop(): boolean {
    const [isDesktop, setIsDesktop] = useState(true);
    useEffect(() => {
        const check = () => setIsDesktop(window.innerWidth >= 768);
        check();
        window.addEventListener('resize', check);
        return () => window.removeEventListener('resize', check);
    }, []);
    return isDesktop;
}

// ---------------------------------------------------------------------------
// Phase 1022-E/G: Takeover Modal
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
    property_name?: string;          // Phase 1044: resolved display_name from properties table
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

// ---------------------------------------------------------------------------
// Phase 1044 — Human-operational task title
// Replaces raw ICAL/booking-ID polluted title with: "Villa Name — Task Kind"
// Used on all OM-facing task list / snapshot surfaces.
// ---------------------------------------------------------------------------
const OPERATIONAL_KIND_LABEL: Record<string, string> = {
    CLEANING:              'Checkout Cleaning',
    CHECKIN_PREP:          'Check-in Prep',
    CHECKOUT_VERIFY:       'Checkout Verification',
    GUEST_WELCOME:         'Guest Welcome',
    MAINTENANCE:           'Maintenance',
    SELF_CHECKIN_FOLLOWUP: 'Self Check-in Follow-up',
    GENERAL:               'General Task',
};

function buildOperationalTaskTitle(task: ManagerTask): string {
    const propertyLabel = task.property_name || task.property_id;
    // Special case: early checkout cleaning has a more specific label
    const isEarlyCheckout = (task as any).is_early_checkout === true;
    const rawKind = task.task_kind?.toUpperCase?.() ?? task.task_kind;
    const kindLabel =
        rawKind === 'CLEANING' && isEarlyCheckout
            ? 'Post-checkout Cleaning'
            : (OPERATIONAL_KIND_LABEL[rawKind] ?? rawKind);
    return `${propertyLabel} — ${kindLabel}`;
}

function TakeoverModal({
    task,
    onClose,
    onTakeoverComplete,
}: {
    task: ManagerTask;
    onClose: () => void;
    onTakeoverComplete: (task: ManagerTask) => void;  // opens execution drawer
}) {
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
            onClose();
            // Phase 1022-G: open execution drawer in-place (no navigation)
            onTakeoverComplete({ ...task, status: 'MANAGER_EXECUTING', taken_over_reason: reason });
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
                    <div style={{ fontWeight: 600, color: 'var(--color-text)' }}>{buildOperationalTaskTitle(task)}</div>
                    <div style={{ color: 'var(--color-text-dim)', fontSize: 12 }}>
                        Status: <strong style={{ color: 'var(--color-warn)' }}>{task.status}</strong>
                        {task.assigned_to && <span style={{ marginLeft: 12 }}>Currently: <strong>{task.assigned_to.slice(0, 12)}…</strong></span>}
                        {task.due_date && <span style={{ marginLeft: 12 }}>Due: <strong>{task.due_date}</strong></span>}
                    </div>
                </div>

                <div style={{ fontSize: 11, color: 'var(--color-text-faint)', marginBottom: 'var(--space-5)', lineHeight: 1.5 }}>
                    You are taking over this task as the active executor.
                    The original worker will be notified. After confirming, you will execute the task directly from this board.
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

// Phase 1022-H: KIND_STEPS only kept for the GENERAL fallback shell.
// All other task kinds now use the real extracted wizard components.
const GENERAL_STEPS: string[] = [
    'Review task description',
    'Complete required actions',
    'Document outcome',
];

// ---------------------------------------------------------------------------
// Phase 1022-H: TaskWizardRouter — routes task_kind to real worker wizard.
// CLEANING → CleanerWizard (real /ops/cleaner flow)
// CHECKIN_PREP / GUEST_WELCOME / SELF_CHECKIN_FOLLOWUP → CheckinWizard (real /ops/checkin flow)
// CHECKOUT_VERIFY → CheckoutWizard (real /ops/checkout flow)
// MAINTENANCE → MaintenanceWizard (real /ops/maintenance flow)
// GENERAL → simplified fallback shell (no real wizard exists for generic tasks)
// ---------------------------------------------------------------------------

function TaskWizardRouter({
    task,
    onCompleted,
}: {
    task: ManagerTask;
    onCompleted: () => void;
}) {
    const kind = task.task_kind;

    // Real wizard: Cleaning
    if (kind === 'CLEANING') {
        return <CleanerWizard onCompleted={onCompleted} />;
    }

    // Real wizard: Check-in (also covers GUEST_WELCOME and SELF_CHECKIN_FOLLOWUP variants)
    if (kind === 'CHECKIN_PREP' || kind === 'GUEST_WELCOME' || kind === 'SELF_CHECKIN_FOLLOWUP') {
        return <CheckinWizard onCompleted={onCompleted} />;
    }

    // Real wizard: Check-out
    if (kind === 'CHECKOUT_VERIFY') {
        return <CheckoutWizard onCompleted={onCompleted} />;
    }

    // Real wizard: Maintenance
    if (kind === 'MAINTENANCE') {
        return <MaintenanceWizard onCompleted={onCompleted} />;
    }

    // Fallback: simplified shell for GENERAL and any unmapped task kinds
    return <GeneralTaskShell task={task} onCompleted={onCompleted} />;
}

interface TaskContext {
    task_kind?: string;
    booking_id?: string;
    property_id?: string;
    priority?: string;
    original_worker_id?: string;
    taken_over_by?: string;
    taken_over_reason?: string;
    taken_over_at?: string;
    property?: { name?: string; address?: string; door_code?: string; notes?: string };
    booking?: { guest_name?: string; check_in?: string; check_out?: string; number_of_guests?: number };
    checklist?: Array<{ id?: string; item?: string; label?: string }>;
}

// Simplified shell kept ONLY for GENERAL tasks (no dedicated worker wizard exists)
function GeneralTaskShell({
    task,
    onCompleted,
}: {
    task: ManagerTask;
    onCompleted: () => void;
}) {
    const [context, setContext]       = useState<TaskContext | null>(null);
    const [ctxLoading, setCtxLoading] = useState(true);
    const [checked, setChecked]       = useState<Record<string, boolean>>({});
    const [completionNotes, setCompletionNotes] = useState('');
    const [completing, setCompleting] = useState(false);
    const [completeErr, setCompleteErr] = useState('');
    const [completed, setCompleted]   = useState(false);

    useEffect(() => {
        setCtxLoading(true);
        apiFetch<{ context: TaskContext }>(`/tasks/${task.id}/context`)
            .then(r => setContext(r.context))
            .catch(() => setContext({}))
            .finally(() => setCtxLoading(false));
    }, [task.id]);

    const steps = GENERAL_STEPS;
    const allChecked = steps.every((_, i) => checked[i]);

    const handleComplete = async () => {
        setCompleting(true); setCompleteErr('');
        try {
            await apiFetch(`/worker/tasks/${task.id}/complete`, {
                method: 'PATCH',
                body: JSON.stringify({ notes: completionNotes.trim() || undefined }),
            });
            setCompleted(true);
            setTimeout(onCompleted, 900);
        } catch (e: any) {
            setCompleteErr(e?.message || 'Could not complete task. Please try again.');
        } finally {
            setCompleting(false);
        }
    };

    const iStyle: React.CSSProperties = {
        width: '100%', boxSizing: 'border-box',
        background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-sm)', color: 'var(--color-text)',
        fontSize: 'var(--text-sm)', padding: '8px 12px', resize: 'vertical',
        fontFamily: 'inherit',
    };

    if (completed) {
        return (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60%', gap: 12, color: '#34d399' }}>
                <div style={{ fontSize: '3rem' }}>✓</div>
                <div style={{ fontWeight: 700, fontSize: 'var(--text-lg)' }}>Task Completed</div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', textAlign: 'center' }}>Returning to task board…</div>
            </div>
        );
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)', paddingBottom: 'var(--space-4)' }}>

            {/* Context card */}
            {ctxLoading ? (
                <div style={{ height: 72, background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', animation: 'pulse 1.5s infinite' }} />
            ) : context && (context.property || context.booking) ? (
                <div style={{
                    background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-4)',
                    display: 'flex', flexDirection: 'column', gap: 6,
                }}>
                    {context.property?.name && (
                        <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                            📍 {context.property.name}
                        </div>
                    )}
                    {context.property?.address && (
                        <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{context.property.address}</div>
                    )}
                    {context.property?.door_code && (
                        <div style={{ fontSize: 12, color: 'var(--color-text-faint)' }}>
                            Door code: <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text)' }}>{context.property.door_code}</strong>
                        </div>
                    )}
                    {context.booking && (
                        <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 4, borderTop: '1px solid var(--color-border)', paddingTop: 6 }}>
                            Guest: <strong>{context.booking.guest_name || '—'}</strong>
                            {context.booking.check_in && <span style={{ marginLeft: 10 }}>In: {context.booking.check_in}</span>}
                            {context.booking.check_out && <span style={{ marginLeft: 10 }}>Out: {context.booking.check_out}</span>}
                            {context.booking.number_of_guests && <span style={{ marginLeft: 10 }}>{context.booking.number_of_guests} guests</span>}
                        </div>
                    )}
                </div>
            ) : null}

            {/* Execution steps */}
            <div>
                <div style={{
                    fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)',
                    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-3)',
                }}>Execution Steps</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {steps.map((step, i) => (
                        <label
                            key={i}
                            style={{
                                display: 'flex', alignItems: 'flex-start', gap: 10,
                                padding: '8px 10px', borderRadius: 'var(--radius-sm)',
                                background: checked[i] ? 'rgba(16,185,129,0.06)' : 'var(--color-surface-2)',
                                border: `1px solid ${checked[i] ? 'rgba(16,185,129,0.2)' : 'var(--color-border)'}`,
                                cursor: 'pointer', transition: 'all 0.15s',
                            }}
                        >
                            <input
                                type="checkbox"
                                checked={!!checked[i]}
                                onChange={() => setChecked(p => ({ ...p, [i]: !p[i] }))}
                                style={{ marginTop: 2, accentColor: '#10b981', flexShrink: 0 }}
                            />
                            <span style={{
                                fontSize: 'var(--text-sm)',
                                color: checked[i] ? '#34d399' : 'var(--color-text)',
                                textDecoration: checked[i] ? 'line-through' : 'none',
                                opacity: checked[i] ? 0.7 : 1,
                                transition: 'all 0.15s',
                            }}>{step}</span>
                        </label>
                    ))}
                </div>
                {!allChecked && (
                    <div style={{ fontSize: 11, color: 'var(--color-text-faint)', marginTop: 6, paddingLeft: 2 }}>
                        Check off steps as you complete them. You can mark complete at any time.
                    </div>
                )}
            </div>

            {/* Completion notes */}
            <div>
                <div style={{
                    fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)',
                    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-2)',
                }}>Completion Notes (optional)</div>
                <textarea
                    id="execution-completion-notes"
                    value={completionNotes}
                    onChange={e => setCompletionNotes(e.target.value)}
                    placeholder="Anything to note for the audit record…"
                    rows={3}
                    style={iStyle}
                />
            </div>

            {completeErr && (
                <div style={{ color: 'var(--color-danger)', fontSize: 'var(--text-sm)' }}>⚠ {completeErr}</div>
            )}

            {/* Mark complete CTA */}
            <button
                id="mark-task-complete-btn"
                onClick={handleComplete}
                disabled={completing}
                style={{
                    background: completing
                        ? 'var(--color-surface-3)'
                        : 'linear-gradient(135deg,#10b981,#059669)',
                    color: '#fff', border: 'none', borderRadius: 'var(--radius-md)',
                    padding: '12px 0', fontSize: 'var(--text-sm)', fontWeight: 700,
                    cursor: completing ? 'not-allowed' : 'pointer',
                    opacity: completing ? 0.7 : 1,
                    width: '100%', transition: 'all 0.15s',
                    boxShadow: '0 2px 12px rgba(16,185,129,0.3)',
                }}
            >
                {completing ? 'Completing…' : '✓ Mark Task Complete'}
            </button>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Phase 1022-G: Manager Execution Drawer (responsive)
// Mobile: full-screen overlay
// Desktop: slide-in side drawer — board stays visible behind
// ---------------------------------------------------------------------------

const KIND_LABEL: Record<string, string> = {
    CLEANING: 'Cleaning',
    CHECKIN_PREP: 'Check-in Prep',
    CHECKOUT_VERIFY: 'Checkout Verify',
    GUEST_WELCOME: 'Guest Welcome',
    MAINTENANCE: 'Maintenance',
    SELF_CHECKIN_FOLLOWUP: 'Self Check-in Follow-up',
    GENERAL: 'General Task',
};

function ManagerExecutionDrawer({
    task,
    onClose,
    onCompleted,
}: {
    task: ManagerTask;
    onClose: () => void;
    onCompleted: () => void;  // refreshes board after completion
}) {
    const isDesktop = useIsDesktop();

    const drawerStyle: React.CSSProperties = isDesktop ? {
        // Desktop: right-side panel, board stays visible left
        position: 'fixed', top: 0, right: 0, bottom: 0,
        width: 'min(520px, 46vw)',
        background: 'var(--color-surface)',
        borderLeft: '1px solid var(--color-border)',
        boxShadow: '-8px 0 40px rgba(0,0,0,0.35)',
        display: 'flex', flexDirection: 'column',
        zIndex: 500,
        overflowY: 'auto',
        animation: 'slideInRight 0.22s ease-out',
    } : {
        // Mobile: full screen
        position: 'fixed', inset: 0,
        background: 'var(--color-surface)',
        display: 'flex', flexDirection: 'column',
        zIndex: 500,
        overflowY: 'auto',
    };

    const backdropStyle: React.CSSProperties = isDesktop ? {
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.35)',
        zIndex: 499,
        backdropFilter: 'blur(2px)',
    } : {};

    const kindLabel = KIND_LABEL[task.task_kind] ?? task.task_kind;
    const takenReason = task.taken_over_reason?.replace(/_/g, ' ') ?? '';

    return (
        <>
            {/* Backdrop (desktop only — dims the board behind the drawer) */}
            {isDesktop && (
                <div style={backdropStyle} onClick={onClose} aria-label="Close execution drawer" />
            )}

            <div style={drawerStyle}>
                {/* Drawer header */}
                <div style={{
                    padding: 'var(--space-4) var(--space-5)',
                    borderBottom: '1px solid var(--color-border)',
                    background: 'linear-gradient(135deg,rgba(239,68,68,0.07),rgba(245,158,11,0.04))',
                    position: 'sticky', top: 0, zIndex: 2,
                    flexShrink: 0,
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-3)' }}>
                        <div>
                            <div style={{
                                fontSize: 'var(--text-xs)', fontWeight: 700,
                                textTransform: 'uppercase', letterSpacing: '0.08em',
                                color: '#f87171', marginBottom: 4,
                            }}>⚡ Takeover Execution</div>
                            <div style={{ fontWeight: 700, fontSize: 'var(--text-lg)', color: 'var(--color-text)', lineHeight: 1.2 }}>
                                {kindLabel}
                            </div>
                        </div>
                        <button
                            id="close-execution-drawer"
                            onClick={onClose}
                            title="Close (task stays in MANAGER_EXECUTING — you can return any time)"
                            style={{
                                background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-full)',
                                width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
                                cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: 16, flexShrink: 0,
                            }}
                        >✕</button>
                    </div>

                    {/* Context pills */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        <span style={{
                            fontSize: 11, fontWeight: 600,
                            padding: '2px 10px', borderRadius: 'var(--radius-full)',
                            background: 'rgba(239,68,68,0.1)', color: '#f87171',
                            border: '1px solid rgba(239,68,68,0.2)',
                        }}>Manager Executing</span>
                        <span style={{
                            fontSize: 11, fontWeight: 600,
                            padding: '2px 10px', borderRadius: 'var(--radius-full)',
                            background: 'var(--color-surface-3)', color: 'var(--color-text-dim)',
                        }}>📍 {task.property_id}</span>
                        {task.due_date && (
                            <span style={{
                                fontSize: 11, fontWeight: 600,
                                padding: '2px 10px', borderRadius: 'var(--radius-full)',
                                background: 'var(--color-surface-3)', color: 'var(--color-text-dim)',
                            }}>Due {task.due_date}</span>
                        )}
                        {task.original_worker_id && (
                            <span style={{
                                fontSize: 11, fontWeight: 600,
                                padding: '2px 10px', borderRadius: 'var(--radius-full)',
                                background: 'rgba(148,163,184,0.1)', color: 'var(--color-text-dim)',
                                border: '1px solid var(--color-border)',
                            }}>↩ Taken over from: {task.original_worker_id.slice(0, 14)}…</span>
                        )}
                        {takenReason && (
                            <span style={{
                                fontSize: 11, fontWeight: 600,
                                padding: '2px 10px', borderRadius: 'var(--radius-full)',
                                background: 'rgba(245,158,11,0.08)', color: '#f59e0b',
                            }}>Reason: {takenReason}</span>
                        )}
                    </div>

                    {/* Safe-close notice */}
                    <div style={{
                        fontSize: 10, color: 'var(--color-text-faint)',
                        marginTop: 'var(--space-3)', lineHeight: 1.5,
                    }}>
                        Closing this panel does not cancel the takeover — the task stays in Manager Executing state and you can resume from the task board.
                    </div>
                </div>

                {/* Scrollable execution body */}
                <div style={{ flex: 1, padding: 'var(--space-5)', overflowY: 'auto' }}>
                    {/* Phase 1022-H: Real worker wizard routing.
                        CLEANING → CleanerWizard (real /ops/cleaner flow)
                        CHECKIN_PREP / GUEST_WELCOME → CheckinWizard (real /ops/checkin flow)
                        CHECKOUT_VERIFY → CheckoutWizard (real /ops/checkout flow)
                        MAINTENANCE → MaintenanceWizard (real /ops/maintenance flow)
                        GENERAL → simplified fallback (no dedicated wizard) */}
                    <TaskWizardRouter task={task} onCompleted={onCompleted} />
                </div>
            </div>

            <style>{`
                @keyframes slideInRight {
                    from { transform: translateX(100%); opacity: 0.6; }
                    to { transform: translateX(0); opacity: 1; }
                }
            `}</style>
        </>
    );
}

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
    onExecute,
}: {
    task: ManagerTask;
    onTakeover: (t: ManagerTask) => void;
    onExecute:  (t: ManagerTask) => void;  // Phase 1022-G: opens execution drawer
}) {
    const sc = STATUS_CONFIG[task.status] ?? STATUS_CONFIG['PENDING'];
    const isTakenOver = task.status === 'MANAGER_EXECUTING';
    const canTakeover = ['PENDING', 'ACKNOWLEDGED', 'IN_PROGRESS'].includes(task.status);
    const dot = PRIORITY_DOT[task.priority] ?? '#94a3b8';

    return (
        <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 140px 110px 100px',
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
                        {buildOperationalTaskTitle(task)}
                    </span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-dim)', paddingLeft: 15 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.65 }}>{task.property_id}</span>
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

            {/* Action — Phase 1022-G: Execute replaces navigation */}
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
                    <button
                        id={`execute-btn-${task.id}`}
                        onClick={() => onExecute(task)}
                        title="Execute this task"
                        style={{
                            background: 'linear-gradient(135deg,#10b981,#059669)',
                            color: '#fff', border: 'none',
                            borderRadius: 'var(--radius-sm)',
                            padding: '5px 12px', fontSize: 11, fontWeight: 700,
                            cursor: 'pointer',
                            boxShadow: '0 1px 6px rgba(16,185,129,0.3)',
                            transition: 'all 0.15s',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        ▶ Execute
                    </button>
                ) : null}
            </div>
        </div>
    );
}

function TaskBoard() {
    const [groups, setGroups]         = useState<Record<string, ManagerTask[]> | null>(null);
    const [total, setTotal]           = useState(0);
    const [loading, setLoading]       = useState(true);
    const [err, setErr]               = useState('');
    const [takeoverTask, setTakeoverTask]   = useState<ManagerTask | null>(null);
    // Phase 1022-G: executing task drives the responsive drawer
    const [executingTask, setExecutingTask] = useState<ManagerTask | null>(null);

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

    // After takeover: open the execution drawer immediately; board will refresh behind it
    const handleTakeoverComplete = (updatedTask: ManagerTask) => {
        setExecutingTask(updatedTask);
        load();  // refresh board so row flips to MANAGER_EXECUTING
    };

    // After task is completed inside the drawer
    const handleExecutionCompleted = () => {
        setExecutingTask(null);
        load();
    };

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
                <TaskRow
                    key={t.id}
                    task={t}
                    onTakeover={setTakeoverTask}
                    onExecute={setExecutingTask}  // Phase 1022-G: ▶ Execute opens drawer
                />
            ))}

            {/* Takeover confirm modal */}
            {takeoverTask && (
                <TakeoverModal
                    task={takeoverTask}
                    onClose={() => setTakeoverTask(null)}
                    onTakeoverComplete={handleTakeoverComplete}  // opens drawer, no navigation
                />
            )}

            {/* Phase 1022-G: Responsive execution drawer */}
            {executingTask && (
                <ManagerExecutionDrawer
                    task={executingTask}
                    onClose={() => setExecutingTask(null)}
                    onCompleted={handleExecutionCompleted}
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

    // Phase 1041: auto-load on mount
    useEffect(() => { doFetch(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
                    {/* Phase 1041: briefing auto-loads; button is now Refresh only */}
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
                        {loading ? 'Generating…' : 'Refresh Briefing'}
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
                        <div style={{ fontSize: 'var(--text-sm)' }}>Loading morning briefing…</div>
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
// Alert rail (Phase 1033)
// ---------------------------------------------------------------------------

type AlertItem = {
    type: string;
    severity: 'critical' | 'high' | 'warning';
    task_id?: string;
    title?: string;
    property_id?: string;
    status?: string;
    due_date?: string | null;
    lane?: string;
    detail?: string;
};

function AlertRail({ alerts, loading }: { alerts: AlertItem[]; loading: boolean }) {
    if (loading) return null;
    if (alerts.length === 0) return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 8, background: '#10b98110', border: '1px solid #10b98130', marginBottom: 16, fontSize: 'var(--text-xs)', color: '#10b981' }}>
            ✓ No active alerts
        </div>
    );

    const criticals = alerts.filter(a => a.severity === 'critical');
    const highs = alerts.filter(a => a.severity === 'high');
    const warnings = alerts.filter(a => a.severity === 'warning');

    return (
        <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-dim)', letterSpacing: '0.06em', marginBottom: 8 }}>ALERTS</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {criticals.slice(0, 3).map((a, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderRadius: 8, background: '#ef444414', border: '1px solid #ef444430' }}>
                        <span style={{ fontSize: '0.85em' }}>🔴</span>
                        <span style={{ fontWeight: 700, fontSize: 'var(--text-xs)', color: '#ef4444' }}>CRITICAL</span>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text)' }}>{a.title || a.type}</span>
                        {a.property_id && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{a.property_id}</span>}
                    </div>
                ))}
                {highs.slice(0, 2).map((a, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderRadius: 8, background: '#f9731614', border: '1px solid #f9731630' }}>
                        <span style={{ fontSize: '0.85em' }}>🟠</span>
                        <span style={{ fontWeight: 700, fontSize: 'var(--text-xs)', color: '#f97316' }}>HIGH</span>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text)' }}>{a.title || a.type}</span>
                        {a.property_id && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{a.property_id}</span>}
                    </div>
                ))}
                {warnings.slice(0, 3).map((a, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderRadius: 8, background: '#f59e0b10', border: '1px solid #f59e0b28' }}>
                        <span style={{ fontSize: '0.85em' }}>⚠️</span>
                        <span style={{ fontWeight: 600, fontSize: 'var(--text-xs)', color: '#f59e0b' }}>WARNING</span>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text)' }}>{a.detail || a.title || a.type}</span>
                        {a.property_id && !a.detail && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{a.property_id}</span>}
                    </div>
                ))}
                {alerts.length > 8 && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', padding: '4px 12px' }}>
                        +{alerts.length - 8} more — <a href="/manager/alerts" style={{ color: 'var(--color-primary)', textDecoration: 'none' }}>View all alerts →</a>
                    </div>
                )}
            </div>
        </div>
    );
}


// ---------------------------------------------------------------------------
// Priority Task Snapshot (Hub-only, max 10 rows, links to Stream for more)
// ---------------------------------------------------------------------------

function PriorityTaskSnapshot() {
    const [tasks, setTasks]     = useState<ManagerTask[]>([]);
    const [loading, setLoading] = useState(true);
    const [err, setErr]         = useState('');
    const [takeoverTask, setTakeoverTask]   = useState<ManagerTask | null>(null);
    const [executingTask, setExecutingTask] = useState<ManagerTask | null>(null);

    const MAX_ROWS = 10;

    const load = useCallback(async () => {
        setLoading(true); setErr('');
        try {
            const res = await apiFetch<{ groups: Record<string, ManagerTask[]>; total: number }>('/manager/tasks');
            const groups = res.groups || {};
            // Canonical Hub priority order: executing → pending → acknowledged → in_progress
            const all: ManagerTask[] = [
                ...(groups.manager_executing || []),
                ...(groups.pending           || []),
                ...(groups.acknowledged      || []),
                ...(groups.in_progress       || []),
            ];
            setTasks(all);
        } catch (e: any) {
            setErr(e?.message || 'Failed to load tasks.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleTakeoverComplete = (updated: ManagerTask) => {
        setExecutingTask(updated);
        load();
    };

    const snapshot = tasks.slice(0, MAX_ROWS);
    const overflow = tasks.length - MAX_ROWS;

    const sc = STATUS_CONFIG;
    const dot = PRIORITY_DOT;

    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            marginBottom: 'var(--space-6)',
        }}>
            {/* Header */}
            <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '12px 16px',
                borderBottom: '1px solid var(--color-border)',
                background: 'linear-gradient(135deg,rgba(239,68,68,0.05),rgba(245,158,11,0.03))',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 15 }}>⚡</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                        Priority Tasks
                    </span>
                    {!loading && (
                        <span style={{
                            fontSize: 11, fontWeight: 700,
                            padding: '1px 8px', borderRadius: 'var(--radius-full)',
                            background: tasks.length > 0 ? 'rgba(239,68,68,0.14)' : 'var(--color-surface-3)',
                            color: tasks.length > 0 ? '#f87171' : 'var(--color-text-dim)',
                        }}>{tasks.length} open</span>
                    )}
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button id="hub-tasks-refresh" onClick={load} disabled={loading} style={{
                        background: 'transparent', border: '1px solid var(--color-border)',
                        color: 'var(--color-text-dim)', borderRadius: 6,
                        padding: '3px 10px', fontSize: 11, cursor: 'pointer', opacity: loading ? 0.5 : 1,
                    }}>↺</button>
                    <a href="/manager/stream" style={{
                        fontSize: 11, fontWeight: 600, color: 'var(--color-primary)',
                        textDecoration: 'none', padding: '3px 10px',
                        border: '1px solid var(--color-primary)',
                        borderRadius: 6, opacity: 0.8,
                    }}>View all in Stream →</a>
                </div>
            </div>

            {/* Loading skeleton */}
            {loading && tasks.length === 0 && (
                [...Array(4)].map((_, i) => (
                    <div key={i} style={{ padding: '10px 16px', borderBottom: '1px solid var(--color-border)', display: 'flex', gap: 12, alignItems: 'center' }}>
                        <div style={{ height: 10, width: 160, background: 'var(--color-surface-3)', borderRadius: 4 }} />
                        <div style={{ height: 10, width: 80, background: 'var(--color-surface-3)', borderRadius: 4 }} />
                    </div>
                ))
            )}

            {/* Error */}
            {err && <div style={{ padding: '10px 16px', color: 'var(--color-danger)', fontSize: 12 }}>⚠ {err}</div>}

            {/* Empty */}
            {!loading && tasks.length === 0 && !err && (
                <div style={{ padding: '32px', textAlign: 'center', color: 'var(--color-text-dim)' }}>
                    <div style={{ fontSize: '1.5rem', marginBottom: 6 }}>✓</div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>All clear</div>
                    <div style={{ fontSize: 12, marginTop: 4 }}>No open tasks in your properties right now.</div>
                </div>
            )}

            {/* Task rows — compact */}
            {snapshot.map(t => {
                const cfg = sc[t.status] ?? sc['PENDING'];
                const isTakenOver = t.status === 'MANAGER_EXECUTING';
                const canTakeover = ['PENDING', 'ACKNOWLEDGED', 'IN_PROGRESS'].includes(t.status);
                return (
                    <div key={t.id} style={{
                        display: 'grid', gridTemplateColumns: '1fr 80px 80px',
                        gap: 8, padding: '9px 16px', alignItems: 'center',
                        borderBottom: '1px solid var(--color-border)',
                        background: isTakenOver ? 'rgba(239,68,68,0.025)' : 'transparent',
                    }}>
                        <div style={{ minWidth: 0 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 2 }}>
                                <span style={{ width: 6, height: 6, borderRadius: '50%', background: dot[t.priority] ?? '#94a3b8', flexShrink: 0 }} />
                                <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {buildOperationalTaskTitle(t)}
                                </span>
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--color-text-dim)', paddingLeft: 13 }}>
                                <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.65 }}>{t.property_id}</span>
                                {t.due_date && <span style={{ marginLeft: 8, color: 'var(--color-text-faint)' }}>· {t.due_date}</span>}
                            </div>
                        </div>
                        <div>
                            <span style={{
                                fontSize: 10, fontWeight: 700,
                                padding: '2px 7px', borderRadius: 'var(--radius-full)',
                                background: cfg.bg, color: cfg.color, whiteSpace: 'nowrap',
                            }}>{cfg.label}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                            {canTakeover ? (
                                <button id={`hub-takeover-${t.id}`} onClick={() => setTakeoverTask(t)} style={{
                                    background: 'linear-gradient(135deg,#ef4444,#dc2626)',
                                    color: '#fff', border: 'none', borderRadius: 5,
                                    padding: '4px 10px', fontSize: 10, fontWeight: 700, cursor: 'pointer',
                                    boxShadow: '0 1px 5px rgba(239,68,68,0.25)', whiteSpace: 'nowrap',
                                }}>⚡ Take Over</button>
                            ) : isTakenOver ? (
                                <button id={`hub-execute-${t.id}`} onClick={() => setExecutingTask(t)} style={{
                                    background: 'linear-gradient(135deg,#10b981,#059669)',
                                    color: '#fff', border: 'none', borderRadius: 5,
                                    padding: '4px 10px', fontSize: 10, fontWeight: 700, cursor: 'pointer',
                                    boxShadow: '0 1px 5px rgba(16,185,129,0.25)', whiteSpace: 'nowrap',
                                }}>▶ Execute</button>
                            ) : null}
                        </div>
                    </div>
                );
            })}

            {/* Overflow link */}
            {overflow > 0 && (
                <div style={{ padding: '10px 16px', borderTop: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
                    <a href="/manager/stream" style={{ fontSize: 12, color: 'var(--color-primary)', textDecoration: 'none', fontWeight: 600 }}>
                        +{overflow} more tasks — Open full Stream →
                    </a>
                </div>
            )}

            {/* Takeover modal */}
            {takeoverTask && (
                <TakeoverModal
                    task={takeoverTask}
                    onClose={() => setTakeoverTask(null)}
                    onTakeoverComplete={handleTakeoverComplete}
                />
            )}
            {/* Execution drawer */}
            {executingTask && (
                <ManagerExecutionDrawer
                    task={executingTask}
                    onClose={() => setExecutingTask(null)}
                    onCompleted={() => { setExecutingTask(null); load(); }}
                />
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Today's Booking Snapshot (Hub-only, today's arrivals + departures)
// ---------------------------------------------------------------------------

type HubBooking = {
    booking_id: string;
    property_id: string;
    property_name: string;
    guest_name: string;
    check_in: string;
    check_out: string;
    urgency_label: string;
    status: string;
    early_checkout_eligible: boolean;
};

function TodayBookingSnapshot() {
    const [bookings, setBookings] = useState<HubBooking[]>([]);
    const [loading, setLoading]   = useState(true);

    useEffect(() => {
        apiFetch<{ bookings: HubBooking[] }>('/manager/stream/bookings')
            .then(r => {
                const today = new Date().toISOString().slice(0, 10);
                // Hub shows only today's arrivals, departures, and active in-stays
                const todayOnly = (r.bookings || []).filter(b => {
                    const ci = b.check_in || '';
                    const co = b.check_out || '';
                    return ci === today || co === today || (ci < today && co > today);
                });
                setBookings(todayOnly);
            })
            .catch(() => setBookings([]))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return (
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: '16px', marginBottom: 'var(--space-6)' }}>
            <div style={{ height: 12, width: 140, background: 'var(--color-surface-3)', borderRadius: 4, marginBottom: 12 }} />
            {[...Array(2)].map((_, i) => <div key={i} style={{ height: 10, width: '60%', background: 'var(--color-surface-3)', borderRadius: 4, marginBottom: 8 }} />)}
        </div>
    );

    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            marginBottom: 'var(--space-6)',
        }}>
            <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '12px 16px',
                borderBottom: bookings.length > 0 ? '1px solid var(--color-border)' : 'none',
                background: 'linear-gradient(135deg,rgba(59,130,246,0.05),rgba(16,185,129,0.03))',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span>📋</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                        Today&apos;s Bookings
                    </span>
                    <span style={{
                        fontSize: 11, fontWeight: 700,
                        padding: '1px 8px', borderRadius: 'var(--radius-full)',
                        background: bookings.length > 0 ? 'rgba(59,130,246,0.14)' : 'var(--color-surface-3)',
                        color: bookings.length > 0 ? '#60a5fa' : 'var(--color-text-dim)',
                    }}>{bookings.length}</span>
                </div>
                <a href="/manager/stream" style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-primary)', textDecoration: 'none', opacity: 0.8 }}>
                    Full runway in Stream →
                </a>
            </div>

            {bookings.length === 0 ? (
                <div style={{ padding: '20px 16px', color: 'var(--color-text-dim)', fontSize: 13, textAlign: 'center' }}>
                    No arrivals, departures, or active stays today.
                </div>
            ) : (
                bookings.map(b => (
                    <div key={b.booking_id} style={{
                        display: 'grid', gridTemplateColumns: '1fr 120px',
                        gap: 8, padding: '9px 16px', alignItems: 'center',
                        borderBottom: '1px solid var(--color-border)',
                    }}>
                        <div style={{ minWidth: 0 }}>
                            <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {b.property_name}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 1 }}>
                                {b.guest_name}
                                {b.check_in && <span style={{ marginLeft: 8, color: 'var(--color-text-faint)' }}>In: {b.check_in}</span>}
                                {b.check_out && <span style={{ marginLeft: 8, color: 'var(--color-text-faint)' }}>Out: {b.check_out}</span>}
                            </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                            <span style={{
                                fontSize: 10, fontWeight: 700,
                                padding: '2px 8px', borderRadius: 'var(--radius-full)',
                                background: b.urgency_label?.includes('Active') ? 'rgba(16,185,129,0.12)' :
                                            b.urgency_label?.includes('Arriving') ? 'rgba(59,130,246,0.12)' :
                                            'rgba(245,158,11,0.12)',
                                color: b.urgency_label?.includes('Active') ? '#10b981' :
                                       b.urgency_label?.includes('Arriving') ? '#60a5fa' :
                                       '#f59e0b',
                                whiteSpace: 'nowrap',
                            }}>
                                {b.urgency_label}
                            </span>
                        </div>
                    </div>
                ))
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Operational Summary Strip — 4 chips from real API data
// ---------------------------------------------------------------------------

// Phase 1041: OpsStrip now receives alertCount from parent (shared fetch — no duplicate API call)
function OpsStrip({ alertCount, ops }: {
    alertCount: number;
    ops: { arrivals_today: number; departures_today: number; cleanings_due_today: number } | null;
}) {
    const chips = [
        { label: 'Check-ins',   value: ops?.arrivals_today   ?? '—', color: '#22c55e' },
        { label: 'Check-outs',  value: ops?.departures_today ?? '—', color: '#60a5fa' },
        { label: 'Cleanings',   value: ops?.cleanings_due_today ?? '—', color: '#f59e0b' },
        { label: 'Alerts',      value: alertCount > 0 ? alertCount : '—', color: alertCount > 0 ? '#ef4444' : '#94a3b8' },
    ];

    return (
        <div style={{ display: 'flex', gap: 10, marginBottom: 'var(--space-6)', flexWrap: 'wrap' }}>
            {chips.map(c => (
                <div key={c.label} style={{
                    flex: '1 1 120px',
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: '14px 16px',
                    display: 'flex', flexDirection: 'column', gap: 4,
                    minWidth: 110,
                }}>
                    <span style={{ fontSize: 22, fontWeight: 700, color: c.color, fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
                        {c.value}
                    </span>
                    <span style={{ fontSize: 10, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
                        {c.label}
                    </span>
                </div>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Hub Page — compact command dashboard
// ---------------------------------------------------------------------------

// Phase 1041: shared Hub data fetch — alerts + ops fetched once, passed to children
function useHubData(refreshKey: number) {
    const [alerts, setAlerts] = useState<AlertItem[]>([]);
    const [alertsLoading, setAlertsLoading] = useState(true);
    const [ops, setOps] = useState<{ arrivals_today: number; departures_today: number; cleanings_due_today: number } | null>(null);

    useEffect(() => {
        setAlertsLoading(true);
        apiFetch<{ alerts: AlertItem[] }>('/manager/alerts')
            .then(r => setAlerts(r.alerts || []))
            .catch(() => setAlerts([]))
            .finally(() => setAlertsLoading(false));
        apiFetch<{ arrivals_today: number; departures_today: number; cleanings_due_today: number }>('/operations/today')
            .then(r => setOps(r))
            .catch(() => {});
    }, [refreshKey]);

    return { alerts, alertsLoading, ops };
}

export default function ManagerPage() {
    const [refreshKey, setRefreshKey] = useState(0);
    const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

    // Phase 1041: soft refresh — no window.location.reload()
    const refresh = () => {
        setRefreshKey(k => k + 1);
        setLastRefresh(new Date());
    };

    const { alerts, alertsLoading, ops } = useHubData(refreshKey);
    const alertCount = alerts.filter(a => a.severity === 'critical' || a.severity === 'high').length;

    return (
        <div style={{ maxWidth: 900 }}>
            <style>{`
                @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
            `}</style>

            {/* ── Page header ──────────────────────────────────────────── */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-6)' }}>
                <div>
                    <p style={{ fontSize: 10, color: 'var(--color-text-faint)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
                        Operational Manager · {lastRefresh.toLocaleTimeString()}
                    </p>
                    <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', lineHeight: 1.1, margin: 0 }}>
                        Command <span style={{ color: 'var(--color-primary)' }}>Hub</span>
                    </h1>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 6 }}>
                        What needs your attention right now?
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <a href="/manager/stream" style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                        color: 'var(--color-text-dim)', borderRadius: 'var(--radius-md)',
                        padding: '7px 14px', fontSize: 12, fontWeight: 600,
                        textDecoration: 'none', transition: 'all 0.15s',
                    }}>
                        📡 Open Stream
                    </a>
                    <button
                        id="hub-refresh"
                        onClick={refresh}
                        style={{
                            background: 'var(--color-primary)', color: '#fff', border: 'none',
                            borderRadius: 'var(--radius-md)', padding: '7px 16px',
                            fontSize: 12, fontWeight: 600, cursor: 'pointer',
                        }}
                    >
                        ↺ Refresh
                    </button>
                </div>
            </div>

            {/* ── 1. Morning Briefing — auto-loads on mount (Phase 1041) ── */}
            <MorningBriefingWidget key={refreshKey} />

            {/* ── 2. Operational Summary Strip ─────────────────────────── */}
            <OpsStrip alertCount={alertCount} ops={ops} />

            {/* ── 3. Alert Rail — mounted (Phase 1041 fix) ─────────────── */}
            <AlertRail alerts={alerts} loading={alertsLoading} />

            {/* ── 4. Priority Task Snapshot — max 10 rows ──────────────── */}
            <PriorityTaskSnapshot key={refreshKey} />

            {/* ── 5. Today's Booking Snapshot ──────────────────────────── */}
            <TodayBookingSnapshot key={refreshKey} />

            {/* ── 6. Booking Audit Lookup — demoted tool ───────────────── */}
            <details style={{ marginTop: 'var(--space-4)' }}>
                <summary style={{
                    cursor: 'pointer', fontSize: 12, fontWeight: 600,
                    color: 'var(--color-text-dim)', padding: '8px 4px',
                    listStyle: 'none', display: 'flex', alignItems: 'center', gap: 6,
                }}>
                    <span>🔍</span> Booking Audit Lookup
                    <span style={{ fontSize: 10, color: 'var(--color-text-faint)', fontWeight: 400, marginLeft: 4 }}>(expand)</span>
                </summary>
                <div style={{ marginTop: 12 }}>
                    <BookingAuditLookup />
                </div>
            </details>

            {/* Footer */}
            <div style={{
                marginTop: 'var(--space-8)',
                paddingTop: 'var(--space-4)',
                borderTop: '1px solid var(--color-border)',
                fontSize: 11, color: 'var(--color-text-faint)',
                display: 'flex', justifyContent: 'space-between',
            }}>
                <span>Domaniqo — Command Hub · Phase 1041</span>
                <span>Full operational view → <a href="/manager/stream" style={{ color: 'var(--color-primary)', textDecoration: 'none' }}>Stream</a></span>
            </div>
        </div>
    );
}
