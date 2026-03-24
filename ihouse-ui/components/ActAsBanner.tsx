'use client';

/**
 * Phase 870/871 — Act As Banner (Revised: multi-tab aware)
 *
 * Non-dismissible, high-contrast banner for active Act As sessions.
 * Appears whenever ActAsContext.isActing is true — which is now guaranteed
 * for any tab load where ihouse_token is an act_as JWT.
 *
 * New-tab case: shows a warning that the session cannot be fully restored,
 * and provides "End Session & Re-login" action.
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

    const roleLabel = ROLE_LABELS[session.actingAsRole] || session.actingAsRole.replace('_', ' ');
    const isUrgent = session.remainingSeconds < 300;

    // Detect new-tab case: original token sentinel was used
    const isNewTab = typeof window !== 'undefined'
        && (sessionStorage.getItem('ihouse_act_as_original_token') === '__new_tab__'
            || (!sessionStorage.getItem('ihouse_act_as_original_token')
                && !!localStorage.getItem('ihouse_act_as_original_token')));

    return (
        <div
            id="act-as-mode-banner"
            style={{
                position: 'sticky',
                top: 0,
                zIndex: 10000,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexWrap: 'wrap',
                gap: '8px 16px',
                padding: '10px 20px',
                background: 'linear-gradient(135deg, rgba(239,68,68,0.18) 0%, rgba(220,38,38,0.10) 100%)',
                borderBottom: '2px solid rgba(239,68,68,0.55)',
                fontFamily: "'Inter', sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: '#EF4444',
                backdropFilter: 'blur(8px)',
                letterSpacing: '0.02em',
                userSelect: 'none',
            }}
        >
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                🔴 <strong>ACTING AS:</strong>&nbsp;{roleLabel}
            </span>

            <span style={{ color: 'rgba(239,68,68,0.35)', fontWeight: 300 }}>|</span>

            <span style={{ fontWeight: 400, opacity: 0.8, fontSize: 12 }}>
                Admin: {session.realAdminEmail || session.realAdminId || 'unknown'}
            </span>

            <span style={{ color: 'rgba(239,68,68,0.35)', fontWeight: 300 }}>|</span>

            <span style={{
                fontWeight: 600,
                fontSize: 12,
                color: isUrgent ? '#F59E0B' : 'rgba(239,68,68,0.75)',
                animationName: isUrgent ? 'act-as-pulse' : 'none',
                animationDuration: '1s',
                animationIterationCount: 'infinite',
            }}>
                Expires: {formatTime(session.remainingSeconds)}
            </span>

            {isNewTab && (
                <>
                    <span style={{ color: 'rgba(239,68,68,0.35)', fontWeight: 300 }}>|</span>
                    <span style={{ fontSize: 11, color: '#F59E0B', fontWeight: 600 }}>
                        ⚠ New tab — re-login required after ending
                    </span>
                </>
            )}

            <span style={{ color: 'rgba(239,68,68,0.35)', fontWeight: 300 }}>|</span>

            <button
                id="act-as-end-session-btn"
                onClick={() => endActAs()}
                style={{
                    background: 'rgba(239,68,68,0.22)',
                    border: '1px solid rgba(239,68,68,0.45)',
                    borderRadius: 6,
                    padding: '4px 14px',
                    fontSize: 12,
                    fontWeight: 700,
                    color: '#EF4444',
                    cursor: 'pointer',
                    fontFamily: "'Inter', sans-serif",
                    transition: 'background 0.15s',
                    textTransform: 'uppercase',
                    letterSpacing: '0.03em',
                }}
                onMouseEnter={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.4)';
                }}
                onMouseLeave={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.22)';
                }}
            >
                {isNewTab ? 'End & Re-login' : 'End Session'}
            </button>

            <style>{`
                @keyframes act-as-pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.45; }
                }
            `}</style>
        </div>
    );
}
