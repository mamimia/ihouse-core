'use client';

/**
 * Phase 158 — Manager Booking Detail View
 * Route: /bookings/[id]
 *
 * Tabs:
 *  Overview  — booking state fields, guest info
 *  Sync Log  — outbound sync log per provider
 *  Tasks     — tasks linked to this booking
 *  Financial — lifecycle status + facts card
 *  History   — amendment history (new endpoint)
 */

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';

// ---------------------------------------------------------------------------
// Inline API helpers (avoids circular imports from lib/api)
// ---------------------------------------------------------------------------

const BASE_URL =
    typeof window !== 'undefined'
        ? (process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000')
        : 'http://localhost:8000';

function getToken(): string {
    return typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') ?? '' : '';
}

async function apiFetch<T>(path: string): Promise<T> {
    const resp = await fetch(`${BASE_URL}${path}`, {
        headers: { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
    });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body?.error ?? `HTTP ${resp.status}`);
    return body;
}

async function apiFetchMut<T>(method: string, path: string, bodyObj?: unknown): Promise<T> {
    const resp = await fetch(`${BASE_URL}${path}`, {
        method,
        headers: { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
        ...(bodyObj !== undefined ? { body: JSON.stringify(bodyObj) } : {}),
    });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body?.error ?? `HTTP ${resp.status}`);
    return body;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BookingState {
    booking_id: string;
    tenant_id: string;
    source: string | null;
    reservation_ref: string | null;
    property_id: string | null;
    status: string | null;
    check_in: string | null;
    check_out: string | null;
    version: number | null;
    created_at: string | null;
    updated_at: string | null;
    guest_id: string | null;  // Phase 194 — nullable guest link
}

interface OutboundLogEntry {
    id: number;
    provider: string;
    event_type: string;
    status: string;
    attempted_at: string;
}

interface Task {
    task_id: string;
    kind: string;
    status: string;
    priority: string;
    due_date: string;
    title: string;
}

interface Amendment {
    envelope_id: string;
    event_type: string;
    version: number;
    received_at: string;
    payload?: Record<string, unknown>;
}

interface Financial {
    booking_id?: string;
    lifecycle_status?: string;
    [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(d: string | null): string {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', weekday: 'short' }); }
    catch { return d; }
}

function fmtDateTime(d: string | null): string {
    if (!d) return '—';
    try { return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }); }
    catch { return d; }
}

function statusChip(status: string | null, size?: 'sm') {
    const s = status ?? '';
    const cfg: Record<string, { bg: string; color: string }> = {
        active: { bg: 'rgba(16,185,129,0.12)', color: 'var(--color-ok)' },
        canceled: { bg: 'rgba(239,68,68,0.12)', color: 'var(--color-danger)' },
        ok: { bg: 'rgba(16,185,129,0.12)', color: 'var(--color-ok)' },
        error: { bg: 'rgba(239,68,68,0.12)', color: 'var(--color-danger)' },
        skipped: { bg: 'rgba(100,100,100,0.12)', color: 'var(--color-muted)' },
        dry_run: { bg: 'rgba(96,165,250,0.12)', color: 'var(--color-info)' },
        pending: { bg: 'rgba(245,158,11,0.12)', color: 'var(--color-warn)' },
        acknowledged: { bg: 'rgba(6,182,212,0.12)', color: 'var(--color-accent)' },
        in_progress: { bg: 'rgba(59,130,246,0.12)', color: 'var(--color-primary)' },
        completed: { bg: 'rgba(16,185,129,0.12)', color: 'var(--color-ok)' },
        CRITICAL: { bg: 'rgba(239,68,68,0.12)', color: 'var(--color-danger)' },
        HIGH: { bg: 'rgba(245,158,11,0.12)', color: 'var(--color-warn)' },
        MEDIUM: { bg: 'rgba(59,130,246,0.12)', color: 'var(--color-primary)' },
        LOW: { bg: 'rgba(100,100,100,0.12)', color: 'var(--color-muted)' },
    };
    const c = cfg[s] ?? { bg: 'rgba(100,100,100,0.12)', color: 'var(--color-muted)' };
    return (
        <span style={{
            fontSize: size === 'sm' ? 'var(--text-xs)' : 'var(--text-xs)',
            fontWeight: 600,
            background: c.bg,
            color: c.color,
            borderRadius: 'var(--radius-full)',
            padding: '2px 8px',
        }}>
            {s}
        </span>
    );
}

// ---------------------------------------------------------------------------
// Field
// ---------------------------------------------------------------------------

function Field({ label, value, mono }: { label: string; value: unknown; mono?: boolean }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {label}
            </span>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', fontFamily: mono ? 'var(--font-mono)' : 'inherit' }}>
                {value == null ? '—' : String(value)}
            </span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

type Tab = 'overview' | 'sync' | 'tasks' | 'financial' | 'history';

const TABS: { id: Tab; label: string; icon: string }[] = [
    { id: 'overview', label: 'Overview', icon: '📋' },
    { id: 'sync', label: 'Sync Log', icon: '🔄' },
    { id: 'tasks', label: 'Tasks', icon: '✓' },
    { id: 'financial', label: 'Financial', icon: '💰' },
    { id: 'history', label: 'History', icon: '📅' },
];

// ---------------------------------------------------------------------------
// Panel components
// ---------------------------------------------------------------------------

function OverviewPanel({ booking }: { booking: BookingState }) {
    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
            <Field label="Booking ID" value={booking.booking_id} mono />
            <Field label="Tenant" value={booking.tenant_id} mono />
            <Field label="Status" value={booking.status} />
            <Field label="Source / OTA" value={booking.source} />
            <Field label="Reservation" value={booking.reservation_ref} mono />
            <Field label="Property" value={booking.property_id} mono />
            <Field label="Check-in" value={fmtDate(booking.check_in)} />
            <Field label="Check-out" value={fmtDate(booking.check_out)} />
            <Field label="Version" value={booking.version} />
            <Field label="Created" value={fmtDateTime(booking.created_at)} />
            <Field label="Last Updated" value={fmtDateTime(booking.updated_at)} />
        </div>
    );
}

function SyncPanel({ booking_id }: { booking_id: string }) {
    const [entries, setEntries] = useState<OutboundLogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        apiFetch<{ entries: OutboundLogEntry[]; count: number }>(`/admin/outbound-log?booking_id=${encodeURIComponent(booking_id)}&limit=50`)
            .then(d => setEntries(d.entries ?? []))
            .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed'))
            .finally(() => setLoading(false));
    }, [booking_id]);

    if (loading) return <div style={{ color: 'var(--color-text-dim)', animation: 'pulse 1.5s infinite' }}>Loading sync log…</div>;
    if (error) return <div style={{ color: 'var(--color-danger)' }}>⚠ {error}</div>;
    if (!entries.length) return <div style={{ color: 'var(--color-text-dim)' }}>No outbound sync events for this booking.</div>;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            {entries.map((e) => (
                <div key={e.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
                    <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', minWidth: 100 }}>{e.provider}</span>
                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{e.event_type}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
                        {statusChip(e.status, 'sm')}
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{fmtDateTime(e.attempted_at)}</span>
                    </div>
                </div>
            ))}
        </div>
    );
}

function TasksPanel({ booking_id }: { booking_id: string }) {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        apiFetch<{ tasks: Task[]; count: number }>(`/tasks?booking_id=${encodeURIComponent(booking_id)}&limit=50`)
            .then(d => setTasks(d.tasks ?? []))
            .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed'))
            .finally(() => setLoading(false));
    }, [booking_id]);

    if (loading) return <div style={{ color: 'var(--color-text-dim)', animation: 'pulse 1.5s infinite' }}>Loading tasks…</div>;
    if (error) return <div style={{ color: 'var(--color-danger)' }}>⚠ {error}</div>;
    if (!tasks.length) return <div style={{ color: 'var(--color-text-dim)' }}>No tasks linked to this booking.</div>;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            {tasks.map(t => (
                <div key={t.task_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', cursor: 'pointer' }}
                    onClick={() => window.location.href = `/tasks/${t.task_id}`}>
                    <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
                        {statusChip(t.priority, 'sm')}
                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{t.title}</span>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>· {t.kind}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
                        {statusChip(t.status, 'sm')}
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{fmtDate(t.due_date)}</span>
                    </div>
                </div>
            ))}
        </div>
    );
}

function FinancialPanel({ booking_id }: { booking_id: string }) {
    const [data, setData] = useState<Financial | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        apiFetch<Financial>(`/financial/${encodeURIComponent(booking_id)}`)
            .then(d => setData(d))
            .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed'))
            .finally(() => setLoading(false));
    }, [booking_id]);

    if (loading) return <div style={{ color: 'var(--color-text-dim)', animation: 'pulse 1.5s infinite' }}>Loading financial…</div>;
    if (error) return <div style={{ color: 'var(--color-danger)' }}>⚠ {error}</div>;
    if (!data) return <div style={{ color: 'var(--color-text-dim)' }}>No financial data available.</div>;

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
            {Object.entries(data).filter(([k]) => !['booking_id', 'tenant_id'].includes(k)).map(([k, v]) => (
                <Field key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')} />
            ))}
        </div>
    );
}

function HistoryPanel({ booking_id }: { booking_id: string }) {
    const [amendments, setAmendments] = useState<Amendment[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        apiFetch<{ amendments: Amendment[]; count: number }>(`/bookings/${encodeURIComponent(booking_id)}/amendments`)
            .then(d => setAmendments(d.amendments ?? []))
            .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed'))
            .finally(() => setLoading(false));
    }, [booking_id]);

    if (loading) return <div style={{ color: 'var(--color-text-dim)', animation: 'pulse 1.5s infinite' }}>Loading amendment history…</div>;
    if (error) return <div style={{ color: 'var(--color-danger)' }}>⚠ {error}</div>;
    if (!amendments.length) return (
        <div style={{ textAlign: 'center', padding: 'var(--space-10)', color: 'var(--color-text-dim)' }}>
            <div style={{ fontSize: '2rem', marginBottom: 'var(--space-3)' }}>✅</div>
            <div style={{ fontWeight: 600 }}>No amendments</div>
            <div style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-2)' }}>This booking has never been amended.</div>
        </div>
    );

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {amendments.map((a, idx) => (
                <div key={a.envelope_id ?? idx} style={{ background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', overflow: 'hidden' }}>
                    {/* Header */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                            <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)' }}>#{idx + 1}</span>
                            <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-primary)' }}>Amendment</span>
                            <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}>v{a.version}</span>
                        </div>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{fmtDateTime(a.received_at)}</span>
                    </div>
                    {/* Payload */}
                    {a.payload && (
                        <div style={{ padding: 'var(--space-3) var(--space-4)' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                {Object.entries(a.payload).map(([k, v]) => (
                                    <Field key={k} label={k.replace(/_/g, ' ')} value={String(v ?? '—')} />
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Guest Link Panel (Phase 194)
// ---------------------------------------------------------------------------

function GuestLinkPanel({ booking_id, initial_guest_id }: { booking_id: string; initial_guest_id: string | null }) {
    const [guestId, setGuestId] = useState<string | null>(initial_guest_id);
    const [input, setInput] = useState('');
    const [saving, setSaving] = useState(false);
    const [err, setErr] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);

    const flash = (msg: string) => { setSuccessMsg(msg); setTimeout(() => setSuccessMsg(null), 3000); };

    const link = async () => {
        if (!input.trim()) { setErr('Enter a guest UUID'); return; }
        setSaving(true); setErr(null);
        try {
            const res = await apiFetchMut<{ guest_id: string; guest_name: string; linked: boolean }>(
                'POST', `/bookings/${booking_id}/link-guest`, { guest_id: input.trim() }
            );
            setGuestId(res.guest_id);
            setInput('');
            flash(`Linked to: ${res.guest_name}`);
        } catch (e) {
            setErr(e instanceof Error ? e.message : 'Failed to link guest');
        } finally { setSaving(false); }
    };

    const unlink = async () => {
        setSaving(true); setErr(null);
        try {
            await apiFetchMut('DELETE', `/bookings/${booking_id}/link-guest`);
            setGuestId(null);
            flash('Guest unlinked');
        } catch (e) {
            setErr(e instanceof Error ? e.message : 'Failed to unlink');
        } finally { setSaving(false); }
    };

    return (
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xl)', padding: 'var(--space-5)', marginTop: 'var(--space-4)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                <span style={{ fontSize: '1.1em' }}>👤</span>
                <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>Guest Link</span>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginLeft: 2 }}>(best-effort annotation)</span>
            </div>

            {successMsg && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-ok)', background: 'rgba(16,185,129,0.08)', borderRadius: 'var(--radius-md)', padding: '6px 10px', marginBottom: 'var(--space-3)' }}>
                    ✓ {successMsg}
                </div>
            )}
            {err && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-danger)', background: 'rgba(239,68,68,0.08)', borderRadius: 'var(--radius-md)', padding: '6px 10px', marginBottom: 'var(--space-3)' }}>
                    ⚠ {err}
                </div>
            )}

            {guestId ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', justifyContent: 'space-between', flexWrap: 'wrap' }}>
                    <div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>Linked Guest</div>
                        <a href={`/guests/${guestId}`} style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-primary)', textDecoration: 'none' }}>
                            {guestId} →
                        </a>
                    </div>
                    <button
                        id="unlink-guest-btn"
                        onClick={unlink} disabled={saving}
                        style={{ padding: '6px 14px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-danger)', fontWeight: 600, fontSize: 'var(--text-xs)', cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.6 : 1 }}
                    >{saving ? 'Unlinking…' : 'Unlink Guest'}</button>
                </div>
            ) : (
                <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
                    <input
                        id="link-guest-input"
                        value={input}
                        onChange={e => { setInput(e.target.value); setErr(null); }}
                        placeholder="Guest UUID…"
                        style={{ flex: 1, minWidth: 240, padding: '7px 10px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', fontFamily: 'var(--font-mono)' }}
                    />
                    <button
                        id="link-guest-btn"
                        onClick={link} disabled={saving}
                        style={{ padding: '7px 18px', background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', fontWeight: 600, fontSize: 'var(--text-sm)', cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.7 : 1, whiteSpace: 'nowrap' }}
                    >{saving ? 'Linking…' : 'Link Guest'}</button>
                    <a href="/guests" style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', textDecoration: 'none' }}>Browse guests →</a>
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function Skeleton() {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {[80, 200, 60].map((h, i) => (
                <div key={i} style={{ height: h, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', animation: 'pulse 1.5s infinite' }} />
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function BookingDetailPage() {
    const params = useParams();
    const router = useRouter();
    const id = params?.id as string;

    const [booking, setBooking] = useState<BookingState | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<Tab>('overview');

    useEffect(() => {
        if (!id) return;
        apiFetch<BookingState>(`/bookings/${encodeURIComponent(id)}`)
            .then(d => setBooking(d))
            .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Not found'))
            .finally(() => setLoading(false));
    }, [id]);

    return (
        <div style={{ maxWidth: 900 }}>
            <style>{`
        @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }
        @keyframes slideUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
      `}</style>

            {/* Back nav */}
            <button
                id="back-to-bookings"
                onClick={() => router.push('/bookings')}
                style={{ background: 'none', border: 'none', color: 'var(--color-primary)', fontSize: 'var(--text-sm)', cursor: 'pointer', padding: 'var(--space-2) 0', marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}
            >
                ← Bookings
            </button>

            {loading && <Skeleton />}
            {!loading && error && (
                <div style={{ textAlign: 'center', padding: 'var(--space-16)', color: 'var(--color-danger)' }}>
                    <div style={{ fontSize: '2rem', marginBottom: 'var(--space-4)' }}>⚠</div>
                    {error}
                </div>
            )}

            {booking && (
                <div style={{ animation: 'slideUp 220ms ease' }}>

                    {/* Title */}
                    <div style={{ marginBottom: 'var(--space-5)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                            <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, letterSpacing: '-0.02em', fontFamily: 'var(--font-mono)' }}>
                                {booking.booking_id}
                            </h1>
                            {statusChip(booking.status)}
                        </div>
                        <div style={{ display: 'flex', gap: 'var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                            <span>{booking.source ?? '—'}</span>
                            <span>·</span>
                            <span>{booking.property_id ?? '—'}</span>
                            <span>·</span>
                            <span>{fmtDate(booking.check_in)} → {fmtDate(booking.check_out)}</span>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div style={{ display: 'flex', gap: 'var(--space-1)', marginBottom: 'var(--space-5)', background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-1)', border: '1px solid var(--color-border)' }}>
                        {TABS.map(t => (
                            <button
                                key={t.id}
                                id={`tab-${t.id}`}
                                onClick={() => setActiveTab(t.id)}
                                style={{
                                    flex: 1,
                                    padding: 'var(--space-2) var(--space-3)',
                                    borderRadius: 'var(--radius-md)',
                                    border: 'none',
                                    background: activeTab === t.id ? 'var(--color-primary)' : 'transparent',
                                    color: activeTab === t.id ? '#fff' : 'var(--color-text-dim)',
                                    fontWeight: activeTab === t.id ? 600 : 400,
                                    fontSize: 'var(--text-sm)',
                                    cursor: 'pointer',
                                    transition: 'all var(--transition-fast)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: 'var(--space-2)',
                                }}
                            >
                                <span style={{ fontSize: '0.85em' }}>{t.icon}</span>
                                <span>{t.label}</span>
                            </button>
                        ))}
                    </div>

                    {/* Panel */}
                    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xl)', padding: 'var(--space-6)', minHeight: 200 }}>
                        {activeTab === 'overview' && <OverviewPanel booking={booking} />}
                        {activeTab === 'sync' && <SyncPanel booking_id={booking.booking_id} />}
                        {activeTab === 'tasks' && <TasksPanel booking_id={booking.booking_id} />}
                        {activeTab === 'financial' && <FinancialPanel booking_id={booking.booking_id} />}
                        {activeTab === 'history' && <HistoryPanel booking_id={booking.booking_id} />}
                    </div>

                    {/* Guest Link panel — Phase 194 */}
                    <GuestLinkPanel booking_id={booking.booking_id} initial_guest_id={booking.guest_id ?? null} />
                </div>
            )}
        </div>
    );
}
