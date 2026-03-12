'use client';

/**
 * Phase 311 — Admin Notification Delivery Dashboard
 * Route: /admin/notifications
 *
 * Displays the full notification delivery log with:
 *  - Channel filter (all, sms, email, line, whatsapp, telegram)
 *  - Status filter (all, sent, failed)
 *  - Reference ID search
 *  - Channel health indicators
 *  - Relative timestamps
 *  - Error detail expansion
 *  - Auto-refresh + SSE
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, NotificationLogEntry } from '../../../../lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relTime(iso: string) {
    const ms = Date.now() - new Date(iso).getTime();
    const min = Math.floor(ms / 60000);
    if (min < 1) return 'just now';
    if (min < 60) return `${min}m ago`;
    if (min < 1440) return `${Math.floor(min / 60)}h ago`;
    return `${Math.floor(min / 1440)}d ago`;
}

function channelColor(ch: string): string {
    const map: Record<string, string> = {
        sms: '#f59e0b',
        email: '#8b5cf6',
        line: '#00B900',
        whatsapp: '#25D366',
        telegram: '#229ED9',
    };
    return map[ch?.toLowerCase()] ?? '#6b7280';
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AdminNotificationsPage() {
    const [entries, setEntries] = useState<NotificationLogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [channelFilter, setChannelFilter] = useState('all');
    const [statusFilter, setStatusFilter] = useState('all');
    const [refSearch, setRefSearch] = useState('');
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const load = useCallback(async () => {
        try {
            const res = await api.getNotificationLog({ limit: 100, reference_id: refSearch || undefined });
            setEntries(res.entries ?? []);
        } catch {
            setEntries([]);
        } finally {
            setLoading(false);
        }
    }, [refSearch]);

    useEffect(() => { setLoading(true); load(); }, [load]);

    // 30s auto-refresh
    useEffect(() => {
        timerRef.current = setInterval(load, 30_000);
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [load]);

    // SSE for real-time
    useEffect(() => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('ihouse_token') ?? '' : '';
        const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
        const es = new EventSource(`${baseUrl}/events/stream?channels=alerts&token=${token}`);
        es.onmessage = (e) => {
            try {
                const evt = JSON.parse(e.data);
                if (evt.channel === 'alerts') setTimeout(load, 1000);
            } catch { /* ignore */ }
        };
        return () => es.close();
    }, [load]);

    // Filtering
    const filtered = entries.filter(e => {
        if (channelFilter !== 'all' && e.channel?.toLowerCase() !== channelFilter) return false;
        if (statusFilter !== 'all' && e.status !== statusFilter) return false;
        return true;
    });

    // Health stats
    const totalSent = entries.filter(e => e.status === 'sent').length;
    const totalFailed = entries.filter(e => e.status === 'failed').length;
    const channels = [...new Set(entries.map(e => e.channel?.toLowerCase()).filter(Boolean))];
    const channelStats = channels.map(ch => {
        const chEntries = entries.filter(e => e.channel?.toLowerCase() === ch);
        const sent = chEntries.filter(e => e.status === 'sent').length;
        const failed = chEntries.filter(e => e.status === 'failed').length;
        return { ch, total: chEntries.length, sent, failed, rate: chEntries.length ? Math.round((sent / chEntries.length) * 100) : 0 };
    });

    const filterBtn = (label: string, value: string, current: string, setter: (v: string) => void) => (
        <button
            key={value}
            onClick={() => setter(value)}
            style={{
                padding: '6px 14px',
                background: current === value ? 'var(--color-primary)' : 'var(--color-surface-2)',
                color: current === value ? '#fff' : 'var(--color-text-dim)',
                border: current === value ? 'none' : '1px solid var(--color-border)',
                borderRadius: 'var(--radius-full)',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all var(--transition-fast)',
            }}
        >{label}</button>
    );

    return (
        <div style={{ maxWidth: 1100 }}>

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-6)' }}>
                <a href="/admin" style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', textDecoration: 'none' }}>← Admin</a>
                <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', margin: '8px 0 4px' }}>
                    Notification <span style={{ color: 'var(--color-primary)' }}>Delivery</span>
                </h1>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', margin: 0 }}>
                    SMS · Email · LINE · WhatsApp · Telegram — delivery log &amp; channel health
                </p>
            </div>

            {/* Channel Health Cards */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: 'var(--space-3)',
                marginBottom: 'var(--space-6)',
            }}>
                {/* Overall */}
                <div style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: 'var(--space-4)',
                }}>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Total</div>
                    <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-text)', marginTop: 4 }}>{entries.length}</div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                        <span style={{ color: 'var(--color-ok)' }}>{totalSent} sent</span> · <span style={{ color: 'var(--color-danger)' }}>{totalFailed} failed</span>
                    </div>
                </div>

                {channelStats.map(cs => (
                    <div key={cs.ch} style={{
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-lg)',
                        padding: 'var(--space-4)',
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                            <span style={{
                                background: channelColor(cs.ch) + '22',
                                color: channelColor(cs.ch),
                                borderRadius: 4,
                                fontSize: 10,
                                fontWeight: 700,
                                padding: '2px 7px',
                                textTransform: 'uppercase',
                            }}>{cs.ch}</span>
                        </div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>{cs.total}</div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                            {cs.rate}% success
                        </div>
                        {/* Mini progress bar */}
                        <div style={{ height: 3, background: 'var(--color-surface-3)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
                            <div style={{ height: '100%', width: `${cs.rate}%`, background: cs.rate >= 80 ? 'var(--color-ok)' : cs.rate >= 50 ? 'var(--color-warn)' : 'var(--color-danger)', transition: 'width .5s' }} />
                        </div>
                    </div>
                ))}
            </div>

            {/* Filters */}
            <div style={{
                display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)', alignItems: 'center',
                marginBottom: 'var(--space-5)',
            }}>
                <div style={{ display: 'flex', gap: 6 }}>
                    {filterBtn('All', 'all', channelFilter, setChannelFilter)}
                    {filterBtn('SMS', 'sms', channelFilter, setChannelFilter)}
                    {filterBtn('Email', 'email', channelFilter, setChannelFilter)}
                    {filterBtn('LINE', 'line', channelFilter, setChannelFilter)}
                    {filterBtn('WhatsApp', 'whatsapp', channelFilter, setChannelFilter)}
                    {filterBtn('Telegram', 'telegram', channelFilter, setChannelFilter)}
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                    {filterBtn('All', 'all', statusFilter, setStatusFilter)}
                    {filterBtn('✓ Sent', 'sent', statusFilter, setStatusFilter)}
                    {filterBtn('✗ Failed', 'failed', statusFilter, setStatusFilter)}
                </div>
                <input
                    id="notif-ref-search"
                    value={refSearch}
                    onChange={e => setRefSearch(e.target.value)}
                    placeholder="Filter by reference ID…"
                    style={{
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        color: 'var(--color-text)',
                        fontSize: 'var(--text-sm)',
                        padding: 'var(--space-2) var(--space-3)',
                        width: 200,
                        fontFamily: 'var(--font-mono)',
                    }}
                />
                <button
                    onClick={() => { setLoading(true); load(); }}
                    style={{
                        background: 'var(--color-surface-2)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        color: 'var(--color-text-dim)',
                        fontSize: 'var(--text-xs)',
                        padding: '6px 12px',
                        cursor: 'pointer',
                    }}
                >↺ Refresh</button>
            </div>

            {/* Table */}
            <div style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
            }}>
                <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
                    <thead>
                        <tr>
                            {['Channel', 'Recipient', 'Type', 'Status', 'Reference', 'Time'].map(h => (
                                <th key={h} style={{
                                    padding: 'var(--space-3) var(--space-4)',
                                    textAlign: 'left',
                                    color: 'var(--color-text-dim)',
                                    fontWeight: 600,
                                    fontSize: 'var(--text-xs)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.06em',
                                    borderBottom: '1px solid var(--color-border)',
                                    background: 'var(--color-surface-2)',
                                    whiteSpace: 'nowrap',
                                }}>{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            [1, 2, 3, 4, 5].map(i => (
                                <tr key={i}>
                                    {[1, 2, 3, 4, 5, 6].map(j => (
                                        <td key={j} style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)' }}>
                                            <div style={{
                                                background: 'linear-gradient(90deg, var(--color-surface-2) 25%, var(--color-surface-3) 50%, var(--color-surface-2) 75%)',
                                                backgroundSize: '200% 100%',
                                                animation: 'shimmer 1.4s infinite',
                                                borderRadius: 4,
                                                height: 14,
                                                width: '70%',
                                            }} />
                                        </td>
                                    ))}
                                </tr>
                            ))
                        ) : filtered.length === 0 ? (
                            <tr>
                                <td colSpan={6} style={{ textAlign: 'center', padding: 'var(--space-10)', color: 'var(--color-text-dim)' }}>
                                    No notifications match current filters.
                                </td>
                            </tr>
                        ) : (
                            filtered.map((e, i) => {
                                const id = e.notification_id || e.notification_delivery_id || String(i);
                                const isExpanded = expandedId === id;
                                return (
                                    <tr
                                        key={id}
                                        onClick={() => e.status === 'failed' ? setExpandedId(isExpanded ? null : id) : undefined}
                                        style={{
                                            cursor: e.status === 'failed' ? 'pointer' : 'default',
                                            transition: 'background .12s',
                                        }}
                                        onMouseEnter={ev => (ev.currentTarget.style.background = 'rgba(59,130,246,0.04)')}
                                        onMouseLeave={ev => (ev.currentTarget.style.background = 'transparent')}
                                    >
                                        <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)' }}>
                                            <span style={{
                                                background: channelColor(e.channel) + '22',
                                                color: channelColor(e.channel),
                                                borderRadius: 4,
                                                fontSize: 10,
                                                fontWeight: 700,
                                                padding: '2px 8px',
                                                textTransform: 'uppercase',
                                            }}>{e.channel}</span>
                                        </td>
                                        <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {e.recipient}
                                        </td>
                                        <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                            {e.notification_type}
                                        </td>
                                        <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)' }}>
                                            <span style={{
                                                fontSize: 11,
                                                fontWeight: 700,
                                                color: e.status === 'sent' ? 'var(--color-ok)' : 'var(--color-danger)',
                                            }}>
                                                {e.status === 'sent' ? '✓ sent' : '✗ failed'}
                                            </span>
                                            {isExpanded && e.error_message && (
                                                <div style={{
                                                    marginTop: 6,
                                                    fontSize: 'var(--text-xs)',
                                                    color: 'var(--color-danger)',
                                                    background: 'rgba(239,68,68,0.06)',
                                                    borderRadius: 4,
                                                    padding: '4px 8px',
                                                    wordBreak: 'break-all',
                                                }}>
                                                    {e.error_message}
                                                </div>
                                            )}
                                        </td>
                                        <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                            {e.reference_id ?? '—'}
                                        </td>
                                        <td style={{ padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', whiteSpace: 'nowrap' }}>
                                            {relTime(e.dispatched_at)}
                                        </td>
                                    </tr>
                                );
                            })
                        )}
                    </tbody>
                </table>
                </div>
            </div>

            {/* Footer */}
            <div style={{
                paddingTop: 'var(--space-6)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-faint)',
                display: 'flex',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 'var(--space-2)',
            }}>
                <span>Domaniqo — Notification Delivery · Phase 311</span>
                <span>Auto-refresh: 30s · SSE live</span>
            </div>

            <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
        </div>
    );
}
