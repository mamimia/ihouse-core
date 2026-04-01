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

function FormattedDate({ dateString }: { dateString: string }) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
        return <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>📅 {dateString}</span>;
    }
    const [year, month, day] = dateString.split('-');
    
    return (
        <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: '1px', color: 'var(--color-text)' }}>
            <span style={{ fontSize: '1.05em', marginRight: 4 }}>📅</span>
            <span style={{ fontSize: '1em', fontWeight: 500, color: 'var(--color-text-dim)' }}>{year}-</span>
            <span style={{ fontSize: '1.05em', fontWeight: 600 }}>{month}-</span>
            <span style={{ fontSize: '1.25em', fontWeight: 800 }}>{day}</span>
        </span>
    );
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

/** Human-readable duration string, tiered by magnitude:
 *  > 48h  → "13d"
 *  24–48h → "1d 6h"
 *  <24h   → "18h 20m"
 *  <60m   → "42m 08s"  (precision matters here)
 */
function fmtDuration(absMs: number): string {
    const totalMins = Math.floor(absMs / 60000);
    const secs      = Math.floor((absMs % 60000) / 1000);
    const totalHrs  = Math.floor(totalMins / 60);
    const mins      = totalMins % 60;
    const days      = Math.floor(totalHrs / 24);
    const hrs       = totalHrs % 24;

    if (days >= 2)  return `${days}d`;
    if (days === 1) return hrs > 0 ? `${days}d ${hrs}h` : `${days}d`;
    if (totalHrs >= 1) return `${totalHrs}h ${String(mins).padStart(2, '0')}m`;
    return `${mins}m ${String(secs).padStart(2, '0')}s`;
}

export function LiveCountdown({ targetDate, targetTime, status }: CountdownProps) {
    const [now, setNow] = useState(() => Date.now());

    useEffect(() => {
        const upper = status.toUpperCase();
        if (upper === 'COMPLETED' || upper === 'CANCELED') return;
        
        // Adaptive tick rate: 1s if < 1h, else 60s
        const diff = targetDate ? new Date(`${targetDate}T${targetTime || '12:00'}`).getTime() - Date.now() : Infinity;
        const interval = (diff < 3600000) ? 1000 : 60000;
        
        const t = setInterval(() => setNow(Date.now()), interval);
        return () => clearInterval(t);
    }, [status, targetDate, targetTime]);

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

    const display = fmtDuration(abs);
    const prefix  = overdue ? '⚠ overdue ' : 'in ';

    return (
        <span style={{
            color,
            fontWeight: overdue || isWarning || isCriticalWarning ? 700 : 500,
            fontVariantNumeric: 'tabular-nums',
            fontSize: 'inherit',
            letterSpacing: '-0.01em',
            animation,
        }}>
            {prefix}{display}
        </span>
    );
}

// ── AckButton — uses server-provided ack_is_open / ack_allowed_at ───────────
// Phase 1033: gate decision comes from server. Local computation removed.
// At rest: always shows "Acknowledge".
// On early press: flashes "Opens in Xh Ym" for 3 seconds then reverts.

function computeOpensIn(allowedAtIso: string): string {
    const delta = new Date(allowedAtIso).getTime() - Date.now();
    if (delta <= 0) return '';
    const totalMins = Math.floor(delta / 60000);
    const h = Math.floor(totalMins / 60);
    const m = totalMins % 60;
    if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
    return `${m}m`;
}

function AckButton({
    onAcknowledge,
    ackIsOpen,
    ackAllowedAt,
}: {
    onAcknowledge: () => void;
    ackIsOpen?: boolean;
    ackAllowedAt?: string;
}) {
    const [msg, setMsg] = useState('');

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (msg) return; // prevent double-tap during flash

        const open = ackIsOpen !== false; // undefined = treat as open
        if (open) {
            onAcknowledge();
            return;
        }
        // Window not yet open — flash "Opens in Xh Ym"
        const label = ackAllowedAt ? computeOpensIn(ackAllowedAt) : '';
        setMsg(label ? `Opens in ${label}` : 'Opens soon');
        setTimeout(() => setMsg(''), 3000);
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

// ── StartButton — mirrors AckButton, uses server-provided start_is_open ───────
// Phase 1033: same compact flash pattern.
// At rest: always shows the task-specific start label.
// On early press: flashes "Opens in Xh Ym" for 3 seconds then reverts.
// MAINTENANCE kind: startIsOpen is always true (no gate) — behaves as normal button.

function StartButton({
    label,
    baseColor,
    onStart,
    startIsOpen,
    startAllowedAt,
}: {
    label: string;
    baseColor: string;
    onStart: () => void;
    startIsOpen?: boolean;
    startAllowedAt?: string;
}) {
    const [msg, setMsg] = useState('');

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (msg) return;

        const open = startIsOpen !== false; // undefined = treat as open
        if (open) {
            onStart();
            return;
        }
        const timeLabel = startAllowedAt ? computeOpensIn(startAllowedAt) : '';
        setMsg(timeLabel ? `Opens in ${timeLabel}` : 'Opens soon');
        setTimeout(() => setMsg(''), 3000);
    };

    return (
        <button onClick={handleClick} style={{
            flex: 2, padding: '8px 6px',
            background: msg ? 'var(--color-surface-2)' : baseColor,
            color: msg ? 'var(--color-text-dim)' : '#fff',
            border: msg ? '1px solid var(--color-border)' : 'none',
            borderRadius: 'var(--radius-sm)',
            fontSize: 11, fontWeight: 700,
            cursor: msg ? 'default' : 'pointer',
            transition: 'all 0.2s',
        }}>
            {msg || label}
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

    date: string;       // task due_date — drives countdown for non-checkout tasks
    time?: string;
    checkIn?: string;
    checkOut?: string;  // real booking checkout date — used for eligibility gating

    guestName?: string;
    guestCount?: number;
    nights?: number;

    actionLabel?: string;
    onStart?: () => void;
    onAcknowledge?: () => void;
    onNavigate?: () => void;

    // Phase 993-fix: Eligibility gate — when false, Start is locked until checkout date.
    // Computed by the parent from check_out, NOT from task.due_date.
    // Defaults to true (backwards-compatible for non-checkout tasks).
    isActionable?: boolean;
    // Label shown on the locked Start button (e.g. "Checkout: Apr 7")
    lockedLabel?: string;
    // Phase 1000: Early checkout exception flow
    isEarlyCheckout?: boolean;
    earlyCheckoutEffectiveAt?: string;   // TIMESTAMPTZ from booking_state
    originalCheckoutDate?: string;       // original booking check_out for reference display

    // Phase 1033: Server-computed timing fields from compute_task_timing().
    // Frontend reads these directly — no local gate computation.
    ackIsOpen?: boolean;        // true = window open, false = too early, undefined = treat as open
    ackAllowedAt?: string;      // ISO timestamp — used to compute "Opens in Xh Ym" flash
    startIsOpen?: boolean;      // same semantics for Start action
    startAllowedAt?: string;    // ISO timestamp
}

// ── Component — dense 2-column layout ────────────────────────────────────────

export default function WorkerTaskCard(props: WorkerTaskCardProps) {
    const {
        kind, status, priority,
        propertyName, propertyCode,
        date, time, checkIn, checkOut,
        guestName, guestCount, nights: nightsProp,
        actionLabel, onStart, onAcknowledge, onNavigate,
        isActionable = true, lockedLabel,
        isEarlyCheckout, earlyCheckoutEffectiveAt, originalCheckoutDate,
        ackIsOpen, ackAllowedAt, startIsOpen, startAllowedAt,
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
        baseColor     = isEarlyCheckout ? '#d97706' : 'var(--color-accent)';  // orange for early
        kindLabel     = isEarlyCheckout ? '🔴 Early Check-out' : '🚪 Check-out';
        if (isEarlyCheckout) defaultAction = 'Start Early Check-out';
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
    const cardBorder    = isEarlyCheckout
        ? 'rgba(217,119,6,0.45)'    // amber border for early checkout
        : (isCritical ? 'rgba(248,81,73,0.4)' : 'var(--color-border)');

    // Format effective_at for display (just the date+time part)
    let earlyEffectiveDisplay: string | null = null;
    if (isEarlyCheckout && earlyCheckoutEffectiveAt) {
        try {
            earlyEffectiveDisplay = new Date(earlyCheckoutEffectiveAt).toLocaleString('en-US', {
                weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
            });
        } catch { earlyEffectiveDisplay = earlyCheckoutEffectiveAt; }
    }
    let originalCheckoutDisplay: string | null = null;
    if (isEarlyCheckout && originalCheckoutDate) {
        try {
            const d = originalCheckoutDate.slice(0, 10);
            originalCheckoutDisplay = new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        } catch { originalCheckoutDisplay = originalCheckoutDate; }
    }

    return (
        <div
            style={{
                background: isEarlyCheckout ? '#fffbeb' : 'var(--color-surface)',
                border: `1px solid ${cardBorder}`,
                borderRadius: 'var(--radius-lg)',
                padding: '12px var(--space-4)',
                cursor: (onStart && isActionable) ? 'pointer' : 'default',
                transition: 'border-color 0.15s, box-shadow 0.15s',
                marginBottom: 'var(--space-2)',
                opacity: isActionable ? 1 : 0.85,
            }}
            onClick={isActionable ? onStart : undefined}
            onMouseEnter={e => {
                if (!onStart || !isActionable) return;
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
                    <FormattedDate dateString={date} />
                )}
                {displayGuest && <span>👤 {displayGuest}</span>}
                {guestCount    && <span>👥 {guestCount}</span>}
                {computedNights && (
                    <span>🌙 {computedNights} {computedNights === 1 ? 'night' : 'nights'}</span>
                )}
            </div>

            {/* ── Early Check-out Exception Banner ── */}
            {isEarlyCheckout && (
                <div style={{
                    marginTop: 8,
                    background: '#fef3c7',
                    border: '1px solid #fde68a',
                    borderRadius: 6,
                    padding: '6px 10px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 3,
                }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#92400e', letterSpacing: '0.02em' }}>
                        ⚡ EARLY DEPARTURE — Exception Approved
                    </div>
                    {earlyEffectiveDisplay && (
                        <div style={{ fontSize: 11, color: '#78350f', fontWeight: 600 }}>
                            Effective: {earlyEffectiveDisplay}
                        </div>
                    )}
                    {originalCheckoutDisplay && (
                        <div style={{ fontSize: 10, color: '#92400e', opacity: 0.75 }}>
                            Original checkout: {originalCheckoutDisplay}
                        </div>
                    )}
                </div>
            )}

            {/* ── Row 3: action buttons ── */}
            {(onStart || onAcknowledge || onNavigate) && (
                <div
                    style={{ marginTop: 10, display: 'flex', gap: 6 }}
                    onClick={e => e.stopPropagation()}
                >
                    {isPending && onAcknowledge && (
                        <AckButton
                            onAcknowledge={onAcknowledge}
                            ackIsOpen={ackIsOpen}
                            ackAllowedAt={ackAllowedAt}
                        />
                    )}
                    {onStart && (
                        isActionable ? (
                            <StartButton
                                label={actionLabel || (inProgress ? 'Resume →' : defaultAction + ' →')}
                                baseColor={baseColor}
                                onStart={onStart}
                                startIsOpen={startIsOpen}
                                startAllowedAt={startAllowedAt}
                            />
                        ) : (
                            <button disabled style={{
                                flex: 2, padding: '8px 6px',
                                background: 'var(--color-surface-2)', color: 'var(--color-text-faint)',
                                border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)',
                                fontSize: 11, fontWeight: 600, cursor: 'not-allowed',
                            }}>
                                🔒 {lockedLabel || 'Not yet available'}
                            </button>
                        )
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
