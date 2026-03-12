'use client';

/**
 * Phase 158 — Manager Booking List View
 * Route: /bookings
 *
 * Filterable booking list for operations managers.
 * Filters: property, status, check-in range, OTA / source provider.
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
    version: number | null;
    created_at: string | null;
    updated_at: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusChip(status: string | null) {
    const s = status ?? 'unknown';
    const cfg: Record<string, { bg: string; color: string; label: string }> = {
        active: { bg: 'rgba(16,185,129,0.12)', color: 'var(--color-ok)', label: 'Active' },
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
        despegar: '#1E9FD6',
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
// Filter bar
// ---------------------------------------------------------------------------

const STATUS_OPTIONS = [
    { value: '', label: 'All statuses' },
    { value: 'active', label: 'Active' },
    { value: 'canceled', label: 'Canceled' },
];

const SOURCE_OPTIONS = [
    '', 'airbnb', 'bookingcom', 'expedia', 'vrbo', 'hotelbeds', 'tripadvisor', 'despegar',
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
                {b.booking_id.slice(0, 12)}…
            </td>
            <td style={{ padding: 'var(--space-3) var(--space-4)' }}>
                {sourceChip(b.source)}
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

function EmptyState() {
    return (
        <tr><td colSpan={6} style={{ padding: 'var(--space-16)', textAlign: 'center', color: 'var(--color-text-dim)' }}>
            <div style={{ fontSize: '2rem', marginBottom: 'var(--space-3)' }}>📋</div>
            <div style={{ fontWeight: 600 }}>No bookings found</div>
            <div style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-2)' }}>Try adjusting your filters.</div>
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
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const [filters, setFilters] = useState<Filters>({
        property_id: '', status: '', source: '', check_in_from: '', check_in_to: '',
    });

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
            setBookings(res.bookings ?? []);
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

    // SSE for real-time booking events (Phase 306)
    useEffect(() => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') ?? '' : '';
        const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
        const es = new EventSource(`${baseUrl}/events/stream?channels=bookings&token=${token}`);
        es.onmessage = (e) => {
            try {
                const evt = JSON.parse(e.data);
                if (evt.channel === 'bookings') {
                    setLiveEvent(`${evt.type}: ${evt.booking_id ?? 'unknown'}`);
                    // Auto-refresh after 1s delay to let DB settle
                    setTimeout(loadBookings, 1000);
                    // Clear notice after 5s
                    setTimeout(() => setLiveEvent(null), 5000);
                }
            } catch { /* ignore parse errors */ }
        };
        return () => es.close();
    }, [loadBookings]);

    const inputStyle: React.CSSProperties = {
        background: 'var(--color-bg)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        color: 'var(--color-text)',
        padding: 'var(--space-2) var(--space-3)',
        fontSize: 'var(--text-sm)',
        fontFamily: 'var(--font-sans)',
        outline: 'none',
    };

    return (
        <div>
            <style>{`
        @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }
        select option { background: var(--color-surface); }
      `}</style>

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-6)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
                <div>
                    <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, letterSpacing: '-0.02em' }}>Bookings</h1>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-1)' }}>
                        {loading ? 'Loading…' : `${bookings.length} result${bookings.length !== 1 ? 's' : ''}`}
                        {lastRefresh && <span style={{ marginLeft: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>· Updated {lastRefresh.toLocaleTimeString()}</span>}
                    </p>
                </div>
                <button
                    onClick={loadBookings}
                    disabled={loading}
                    style={{
                        background: loading ? 'var(--color-surface-3)' : 'var(--color-primary)',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-2) var(--space-5)',
                        fontSize: 'var(--text-sm)',
                        fontWeight: 600,
                        opacity: loading ? 0.7 : 1,
                        cursor: loading ? 'default' : 'pointer',
                        transition: 'all var(--transition-fast)',
                    }}
                >
                    {loading ? '⟳  Refreshing…' : '↺  Refresh'}
                </button>
            </div>

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
                {/* Property ID */}
                <input
                    id="filter-property"
                    placeholder="Property ID"
                    value={filters.property_id}
                    onChange={e => setFilters(f => ({ ...f, property_id: e.target.value }))}
                    style={{ ...inputStyle, flex: '1 1 120px', minWidth: 100 }}
                />

                {/* Status */}
                <select
                    id="filter-status"
                    value={filters.status}
                    onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
                    style={{ ...inputStyle, flex: '1 1 120px', minWidth: 100 }}
                >
                    {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>

                {/* Source / OTA */}
                <select
                    id="filter-source"
                    value={filters.source}
                    onChange={e => setFilters(f => ({ ...f, source: e.target.value }))}
                    style={{ ...inputStyle, flex: '1 1 120px', minWidth: 100 }}
                >
                    {SOURCE_OPTIONS.map(s => <option key={s} value={s}>{s || 'All providers'}</option>)}
                </select>

                {/* Check-in from */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Check-in</span>
                    <input id="filter-checkin-from" type="date" value={filters.check_in_from}
                        onChange={e => setFilters(f => ({ ...f, check_in_from: e.target.value }))}
                        style={{ ...inputStyle, colorScheme: 'dark' }} />
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>–</span>
                    <input id="filter-checkin-to" type="date" value={filters.check_in_to}
                        onChange={e => setFilters(f => ({ ...f, check_in_to: e.target.value }))}
                        style={{ ...inputStyle, colorScheme: 'dark' }} />
                </div>

                {/* Reset */}
                <button
                    id="filter-reset"
                    onClick={() => setFilters({ property_id: '', status: '', source: '', check_in_from: '', check_in_to: '' })}
                    style={{
                        padding: 'var(--space-2) var(--space-4)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        background: 'transparent',
                        color: 'var(--color-text-dim)',
                        fontSize: 'var(--text-sm)',
                        cursor: 'pointer',
                    }}
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
                            {['Booking ID', 'Provider', 'Property', 'Check-in', 'Check-out', 'Status'].map(h => (
                                <th key={h} style={{ padding: 'var(--space-3) var(--space-4)', textAlign: 'left', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {loading
                            ? Array.from({ length: 5 }).map((_, i) => (
                                <tr key={i}>
                                    {Array.from({ length: 6 }).map((__, j) => (
                                        <td key={j} style={{ padding: 'var(--space-3) var(--space-4)' }}>
                                            <div style={{ height: 14, background: 'var(--color-surface-3)', borderRadius: 4, animation: 'pulse 1.5s infinite' }} />
                                        </td>
                                    ))}
                                </tr>
                            ))
                            : bookings.length === 0
                                ? <EmptyState />
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
