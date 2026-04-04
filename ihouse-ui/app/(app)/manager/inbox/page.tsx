'use client';

/**
 * Phase 1051 / 1052 — Operational Guest Inbox + Reply Path
 * Phase 1068 — Auto-poll (15s), unread badge sync via OMUnreadContext
 * Route: /manager/inbox
 *
 * 1051: Inbox list (one row per stay-thread), sorted unread-first.
 *       Click row → slide-in thread drawer (read-only view).
 * 1052: Real reply input in the drawer.
 *       POST /manager/guest-messages/{booking_id}/reply
 *       sender_type='host', sender_id=caller user_id (NOT tenant_id).
 *       New message appended optimistically. Drawer stays open.
 *       Dossier Chat tab picks up the reply on next load (shared DB table).
 *       Guest portal: NOT exposed yet (Phase 1053).
 * 1068: Auto-polls every 15s. On open/reply, calls unread context refresh()
 *       to sync nav badge immediately.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { apiFetch } from '@/lib/api';
import { useUnread } from '@/contexts/OMUnreadContext';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ConversationSummary {
    booking_id: string;
    property_id: string;
    property_display_name: string;
    guest_name: string;
    checkin_date: string | null;
    checkout_date: string | null;
    booking_status: string | null;
    unread_count: number;
    last_message: string;
    last_message_at: string | null;
    last_sender_type: string | null;
    assigned_to: string;
    assigned_to_name: string;
}

interface ThreadMessage {
    id: string;
    sender_type: string;
    message: string;
    read_at: string | null;
    created_at: string;
    is_deleted?: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtRelative(iso: string | null): string {
    if (!iso) return '—';
    try {
        const d = new Date(iso);
        const diffMs = Date.now() - d.getTime();
        const diffMin = Math.floor(diffMs / 60000);
        if (diffMin < 1) return 'just now';
        if (diffMin < 60) return `${diffMin}m ago`;
        const diffH = Math.floor(diffMin / 60);
        if (diffH < 24) return `${diffH}h ago`;
        const diffD = Math.floor(diffH / 24);
        if (diffD < 7) return `${diffD}d ago`;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return iso ?? '—'; }
}

function fmtDateShort(iso: string | null): string {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return iso; }
}

function fmtFull(iso: string): string {
    try {
        return new Date(iso).toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch { return iso; }
}

function statusColor(status: string | null): string {
    const s = (status || '').toLowerCase();
    if (['checked_in', 'instay', 'active', 'checkedin'].includes(s)) return '#3fb850';
    if (['confirmed', 'booked', 'approved'].includes(s)) return '#58a6ff';
    if (['cancelled', 'canceled'].includes(s)) return '#ef4444';
    return 'var(--color-text-dim)';
}

// ---------------------------------------------------------------------------
// Thread Drawer — slide-in panel showing full message history for one stay
// ---------------------------------------------------------------------------

function ThreadDrawer({
    conversation,
    onClose,
    onMarkedRead,
    onReplySent,
}: {
    conversation: ConversationSummary;
    onClose: () => void;
    onMarkedRead: (booking_id: string) => void;
    onReplySent: (booking_id: string, message: string) => void;
}) {
    const [messages, setMessages] = useState<ThreadMessage[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    // Phase 1052 — reply state
    const [replyText, setReplyText] = useState('');
    const [sending, setSending] = useState(false);
    const [sendError, setSendError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await apiFetch<{ messages: ThreadMessage[] }>(
                    `/manager/guest-messages/${encodeURIComponent(conversation.booking_id)}`
                );
                if (!cancelled) {
                    setMessages(res.messages ?? []);
                }
                // Mark thread as read (best-effort, non-blocking)
                if (conversation.unread_count > 0) {
                    apiFetch(
                        `/manager/guest-messages/${encodeURIComponent(conversation.booking_id)}/read`,
                        { method: 'PATCH' }
                    )
                        .then(() => { if (!cancelled) onMarkedRead(conversation.booking_id); })
                        .catch(() => {/* non-blocking */});
                }
            } catch {
                if (!cancelled) setError('Could not load thread. Please retry.');
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        load();
        return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [conversation.booking_id]);

    // Close on Escape
    useEffect(() => {
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [onClose]);

    // Phase 1052 — send a host reply
    const sendReply = async () => {
        const text = replyText.trim();
        if (!text || sending) return;
        setSending(true);
        setSendError(null);
        try {
            const res = await apiFetch<{ message: ThreadMessage }>(
                `/manager/guest-messages/${encodeURIComponent(conversation.booking_id)}/reply`,
                { method: 'POST', body: JSON.stringify({ message: text }) }
            );
            // Optimistic append
            setMessages(prev => [...prev, res.message]);
            setReplyText('');
            // Update inbox list last_message
            onReplySent(conversation.booking_id, text);
        } catch {
            setSendError('Could not send. Please retry.');
        } finally {
            setSending(false);
        }
    };

    return (
        <>
            {/* Backdrop */}
            <div
                onClick={onClose}
                style={{
                    position: 'fixed', inset: 0,
                    background: 'rgba(0,0,0,0.45)',
                    backdropFilter: 'blur(2px)',
                    zIndex: 300,
                }}
            />

            {/* Drawer panel */}
            <div style={{
                position: 'fixed', top: 0, right: 0, bottom: 0,
                width: '100%', maxWidth: 520,
                background: 'var(--color-surface)',
                borderLeft: '1px solid var(--color-border)',
                zIndex: 301,
                display: 'flex', flexDirection: 'column',
                animation: 'slideInRight .22s ease',
                boxShadow: '-8px 0 40px rgba(0,0,0,0.3)',
            }}>

                {/* Drawer header */}
                <div style={{
                    padding: '16px 20px',
                    borderBottom: '1px solid var(--color-border)',
                    background: 'var(--color-surface-2)',
                    flexShrink: 0,
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text)', marginBottom: 3 }}>
                                {conversation.guest_name || 'Guest'}
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 4 }}>
                                🏠 {conversation.property_display_name}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--color-text-dim)' }}>
                                {fmtDateShort(conversation.checkin_date)} → {fmtDateShort(conversation.checkout_date)}
                                {conversation.booking_status && (
                                    <span style={{
                                        marginLeft: 10, fontSize: 10, fontWeight: 700,
                                        color: statusColor(conversation.booking_status),
                                        textTransform: 'uppercase', letterSpacing: '0.05em',
                                    }}>
                                        {conversation.booking_status}
                                    </span>
                                )}
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            style={{
                                background: 'none', border: 'none', fontSize: 20,
                                color: 'var(--color-text-dim)', cursor: 'pointer',
                                padding: '0 0 0 16px', flexShrink: 0,
                            }}
                        >✕</button>
                    </div>
                    <div style={{
                        marginTop: 8, fontSize: 11, color: 'var(--color-text-dim)',
                        fontFamily: 'var(--font-mono)',
                    }}>
                        {conversation.booking_id}
                    </div>
                </div>

                {/* Thread body */}
                <div style={{
                    flex: 1, overflowY: 'auto',
                    padding: '16px 20px',
                    display: 'flex', flexDirection: 'column', gap: 10,
                }}>
                    {loading ? (
                        <div style={{ textAlign: 'center', padding: 40, color: 'var(--color-text-dim)', fontSize: 13 }}>
                            Loading thread…
                        </div>
                    ) : error ? (
                        <div style={{
                            background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
                            borderRadius: 8, padding: '12px 16px',
                            color: '#ef4444', fontSize: 13,
                        }}>⚠ {error}</div>
                    ) : messages.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: 40, color: 'var(--color-muted)', fontSize: 13 }}>
                            No messages in this thread yet.
                        </div>
                    ) : (
                        messages.map((msg) => {
                            const isGuest = msg.sender_type === 'guest';
                            const isDeleted = msg.is_deleted === true;
                            return (
                                <div
                                    key={msg.id}
                                    style={{
                                        display: 'flex', flexDirection: 'column',
                                        alignItems: isGuest ? 'flex-start' : 'flex-end',
                                    }}
                                >
                                    {/* Sender label */}
                                    <div style={{
                                        fontSize: 10, fontWeight: 700,
                                        color: isGuest ? 'var(--color-text-dim)' : '#58a6ff',
                                        textTransform: 'uppercase', letterSpacing: '0.05em',
                                        marginBottom: 3,
                                    }}>
                                        {isGuest ? `👤 ${conversation.guest_name || 'Guest'}` : '🏢 Host'}
                                    </div>
                                    {/* Bubble — Phase 1068: tombstone for deleted */}
                                    {isDeleted ? (
                                        <div style={{
                                            maxWidth: '78%',
                                            padding: '7px 14px',
                                            borderRadius: isGuest ? '4px 16px 16px 16px' : '16px 4px 16px 16px',
                                            background: 'transparent',
                                            border: '1px dashed var(--color-border)',
                                            fontSize: 12, color: 'var(--color-muted)',
                                            fontStyle: 'italic', lineHeight: 1.5,
                                        }}>
                                            🗑 Message deleted by guest
                                        </div>
                                    ) : (
                                        <div style={{
                                            maxWidth: '78%',
                                            padding: '9px 14px',
                                            borderRadius: isGuest ? '4px 16px 16px 16px' : '16px 4px 16px 16px',
                                            background: isGuest ? 'var(--color-surface-2)' : 'rgba(88,166,255,0.1)',
                                            border: isGuest ? '1px solid var(--color-border)' : '1px solid rgba(88,166,255,0.2)',
                                            fontSize: 13, color: 'var(--color-text)',
                                            lineHeight: 1.55, wordBreak: 'break-word',
                                        }}>
                                            {msg.message}
                                        </div>
                                    )}
                                    {/* Meta: timestamp + read indicator */}
                                    <div style={{
                                        fontSize: 10, color: 'var(--color-muted)',
                                        marginTop: 3, display: 'flex', gap: 6, alignItems: 'center',
                                    }}>
                                        <span>{fmtFull(msg.created_at)}</span>
                                        {isGuest && !isDeleted && (
                                            <span style={{
                                                color: msg.read_at ? '#3fb850' : 'var(--color-text-dim)',
                                                fontWeight: 600,
                                            }}>
                                                {msg.read_at ? '✓ Read' : '○ Unread'}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Reply footer — Phase 1052 */}
                <div style={{
                    padding: '12px 16px',
                    borderTop: '1px solid var(--color-border)',
                    background: 'var(--color-surface-2)',
                    flexShrink: 0,
                }}>
                    {sendError && (
                        <div style={{
                            fontSize: 11, color: '#ef4444',
                            marginBottom: 8,
                        }}>⚠ {sendError}</div>
                    )}
                    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                        <textarea
                            value={replyText}
                            onChange={e => setReplyText(e.target.value)}
                            onKeyDown={e => {
                                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                                    e.preventDefault();
                                    sendReply();
                                }
                            }}
                            placeholder="Reply to guest… (⌘↵ to send)"
                            rows={2}
                            disabled={sending}
                            style={{
                                flex: 1,
                                resize: 'none',
                                background: 'var(--color-surface)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 8,
                                color: 'var(--color-text)',
                                fontSize: 13,
                                padding: '8px 12px',
                                fontFamily: 'inherit',
                                lineHeight: 1.5,
                                outline: 'none',
                                opacity: sending ? 0.6 : 1,
                                transition: 'border-color .15s',
                            }}
                            onFocus={e => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                            onBlur={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
                        />
                        <button
                            onClick={sendReply}
                            disabled={sending || !replyText.trim()}
                            style={{
                                flexShrink: 0,
                                padding: '0 16px',
                                height: 60,
                                background: sending || !replyText.trim()
                                    ? 'var(--color-surface-3,#2d2d2d)'
                                    : 'linear-gradient(135deg,#6366f1,#4f46e5)',
                                border: 'none',
                                borderRadius: 8,
                                color: '#fff',
                                fontSize: 13, fontWeight: 700,
                                cursor: sending || !replyText.trim() ? 'not-allowed' : 'pointer',
                                opacity: sending || !replyText.trim() ? 0.55 : 1,
                                transition: 'all .15s',
                                boxShadow: sending || !replyText.trim() ? 'none' : '0 2px 10px rgba(99,102,241,0.4)',
                                display: 'flex', alignItems: 'center', gap: 6,
                            }}
                        >
                            {sending ? '…' : '↑ Send'}
                        </button>
                    </div>
                    <div style={{
                        fontSize: 10, color: 'var(--color-muted)',
                        marginTop: 5, textAlign: 'right',
                    }}>
                        Host reply · not visible to guest yet
                    </div>
                </div>
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Conversation row
// ---------------------------------------------------------------------------

function ConversationRow({
    conv,
    onClick,
}: {
    conv: ConversationSummary;
    onClick: () => void;
}) {
    const hasUnread = conv.unread_count > 0;

    return (
        <div
            onClick={onClick}
            style={{
                padding: '14px 20px',
                borderBottom: '1px solid var(--color-border)',
                cursor: 'pointer',
                transition: 'background .12s',
                background: hasUnread ? 'rgba(99,102,241,0.03)' : 'transparent',
                borderLeft: hasUnread ? '3px solid var(--color-primary)' : '3px solid transparent',
                display: 'flex', gap: 14, alignItems: 'flex-start',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
            onMouseLeave={e => (e.currentTarget.style.background = hasUnread ? 'rgba(99,102,241,0.03)' : 'transparent')}
        >
            {/* Unread dot */}
            <div style={{
                width: 8, height: 8, borderRadius: '50%', flexShrink: 0, marginTop: 6,
                background: hasUnread ? 'var(--color-primary)' : 'transparent',
                boxShadow: hasUnread ? '0 0 6px rgba(99,102,241,0.6)' : 'none',
                transition: 'all .2s',
            }} />

            {/* Main content */}
            <div style={{ flex: 1, minWidth: 0 }}>
                {/* Row 1: guest name + timestamp */}
                <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'baseline', gap: 8, marginBottom: 3,
                }}>
                    <span style={{
                        fontSize: 14, fontWeight: hasUnread ? 700 : 500,
                        color: 'var(--color-text)', overflow: 'hidden',
                        textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                        {conv.guest_name || 'Guest'}
                    </span>
                    <span style={{
                        fontSize: 11, color: 'var(--color-muted)', flexShrink: 0,
                        fontWeight: hasUnread ? 600 : 400,
                    }}>
                        {fmtRelative(conv.last_message_at)}
                    </span>
                </div>

                {/* Row 2: property + dates */}
                <div style={{
                    fontSize: 12, color: 'var(--color-text-dim)', marginBottom: 5,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                    🏠 {conv.property_display_name}
                    <span style={{ marginLeft: 8, color: 'var(--color-muted)', fontSize: 11 }}>
                        {fmtDateShort(conv.checkin_date)} → {fmtDateShort(conv.checkout_date)}
                    </span>
                    {conv.booking_status && (
                        <span style={{
                            marginLeft: 8, fontSize: 10, fontWeight: 700,
                            color: statusColor(conv.booking_status),
                            textTransform: 'uppercase', letterSpacing: '0.04em',
                        }}>
                            {conv.booking_status}
                        </span>
                    )}
                </div>

                {/* Row 3: last message preview */}
                <div style={{
                    fontSize: 12, color: hasUnread ? 'var(--color-text)' : 'var(--color-text-dim)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    display: 'flex', gap: 5, alignItems: 'center',
                }}>
                    {conv.last_sender_type === 'host' && (
                        <span style={{ color: '#58a6ff', fontWeight: 600, fontSize: 11, flexShrink: 0 }}>You:</span>
                    )}
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {conv.last_message || 'No message yet'}
                    </span>
                </div>
            </div>

            {/* Unread badge */}
            {hasUnread && (
                <div style={{
                    flexShrink: 0,
                    minWidth: 20, height: 20, borderRadius: 999,
                    background: 'var(--color-primary)',
                    color: '#fff', fontSize: 11, fontWeight: 700,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    padding: '0 6px',
                }}>
                    {conv.unread_count}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ManagerInboxPage() {
    const [conversations, setConversations] = useState<ConversationSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [openThread, setOpenThread] = useState<ConversationSummary | null>(null);
    const [lastFetched, setLastFetched] = useState<Date | null>(null);
    const { refresh: refreshBadge } = useUnread();
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await apiFetch<{ conversations: ConversationSummary[] }>(
                '/manager/guest-messages'
            );
            setConversations(res.conversations ?? []);
            setLastFetched(new Date());
        } catch {
            setError('Could not load inbox. Please retry.');
        } finally {
            setLoading(false);
        }
    }, []);

    // Initial load + 15s auto-poll
    useEffect(() => {
        load();
        pollRef.current = setInterval(load, 15_000);
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, [load]);

    // Mark as read in local state when a thread is opened
    const handleMarkedRead = useCallback((booking_id: string) => {
        setConversations(prev =>
            prev.map(c => c.booking_id === booking_id ? { ...c, unread_count: 0 } : c)
        );
        // Sync nav badge immediately
        refreshBadge();
    }, [refreshBadge]);

    // Update inbox row when a reply is sent (Phase 1052)
    const handleReplySent = useCallback((booking_id: string, message: string) => {
        setConversations(prev => prev.map(c =>
            c.booking_id === booking_id
                ? { ...c, last_message: message, last_sender_type: 'host', last_message_at: new Date().toISOString() }
                : c
        ));
        // Sync badge immediately
        refreshBadge();
    }, [refreshBadge]);


    const totalUnread = conversations.reduce((s, c) => s + c.unread_count, 0);

    return (
        <div style={{
            minHeight: '100vh',
            background: 'var(--color-bg)',
            color: 'var(--color-text)',
            fontFamily: 'var(--font-sans)',
        }}>
            <style>{`
                @keyframes slideInRight {
                    from { transform: translateX(100%); opacity: 0; }
                    to   { transform: translateX(0);    opacity: 1; }
                }
                @keyframes fadeInUp {
                    from { opacity: 0; transform: translateY(8px); }
                    to   { opacity: 1; transform: translateY(0); }
                }
            `}</style>

            {/* Page header */}
            <div style={{
                padding: '20px 24px 0',
                maxWidth: 720, margin: '0 auto',
            }}>
                <a
                    href="/manager"
                    style={{
                        fontSize: 12, color: 'var(--color-text-dim)',
                        textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4,
                        marginBottom: 16,
                    }}
                >
                    ← Manager
                </a>

                <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', marginBottom: 20, gap: 12, flexWrap: 'wrap',
                }}>
                    <div>
                        <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--color-text)', margin: 0 }}>
                            💬 Guest Inbox
                        </h1>
                        <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 4 }}>
                            {loading
                                ? 'Loading…'
                                : conversations.length === 0
                                    ? 'No active threads assigned to you'
                                    : `${conversations.length} thread${conversations.length !== 1 ? 's' : ''}`
                                        + (totalUnread > 0 ? ` · ${totalUnread} unread` : ' · all read')}
                        </div>
                    </div>

                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        {lastFetched && (
                            <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>
                                Updated {fmtRelative(lastFetched.toISOString())}
                            </span>
                        )}
                        <button
                            onClick={load}
                            disabled={loading}
                            style={{
                                padding: '6px 14px',
                                background: 'var(--color-surface)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 8,
                                color: 'var(--color-text-dim)',
                                fontSize: 12, fontWeight: 600, cursor: 'pointer',
                                opacity: loading ? 0.5 : 1,
                                transition: 'opacity .15s',
                            }}
                        >
                            {loading ? '…' : '↻ Refresh'}
                        </button>
                    </div>
                </div>
            </div>

            {/* Inbox content */}
            <div style={{ maxWidth: 720, margin: '0 auto', padding: '0 24px 40px' }}>

                {/* Unread summary bar — only when unread */}
                {totalUnread > 0 && !loading && (
                    <div style={{
                        background: 'rgba(99,102,241,0.07)',
                        border: '1px solid rgba(99,102,241,0.18)',
                        borderRadius: 10, padding: '10px 16px',
                        marginBottom: 16,
                        fontSize: 13, color: 'var(--color-text)',
                        display: 'flex', alignItems: 'center', gap: 8,
                        animation: 'fadeInUp .2s ease',
                    }}>
                        <span style={{
                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                            width: 22, height: 22, borderRadius: '50%',
                            background: 'var(--color-primary)',
                            color: '#fff', fontSize: 11, fontWeight: 700, flexShrink: 0,
                        }}>
                            {totalUnread}
                        </span>
                        <span>
                            {totalUnread === 1
                                ? '1 unread message from a guest'
                                : `${totalUnread} unread guest messages`}
                        </span>
                    </div>
                )}

                {/* Inbox panel */}
                <div style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 12,
                    overflow: 'hidden',
                    animation: 'fadeInUp .25s ease',
                }}>
                    {loading ? (
                        /* Skeleton */
                        [1, 2, 3].map(i => (
                            <div key={i} style={{
                                padding: '14px 20px',
                                borderBottom: '1px solid var(--color-border)',
                                display: 'flex', gap: 14, alignItems: 'flex-start',
                            }}>
                                <div style={{
                                    width: 8, height: 8, borderRadius: '50%',
                                    background: 'var(--color-surface-2)', marginTop: 6,
                                }} />
                                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 7 }}>
                                    <div style={{
                                        height: 13, width: '40%', borderRadius: 6,
                                        background: 'linear-gradient(90deg,var(--color-surface-2) 25%,var(--color-surface-3,#2d2d2d) 50%,var(--color-surface-2) 75%)',
                                        backgroundSize: '200% 100%',
                                        animation: 'shimmer 1.4s infinite',
                                    }} />
                                    <div style={{
                                        height: 11, width: '60%', borderRadius: 6,
                                        background: 'linear-gradient(90deg,var(--color-surface-2) 25%,var(--color-surface-3,#2d2d2d) 50%,var(--color-surface-2) 75%)',
                                        backgroundSize: '200% 100%',
                                        animation: 'shimmer 1.4s infinite',
                                    }} />
                                    <div style={{
                                        height: 11, width: '80%', borderRadius: 6,
                                        background: 'linear-gradient(90deg,var(--color-surface-2) 25%,var(--color-surface-3,#2d2d2d) 50%,var(--color-surface-2) 75%)',
                                        backgroundSize: '200% 100%',
                                        animation: 'shimmer 1.4s infinite',
                                    }} />
                                </div>
                            </div>
                        ))
                    ) : error ? (
                        <div style={{
                            padding: '24px 20px', textAlign: 'center',
                            color: '#ef4444', fontSize: 13,
                        }}>
                            ⚠ {error}
                            <button
                                onClick={load}
                                style={{
                                    display: 'block', margin: '10px auto 0',
                                    background: 'none', border: 'none',
                                    color: 'var(--color-primary)', cursor: 'pointer',
                                    fontSize: 12, fontWeight: 600,
                                }}
                            >
                                Retry
                            </button>
                        </div>
                    ) : conversations.length === 0 ? (
                        <div style={{ padding: '48px 20px', textAlign: 'center' }}>
                            <div style={{ fontSize: 36, marginBottom: 12 }}>💬</div>
                            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text)', marginBottom: 6 }}>
                                Inbox is clear
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--color-muted)', maxWidth: 280, margin: '0 auto' }}>
                                No guest messages are currently assigned to you.
                                Messages appear here when guests write via their portal.
                            </div>
                        </div>
                    ) : (
                        conversations.map(conv => (
                            <ConversationRow
                                key={conv.booking_id}
                                conv={conv}
                                onClick={() => setOpenThread(conv)}
                            />
                        ))
                    )}
                </div>

                {/* Context note */}
                {!loading && conversations.length > 0 && (
                    <div style={{
                        marginTop: 12, fontSize: 11,
                        color: 'var(--color-muted)', textAlign: 'center',
                    }}>
                        Only threads assigned to you are shown here.
                        Open a thread to see the full conversation.
                    </div>
                )}
            </div>

            {/* Thread drawer overlay */}
            {openThread && (
                <ThreadDrawer
                    conversation={openThread}
                    onClose={() => setOpenThread(null)}
                    onMarkedRead={handleMarkedRead}
                    onReplySent={handleReplySent}
                />
            )}
        </div>
    );
}
