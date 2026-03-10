'use client';

/**
 * Phase 200 — Booking Calendar UI
 * Route: /calendar
 *
 * Month-view booking calendar for property managers.
 * Reads from GET /bookings with check_in_from / check_in_to / property_id / status.
 * No new backend endpoints.
 */

import { useEffect, useState, useCallback } from 'react';
import { api, Booking } from '../../lib/api';

// ---------------------------------------------------------------------------
// Date utilities
// ---------------------------------------------------------------------------

function isoDate(d: Date): string {
    return d.toISOString().slice(0, 10);
}

function addMonths(d: Date, n: number): Date {
    const r = new Date(d);
    r.setDate(1);
    r.setMonth(r.getMonth() + n);
    return r;
}

function monthLabel(d: Date): string {
    return d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

/** Returns the array of Date cells for a 6-row grid starting on the Sunday before the 1st */
function buildCalendarGrid(year: number, month: number): Date[] {
    const first = new Date(year, month, 1);
    const startOffset = first.getDay(); // 0=Sun
    const cells: Date[] = [];
    for (let i = -startOffset; i < 42 - startOffset; i++) {
        cells.push(new Date(year, month, 1 + i));
    }
    return cells;
}

// ---------------------------------------------------------------------------
// Source colours (same as bookings page)
// ---------------------------------------------------------------------------

const SOURCE_COLOURS: Record<string, string> = {
    airbnb: '#FF5A5F',
    bookingcom: '#003580',
    expedia: '#00355F',
    vrbo: '#3D67FF',
    hotelbeds: '#0099CC',
    tripadvisor: '#34E0A1',
    despegar: '#1E9FD6',
    rakuten: '#BF0000',
    hostelworld: '#F26E22',
};

function sourceColor(source: string | null): string {
    if (!source) return 'var(--color-primary)';
    return SOURCE_COLOURS[source.toLowerCase()] ?? 'var(--color-primary)';
}

// ---------------------------------------------------------------------------
// Booking block — rendered inside a day cell
// ---------------------------------------------------------------------------

interface BookingBlockProps {
    booking: Booking;
    isStart: boolean;
    isEnd: boolean;
    isContinuation: boolean;
}

function BookingBlock({ booking, isStart, isEnd, isContinuation }: BookingBlockProps) {
    const [hovered, setHovered] = useState(false);
    const isCanceled = booking.status === 'canceled';
    const bg = isCanceled ? 'rgba(239,68,68,0.18)' : `${sourceColor(booking.source)}33`;
    const border = isCanceled ? 'rgba(239,68,68,0.5)' : `${sourceColor(booking.source)}99`;
    const textColor = isCanceled ? 'var(--color-danger)' : 'var(--color-text)';

    return (
        <div
            style={{
                position: 'relative',
                background: bg,
                border: `1px solid ${border}`,
                borderRadius: isStart && isEnd ? 'var(--radius-sm)'
                    : isStart ? '3px 0 0 3px'
                        : isEnd ? '0 3px 3px 0'
                            : '0',
                marginLeft: isStart ? 2 : 0,
                marginRight: isEnd ? 2 : 0,
                padding: '1px 4px',
                fontSize: 'var(--text-xs)',
                color: textColor,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                cursor: 'pointer',
                opacity: isCanceled ? 0.65 : 1,
                marginBottom: 2,
                transition: 'opacity var(--transition-fast)',
            }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            onClick={() => window.open(`/bookings/${booking.booking_id}`, '_blank')}
        >
            {isContinuation ? '→' : (booking.source ?? '?')}
            {isEnd && !isContinuation && booking.check_out ? ` ✕` : ''}

            {/* Tooltip */}
            {hovered && (
                <div style={{
                    position: 'absolute',
                    top: '110%',
                    left: 0,
                    zIndex: 100,
                    background: 'var(--color-surface-3)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-2) var(--space-3)',
                    minWidth: 180,
                    boxShadow: 'var(--shadow-lg)',
                    pointerEvents: 'none',
                }}>
                    <div style={{ fontWeight: 600, fontSize: 'var(--text-xs)', color: 'var(--color-text)', marginBottom: 2 }}>
                        {booking.source ?? 'unknown'} — {booking.status ?? '?'}
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                        {booking.booking_id.slice(0, 16)}…
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                        {booking.check_in} → {booking.check_out}
                    </div>
                    {booking.property_id && (
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 1 }}>
                            {booking.property_id}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Day cell
// ---------------------------------------------------------------------------

interface DayCellProps {
    date: Date;
    isCurrentMonth: boolean;
    isToday: boolean;
    bookingsForDay: Array<{ booking: Booking; isStart: boolean; isEnd: boolean; isContinuation: boolean }>;
}

function DayCell({ date, isCurrentMonth, isToday, bookingsForDay }: DayCellProps) {
    return (
        <div style={{
            minHeight: 90,
            padding: '4px 2px 2px',
            borderRight: '1px solid var(--color-border)',
            borderBottom: '1px solid var(--color-border)',
            background: isToday ? 'rgba(59,130,246,0.06)' : 'transparent',
            opacity: isCurrentMonth ? 1 : 0.35,
            overflow: 'hidden',
        }}>
            {/* Day number */}
            <div style={{
                fontSize: 'var(--text-xs)',
                fontWeight: isToday ? 700 : 400,
                color: isToday ? 'var(--color-primary)' : 'var(--color-text-dim)',
                marginBottom: 3,
                paddingLeft: 3,
                display: 'flex',
                alignItems: 'center',
                gap: 3,
            }}>
                {isToday && (
                    <span style={{
                        display: 'inline-block',
                        width: 18, height: 18,
                        background: 'var(--color-primary)',
                        color: '#fff',
                        borderRadius: 'var(--radius-full)',
                        textAlign: 'center',
                        lineHeight: '18px',
                        fontSize: 10,
                        fontWeight: 700,
                    }}>
                        {date.getDate()}
                    </span>
                )}
                {!isToday && date.getDate()}
            </div>

            {/* Booking blocks */}
            {bookingsForDay.map(({ booking, isStart, isEnd, isContinuation }) => (
                <BookingBlock
                    key={`${booking.booking_id}-${isoDate(date)}`}
                    booking={booking}
                    isStart={isStart}
                    isEnd={isEnd}
                    isContinuation={isContinuation}
                />
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const STATUS_OPTS = [
    { value: '', label: 'All' },
    { value: 'active', label: 'Active' },
    { value: 'canceled', label: 'Canceled' },
];

const DOW_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function CalendarPage() {
    const today = new Date();
    const [viewDate, setViewDate] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
    const [propertyId, setPropertyId] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [bookings, setBookings] = useState<Booking[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const year = viewDate.getFullYear();
    const month = viewDate.getMonth();
    const cells = buildCalendarGrid(year, month);

    // Build ISO window for the visible grid (cells[0]..cells[41])
    const windowStart = isoDate(cells[0]);
    const windowEnd = isoDate(cells[cells.length - 1]);

    const loadBookings = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const resp = await api.getBookings({
                check_in_from: windowStart,
                check_in_to: windowEnd,
                ...(propertyId ? { property_id: propertyId } : {}),
                ...(statusFilter ? { status: statusFilter } : {}),
                limit: 500,
            });
            setBookings(resp.bookings ?? []);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to load bookings');
        } finally {
            setLoading(false);
        }
    }, [windowStart, windowEnd, propertyId, statusFilter]);

    useEffect(() => { loadBookings(); }, [loadBookings]);

    // For each day cell, compute which bookings occupy it
    function bookingsForDate(cell: Date): DayCellProps['bookingsForDay'] {
        const cellStr = isoDate(cell);
        const result: DayCellProps['bookingsForDay'] = [];
        for (const b of bookings) {
            const cin = b.check_in;
            const cout = b.check_out;
            if (!cin || !cout) continue;
            if (cellStr < cin || cellStr >= cout) continue;
            const isStart = cellStr === cin;
            const isEnd = isoDate(new Date(new Date(cout).getTime() - 86400000)) === cellStr;
            // Continuation: first day of a week row but not the actual start
            const isContinuation = !isStart && cell.getDay() === 0;
            result.push({ booking: b, isStart, isEnd, isContinuation });
        }
        return result;
    }

    const todayStr = isoDate(today);

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

    const navBtnStyle: React.CSSProperties = {
        background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        color: 'var(--color-text)',
        padding: 'var(--space-2) var(--space-4)',
        fontSize: 'var(--text-sm)',
        cursor: 'pointer',
        transition: 'background var(--transition-fast)',
    };

    return (
        <div>
            <style>{`
                @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }
                select option { background: var(--color-surface); }
            `}</style>

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-5)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
                <div>
                    <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, letterSpacing: '-0.02em' }}>
                        Booking Calendar
                    </h1>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-1)' }}>
                        {loading ? 'Loading…' : `${bookings.length} booking${bookings.length !== 1 ? 's' : ''} in view`}
                    </p>
                </div>

                {/* Toolbar */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                    {/* Property filter */}
                    <input
                        id="calendar-property-filter"
                        placeholder="Property ID"
                        value={propertyId}
                        onChange={e => setPropertyId(e.target.value)}
                        style={{ ...inputStyle, width: 130 }}
                    />

                    {/* Status toggle */}
                    <div style={{ display: 'flex', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                        {STATUS_OPTS.map(o => (
                            <button
                                key={o.value}
                                id={`calendar-status-${o.value || 'all'}`}
                                onClick={() => setStatusFilter(o.value)}
                                style={{
                                    padding: 'var(--space-2) var(--space-3)',
                                    fontSize: 'var(--text-sm)',
                                    border: 'none',
                                    borderRight: '1px solid var(--color-border)',
                                    cursor: 'pointer',
                                    background: statusFilter === o.value ? 'var(--color-primary)' : 'var(--color-surface-2)',
                                    color: statusFilter === o.value ? '#fff' : 'var(--color-text-dim)',
                                    transition: 'all var(--transition-fast)',
                                    fontFamily: 'var(--font-sans)',
                                }}
                            >
                                {o.label}
                            </button>
                        ))}
                    </div>

                    {/* Month nav */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        <button
                            id="calendar-prev-month"
                            onClick={() => setViewDate(d => addMonths(d, -1))}
                            style={navBtnStyle}
                        >
                            ‹
                        </button>
                        <span style={{ fontWeight: 600, fontSize: 'var(--text-base)', minWidth: 150, textAlign: 'center' }}>
                            {monthLabel(viewDate)}
                        </span>
                        <button
                            id="calendar-next-month"
                            onClick={() => setViewDate(d => addMonths(d, 1))}
                            style={navBtnStyle}
                        >
                            ›
                        </button>
                    </div>

                    {/* Today button */}
                    <button
                        id="calendar-today"
                        onClick={() => setViewDate(new Date(today.getFullYear(), today.getMonth(), 1))}
                        style={{ ...navBtnStyle, color: 'var(--color-primary)', borderColor: 'rgba(59,130,246,0.4)' }}
                    >
                        Today
                    </button>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)', color: 'var(--color-danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)' }}>
                    ⚠ {error}
                </div>
            )}

            {/* Calendar grid */}
            <div style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
                boxShadow: 'var(--shadow-md)',
            }}>
                {/* Day-of-week header */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', borderBottom: '1px solid var(--color-border)' }}>
                    {DOW_LABELS.map(d => (
                        <div key={d} style={{
                            padding: 'var(--space-2)',
                            textAlign: 'center',
                            fontSize: 'var(--text-xs)',
                            fontWeight: 600,
                            color: 'var(--color-text-dim)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.07em',
                            background: 'var(--color-surface-2)',
                        }}>
                            {d}
                        </div>
                    ))}
                </div>

                {/* 6-row grid */}
                {loading ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)' }}>
                        {Array.from({ length: 42 }).map((_, i) => (
                            <div key={i} style={{ minHeight: 90, padding: 6, borderRight: '1px solid var(--color-border)', borderBottom: '1px solid var(--color-border)' }}>
                                <div style={{ height: 10, width: 18, background: 'var(--color-surface-3)', borderRadius: 4, marginBottom: 6, animation: 'pulse 1.5s infinite' }} />
                                {i % 3 === 0 && <div style={{ height: 14, background: 'var(--color-surface-3)', borderRadius: 3, animation: 'pulse 1.5s infinite', animationDelay: `${(i % 7) * 0.1}s` }} />}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)' }}>
                        {cells.map((cell) => {
                            const isCurrentMonth = cell.getMonth() === month;
                            const isToday = isoDate(cell) === todayStr;
                            const dayBookings = bookingsForDate(cell);
                            return (
                                <DayCell
                                    key={isoDate(cell)}
                                    date={cell}
                                    isCurrentMonth={isCurrentMonth}
                                    isToday={isToday}
                                    bookingsForDay={dayBookings}
                                />
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Legend */}
            <div style={{ marginTop: 'var(--space-4)', display: 'flex', gap: 'var(--space-6)', alignItems: 'center' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Legend</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <div style={{ width: 24, height: 10, background: 'rgba(16,185,129,0.25)', border: '1px solid rgba(16,185,129,0.6)', borderRadius: 3 }} />
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Active</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <div style={{ width: 24, height: 10, background: 'rgba(239,68,68,0.18)', border: '1px solid rgba(239,68,68,0.5)', borderRadius: 3, opacity: 0.65 }} />
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Canceled</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>→ continues from previous week</span>
                </div>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginLeft: 'auto' }}>
                    Click a booking block to open its detail page
                </span>
            </div>
        </div>
    );
}
