import React, { useState, useEffect } from 'react';

// Phase 885 — Canonical Worker Task Card component
// Ensures all worker roles see the exact same worker-safe UI without admin links.

function getTargetTime(kind: string, dueTime?: string): string {
    const defaultTimes: Record<string, string> = {
        'CHECKOUT_VERIFY': '11:00:00',
        'CHECKOUT_PREP': '11:00:00',
        'CLEANING': '11:00:00',
        'CHECKIN_PREP': '14:00:00',
        'GUEST_WELCOME': '14:00:00',
    };
    return dueTime || defaultTimes[kind] || '12:00:00';
}

function TaskCountdownChip({ targetDate, targetTime, status }: { targetDate?: string, targetTime?: string, status: string }) {
    const [now, setNow] = useState(Date.now());
    
    useEffect(() => {
        if (status === 'COMPLETED' || status === 'completed' || status === 'CANCELED' || status === 'canceled') return;
        const timer = setInterval(() => setNow(Date.now()), 1000);
        return () => clearInterval(timer);
    }, [status]);

    if (status === 'COMPLETED' || status === 'completed') {
        return <span style={{ color: 'var(--color-ok)' }}>✅ Done</span>;
    }
    if (status === 'CANCELED' || status === 'canceled') {
        return <span style={{ color: 'var(--color-text-faint)' }}>Canceled</span>;
    }
    
    if (!targetDate) return <span style={{ color: 'var(--color-text-dim)' }}>⏱ No date</span>;

    const timeStr = targetTime || '14:00:00';
    const target = new Date(`${targetDate}T${timeStr}`).getTime();
    if (isNaN(target)) return null;

    const diff = target - now;
    const isOverdue = diff < 0;
    const absDiff = Math.abs(diff);

    const hours = Math.floor(absDiff / 3600000);
    const mins = Math.floor((absDiff % 3600000) / 60000);

    const display = `${isOverdue ? 'Overdue by ' : 'Due in '}${hours}h ${mins}m`;
    const color = isOverdue ? 'var(--color-alert)' : (hours < 2 ? 'var(--color-warn)' : 'var(--color-text-dim)');

    return <span style={{ color, fontWeight: isOverdue ? 700 : 400 }}>{isOverdue ? '⚠ ' : '⏱ '}{display}</span>;
}

export interface WorkerTaskCardProps {
    taskId?: string; // optional just for identifying
    kind: string; // 'CLEANING', 'CHECKIN_PREP', etc.
    status: string;
    priority?: string;
    
    propertyName: string;
    propertyCode: string; // usually property_id
    
    date: string;
    time?: string;
    
    // Optional metadata
    guestName?: string;
    guestCount?: number;
    nights?: number;
    
    // Overrides
    actionLabel?: string;
    
    // Actions
    onStart?: () => void;
    onAcknowledge?: () => void;
    onNavigate?: () => void;
}

export default function WorkerTaskCard(props: WorkerTaskCardProps) {
    const { 
        kind, status, priority, 
        propertyName, propertyCode, 
        date, time, guestName, guestCount, nights, 
        actionLabel, onStart, onAcknowledge, onNavigate 
    } = props;

    let defaultAction = 'Start Task';
    let baseColor = 'var(--color-primary)';
    let kindLabel = kind;
    
    if (kind.includes('CLEAN')) {
        defaultAction = 'Start Cleaning';
        kindLabel = '🧹 Cleaning';
    } else if (kind.includes('CHECKIN') || kind.includes('GUEST')) {
        defaultAction = 'Start Check-in';
        baseColor = 'var(--color-sage)';
        kindLabel = '🏠 Check-in';
    } else if (kind.includes('CHECKOUT')) {
        defaultAction = 'Start Check-out';
        baseColor = 'var(--color-accent)';
        kindLabel = '📦 Check-out';
    } else if (kind.includes('MAINTENANCE')) {
        defaultAction = 'View Maintenance';
        baseColor = 'var(--color-warn)';
        kindLabel = '🔧 Maintenance';
    }

    const isPending = status.toUpperCase() === 'PENDING';
    const isCompleted = status.toUpperCase() === 'COMPLETED';
    const inProgress = status.toUpperCase() === 'IN_PROGRESS';

    const cardStyle = {
        background: 'var(--color-surface)', 
        border: `1px solid ${priority === 'CRITICAL' && isPending ? 'rgba(248,81,73,0.4)' : 'var(--color-border)'}`,
        borderRadius: 'var(--radius-lg)', 
        padding: 'var(--space-5)',
        cursor: 'pointer', 
        transition: 'border-color 0.2s',
        marginBottom: 'var(--space-3)'
    };

    // Clean guest name mapping (Phase 885)
    // "iCal IDs / opaque booking refs must not be shown to workers"
    const isCleanGuestName = guestName && !guestName.startsWith('ICAL-') && !guestName.startsWith('Check-in') && !guestName.startsWith('Check-out');

    return (
        <div style={cardStyle}
             onClick={onStart}
             onMouseEnter={e => (e.currentTarget.style.borderColor = baseColor)}
             onMouseLeave={e => (e.currentTarget.style.borderColor = priority === 'CRITICAL' && isPending ? 'rgba(248,81,73,0.4)' : 'var(--color-border)')}>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                <div>
                    <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                        {propertyName || propertyCode}
                    </div>
                    {propertyName && propertyName !== propertyCode && (
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                            {propertyCode}
                        </div>
                    )}
                </div>
                <div style={{ display: 'flex', gap: 4, flexDirection: 'column', alignItems: 'flex-end' }}>
                    <span style={{
                        padding: '2px 10px', borderRadius: 12, fontSize: 'var(--text-xs)', fontWeight: 600,
                        background: isCompleted ? 'rgba(74,222,128,0.1)' : 'var(--color-surface-2)', 
                        color: isCompleted ? 'var(--color-ok)' : 'var(--color-text-dim)',
                    }}>
                        {status.replace('_', ' ')}
                    </span>
                    {priority === 'CRITICAL' && isPending && (
                        <span style={{ fontSize: 9, color: '#fff', background: '#f85149', padding: '2px 4px', borderRadius: 4, fontWeight: 700 }}>
                            CRITICAL
                        </span>
                    )}
                </div>
            </div>

            <div style={{ display: 'flex', gap: 'var(--space-4)', fontSize: 'var(--text-xs)', flexWrap: 'wrap', marginBottom: 'var(--space-2)' }}>
                <span style={{ color: baseColor, fontWeight: 600 }}>{kindLabel}</span>
                <span style={{ color: 'var(--color-text-dim)' }}>📅 {date || '—'}</span>
                {date && <TaskCountdownChip targetDate={date} targetTime={getTargetTime(kind, time)} status={status} />}
            </div>

            {/* Optional Metadata block (guests, nights) */}
            {(isCleanGuestName || guestCount || nights) ? (
                <div style={{ display: 'flex', gap: 'var(--space-4)', fontSize: 'var(--text-xs)', marginTop: 'var(--space-1)', flexWrap: 'wrap' }}>
                    {isCleanGuestName && (
                        <span style={{ color: 'var(--color-text-dim)', fontWeight: 600 }}>👤 {guestName}</span>
                    )}
                    {guestCount ? <span style={{ color: 'var(--color-text-dim)' }}>👥 {guestCount} guests</span> : null}
                    {nights ? <span style={{ color: 'var(--color-text-dim)' }}>🌙 {nights} nights</span> : null}
                </div>
            ) : null}

            {/* Actions */}
            <div style={{ marginTop: 'var(--space-4)', display: 'flex', gap: 'var(--space-2)' }} onClick={e => e.stopPropagation()}>
                {isPending && onAcknowledge && (
                    <button onClick={onAcknowledge} style={{
                        flex: 1, padding: '8px', background: 'rgba(212,149,106,0.1)', color: 'var(--color-warn)',
                        border: '1px solid rgba(212,149,106,0.3)', borderRadius: 'var(--radius-sm)',
                        fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                    }}>Acknowledge</button>
                )}
                <button onClick={onStart} style={{
                    flex: onAcknowledge && isPending ? 1 : 2, padding: '8px', background: baseColor, color: '#fff',
                    border: 'none', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                }}>
                    {actionLabel || (inProgress ? 'Resume →' : defaultAction + ' →')}
                </button>
                {onNavigate && (
                    <button onClick={onNavigate} style={{
                        padding: '8px 12px', background: 'var(--color-surface-2)', color: 'var(--color-text-dim)',
                        border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', cursor: 'pointer',
                    }}>📍</button>
                )}
            </div>
        </div>
    );
}
