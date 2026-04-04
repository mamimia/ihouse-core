'use client';

/**
 * Phase 1068 — OM Floating Unread Popup Alert
 *
 * A small, non-blocking popup that appears in the bottom-right corner
 * when a new guest message or system event (checkout completion, etc.) arrives.
 *
 * Behavior:
 * - Appears when newestAlert is set in OMUnreadContext
 * - Auto-dismisses after 8 seconds
 * - Clicking it navigates to /manager/inbox
 * - Can be manually dismissed with ✕
 * - Shows guest name + message preview + sender type label
 * - Does NOT mark as read — opening the thread in the inbox does that
 */

import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useUnread } from '@/contexts/OMUnreadContext';

const AUTO_DISMISS_MS = 8_000;

export default function OMUnreadPopup() {
    const { newestAlert, dismissAlert } = useUnread();
    const router = useRouter();
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Auto-dismiss after 8 seconds
    useEffect(() => {
        if (!newestAlert) return;
        timerRef.current = setTimeout(() => {
            dismissAlert();
        }, AUTO_DISMISS_MS);
        return () => {
            if (timerRef.current) clearTimeout(timerRef.current);
        };
    }, [newestAlert, dismissAlert]);

    if (!newestAlert) return null;

    const isSystemEvent = newestAlert.sender_type === 'system';

    const handleClick = () => {
        dismissAlert();
        router.push('/manager/inbox');
    };

    return (
        <>
            <style>{`
                @keyframes omPopupIn {
                    from { opacity: 0; transform: translateY(16px) scale(0.96); }
                    to   { opacity: 1; transform: translateY(0)    scale(1); }
                }
                @keyframes omPopupProgress {
                    from { transform: scaleX(1); }
                    to   { transform: scaleX(0); }
                }
            `}</style>
            <div
                onClick={handleClick}
                style={{
                    position: 'fixed',
                    bottom: 80,
                    right: 20,
                    zIndex: 9999,
                    width: 320,
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 14,
                    boxShadow: '0 8px 32px rgba(0,0,0,0.25), 0 1px 0 rgba(255,255,255,0.06) inset',
                    overflow: 'hidden',
                    cursor: 'pointer',
                    animation: 'omPopupIn 0.28s cubic-bezier(0.22, 1, 0.36, 1)',
                    // Coloured left border to signal type
                    borderLeft: isSystemEvent
                        ? '4px solid #f59e0b'
                        : '4px solid var(--color-primary)',
                }}
            >
                {/* Progress bar — shrinks over AUTO_DISMISS_MS */}
                <div style={{
                    position: 'absolute',
                    bottom: 0, left: 0, right: 0,
                    height: 2,
                    background: isSystemEvent
                        ? 'rgba(245,158,11,0.35)'
                        : 'rgba(99,102,241,0.35)',
                    transformOrigin: 'left',
                    animation: `omPopupProgress ${AUTO_DISMISS_MS}ms linear forwards`,
                }} />

                {/* Content */}
                <div style={{ padding: '14px 14px 16px 16px' }}>
                    {/* Header row */}
                    <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: 8,
                    }}>
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                        }}>
                            <span style={{ fontSize: 14 }}>
                                {isSystemEvent ? '📋' : '💬'}
                            </span>
                            <span style={{
                                fontSize: 11, fontWeight: 700,
                                color: isSystemEvent ? '#f59e0b' : 'var(--color-primary)',
                                textTransform: 'uppercase', letterSpacing: '0.06em',
                            }}>
                                {isSystemEvent ? 'Guest Event' : 'Guest Message'}
                            </span>
                        </div>
                        <button
                            onClick={e => { e.stopPropagation(); dismissAlert(); }}
                            style={{
                                background: 'none', border: 'none',
                                fontSize: 14, color: 'var(--color-text-dim)',
                                cursor: 'pointer', padding: '0 0 0 8px',
                                lineHeight: 1, flexShrink: 0,
                            }}
                            aria-label="Dismiss"
                        >✕</button>
                    </div>

                    {/* Guest name */}
                    <div style={{
                        fontSize: 13, fontWeight: 700,
                        color: 'var(--color-text)',
                        marginBottom: 4,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                        {newestAlert.guest_name}
                    </div>

                    {/* Message preview */}
                    <div style={{
                        fontSize: 12, color: 'var(--color-text-dim)',
                        lineHeight: 1.5,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                    }}>
                        {newestAlert.preview || '—'}
                    </div>

                    {/* CTA hint */}
                    <div style={{
                        marginTop: 10, fontSize: 10,
                        color: 'var(--color-muted)',
                        display: 'flex', alignItems: 'center', gap: 4,
                    }}>
                        <span>Tap to open inbox</span>
                        <span style={{ opacity: 0.5 }}>·</span>
                        <span>auto-dismiss in {Math.round(AUTO_DISMISS_MS / 1000)}s</span>
                    </div>
                </div>
            </div>
        </>
    );
}
