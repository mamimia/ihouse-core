import React, { useState, useEffect } from 'react';

// Phase 885/886 — Canonical Worker Task Card
// - No admin links, no iCal refs, no internal IDs shown to workers
// - Live countdown, prominent date, location button parity between roles
// - propertyName is always primary title; propertyCode is secondary only

// ── Helpers ──────────────────────────────────────────────────────────────────

function getDefaultTime(kind: string): string {
    const map: Record<string, string> = {
        'CHECKOUT_VERIFY': '11:00',
        'CHECKOUT_PREP':   '11:00',
        'CLEANING':        '10:00',
        'CHECKIN_PREP':    '14:00',
        'GUEST_WELCOME':   '14:00',
    };
    return map[kind] || '12:00';
}

/** Returns true if the string looks like an opaque machine identifier workers should never see. */
function isOpaqueRef(s: string): boolean {
    if (!s) return false;
    // iCal-style, UUID, or known prefixes
    if (/^ICAL-/i.test(s)) return true;
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s)) return true;
    // Things that look like internal task titles, e.g. "Checkout verification for …"
    if (/^(checkout|check-out|checkin|check-in)\s+(verification|prep|task)\s+for/i.test(s)) return true;
    return false;
}

/** Compute nights from ISO date strings, returns null when not computable. */
export function computeNights(checkIn?: string, checkOut?: string): number | null {
    if (!checkIn || !checkOut) return null;
    const d1 = new Date(checkIn).getTime();
    const d2 = new Date(checkOut).getTime();
    if (isNaN(d1) || isNaN(d2) || d2 <= d1) return null;
    return Math.round((d2 - d1) / 86400000);
}

// ── Live Countdown ────────────────────────────────────────────────────────────

interface CountdownProps { targetDate?: string; targetTime?: string; status: string; }

function LiveCountdown({ targetDate, targetTime, status }: CountdownProps) {
    const [now, setNow] = useState(() => Date.now());

    useEffect(() => {
        const upper = status.toUpperCase();
        if (upper === 'COMPLETED' || upper === 'CANCELED') return;
        const t = setInterval(() => setNow(Date.now()), 1000);
        return () => clearInterval(t);
    }, [status]);

    const upper = status.toUpperCase();
    if (upper === 'COMPLETED') return <span style={{ color: 'var(--color-ok)', fontWeight: 700 }}>✅ Done</span>;
    if (upper === 'CANCELED')  return <span style={{ color: 'var(--color-text-faint)' }}>Canceled</span>;
    if (!targetDate)           return null;

    const time = targetTime || '12:00';
    const target = new Date(`${targetDate}T${time.length === 5 ? time + ':00' : time}`).getTime();
    if (isNaN(target)) return null;

    const diff = target - now;
    const abs  = Math.abs(diff);
    const overdue = diff < 0;
    const hours = Math.floor(abs / 3600000);
    const mins  = Math.floor((abs % 3600000) / 60000);
    const secs  = Math.floor((abs % 60000) / 1000);

    const isUrgent = !overdue && hours < 2;
    const color = overdue ? 'var(--color-alert)' : isUrgent ? 'var(--color-warn)' : 'var(--color-text-dim)';

    // Show h:mm for distant tasks, h:mm:ss when < 2 h for urgency
    const display = isUrgent || overdue
        ? `${hours}h ${String(mins).padStart(2,'0')}m ${String(secs).padStart(2,'0')}s`
        : `${hours}h ${String(mins).padStart(2,'0')}m`;

    return (
        <span style={{ color, fontWeight: overdue || isUrgent ? 700 : 400, fontVariantNumeric: 'tabular-nums' }}>
            {overdue ? '⚠ Overdue ' : '⏱ '}{display}
        </span>
    );
}

// ── Public Interface ──────────────────────────────────────────────────────────

export interface WorkerTaskCardProps {
    taskId?: string;
    kind: string;           // CLEANING | CHECKIN_PREP | CHECKOUT_VERIFY | MAINTENANCE …
    status: string;
    priority?: string;

    /** Real villa/property name — always the PRIMARY title. */
    propertyName: string;
    /** Short code, e.g. KPG-502 — shown as secondary only. */
    propertyCode?: string;

    /** ISO date string, e.g. 2026-03-25 */
    date: string;
    /** Override time for countdown, e.g. "14:00" */
    time?: string;

    /** Check-in date for nights calculation (optional, falls back to check_in) */
    checkIn?: string;
    /** Check-out date for nights calculation (optional) */
    checkOut?: string;

    guestName?: string;
    guestCount?: number;
    /** If not provided but checkIn + checkOut are given, computed automatically. */
    nights?: number;

    actionLabel?: string;

    onStart?: () => void;
    onAcknowledge?: () => void;
    /** Navigate to property location — renders 📍 button when provided. */
    onNavigate?: () => void;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function WorkerTaskCard(props: WorkerTaskCardProps) {
    const {
        kind, status, priority,
        propertyName, propertyCode,
        date, time, checkIn, checkOut,
        guestName, guestCount, nights: nightsProp,
        actionLabel, onStart, onAcknowledge, onNavigate,
    } = props;

    // ── Kind metadata ─────────────────────────────────────────────────────────
    let defaultAction = 'Start Task';
    let baseColor     = 'var(--color-primary)';
    let kindLabel     = kind;

    if (kind.includes('CLEAN')) {
        defaultAction = 'Start Cleaning';
        kindLabel     = '🧹 Cleaning';
    } else if (kind.includes('CHECKIN') || kind.includes('GUEST')) {
        defaultAction = 'Start Check-in';
        baseColor     = 'var(--color-sage)';
        kindLabel     = '🏠 Check-in';
    } else if (kind.includes('CHECKOUT')) {
        defaultAction = 'Start Check-out';
        baseColor     = 'var(--color-accent)';
        kindLabel     = '🚪 Check-out';
    } else if (kind.includes('MAINTENANCE')) {
        defaultAction = 'View Issue';
        baseColor     = 'var(--color-warn)';
        kindLabel     = '🔧 Maintenance';
    }

    // ── Status flags ──────────────────────────────────────────────────────────
    const upper      = status.toUpperCase();
    const isPending  = upper === 'PENDING';
    const isCompleted= upper === 'COMPLETED';
    const inProgress = upper === 'IN_PROGRESS';

    // ── Content sanitation ────────────────────────────────────────────────────
    // Title: prefer propertyName; if it's opaque fall back to propertyCode
    const displayTitle = (propertyName && !isOpaqueRef(propertyName))
        ? propertyName
        : (propertyCode || propertyName || '—');

    // Code: shown as secondary only when different from title
    const showCode = propertyCode && propertyCode !== displayTitle;

    // Guest name: never show iCal refs or internal task titles
    const displayGuest = (guestName && !isOpaqueRef(guestName)) ? guestName : undefined;

    // Nights: compute from dates if not supplied
    const computedNights = nightsProp ?? computeNights(checkIn, checkOut);

    // ── Countdown target ──────────────────────────────────────────────────────
    const countdownTime = time || getDefaultTime(kind);

    // ── Styles ────────────────────────────────────────────────────────────────
    const isCritical = priority === 'CRITICAL' && isPending;
    const cardBorder = isCritical ? 'rgba(248,81,73,0.4)' : 'var(--color-border)';

    return (
        <div
            style={{
                background: 'var(--color-surface)',
                border: `1px solid ${cardBorder}`,
                borderRadius: 'var(--radius-lg)',
                padding: 'var(--space-5)',
                cursor: onStart ? 'pointer' : 'default',
                transition: 'border-color 0.2s, box-shadow 0.2s',
                marginBottom: 'var(--space-3)',
            }}
            onClick={onStart}
            onMouseEnter={e => {
                if (!onStart) return;
                e.currentTarget.style.borderColor = baseColor;
                e.currentTarget.style.boxShadow = `0 0 0 1px ${baseColor}22`;
            }}
            onMouseLeave={e => {
                e.currentTarget.style.borderColor = cardBorder;
                e.currentTarget.style.boxShadow = 'none';
            }}
        >
            {/* ── Header row: property title + status badge ── */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                <div style={{ minWidth: 0, paddingRight: 8 }}>
                    {/* PRIMARY title — always the real property name */}
                    <div style={{
                        fontSize: 'var(--text-lg)', fontWeight: 800,
                        color: 'var(--color-text)', lineHeight: 1.2,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                        {displayTitle}
                    </div>
                    {/* Secondary code */}
                    {showCode && (
                        <div style={{
                            fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)',
                            fontFamily: 'var(--font-mono)', marginTop: 2,
                        }}>
                            {propertyCode}
                        </div>
                    )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
                    <span style={{
                        padding: '2px 10px', borderRadius: 12, fontSize: 'var(--text-xs)', fontWeight: 600,
                        background: isCompleted ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-2)',
                        color: isCompleted ? 'var(--color-ok)' : 'var(--color-text-dim)',
                    }}>
                        {status.replace(/_/g, ' ')}
                    </span>
                    {isCritical && (
                        <span style={{ fontSize: 9, color: '#fff', background: '#f85149', padding: '2px 5px', borderRadius: 4, fontWeight: 700 }}>
                            CRITICAL
                        </span>
                    )}
                </div>
            </div>

            {/* ── Date row — more prominent ── */}
            <div style={{
                display: 'flex', gap: 'var(--space-3)', alignItems: 'center',
                fontSize: 'var(--text-sm)', flexWrap: 'wrap',
                marginBottom: 'var(--space-2)',
            }}>
                <span style={{ color: baseColor, fontWeight: 700 }}>{kindLabel}</span>
                {date && (
                    <span style={{
                        color: 'var(--color-text)', fontWeight: 700,
                        fontSize: 'var(--text-sm)',
                    }}>
                        📅 {date}
                    </span>
                )}
            </div>

            {/* ── Live countdown ── */}
            {date && (
                <div style={{ fontSize: 'var(--text-xs)', marginBottom: 'var(--space-2)' }}>
                    <LiveCountdown targetDate={date} targetTime={countdownTime} status={status} />
                </div>
            )}

            {/* ── Optional metadata: guest, count, nights ── */}
            {(displayGuest || guestCount || computedNights) && (
                <div style={{
                    display: 'flex', gap: 'var(--space-3)', fontSize: 'var(--text-xs)',
                    color: 'var(--color-text-dim)', flexWrap: 'wrap',
                    marginBottom: 'var(--space-2)',
                }}>
                    {displayGuest && <span>👤 {displayGuest}</span>}
                    {guestCount    && <span>👥 {guestCount} guests</span>}
                    {computedNights && <span>🌙 {computedNights} {computedNights === 1 ? 'night' : 'nights'}</span>}
                </div>
            )}

            {/* ── Actions ── */}
            {(onStart || onAcknowledge || onNavigate) && (
                <div
                    style={{ marginTop: 'var(--space-4)', display: 'flex', gap: 'var(--space-2)' }}
                    onClick={e => e.stopPropagation()}
                >
                    {isPending && onAcknowledge && (
                        <button
                            onClick={onAcknowledge}
                            style={{
                                flex: 1, padding: '10px 8px',
                                background: 'rgba(212,149,106,0.1)', color: 'var(--color-warn)',
                                border: '1px solid rgba(212,149,106,0.3)', borderRadius: 'var(--radius-sm)',
                                fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                            }}
                        >
                            Acknowledge
                        </button>
                    )}
                    {onStart && (
                        <button
                            onClick={onStart}
                            style={{
                                flex: 2, padding: '10px 8px',
                                background: baseColor, color: '#fff',
                                border: 'none', borderRadius: 'var(--radius-sm)',
                                fontSize: 'var(--text-xs)', fontWeight: 700, cursor: 'pointer',
                            }}
                        >
                            {actionLabel || (inProgress ? 'Resume →' : defaultAction + ' →')}
                        </button>
                    )}
                    {onNavigate && (
                        <button
                            onClick={onNavigate}
                            title="Navigate to property"
                            style={{
                                flexShrink: 0, padding: '10px 14px',
                                background: 'var(--color-surface-2)', color: 'var(--color-text-dim)',
                                border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)',
                                fontSize: 'var(--text-base)', cursor: 'pointer',
                            }}
                        >
                            📍
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}
