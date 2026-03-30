'use client';

/**
 * Phase 158 — Manager Booking List View + Strategic Pivot UI
 * Route: /bookings
 *
 * Filterable booking list for operations managers.
 * Gap 3: "+ Add Booking" modal for manual booking creation
 * Gap 4: "+ iCal Feed" modal for iCal feed management
 *
 * WHO creates bookings here:
 *   - Manager / Admin — the primary user role
 *   - NOT cleaners, NOT workers
 *
 * ENTRY POINTS:
 *   1. "+ Add Booking" button in header → opens manual booking form modal
 *   2. "📡 iCal Feed" button in header → opens iCal feed management modal
 *
 * PERSISTENCE:
 *   Add Booking → POST /bookings/manual → writes to `bookings` table + auto-creates tasks
 *   iCal Feed  → POST /integrations/ical/connect → writes to `ical_connections` + `booking_state`
 *
 * REFLECTION:
 *   After either action succeeds, the booking list auto-refreshes so
 *   new bookings appear immediately in the table below.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, ApiError } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Booking {
    booking_id: string;
    source: string | null;
    reservation_ref: string | null;
    property_id: string | null;
    status: string | null;
    check_in: string | null;
    check_out: string | null;
    guest_name?: string | null;
    version: number | null;
    created_at: string | null;
    updated_at: string | null;
    checked_in_at?: string | null;
    checked_out_at?: string | null;
    is_calendar_block?: boolean;
}

interface PropertyOption {
    property_id: string;
    display_name: string;
    status: string;
}

// Map of property_id → display_name for fast lookup in the table
type PropertyMap = Record<string, string>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Operational status derivation
// ---------------------------------------------------------------------------
//
// The DB `status` column is the SOURCE-LAYER status (active/confirmed/checked_in
// checked_out/canceled). This is NOT the operational status.
//
// We derive a normalized OPERATIONAL status from:
//   db_status + check_in date + check_out date + checked_in_at + checked_out_at
//
// This is display-only. The DB is never mutated by this function.

type OpStatus =
    | 'in_stay'
    | 'checkout_today'
    | 'overdue_checkout'
    | 'checking_in_today'
    | 'upcoming'
    | 'completed'
    | 'admin_closed'
    | 'cancelled'
    | 'unknown';

function deriveOperationalStatus(b: Booking): OpStatus {
    const raw = (b.status ?? '').toLowerCase();
    if (raw === 'canceled' || raw === 'cancelled') return 'cancelled';
    if (raw === 'admin_closed') return 'admin_closed';
    if (raw === 'checked_out' || b.checked_out_at) return 'completed';

    // Phase 1027c — always use UTC date for comparisons.
    // (Touches deriveOperationalStatus logic originally introduced in Phase 158.
    //  Phase 888 is unrelated — this is the current active operational truth fix.)
    // Using `new Date()` + setHours(0,0,0,0) produces the LOCAL date which shifts
    // with the viewer's timezone. A Bangkok admin viewing at 23:59 Bangkok time
    // is already the next UTC day, causing stale "Checkout Today" labels.
    // Canonical rule: all date comparisons use UTC YYYY-MM-DD.
    const nowUtc = new Date();
    const todayStr = `${nowUtc.getUTCFullYear()}-${String(nowUtc.getUTCMonth() + 1).padStart(2, '0')}-${String(nowUtc.getUTCDate()).padStart(2, '0')}`;

    const checkIn  = b.check_in  ?? null;
    const checkOut = b.check_out ?? null;

    // checked_in = worker performed check-in, guest is in-stay
    if (raw === 'checked_in') {
        if (checkOut === todayStr) return 'checkout_today';
        if (checkOut && checkOut < todayStr) return 'overdue_checkout'; // missed checkout
        return 'in_stay';
    }

    // active (OTA iCal) or confirmed (manual) — reservation layer, not serviced yet
    if (raw === 'active' || raw === 'confirmed') {
        if (!checkOut) return 'upcoming';
        if (checkOut < todayStr) return 'overdue_checkout'; // past checkout, no service
        if (checkOut === todayStr) return 'checkout_today';  // due today
        if (checkIn === todayStr) return 'checking_in_today';
        return 'upcoming';
    }

    return 'unknown';
}


const OP_STATUS_CONFIG: Record<OpStatus, { label: string; bg: string; color: string; border?: string; desc: string }> = {
    in_stay:           { label: '🟢 In Stay',       bg: 'rgba(16,185,129,0.12)',  color: 'var(--color-ok)',           desc: 'Worker has checked the guest in. Guest is currently staying.' },
    checkout_today:    { label: '⏰ Checkout Today', bg: 'rgba(99,102,241,0.12)', color: 'var(--color-primary)',      desc: 'Checkout date is today. Awaiting worker checkout action.' },
    overdue_checkout:  { label: '⚠ Overdue',         bg: 'rgba(245,158,11,0.14)', color: '#b45309', border: '1px solid rgba(245,158,11,0.4)', desc: 'Checkout date has passed with no worker checkout recorded. Needs resolution.' },
    checking_in_today: { label: '📥 Arriving Today', bg: 'rgba(99,102,241,0.12)', color: 'var(--color-primary)',      desc: 'Check-in date is today. Guest expected to arrive.' },
    upcoming:          { label: 'Upcoming',           bg: 'rgba(100,100,100,0.08)', color: 'var(--color-text-dim)',   desc: 'Future confirmed reservation. No action needed yet.' },
    completed:         { label: 'Checked Out',        bg: 'rgba(100,100,100,0.08)', color: 'var(--color-muted)',      desc: 'Worker has completed the checkout. Stay is fully closed.' },
    admin_closed:      { label: '🔒 Admin Closed',   bg: 'rgba(100,100,100,0.08)', color: 'var(--color-text-faint)', border: '1px solid var(--color-border)', desc: 'Administratively resolved by an admin. No worker checkout was performed. No settlement or tasks were triggered.' },
    cancelled:         { label: 'Cancelled',          bg: 'rgba(239,68,68,0.10)', color: 'var(--color-danger)',       desc: 'Booking was cancelled by the OTA, guest, or admin.' },
    unknown:           { label: 'Unknown',            bg: 'rgba(100,100,100,0.08)', color: 'var(--color-muted)',      desc: 'Status could not be derived. Contact support if this persists.' },
};

// ---------------------------------------------------------------------------
// Status Info Popover
// ---------------------------------------------------------------------------

function StatusInfoPopover() {
    const [open, setOpen] = useState(false);

    // Close on Escape key
    useEffect(() => {
        if (!open) return;
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
        document.addEventListener('keydown', handler);
        return () => document.removeEventListener('keydown', handler);
    }, [open]);

    return (
        <>
            <button
                id="status-info-btn"
                onClick={() => setOpen(o => !o)}
                aria-expanded={open}
                title="What do these statuses mean?"
                style={{
                    background: open ? 'var(--color-surface-3)' : 'var(--color-surface-2)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-full)', color: 'var(--color-text-dim)',
                    fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                    padding: '3px 10px', display: 'flex', alignItems: 'center', gap: 4,
                    transition: 'background var(--transition-fast)',
                }}
            >ⓘ Status Guide</button>

            {open && (
                /* Full-viewport backdrop — clicking it closes the modal */
                <div
                    onClick={() => setOpen(false)}
                    style={{
                        position: 'fixed', inset: 0, zIndex: 1000,
                        background: 'rgba(0,0,0,0.45)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        padding: '16px',          /* gutters so card never touches screen edges */
                    }}
                >
                    {/* Card — stopPropagation so clicking inside doesn't close */}
                    <div
                        onClick={e => e.stopPropagation()}
                        role="dialog"
                        aria-modal="true"
                        aria-label="Booking Status Guide"
                        style={{
                            background: 'var(--color-surface)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-xl)',
                            width: '100%', maxWidth: 480,
                            /* scrollable if viewport is short */
                            maxHeight: 'calc(100vh - 48px)',
                            overflowY: 'auto',
                            boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
                            padding: 'var(--space-5)',
                        }}
                    >
                        {/* Header */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
                            <span style={{ fontWeight: 700, fontSize: 'var(--text-base)', color: 'var(--color-text)' }}>
                                Booking Status Guide
                            </span>
                            <button
                                id="status-info-close"
                                onClick={() => setOpen(false)}
                                aria-label="Close"
                                style={{
                                    background: 'none', border: 'none', cursor: 'pointer',
                                    color: 'var(--color-text-dim)', fontSize: '1.2rem', lineHeight: 1,
                                    padding: '2px 6px', borderRadius: 'var(--radius-md)',
                                }}
                            >✕</button>
                        </div>

                        {/* Status entries */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {(Object.entries(OP_STATUS_CONFIG) as [OpStatus, typeof OP_STATUS_CONFIG[OpStatus]][]).map(([key, cfg]) => (
                                <div key={key} style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
                                    <span style={{
                                        fontSize: 'var(--text-xs)', fontWeight: 600, whiteSpace: 'nowrap',
                                        background: cfg.bg, color: cfg.color, border: cfg.border,
                                        borderRadius: 'var(--radius-full)', padding: '3px 10px',
                                        flexShrink: 0, minWidth: 110, textAlign: 'center',
                                    }}>{cfg.label}</span>
                                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', lineHeight: 1.55 }}>{cfg.desc}</span>
                                </div>
                            ))}
                        </div>

                        {/* Footer */}
                        <div style={{
                            marginTop: 'var(--space-4)', paddingTop: 'var(--space-3)',
                            borderTop: '1px solid var(--color-border)',
                            fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', lineHeight: 1.5,
                        }}>
                            Statuses are derived in real-time from reservation dates and worker actions.
                            Calendar blocks are shown separately and never receive operational status chips.
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

const OP_STATUS_PRIORITY: Record<OpStatus, number> = {
    in_stay: 1, checkout_today: 2, overdue_checkout: 3,
    checking_in_today: 4, upcoming: 5, completed: 6, admin_closed: 6, cancelled: 7, unknown: 8,
};

function operationalChip(b: Booking) {
    const op = deriveOperationalStatus(b);
    const c = OP_STATUS_CONFIG[op];
    return (
        <span style={{
            fontSize: 'var(--text-xs)', fontWeight: 600,
            background: c.bg, color: c.color,
            borderRadius: 'var(--radius-full)',
            padding: '2px 8px',
            border: c.border,
        }}>
            {c.label}
        </span>
    );
}


function sourceChip(source: string | null) {
    if (!source) return <span style={{ color: 'var(--color-text-faint)', fontSize: 'var(--text-xs)' }}>—</span>;
    const colours: Record<string, string> = {
        airbnb: '#FF5A5F', bookingcom: '#003580', expedia: '#00355F',
        vrbo: '#3D67FF', hotelbeds: '#0099CC', tripadvisor: '#34E0A1',
        despegar: '#1E9FD6', direct: '#6366f1', self_use: '#8b5cf6',
        owner_use: '#d946ef', maintenance_block: '#f59e0b', ical: '#10b981',
    };
    const col = colours[source.toLowerCase()] ?? 'var(--color-primary)';
    return (
        <span style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            color: '#fff',
            background: col,
            borderRadius: 'var(--radius-full)',
            padding: '2px 8px',
        }}>
            {source}
        </span>
    );
}

function fmtDate(d: string | null): string {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
    catch { return d; }
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const inputStyle: React.CSSProperties = {
    background: 'var(--color-bg)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    color: 'var(--color-text)',
    padding: 'var(--space-2) var(--space-3)',
    fontSize: 'var(--text-sm)',
    fontFamily: 'var(--font-sans)',
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box' as const,
};

const labelStyle: React.CSSProperties = {
    fontSize: 'var(--text-xs)',
    fontWeight: 600,
    color: 'var(--color-text-dim)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    marginBottom: '4px',
    display: 'block',
};

const btnPrimary: React.CSSProperties = {
    background: 'var(--color-primary)',
    color: '#fff',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-2) var(--space-5)',
    fontSize: 'var(--text-sm)',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
};

const btnSecondary: React.CSSProperties = {
    background: 'transparent',
    color: 'var(--color-text-dim)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-2) var(--space-4)',
    fontSize: 'var(--text-sm)',
    cursor: 'pointer',
};

// ---------------------------------------------------------------------------
// Modal overlay
// ---------------------------------------------------------------------------

function ModalOverlay({ open, onClose, title, children }: {
    open: boolean; onClose: () => void; title: string;
    children: React.ReactNode;
}) {
    if (!open) return null;
    return (
        <div
            id="modal-overlay"
            onClick={onClose}
            style={{
                position: 'fixed', inset: 0, zIndex: 1000,
                background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 'var(--space-4)',
            }}
        >
            <div
                onClick={e => e.stopPropagation()}
                style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-lg)',
                    maxWidth: 520, width: '100%',
                    maxHeight: '85vh', overflowY: 'auto',
                    boxShadow: '0 25px 50px -12px rgba(0,0,0,0.4)',
                }}
            >
                {/* Modal header */}
                <div style={{
                    padding: 'var(--space-5) var(--space-5) var(--space-3)',
                    borderBottom: '1px solid var(--color-border)',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                    <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, margin: 0 }}>{title}</h2>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'transparent', border: 'none', color: 'var(--color-text-dim)',
                            cursor: 'pointer', fontSize: '1.2rem', padding: 4,
                        }}
                    >✕</button>
                </div>
                <div style={{ padding: 'var(--space-5)' }}>
                    {children}
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Status banners
// ---------------------------------------------------------------------------

function SuccessBanner({ message, onDismiss }: { message: string; onDismiss: () => void }) {
    return (
        <div style={{
            background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.3)',
            borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)',
            fontSize: 'var(--text-sm)', color: 'var(--color-ok)',
            marginBottom: 'var(--space-4)', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
            <span>✅ {message}</span>
            <button onClick={onDismiss} style={{ background: 'transparent', border: 'none', color: 'var(--color-ok)', cursor: 'pointer', fontWeight: 700 }}>✕</button>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Gap 3: Add Manual Booking Modal
// ---------------------------------------------------------------------------

const BOOKING_SOURCES = [
    { value: 'direct', label: '📞 Direct Booking', desc: 'Phone, email, walk-in' },
    { value: 'self_use', label: '🏡 Self Use', desc: 'Owner personal stay' },
    { value: 'owner_use', label: '👤 Owner Use', desc: 'Owner guest stay' },
    { value: 'maintenance_block', label: '🔧 Maintenance Block', desc: 'Block dates for repairs' },
];

const TASK_OPT_OUTS = [
    { value: 'checkin', label: 'Check-in prep' },
    { value: 'cleaning', label: 'Cleaning' },
    { value: 'checkout', label: 'Check-out verify' },
];

function AddBookingModal({ open, onClose, onSuccess, properties }: {
    open: boolean; onClose: () => void;
    onSuccess: (msg: string) => void;
    properties: PropertyOption[];
}) {
    const [form, setForm] = useState({
        property_id: '', check_in: '', check_out: '',
        guest_name: '', booking_source: 'direct',
        notes: '', number_of_guests: 1,
        tasks_opt_out: [] as string[],
    });
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Date validation
    const dateError = form.check_in && form.check_out && form.check_in >= form.check_out
        ? 'Check-out must be after check-in' : null;

    // Guest name required except maintenance_block
    const nameRequired = form.booking_source !== 'maintenance_block';

    const canSubmit = form.property_id && form.check_in && form.check_out
        && !dateError && (!nameRequired || form.guest_name.trim()) && !submitting;

    const handleSubmit = async () => {
        if (!canSubmit) return;
        setSubmitting(true); setError(null);
        try {
            const res = await api.createManualBooking({
                property_id: form.property_id,
                check_in: form.check_in,
                check_out: form.check_out,
                guest_name: form.guest_name.trim(),
                booking_source: form.booking_source,
                notes: form.notes.trim() || undefined,
                number_of_guests: form.number_of_guests,
                tasks_opt_out: form.tasks_opt_out.length ? form.tasks_opt_out : undefined,
            });
            const tasks = res.tasks_created?.length
                ? ` · Tasks: ${res.tasks_created.join(', ')}`
                : '';
            onSuccess(`Booking ${res.booking_id} created${tasks}`);
            // Reset form
            setForm({ property_id: '', check_in: '', check_out: '', guest_name: '', booking_source: 'direct', notes: '', number_of_guests: 1, tasks_opt_out: [] });
            onClose();
        } catch (err: unknown) {
            if (err instanceof ApiError) {
                setError((err.body as any)?.detail || `API ${err.status}: ${err.code}`);
            } else {
                setError(err instanceof Error ? err.message : 'Failed to create booking');
            }
        } finally {
            setSubmitting(false);
        }
    };

    const toggleOptOut = (val: string) => {
        setForm(f => ({
            ...f,
            tasks_opt_out: f.tasks_opt_out.includes(val)
                ? f.tasks_opt_out.filter(v => v !== val)
                : [...f.tasks_opt_out, val],
        }));
    };

    return (
        <ModalOverlay open={open} onClose={onClose} title="Add Booking">
            {/* Error banner */}
            {error && (
                <div style={{
                    background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)',
                    color: 'var(--color-danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)',
                }}>
                    ⚠ {error}
                </div>
            )}

            {/* Property selector */}
            <div style={{ marginBottom: 'var(--space-4)' }}>
                <label style={labelStyle}>Property *</label>
                <select
                    id="booking-property"
                    value={form.property_id}
                    onChange={e => setForm(f => ({ ...f, property_id: e.target.value }))}
                    style={inputStyle}
                >
                    <option value="">Select property…</option>
                    {properties.map(p => (
                        <option key={p.property_id} value={p.property_id}>
                            {p.display_name || p.property_id}
                        </option>
                    ))}
                </select>
            </div>

            {/* Dates */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                <div>
                    <label style={labelStyle}>Check-in *</label>
                    <input id="booking-checkin" type="date" value={form.check_in}
                        onChange={e => setForm(f => ({ ...f, check_in: e.target.value }))}
                        style={{ ...inputStyle }} />
                </div>
                <div>
                    <label style={labelStyle}>Check-out *</label>
                    <input id="booking-checkout" type="date" value={form.check_out}
                        onChange={e => setForm(f => ({ ...f, check_out: e.target.value }))}
                        style={{ ...inputStyle }} />
                </div>
            </div>
            {dateError && (
                <div style={{ color: 'var(--color-danger)', fontSize: 'var(--text-xs)', marginTop: '-12px', marginBottom: 'var(--space-3)' }}>
                    ⚠ {dateError}
                </div>
            )}

            {/* Guest name */}
            <div style={{ marginBottom: 'var(--space-4)' }}>
                <label style={labelStyle}>Guest Name {nameRequired ? '*' : '(optional)'}</label>
                <input
                    id="booking-guest"
                    placeholder={form.booking_source === 'maintenance_block' ? 'N/A for maintenance' : 'Guest full name'}
                    value={form.guest_name}
                    onChange={e => setForm(f => ({ ...f, guest_name: e.target.value }))}
                    style={inputStyle}
                />
            </div>

            {/* Source */}
            <div style={{ marginBottom: 'var(--space-4)' }}>
                <label style={labelStyle}>Booking Source</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
                    {BOOKING_SOURCES.map(s => (
                        <button
                            key={s.value}
                            onClick={() => setForm(f => ({ ...f, booking_source: s.value }))}
                            style={{
                                background: form.booking_source === s.value
                                    ? 'rgba(99,102,241,0.15)' : 'var(--color-bg)',
                                border: `1px solid ${form.booking_source === s.value
                                    ? 'var(--color-primary)' : 'var(--color-border)'}`,
                                borderRadius: 'var(--radius-md)',
                                padding: 'var(--space-2) var(--space-3)',
                                textAlign: 'left' as const,
                                cursor: 'pointer',
                                transition: 'all var(--transition-fast)',
                            }}
                        >
                            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{s.label}</div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>{s.desc}</div>
                        </button>
                    ))}
                </div>
            </div>

            {/* Guests count */}
            <div style={{ marginBottom: 'var(--space-4)' }}>
                <label style={labelStyle}>Number of guests</label>
                <input
                    id="booking-guests-count"
                    type="number" min={1} max={50}
                    value={form.number_of_guests}
                    onChange={e => setForm(f => ({ ...f, number_of_guests: parseInt(e.target.value) || 1 }))}
                    style={{ ...inputStyle, maxWidth: 100 }}
                />
            </div>

            {/* Task opt-outs (only visible for self_use / owner_use) */}
            {(form.booking_source === 'self_use' || form.booking_source === 'owner_use') && (
                <div style={{ marginBottom: 'var(--space-4)' }}>
                    <label style={labelStyle}>Skip tasks (optional)</label>
                    <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                        {TASK_OPT_OUTS.map(t => (
                            <label key={t.value} style={{
                                display: 'flex', alignItems: 'center', gap: 6,
                                fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', cursor: 'pointer',
                            }}>
                                <input
                                    type="checkbox"
                                    checked={form.tasks_opt_out.includes(t.value)}
                                    onChange={() => toggleOptOut(t.value)}
                                />
                                {t.label}
                            </label>
                        ))}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                        Skipped tasks will not be auto-created for this booking
                    </div>
                </div>
            )}

            {/* Notes */}
            <div style={{ marginBottom: 'var(--space-5)' }}>
                <label style={labelStyle}>Notes (optional)</label>
                <textarea
                    id="booking-notes"
                    value={form.notes}
                    onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                    placeholder="Any special instructions…"
                    rows={2}
                    style={{ ...inputStyle, resize: 'vertical' as const }}
                />
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end' }}>
                <button onClick={onClose} style={btnSecondary}>Cancel</button>
                <button
                    id="booking-submit"
                    onClick={handleSubmit}
                    disabled={!canSubmit}
                    style={{
                        ...btnPrimary,
                        opacity: canSubmit ? 1 : 0.5,
                        cursor: canSubmit ? 'pointer' : 'not-allowed',
                    }}
                >
                    {submitting ? '⟳ Creating…' : '✓ Create Booking'}
                </button>
            </div>
        </ModalOverlay>
    );
}

// ---------------------------------------------------------------------------
// Gap 4: iCal Feed Manager Modal
// ---------------------------------------------------------------------------

function IcalFeedModal({ open, onClose, onSuccess, properties }: {
    open: boolean; onClose: () => void;
    onSuccess: (msg: string) => void;
    properties: PropertyOption[];
}) {
    const [form, setForm] = useState({ property_id: '', ical_url: '' });
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<{ connection_id: string; bookings_created: number; status: string } | null>(null);

    // URL validation
    const urlValid = (() => {
        if (!form.ical_url) return null; // no input yet
        try {
            const u = new URL(form.ical_url);
            return u.protocol === 'https:' || u.protocol === 'http:';
        } catch { return false; }
    })();

    const urlWarning = urlValid === false ? 'Please enter a valid URL (https://…)' : null;

    const canSubmit = form.property_id && form.ical_url.trim() && urlValid && !submitting;

    const handleConnect = async () => {
        if (!canSubmit) return;
        setSubmitting(true); setError(null); setResult(null);
        try {
            const res = await api.connectIcalFeed({
                property_id: form.property_id,
                ical_url: form.ical_url.trim(),
            });
            setResult(res);
            if (res.bookings_created > 0) {
                onSuccess(`iCal connected: ${res.bookings_created} bookings imported for ${form.property_id}`);
            } else {
                onSuccess(`iCal connected (no bookings found in feed yet)`);
            }
        } catch (err: unknown) {
            if (err instanceof ApiError) {
                setError((err.body as any)?.detail || `API ${err.status}: ${err.code}`);
            } else {
                setError(err instanceof Error ? err.message : 'Failed to connect iCal feed');
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <ModalOverlay open={open} onClose={onClose} title="📡 Connect iCal Feed">
            {/* Explainer */}
            <div style={{
                background: 'rgba(99,102,241,0.08)', borderRadius: 'var(--radius-md)',
                padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-4)',
                fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)',
                lineHeight: 1.5,
            }}>
                Paste your iCal feed URL from Airbnb, Booking.com, or any calendar service.
                The system will fetch bookings immediately and re-sync every 15 minutes automatically.
            </div>

            {/* Error */}
            {error && (
                <div style={{
                    background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)',
                    color: 'var(--color-danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)',
                }}>
                    ⚠ {error}
                </div>
            )}

            {/* Success result */}
            {result && (
                <div style={{
                    background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)',
                    marginBottom: 'var(--space-4)', fontSize: 'var(--text-sm)',
                }}>
                    <div style={{ fontWeight: 600, color: 'var(--color-ok)', marginBottom: 4 }}>
                        ✅ Feed Connected
                    </div>
                    <div style={{ color: 'var(--color-text-dim)', display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span>Connection ID: <code style={{ color: 'var(--color-text)' }}>{result.connection_id}</code></span>
                        <span>Bookings imported: <strong style={{ color: result.bookings_created > 0 ? 'var(--color-ok)' : 'var(--color-text-faint)' }}>
                            {result.bookings_created}
                        </strong></span>
                        <span>Status: <strong style={{ color: 'var(--color-ok)' }}>{result.status}</strong></span>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                            Auto re-sync every 15 minutes ·
                            {result.bookings_created === 0 ? ' Feed may be empty or have no upcoming bookings' : ' Bookings are now visible in the list below'}
                        </span>
                    </div>
                </div>
            )}

            {/* Property selector */}
            <div style={{ marginBottom: 'var(--space-4)' }}>
                <label style={labelStyle}>Property *</label>
                <select
                    id="ical-property"
                    value={form.property_id}
                    onChange={e => setForm(f => ({ ...f, property_id: e.target.value }))}
                    style={inputStyle}
                >
                    <option value="">Select property…</option>
                    {properties.map(p => (
                        <option key={p.property_id} value={p.property_id}>
                            {p.display_name || p.property_id}
                        </option>
                    ))}
                </select>
            </div>

            {/* iCal URL */}
            <div style={{ marginBottom: 'var(--space-4)' }}>
                <label style={labelStyle}>iCal Feed URL *</label>
                <input
                    id="ical-url"
                    placeholder="https://www.airbnb.com/calendar/ical/..."
                    value={form.ical_url}
                    onChange={e => setForm(f => ({ ...f, ical_url: e.target.value }))}
                    style={{
                        ...inputStyle,
                        borderColor: urlWarning ? 'var(--color-danger)' : 'var(--color-border)',
                    }}
                />
                {urlWarning && (
                    <div style={{ color: 'var(--color-danger)', fontSize: 'var(--text-xs)', marginTop: 4 }}>
                        ⚠ {urlWarning}
                    </div>
                )}
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                    Find this in your OTA dashboard → Calendar → Export / Sync → Copy iCal URL
                </div>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end' }}>
                <button onClick={onClose} style={btnSecondary}>
                    {result ? 'Done' : 'Cancel'}
                </button>
                {!result && (
                    <button
                        id="ical-submit"
                        onClick={handleConnect}
                        disabled={!canSubmit}
                        style={{
                            ...btnPrimary,
                            opacity: canSubmit ? 1 : 0.5,
                            cursor: canSubmit ? 'pointer' : 'not-allowed',
                        }}
                    >
                        {submitting ? '⟳ Connecting…' : '📡 Connect Feed'}
                    </button>
                )}
            </div>
        </ModalOverlay>
    );
}

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

const STATUS_OPTIONS = [
    { value: '', label: 'All statuses' },
    { value: 'active', label: 'Active' },
    { value: 'confirmed', label: 'Confirmed' },
    { value: 'canceled', label: 'Canceled' },
];

const SOURCE_OPTIONS = [
    '', 'airbnb', 'bookingcom', 'ical', 'direct', 'self_use', 'owner_use',
    'maintenance_block', 'expedia', 'vrbo',
];

interface Filters {
    property_id: string;
    status: string;
    source: string;
    check_in_from: string;
    check_in_to: string;
}

// ---------------------------------------------------------------------------
// Property cell — shows code + display name
// ---------------------------------------------------------------------------

function PropertyCell({ propertyId, propertyMap }: { propertyId: string | null; propertyMap: PropertyMap }) {
    if (!propertyId) return <span style={{ color: 'var(--color-text-faint)' }}>—</span>;
    const name = propertyMap[propertyId];
    return (
        <div>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text)', fontWeight: 600 }}>{propertyId}</span>
            {name && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 160 }} title={name}>{name}</div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Property Autocomplete Filter
// ---------------------------------------------------------------------------

function PropertyAutocompleteFilter({
    value, onChange, properties,
}: { value: string; onChange: (v: string) => void; properties: PropertyOption[] }) {
    const [query, setQuery] = useState(value);
    const [open, setOpen] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    // Sync external value changes
    useEffect(() => { setQuery(value); }, [value]);

    const normalised = query.toLowerCase().replace(/[^a-z0-9]/g, '');
    const suggestions = properties.filter(p => {
        const code = p.property_id.toLowerCase().replace(/[^a-z0-9]/g, '');
        const name = (p.display_name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
        return code.includes(normalised) || name.includes(normalised);
    }).slice(0, 8);

    const select = (pid: string) => {
        setQuery(pid);
        onChange(pid);
        setOpen(false);
    };

    const handleChange = (v: string) => {
        setQuery(v);
        setOpen(true);
        if (v === '') onChange('');
    };

    const handleBlur = () => {
        // small delay so click on suggestion registers first
        setTimeout(() => setOpen(false), 150);
        // if not an exact match, clear the filter
        const exact = properties.find(p => p.property_id === query);
        if (!exact && query !== '') { setQuery(''); onChange(''); }
    };

    return (
        <div style={{ position: 'relative', flex: '1 1 160px', minWidth: 120 }}>
            <input
                id="filter-property"
                ref={inputRef}
                value={query}
                placeholder="Property (code or name)"
                onChange={e => handleChange(e.target.value)}
                onFocus={() => setOpen(true)}
                onBlur={handleBlur}
                autoComplete="off"
                style={{ ...inputStyle, width: '100%', boxSizing: 'border-box' }}
            />
            {open && suggestions.length > 0 && (
                <div style={{
                    position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 200,
                    background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)', marginTop: 2,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.4)', overflow: 'hidden',
                }}>
                    {suggestions.map(p => (
                        <div
                            key={p.property_id}
                            onMouseDown={() => select(p.property_id)}
                            style={{
                                padding: 'var(--space-2) var(--space-3)', cursor: 'pointer',
                                borderBottom: '1px solid var(--color-border)',
                                transition: 'background var(--transition-fast)',
                            }}
                            onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                        >
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-primary)' }}>{p.property_id}</span>
                            {p.display_name && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginLeft: 8 }}>{p.display_name}</span>}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Booking row
// ---------------------------------------------------------------------------

function BookingRow({ b, propertyMap, onClick }: { b: Booking; propertyMap: PropertyMap; onClick: () => void }) {
    return (
        <tr
            onClick={onClick}
            style={{
                borderBottom: '1px solid var(--color-border)',
                cursor: 'pointer',
                transition: 'background var(--transition-fast)',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
        >
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                {b.booking_id.length > 12 ? b.booking_id.slice(0, 12) + '…' : b.booking_id}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)' }}>
                {sourceChip(b.source)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                {b.guest_name || '—'}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)' }}>
                <PropertyCell propertyId={b.property_id} propertyMap={propertyMap} />
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-sm)' }}>
                {fmtDate(b.check_in)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-sm)' }}>
                {fmtDate(b.check_out)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)' }}>
                {operationalChip(b)}
            </td>
        </tr>
    );
}

// ---------------------------------------------------------------------------
// Calendar Block row (separate surface, no operational status)
// ---------------------------------------------------------------------------

function CalendarBlockRow({ b, propertyMap }: { b: Booking; propertyMap: PropertyMap }) {
    return (
        <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                {b.booking_id.length > 12 ? b.booking_id.slice(0, 12) + '…' : b.booking_id}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)' }}>
                {sourceChip(b.source)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', fontStyle: 'italic' }}>
                {b.guest_name || '—'}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)' }}>
                <PropertyCell propertyId={b.property_id} propertyMap={propertyMap} />
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-sm)' }}>
                {fmtDate(b.check_in)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-sm)' }}>
                {fmtDate(b.check_out)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)' }}>
                <span style={{
                    fontSize: 'var(--text-xs)', fontWeight: 600,
                    background: 'rgba(100,100,116,0.12)', color: 'var(--color-text-dim)',
                    borderRadius: 'var(--radius-full)', padding: '2px 8px',
                    border: '1px solid var(--color-border)',
                }}>🚫 Blocked</span>
            </td>
        </tr>
    );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState({ onAddBooking, onAddIcal }: { onAddBooking: () => void; onAddIcal: () => void }) {
    return (
        <tr><td colSpan={7} style={{ padding: 'var(--space-16)', textAlign: 'center', color: 'var(--color-text-dim)' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: 'var(--space-3)' }}>📋</div>
            <div style={{ fontWeight: 700, fontSize: 'var(--text-lg)', marginBottom: 'var(--space-2)' }}>No bookings yet</div>
            <div style={{ fontSize: 'var(--text-sm)', marginBottom: 'var(--space-5)', maxWidth: 360, margin: '0 auto', color: 'var(--color-text-faint)' }}>
                Get started by adding a booking manually or connecting an iCal feed from your OTA.
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'center', marginTop: 'var(--space-4)' }}>
                <button onClick={onAddBooking} style={btnPrimary}>+ Add Booking</button>
                <button onClick={onAddIcal} style={{ ...btnPrimary, background: 'var(--color-olive)' }}>📡 iCal Feed</button>
            </div>
        </td></tr>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function BookingsPage() {
    const [bookings, setBookings] = useState<Booking[]>([]);
    const [blocks, setBlocks] = useState<Booking[]>([]);
    const [loading, setLoading] = useState(true);
    const [blocksLoading, setBlocksLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
    const [liveEvent, setLiveEvent] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);
    const [tab, setTab] = useState<'bookings' | 'blocks'>('bookings');
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const [filters, setFilters] = useState<Filters>({
        property_id: '', status: '', source: '', check_in_from: '', check_in_to: '',
    });
    const [showAddBooking, setShowAddBooking] = useState(false);
    const [showIcalFeed, setShowIcalFeed] = useState(false);
    const [properties, setProperties] = useState<PropertyOption[]>([]);
    const [propertyMap, setPropertyMap] = useState<PropertyMap>({});

    useEffect(() => {
        api.listProperties().then(res => {
            const props = res.properties ?? [];
            setProperties(props);
            setPropertyMap(Object.fromEntries(props.map(p => [p.property_id, p.display_name || p.property_id])));
        }).catch(() => {});
    }, []);

    const loadBookings = useCallback(async () => {
        setLoading(true); setError(null);
        try {
            const res = await api.getBookings({
                property_id: filters.property_id || undefined,
                status: filters.status || undefined,
                source: filters.source || undefined,
                check_in_from: filters.check_in_from || undefined,
                check_in_to: filters.check_in_to || undefined,
            });
            const list = res.bookings ?? [];
            list.sort((a: Booking, b: Booking) => {
                const pa = OP_STATUS_PRIORITY[deriveOperationalStatus(a)];
                const pb = OP_STATUS_PRIORITY[deriveOperationalStatus(b)];
                if (pa !== pb) return pa - pb;
                const da = a.check_out ?? a.check_in ?? '';
                const db = b.check_out ?? b.check_in ?? '';
                return da < db ? -1 : da > db ? 1 : 0;
            });
            setBookings(list);
            setLastRefresh(new Date());
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to load bookings');
        } finally {
            setLoading(false);
        }
    }, [filters]);

    const loadBlocks = useCallback(async () => {
        setBlocksLoading(true);
        try {
            const res = await api.getCalendarBlocks({ property_id: filters.property_id || undefined });
            setBlocks(res.bookings ?? []);
        } catch { /* silent */ } finally {
            setBlocksLoading(false);
        }
    }, [filters.property_id]);

    useEffect(() => { loadBookings(); }, [loadBookings]);
    useEffect(() => { loadBlocks(); }, [loadBlocks]);

    useEffect(() => {
        timerRef.current = setInterval(() => { loadBookings(); loadBlocks(); }, 60_000);
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [loadBookings, loadBlocks]);

    useEffect(() => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') ?? '' : '';
        const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
        const es = new EventSource(`${baseUrl}/events/stream?channels=bookings&token=${token}`);
        es.onmessage = (e) => {
            try {
                const evt = JSON.parse(e.data);
                if (evt.channel === 'bookings') {
                    setLiveEvent(`${evt.type}: ${evt.booking_id ?? 'unknown'}`);
                    setTimeout(() => { loadBookings(); loadBlocks(); }, 1000);
                    setTimeout(() => setLiveEvent(null), 5000);
                }
            } catch { /* ignore */ }
        };
        return () => es.close();
    }, [loadBookings, loadBlocks]);

    return (
        <div>
            <style>{`
        @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }
        select option { background: var(--color-surface); }
      `}</style>

            <AddBookingModal open={showAddBooking} onClose={() => setShowAddBooking(false)}
                onSuccess={(msg) => { setSuccessMsg(msg); loadBookings(); setTimeout(() => setSuccessMsg(null), 8000); }}
                properties={properties} />
            <IcalFeedModal open={showIcalFeed} onClose={() => { setShowIcalFeed(false); loadBookings(); loadBlocks(); }}
                onSuccess={(msg) => { setSuccessMsg(msg); loadBookings(); loadBlocks(); setTimeout(() => setSuccessMsg(null), 8000); }}
                properties={properties} />

            <div style={{ marginBottom: 'var(--space-4)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
                <div>
                    <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, letterSpacing: '-0.02em' }}>Bookings</h1>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-1)' }}>
                        {loading ? 'Loading…' : `${bookings.length} booking${bookings.length !== 1 ? 's' : ''}`}
                        {blocks.length > 0 && <span style={{ marginLeft: 8, color: 'var(--color-text-faint)' }}>· {blocks.length} calendar block{blocks.length !== 1 ? 's' : ''}</span>}
                        {lastRefresh && <span style={{ marginLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>· Updated {lastRefresh.toLocaleTimeString()}</span>}
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                    <button id="btn-add-booking" onClick={() => setShowAddBooking(true)} style={{ ...btnPrimary, display: 'flex', alignItems: 'center', gap: 6 }}>+ Add Booking</button>
                    <button id="btn-ical-feed" onClick={() => setShowIcalFeed(true)} style={{ ...btnPrimary, background: 'var(--color-olive)' }}>📡 iCal Feed</button>
                    <button onClick={() => { loadBookings(); loadBlocks(); }} disabled={loading} style={{ ...btnSecondary, opacity: loading ? 0.7 : 1 }}>
                        {loading ? '⟳' : '↺'} Refresh
                    </button>
                </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)', borderBottom: '1px solid var(--color-border)', paddingBottom: 0 }}>
                {(['bookings', 'blocks'] as const).map(t => (
                    <button key={t} id={`tab-${t}`} onClick={() => setTab(t)} style={{
                        padding: 'var(--space-2) var(--space-4)',
                        background: 'none', border: 'none',
                        borderBottom: `2px solid ${tab === t ? 'var(--color-primary)' : 'transparent'}`,
                        color: tab === t ? 'var(--color-primary)' : 'var(--color-text-dim)',
                        cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)',
                        marginBottom: -1,
                    }}>
                        {t === 'bookings' ? `📋 Bookings${!loading ? ` (${bookings.length})` : ''}` : `🚫 Calendar Blocks${!blocksLoading ? ` (${blocks.length})` : ''}`}
                    </button>
                ))}
                <div style={{ marginLeft: 'auto', paddingBottom: 'var(--space-1)' }}>
                    <StatusInfoPopover />
                </div>
            </div>

            {tab === 'blocks' && (
                <div style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', display: 'flex', gap: 'var(--space-2)' }}>
                    <span>ℹ️</span>
                    <div>
                        <strong style={{ color: 'var(--color-text)', display: 'block', marginBottom: 2 }}>Calendar Blocks — Availability Holds Only</strong>
                        These rows are iCal availability blocks (e.g. “Airbnb (Not available)”, “Not available”).  They are <strong>not real guest reservations</strong>.
                        They never generate tasks, never affect settlement, and are preserved here for audit/source-truth visibility only.
                    </div>
                </div>
            )}

            {successMsg && <SuccessBanner message={successMsg} onDismiss={() => setSuccessMsg(null)} />}

            {liveEvent && (
                <div style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--color-primary)', marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: 'var(--color-primary)', animation: 'pulse 1.5s infinite' }} />
                    Live: {liveEvent}
                </div>
            )}

            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)', marginBottom: 'var(--space-5)', display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)', alignItems: 'center' }}>
                <PropertyAutocompleteFilter value={filters.property_id} onChange={v => setFilters(f => ({ ...f, property_id: v }))} properties={properties} />
                {tab === 'bookings' && (
                    <>
                        <select id="filter-status" value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))} style={{ ...inputStyle, flex: '1 1 120px' }}>
                            {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                        <select id="filter-source" value={filters.source} onChange={e => setFilters(f => ({ ...f, source: e.target.value }))} style={{ ...inputStyle, flex: '1 1 120px' }}>
                            {SOURCE_OPTIONS.map(s => <option key={s} value={s}>{s || 'All providers'}</option>)}
                        </select>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Check-in</span>
                            <input id="filter-checkin-from" type="date" value={filters.check_in_from} onChange={e => setFilters(f => ({ ...f, check_in_from: e.target.value }))} style={{ ...inputStyle, width: 'auto' }} />
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>–</span>
                            <input id="filter-checkin-to" type="date" value={filters.check_in_to} onChange={e => setFilters(f => ({ ...f, check_in_to: e.target.value }))} style={{ ...inputStyle, width: 'auto' }} />
                        </div>
                    </>
                )}
                <button id="filter-reset" onClick={() => setFilters({ property_id: '', status: '', source: '', check_in_from: '', check_in_to: '' })} style={btnSecondary}>Reset</button>
            </div>

            {error && <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)', color: 'var(--color-danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)' }}>⚠ {error}</div>}

            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
                            {['Booking ID', 'Source', 'Guest', 'Property', 'Check-in', 'Check-out', 'Status'].map(h => (
                                <th key={h} style={{ padding: 'var(--space-3) var(--space-4)', textAlign: 'left', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {tab === 'bookings' ? (
                            loading
                                ? Array.from({ length: 5 }).map((_, i) => (
                                    <tr key={i}>{Array.from({ length: 7 }).map((__, j) => (
                                        <td key={j} style={{ padding: 'var(--space-3) var(--space-4)' }}><div style={{ height: 14, background: 'var(--color-surface-3)', borderRadius: 4, animation: 'pulse 1.5s infinite' }} /></td>
                                    ))}</tr>
                                ))
                                : bookings.length === 0
                                    ? <EmptyState onAddBooking={() => setShowAddBooking(true)} onAddIcal={() => setShowIcalFeed(true)} />
                                    : bookings.map(b => (
                                        <BookingRow key={b.booking_id} b={b} propertyMap={propertyMap}
                                            onClick={() => { window.location.href = `/bookings/${b.booking_id}`; }} />
                                    ))
                        ) : (
                            blocksLoading
                                ? Array.from({ length: 3 }).map((_, i) => (
                                    <tr key={i}>{Array.from({ length: 7 }).map((__, j) => (
                                        <td key={j} style={{ padding: 'var(--space-3) var(--space-4)' }}><div style={{ height: 14, background: 'var(--color-surface-3)', borderRadius: 4, animation: 'pulse 1.5s infinite' }} /></td>
                                    ))}</tr>
                                ))
                                : blocks.length === 0
                                    ? (
                                        <tr><td colSpan={7} style={{ padding: 'var(--space-16)', textAlign: 'center', color: 'var(--color-text-dim)' }}>
                                            <div style={{ fontSize: '2rem', marginBottom: 'var(--space-2)' }}>🚫</div>
                                            <div style={{ fontWeight: 700, marginBottom: 4 }}>No calendar blocks found</div>
                                            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)' }}>All iCal feeds are clean for this property.</div>
                                        </td></tr>
                                    )
                                    : blocks.map(b => <CalendarBlockRow key={b.booking_id} b={b} propertyMap={propertyMap} />)
                        )}
                    </tbody>
                </table>
                </div>
            </div>
        </div>
    );
}
