'use client';

/**
 * Phase 870 — Act As Banner
 *
 * Persistent, non-dismissible, high-contrast banner displayed during Act As sessions.
 * Per admin-preview-and-act-as.md §3:
 *
 *   🔴 ACTING AS: Cleaner  |  Admin: admin@domaniqo.com  |  Expires: 47 min  |  [End Session]
 *
 * Rules:
 *   - Cannot be hidden, minimized, or styled away
 *   - Uses high-contrast red/amber distinct from Preview Mode (yellow)
 *   - Shows real admin email for clarity
 *   - Includes countdown and explicit exit action
 */

import { useActAs } from '../lib/ActAsContext';

const ROLE_LABELS: Record<string, string> = {
    manager: 'Ops Manager',
    owner: 'Owner',
    cleaner: 'Cleaner',
    checkin: 'Check-in Staff',
    checkout: 'Check-out Staff',
    checkin_checkout: 'Check-in & Check-out',
    maintenance: 'Maintenance',
    worker: 'Staff',
};

function formatTime(totalSeconds: number): string {
    if (totalSeconds <= 0) return '0:00';
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}:${s.toString().padStart(2, '0')}`;
    return `0:${s.toString().padStart(2, '0')}`;
}

export default function ActAsBanner() {
    const { session, isActing, endActAs } = useActAs();

    if (!isActing || !session) return null;

    const roleLabel = ROLE_LABELS[session.actingAsRole] || session.actingAsRole;
    const isUrgent = session.remainingSeconds < 300; // < 5 min

    return (
        <div
            id="act-as-mode-banner"
            style={{
                position: 'sticky',
                top: 0,
                zIndex: 10000, // Higher than preview banner (9999)
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 16,
                padding: '10px 20px',
                background: 'linear-gradient(135deg, rgba(239,68,68,0.20) 0%, rgba(239,68,68,0.10) 100%)',
                borderBottom: '2px solid rgba(239,68,68,0.6)',
                fontFamily: "'Inter', sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: '#EF4444',
                backdropFilter: 'blur(8px)',
                letterSpacing: '0.02em',
                // Cannot be hidden or styled away
                pointerEvents: 'auto',
                userSelect: 'none',
            }}
        >
            <span>🔴 ACTING AS: {roleLabel}</span>
            <span style={{ color: 'rgba(239,68,68,0.4)', fontWeight: 400 }}>|</span>
            <span style={{ fontWeight: 400, opacity: 0.8, fontSize: 12 }}>
                Admin: {session.realAdminEmail || 'unknown'}
            </span>
            <span style={{ color: 'rgba(239,68,68,0.4)', fontWeight: 400 }}>|</span>
            <span style={{
                fontWeight: 600,
                fontSize: 12,
                color: isUrgent ? '#F59E0B' : 'rgba(239,68,68,0.8)',
                animation: isUrgent ? 'pulse 1s infinite' : 'none',
            }}>
                Expires: {formatTime(session.remainingSeconds)}
            </span>
            <span style={{ color: 'rgba(239,68,68,0.4)', fontWeight: 400 }}>|</span>
            <button
                onClick={() => endActAs()}
                style={{
                    background: 'rgba(239,68,68,0.25)',
                    border: '1px solid rgba(239,68,68,0.5)',
                    borderRadius: 6,
                    padding: '4px 14px',
                    fontSize: 12,
                    fontWeight: 700,
                    color: '#EF4444',
                    cursor: 'pointer',
                    fontFamily: "'Inter', sans-serif",
                    transition: 'all 0.15s',
                    textTransform: 'uppercase',
                    letterSpacing: '0.03em',
                }}
                onMouseEnter={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.45)';
                }}
                onMouseLeave={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.25)';
                }}
            >
                End Session
            </button>

            {/* Pulse animation for urgent timer */}
            <style>{`
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
            `}</style>
        </div>
    );
}
