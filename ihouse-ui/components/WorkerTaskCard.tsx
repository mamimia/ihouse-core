import React, { useState, useEffect } from 'react';

// Phase 885/886/887 — Canonical Worker Task Card
// Layout: dense 2-column header — property+meta left, countdown+status right
// Hierarchy: property name primary; date + live countdown prominent; action row compact

// ── Helpers ──────────────────────────────────────────────────────────────────

function getDefaultTime(kind: string): string {
    const map: Record<string, string> = {
        'CHECKOUT_VERIFY': '11:00',
        'CHECKOUT_PREP':   '11:00',
        'CLEANING':        '10:00',
        'CHECKIN_PREP':    '14:00',
        'GUEST_WELCOME':   '14:00',
        'MAINTENANCE':     '17:00',
    };
    return map[kind] || '12:00';
}

function isOpaqueRef(s: string): boolean {
    if (!s) return false;
    if (/^ICAL-/i.test(s)) return true;
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s)) return true;
    if (/^(checkout|check-out|checkin|check-in)\s+(verification|prep|task)\s+for/i.test(s)) return true;
    return false;
}

export function computeNights(checkIn?: string, checkOut?: string): number | null {
    if (!checkIn || !checkOut) return null;
    const d1 = new Date(checkIn).getTime();
    const d2 = new Date(checkOut).getTime();
    if (isNaN(d1) || isNaN(d2) || d2 <= d1) return null;
    const n = Math.round((d2 - d1) / 86400000);
    return n > 0 ? n : null;
}

// ── Live Countdown — always ticks every second ───────────────────────────────

interface CountdownProps { targetDate?: string; targetTime?: string; status: string; }

export function LiveCountdown({ targetDate, targetTime, status }: CountdownProps) {
    const [now, setNow] = useState(() => Date.now());

    useEffect(() => {
        const upper = status.toUpperCase();
        if (upper === 'COMPLETED' || upper === 'CANCELED') return;
        const t = setInterval(() => setNow(Date.now()), 1000);
        return () => clearInterval(t);
    }, [status]);

    const upper = status.toUpperCase();
    if (upper === 'COMPLETED') return (
        <span style={{ color: 'var(--color-ok)', fontWeight: 700, fontSize: 'inherit' }}>✅ Done</span>
    );
    if (upper === 'CANCELED') return (
        <span style={{ color: 'var(--color-text-faint)', fontSize: 'inherit' }}>Canceled</span>
    );
    if (!targetDate) return (
        <span style={{ color: 'var(--color-text-faint)', fontSize: 'inherit' }}>No date</span>
    );

    const time = targetTime || '12:00';
    const target = new Date(`${targetDate}T${time.length === 5 ? time + ':00' : time}`).getTime();
    if (isNaN(target)) return null;

    const diff    = target - now;
    const abs     = Math.abs(diff);
    const overdue = diff < 0;
    const hours   = Math.floor(abs / 3600000);
    const mins    = Math.floor((abs % 3600000) / 60000);
    const secs    = Math.floor((abs % 60000) / 1000);

    const isWarning = !overdue && diff <= 25 * 60000;
    const isCriticalWarning = !overdue && diff <= 5 * 60000;
    const isActiveTask = upper === 'PENDING' || upper === 'ACKNOWLEDGED';

    let color = 'var(--color-text-dim)';
    let animation = 'none';

    if (overdue) {
        color = 'var(--color-danger)';
        if (isActiveTask) animation = 'pulse-fast 1s ease-in-out infinite';
    } else if (isCriticalWarning) {
        color = 'var(--color-danger)';
        if (isActiveTask) animation = 'pulse-soft 2s ease-in-out infinite';
    } else if (isWarning) {
        color = 'var(--color-warn)';
    }

    // Always show seconds
    const display = overdue
        ? `${hours}h ${String(mins).padStart(2, '0')}m ${String(secs).padStart(2, '0')}s`
        : `${hours}h ${String(mins).padStart(2, '0')}m ${String(secs).padStart(2, '0')}s`;

    return (
        <span style={{
            color,
            fontWeight: overdue || isWarning || isCriticalWarning ? 700 : 500,
            fontVariantNumeric: 'tabular-nums',
            fontSize: 'inherit',
            letterSpacing: '-0.01em',
            animation,
        }}>
            {overdue ? '⚠ ' : '⏱ '}{display}
        </span>
    );
}

function AckButton({ date, time, onAcknowledge }: { date: string, time: string, onAcknowledge: () => void }) {
    const [msg, setMsg] = useState('');

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (msg) return; // Prevent multiple clicks during cooldown
        
        if (!date) {
            onAcknowledge();
            return;
        }
        const parsedDate = date && date !== 'Unknown' ? date : new Date().toISOString().split('T')[0];
        const target = new Date(`${parsedDate}T${time.length === 5 ? time + ':00' : time}`).getTime();
        if (isNaN(target)) {
            onAcknowledge();
            return;
        }
        const diff = target - Date.now();
        const twentyFourHours = 24 * 60 * 60 * 1000;
        
        if (diff > twentyFourHours) {
            const h = Math.floor(diff / 3600000);
            const m = Math.floor((diff % 3600000) / 60000);
            const days = Math.floor(h / 24);
            const remainingH = h % 24;
            
            let timeStr = '';
            if (days > 0) timeStr = `${days}d ${remainingH}h`;
            else timeStr = `${h}h ${m}m`;
            
            setMsg(`Available in ${timeStr}`);
            setTimeout(() => setMsg(''), 5000);
        } else {
            onAcknowledge();
        }
    };

    return (
        <button onClick={handleClick} style={{
            flex: 1, padding: '8px 6px',
            background: msg ? 'var(--color-surface-2)' : 'rgba(212,149,106,0.1)',
            color: msg ? 'var(--color-text-dim)' : 'var(--color-warn)',
            border: msg ? '1px solid var(--color-border)' : '1px solid rgba(212,149,106,0.3)',
            borderRadius: 'var(--radius-sm)',
            fontSize: 11, fontWeight: 600, cursor: msg ? 'default' : 'pointer',
            transition: 'all 0.2s',
        }}>
            {msg || 'Acknowledge'}
        </button>
    );
}

// ── Public Interface ──────────────────────────────────────────────────────────

export interface WorkerTaskCardProps {
    taskId?: string;
    kind: string;
    status: string;
    priority?: string;

    propertyName: string;
    propertyCode?: string;

    date: string;
    time?: string;
    checkIn?: string;
    checkOut?: string;

    guestName?: string;
    guestCount?: number;
    nights?: number;

    actionLabel?: string;
    onStart?: () => void;
    onAcknowledge?: () => void;
    onNavigate?: () => void;
}

// ── Component — dense 2-column layout ────────────────────────────────────────

export default function WorkerTaskCard(props: WorkerTaskCardProps) {
    const {
        kind, status, priority,
        propertyName, propertyCode,
        date, time, checkIn, checkOut,
        guestName, guestCount, nights: nightsProp,
        actionLabel, onStart, onAcknowledge, onNavigate,
    } = props;

    // Kind metadata
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

    const upper      = status.toUpperCase();
    const isPending  = upper === 'PENDING';
    const isCompleted = upper === 'COMPLETED';
    const inProgress = upper === 'IN_PROGRESS';

    const displayTitle = (propertyName && !isOpaqueRef(propertyName))
        ? propertyName
        : (propertyCode || propertyName || '—');
    const showCode = propertyCode && propertyCode !== displayTitle;
    const displayGuest = (guestName && !isOpaqueRef(guestName)) ? guestName : undefined;

    // Nights: use prop if > 1 (don't show "1 night" when synthetic), else compute from dates
    // Synthetic tasks default check_in=check_out so nights=0 → computeNights returns null → omit
    const computedNights = (nightsProp != null && nightsProp > 1)
        ? nightsProp
        : computeNights(checkIn, checkOut);

    const countdownTime = time || getDefaultTime(kind);
    const isCritical    = priority === 'CRITICAL' && isPending;
    const cardBorder    = isCritical ? 'rgba(248,81,73,0.4)' : 'var(--color-border)';

    return (
        <div
            style={{
                background: 'var(--color-surface)',
                border: `1px solid ${cardBorder}`,
                borderRadius: 'var(--radius-lg)',
                padding: '12px var(--space-4)',   // tighter vertical padding
                cursor: onStart ? 'pointer' : 'default',
                transition: 'border-color 0.15s, box-shadow 0.15s',
                marginBottom: 'var(--space-2)',   // tighter stack gap
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
            <style>{`
            @keyframes pulse-soft {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            @keyframes pulse-fast {
                0% { opacity: 1; }
                50% { opacity: 0.2; }
                100% { opacity: 1; }
            }
            `}</style>
            {/* ── Row 1: Property name (left) + Countdown + Status (right) ── */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                gap: 8,
            }}>
                {/* LEFT: property title */}
                <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{
                        fontSize: 'var(--text-base)', fontWeight: 800,
                        color: 'var(--color-text)', lineHeight: 1.2,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                        {displayTitle}
                    </div>
                    {showCode && (
                        <div style={{
                            fontSize: 10, color: 'var(--color-text-faint)',
                            fontFamily: 'var(--font-mono)', marginTop: 1,
                        }}>
                            {propertyCode}
                        </div>
                    )}
                </div>

                {/* RIGHT: live countdown + status badge — stacked */}
                <div style={{
                    display: 'flex', flexDirection: 'column',
                    alignItems: 'flex-end', gap: 3, flexShrink: 0,
                }}>
                    {/* Countdown — prominent, always visible */}
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, textAlign: 'right' }}>
                        <LiveCountdown targetDate={date} targetTime={countdownTime} status={status} />
                    </div>
                    {/* Status badge */}
                    <span style={{
                        padding: '1px 8px', borderRadius: 10,
                        fontSize: 10, fontWeight: 600,
                        background: isCompleted ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-2)',
                        color: isCompleted ? 'var(--color-ok)' : 'var(--color-text-faint)',
                    }}>
                        {status.replace(/_/g, ' ')}
                    </span>
                    {isCritical && (
                        <span style={{
                            fontSize: 9, color: '#fff', background: '#f85149',
                            padding: '1px 5px', borderRadius: 4, fontWeight: 700,
                        }}>CRITICAL</span>
                    )}
                </div>
            </div>

            {/* ── Row 2: kind badge + date + optional metadata ── */}
            <div style={{
                display: 'flex', gap: 'var(--space-3)', alignItems: 'center',
                flexWrap: 'wrap', marginTop: 6,
                fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)',
            }}>
                <span style={{ color: baseColor, fontWeight: 700 }}>{kindLabel}</span>
                {date && (
                    <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>📅 {date}</span>
                )}
                {displayGuest && <span>👤 {displayGuest}</span>}
                {guestCount    && <span>👥 {guestCount}</span>}
                {computedNights && (
                    <span>🌙 {computedNights} {computedNights === 1 ? 'night' : 'nights'}</span>
                )}
            </div>

            {/* ── Row 3: action buttons ── */}
            {(onStart || onAcknowledge || onNavigate) && (
                <div
                    style={{ marginTop: 10, display: 'flex', gap: 6 }}
                    onClick={e => e.stopPropagation()}
                >
                    {isPending && onAcknowledge && (
                        <AckButton
                            date={date}
                            time={countdownTime}
                            onAcknowledge={onAcknowledge}
                        />
                    )}
                    {onStart && (
                        <button onClick={onStart} style={{
                            flex: 2, padding: '8px 6px',
                            background: baseColor, color: '#fff',
                            border: 'none', borderRadius: 'var(--radius-sm)',
                            fontSize: 11, fontWeight: 700, cursor: 'pointer',
                        }}>
                            {actionLabel || (inProgress ? 'Resume →' : defaultAction + ' →')}
                        </button>
                    )}
                    {onNavigate && (
                        <button onClick={onNavigate} title="Navigate to property" style={{
                            flexShrink: 0, padding: '8px 12px',
                            background: 'var(--color-surface-2)', color: 'var(--color-text-dim)',
                            border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)',
                            fontSize: 13, cursor: 'pointer',
                        }}>📍</button>
                    )}
                </div>
            )}
        </div>
    );
}
