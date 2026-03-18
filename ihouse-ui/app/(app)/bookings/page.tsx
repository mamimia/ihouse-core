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
}

interface PropertyOption {
    property_id: string;
    display_name: string;
    status: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusChip(status: string | null) {
    const s = status ?? 'unknown';
    const cfg: Record<string, { bg: string; color: string; label: string }> = {
        active: { bg: 'rgba(16,185,129,0.12)', color: 'var(--color-ok)', label: 'Active' },
        confirmed: { bg: 'rgba(16,185,129,0.12)', color: 'var(--color-ok)', label: 'Confirmed' },
        canceled: { bg: 'rgba(239,68,68,0.12)', color: 'var(--color-danger)', label: 'Canceled' },
    };
    const c = cfg[s] ?? { bg: 'rgba(100,100,100,0.12)', color: 'var(--color-muted)', label: s };
    return (
        <span style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            background: c.bg,
            color: c.color,
            borderRadius: 'var(--radius-full)',
            padding: '2px 8px',
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
                        style={{ ...inputStyle, colorScheme: 'dark' }} />
                </div>
                <div>
                    <label style={labelStyle}>Check-out *</label>
                    <input id="booking-checkout" type="date" value={form.check_out}
                        onChange={e => setForm(f => ({ ...f, check_out: e.target.value }))}
                        style={{ ...inputStyle, colorScheme: 'dark' }} />
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
// Booking row
// ---------------------------------------------------------------------------

function BookingRow({ b, onClick }: { b: Booking; onClick: () => void }) {
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
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                {b.property_id ?? '—'}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-sm)' }}>
                {fmtDate(b.check_in)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-sm)' }}>
                {fmtDate(b.check_out)}
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)' }}>
                {statusChip(b.status)}
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
                <button onClick={onAddIcal} style={{ ...btnPrimary, background: '#10b981' }}>📡 iCal Feed</button>
            </div>
        </td></tr>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function BookingsPage() {
    const [bookings, setBookings] = useState<Booking[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
    const [liveEvent, setLiveEvent] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const [filters, setFilters] = useState<Filters>({
        property_id: '', status: '', source: '', check_in_from: '', check_in_to: '',
    });

    // Modal state
    const [showAddBooking, setShowAddBooking] = useState(false);
    const [showIcalFeed, setShowIcalFeed] = useState(false);
    const [showIntegrations, setShowIntegrations] = useState(false);
    const [properties, setProperties] = useState<PropertyOption[]>([]);

    // Load properties for dropdowns
    useEffect(() => {
        api.listProperties()
            .then(res => setProperties(res.properties ?? []))
            .catch(() => { /* properties will just show IDs */ });
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
                if (!a.check_in) return 1;
                if (!b.check_in) return -1;
                return new Date(a.check_in).getTime() - new Date(b.check_in).getTime();
            });
            setBookings(list);
            setLastRefresh(new Date());
        } catch (err: unknown) {
            if (err instanceof ApiError) {
                setError(`API ${err.status}: ${err.code}`);
            } else {
                setError(err instanceof Error ? err.message : 'Failed to load bookings');
            }
        } finally {
            setLoading(false);
        }
    }, [filters]);

    useEffect(() => { loadBookings(); }, [loadBookings]);

    // 60s auto-refresh
    useEffect(() => {
        timerRef.current = setInterval(loadBookings, 60_000);
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [loadBookings]);

    // SSE for real-time booking events
    useEffect(() => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') ?? '' : '';
        const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
        const es = new EventSource(`${baseUrl}/events/stream?channels=bookings&token=${token}`);
        es.onmessage = (e) => {
            try {
                const evt = JSON.parse(e.data);
                if (evt.channel === 'bookings') {
                    setLiveEvent(`${evt.type}: ${evt.booking_id ?? 'unknown'}`);
                    setTimeout(loadBookings, 1000);
                    setTimeout(() => setLiveEvent(null), 5000);
                }
            } catch { /* ignore */ }
        };
        return () => es.close();
    }, [loadBookings]);

    const handleBookingSuccess = (msg: string) => {
        setSuccessMsg(msg);
        loadBookings(); // Refresh the list immediately
        setTimeout(() => setSuccessMsg(null), 8000);
    };

    return (
        <div>
            <style>{`
        @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }
        select option { background: var(--color-surface); }
      `}</style>

            {/* Modals */}
            <AddBookingModal
                open={showAddBooking}
                onClose={() => setShowAddBooking(false)}
                onSuccess={handleBookingSuccess}
                properties={properties}
            />
            <IcalFeedModal
                open={showIcalFeed}
                onClose={() => { setShowIcalFeed(false); loadBookings(); }}
                onSuccess={handleBookingSuccess}
                properties={properties}
            />

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-6)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
                <div>
                    <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, letterSpacing: '-0.02em' }}>Bookings</h1>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-1)' }}>
                        {loading ? 'Loading…' : `${bookings.length} result${bookings.length !== 1 ? 's' : ''}`}
                        {lastRefresh && <span style={{ marginLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>· Updated {lastRefresh.toLocaleTimeString()}</span>}
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                    <button
                        id="btn-add-booking"
                        onClick={() => setShowAddBooking(true)}
                        style={{
                            ...btnPrimary,
                            display: 'flex', alignItems: 'center', gap: 6,
                        }}
                    >
                        + Add Booking
                    </button>
                    <button
                        id="btn-ical-feed"
                        onClick={() => setShowIcalFeed(true)}
                        style={{
                            ...btnPrimary,
                            background: '#10b981',
                            display: 'flex', alignItems: 'center', gap: 6,
                        }}
                    >
                        📡 iCal Feed
                    </button>
                    <div style={{ position: 'relative' }}>
                        <button
                            id="btn-integrations"
                            onClick={() => setShowIntegrations(!showIntegrations)}
                            style={{
                                ...btnPrimary,
                                background: '#6366f1',
                                display: 'flex', alignItems: 'center', gap: 6,
                            }}
                        >
                            🔌 Integrations ▾
                        </button>
                        {showIntegrations && (
                            <div style={{
                                position: 'absolute', top: '100%', right: 0, marginTop: 4,
                                background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-lg)', padding: 'var(--space-3) 0',
                                minWidth: 260, boxShadow: '0 12px 48px rgba(0,0,0,0.5)', zIndex: 50,
                            }}>
                                <div style={{ padding: '0 var(--space-4)', marginBottom: 'var(--space-2)' }}>
                                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Active</span>
                                </div>
                                <button onClick={() => { setShowIntegrations(false); setShowIcalFeed(true); }} style={{ width: '100%', padding: 'var(--space-2) var(--space-4)', background: 'none', border: 'none', color: 'var(--color-text)', textAlign: 'left', cursor: 'pointer', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span style={{ color: '#22c55e' }}>✅</span> iCal Feeds
                                </button>
                                <div style={{ height: 1, background: 'var(--color-border)', margin: 'var(--space-2) 0' }} />
                                <div style={{ padding: '0 var(--space-4)', marginBottom: 'var(--space-2)' }}>
                                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Requires Setup</span>
                                </div>
                                <a href="/admin/integrations" style={{ display: 'flex', padding: 'var(--space-2) var(--space-4)', color: 'var(--color-text)', textDecoration: 'none', fontSize: 'var(--text-sm)', alignItems: 'center', gap: 8 }}>
                                    <span>⚙️</span> Guesty PMS
                                </a>
                                <a href="/admin/integrations" style={{ display: 'flex', padding: 'var(--space-2) var(--space-4)', color: 'var(--color-text)', textDecoration: 'none', fontSize: 'var(--text-sm)', alignItems: 'center', gap: 8 }}>
                                    <span>⚙️</span> Hostaway PMS
                                </a>
                                <div style={{ height: 1, background: 'var(--color-border)', margin: 'var(--space-2) 0' }} />
                                <div style={{ padding: '0 var(--space-4)', marginBottom: 'var(--space-2)' }}>
                                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Planned</span>
                                </div>
                                <div style={{ padding: 'var(--space-2) var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span>🔜</span> Booking.com · Airbnb · Expedia
                                </div>
                                <div style={{ height: 1, background: 'var(--color-border)', margin: 'var(--space-2) 0' }} />
                                <a href="/admin/integrations" style={{ display: 'flex', padding: 'var(--space-2) var(--space-4)', color: 'var(--color-primary)', textDecoration: 'none', fontSize: 'var(--text-sm)', fontWeight: 600, alignItems: 'center', gap: 8 }}>
                                    <span>⚡</span> Integration Dashboard
                                </a>
                            </div>
                        )}
                    </div>
                    <button
                        onClick={loadBookings}
                        disabled={loading}
                        style={{
                            ...btnSecondary,
                            opacity: loading ? 0.7 : 1,
                        }}
                    >
                        {loading ? '⟳' : '↺'} Refresh
                    </button>
                </div>
            </div>

            {/* Success banner */}
            {successMsg && <SuccessBanner message={successMsg} onDismiss={() => setSuccessMsg(null)} />}

            {/* Live event banner */}
            {liveEvent && (
                <div style={{
                    background: 'rgba(99, 102, 241, 0.1)',
                    border: '1px solid rgba(99, 102, 241, 0.3)',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-2) var(--space-4)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-primary)',
                    marginBottom: 'var(--space-4)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                }}>
                    <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: 'var(--color-primary)', animation: 'pulse 1.5s infinite' }} />
                    Live: {liveEvent}
                </div>
            )}

            {/* Filter bar */}
            <div style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-4)',
                marginBottom: 'var(--space-5)',
                display: 'flex',
                flexWrap: 'wrap',
                gap: 'var(--space-3)',
                alignItems: 'center',
            }}>
                <input
                    id="filter-property"
                    placeholder="Property ID"
                    value={filters.property_id}
                    onChange={e => setFilters(f => ({ ...f, property_id: e.target.value }))}
                    style={{ ...inputStyle, flex: '1 1 120px', minWidth: 100, width: 'auto' }}
                />
                <select
                    id="filter-status"
                    value={filters.status}
                    onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
                    style={{ ...inputStyle, flex: '1 1 120px', minWidth: 100, width: 'auto' }}
                >
                    {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                <select
                    id="filter-source"
                    value={filters.source}
                    onChange={e => setFilters(f => ({ ...f, source: e.target.value }))}
                    style={{ ...inputStyle, flex: '1 1 120px', minWidth: 100, width: 'auto' }}
                >
                    {SOURCE_OPTIONS.map(s => <option key={s} value={s}>{s || 'All providers'}</option>)}
                </select>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Check-in</span>
                    <input id="filter-checkin-from" type="date" value={filters.check_in_from}
                        onChange={e => setFilters(f => ({ ...f, check_in_from: e.target.value }))}
                        style={{ ...inputStyle, colorScheme: 'dark', width: 'auto' }} />
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>–</span>
                    <input id="filter-checkin-to" type="date" value={filters.check_in_to}
                        onChange={e => setFilters(f => ({ ...f, check_in_to: e.target.value }))}
                        style={{ ...inputStyle, colorScheme: 'dark', width: 'auto' }} />
                </div>
                <button
                    id="filter-reset"
                    onClick={() => setFilters({ property_id: '', status: '', source: '', check_in_from: '', check_in_to: '' })}
                    style={btnSecondary}
                >
                    Reset
                </button>
            </div>

            {/* Error */}
            {error && (
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)', color: 'var(--color-danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)' }}>
                    ⚠ {error}
                </div>
            )}

            {/* Table */}
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
                        {loading
                            ? Array.from({ length: 5 }).map((_, i) => (
                                <tr key={i}>
                                    {Array.from({ length: 7 }).map((__, j) => (
                                        <td key={j} style={{ padding: 'var(--space-3) var(--space-4)' }}>
                                            <div style={{ height: 14, background: 'var(--color-surface-3)', borderRadius: 4, animation: 'pulse 1.5s infinite' }} />
                                        </td>
                                    ))}
                                </tr>
                            ))
                            : bookings.length === 0
                                ? <EmptyState onAddBooking={() => setShowAddBooking(true)} onAddIcal={() => setShowIcalFeed(true)} />
                                : bookings.map(b => (
                                    <BookingRow
                                        key={b.booking_id}
                                        b={b}
                                        onClick={() => window.location.href = `/bookings/${b.booking_id}`}
                                    />
                                ))
                        }
                    </tbody>
                </table>
                </div>
            </div>
        </div>
    );
}
