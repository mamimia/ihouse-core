/*
 * Phase 205 — DLQ Inspector Admin Page
 *
 * Route: /admin/dlq
 * Lists entries from the OTA dead letter queue with status filter tabs.
 * Each pending/error entry has a Replay button that calls POST /admin/dlq/{id}/replay.
 * Applied entries show replay_trace_id instead of a Replay button.
 */
'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, DlqEntry } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

const STATUS_COLOR: Record<string, string> = {
    pending: '#f59e0b',
    error: '#ef4444',
    applied: '#10b981',
};

const STATUS_LABEL: Record<string, string> = {
    pending: 'Pending',
    error: 'Error',
    applied: 'Applied',
};

type StatusFilter = 'all' | 'pending' | 'applied' | 'error';

// ---------------------------------------------------------------------------
// Toast helper
// ---------------------------------------------------------------------------

function useToast() {
    const [msg, setMsg] = useState<string | null>(null);
    const show = (m: string) => {
        setMsg(m);
        setTimeout(() => setMsg(null), 3000);
    };
    return { msg, show };
}

// ---------------------------------------------------------------------------
// DLQ Admin Page
// ---------------------------------------------------------------------------

export default function DlqAdminPage() {
    const [entries, setEntries] = useState<DlqEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<StatusFilter>('all');
    const [replaying, setReplaying] = useState<string | null>(null);
    const [batchReplaying, setBatchReplaying] = useState(false);
    const [batchProgress, setBatchProgress] = useState('');
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const { msg: toast, show: showToast } = useToast();

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const resp = await api.getDlqEntries({ status: filter, limit: 50 });
            setEntries(resp.entries ?? []);
        } catch {
            showToast('⚠ Failed to load DLQ entries');
        } finally {
            setLoading(false);
        }
    }, [filter]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => { load(); }, [load]);

    const handleReplay = async (envId: string) => {
        setReplaying(envId);
        try {
            const result = await api.replayDlqEntry(envId);
            if (result.already_replayed) {
                showToast('ℹ Already applied — no replay needed');
            } else {
                showToast(`✓ Replay triggered: ${result.replay_result ?? 'OK'}`);
            }
            await load();
        } catch {
            showToast('⚠ Replay failed');
        } finally {
            setReplaying(null);
        }
    };

    // Phase 362 — Batch replay all pending entries
    const handleBatchReplay = async () => {
        const pending = entries.filter(e => e.status === 'pending' || e.status === 'error');
        if (pending.length === 0) {
            showToast('ℹ No pending/error entries to replay');
            return;
        }
        setBatchReplaying(true);
        let ok = 0, fail = 0;
        for (let i = 0; i < pending.length; i++) {
            const envId = pending[i].envelope_id ?? '';
            setBatchProgress(`Replaying ${i + 1}/${pending.length}…`);
            try {
                const result = await api.replayDlqEntry(envId);
                if (!result.already_replayed) ok++;
            } catch {
                fail++;
            }
        }
        setBatchProgress('');
        setBatchReplaying(false);
        showToast(`✓ Batch replay: ${ok} replayed, ${fail} failed`);
        await load();
    };

    const FILTERS: { key: StatusFilter; label: string }[] = [
        { key: 'all', label: 'All' },
        { key: 'pending', label: 'Pending' },
        { key: 'error', label: 'Error' },
        { key: 'applied', label: 'Applied' },
    ];

    return (
        <div style={{
            minHeight: '100vh',
            background: 'linear-gradient(135deg, #0f0c29, #1a1255, #0f0c29)',
            fontFamily: "'Inter', system-ui, sans-serif",
            color: '#e2e8f0',
            padding: '32px 24px',
        }}>
            {/* Google Fonts */}
            <style>{`@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');`}</style>

            {/* Toast */}
            {toast && (
                <div style={{
                    position: 'fixed', top: 24, right: 24, zIndex: 9999,
                    background: '#1e293b', border: '1px solid #334155',
                    borderRadius: 12, padding: '12px 20px',
                    fontSize: 13, color: '#e2e8f0',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
                    animation: 'fadeIn 0.2s ease',
                }}>{toast}</div>
            )}

            <style>{`
                @keyframes fadeIn { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes spin   { to { transform: rotate(360deg); } }
            `}</style>

            <div style={{ maxWidth: 960, margin: '0 auto' }}>

                {/* Header */}
                <div style={{ marginBottom: 32 }}>
                    <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, letterSpacing: '-0.02em' }}>
                        🗂 DLQ Inspector
                    </h1>
                    <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 13 }}>
                        OTA Dead Letter Queue — inspect and replay failed events
                    </p>
                </div>

                {/* Filter tabs */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
                    {FILTERS.map(f => (
                        <button
                            key={f.key}
                            id={`dlq-filter-${f.key}`}
                            onClick={() => setFilter(f.key)}
                            style={{
                                padding: '6px 16px',
                                borderRadius: 99,
                                border: filter === f.key
                                    ? '1px solid #6366f1'
                                    : '1px solid #1e293b',
                                background: filter === f.key ? '#6366f1' : '#0f172a',
                                color: filter === f.key ? '#fff' : '#94a3b8',
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: 'pointer',
                                letterSpacing: '0.04em',
                                textTransform: 'uppercase',
                            }}
                        >{f.label}</button>
                    ))}
                    <div style={{ flex: 1 }} />
                    <button
                        id="dlq-refresh"
                        onClick={() => load()}
                        style={{
                            padding: '6px 14px',
                            borderRadius: 99,
                            border: '1px solid #1e293b',
                            background: '#0f172a',
                            color: '#64748b',
                            fontSize: 12,
                            cursor: 'pointer',
                        }}
                    >↻ Refresh</button>
                    {/* Phase 362 — Batch replay button */}
                    <button
                        id="dlq-batch-replay"
                        onClick={handleBatchReplay}
                        disabled={batchReplaying || entries.filter(e => e.status === 'pending' || e.status === 'error').length === 0}
                        style={{
                            padding: '6px 14px',
                            borderRadius: 99,
                            border: 'none',
                            background: batchReplaying ? '#334155' : '#6366f1',
                            color: '#fff',
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: batchReplaying ? 'not-allowed' : 'pointer',
                            opacity: batchReplaying ? 0.7 : 1,
                        }}
                    >{batchReplaying ? batchProgress || 'Replaying…' : '▶▶ Replay All'}</button>
                </div>

                {/* Loading skeleton */}
                {loading && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {[...Array(4)].map((_, i) => (
                            <div key={i} style={{
                                height: 64, borderRadius: 14,
                                background: 'linear-gradient(90deg, #1e293b 25%, #293548 50%, #1e293b 75%)',
                                backgroundSize: '200% 100%',
                                animation: 'pulse 1.5s infinite',
                            }} />
                        ))}
                    </div>
                )}

                {/* Empty state */}
                {!loading && entries.length === 0 && (
                    <div style={{ textAlign: 'center', padding: '60px 0', color: '#475569', fontSize: 14 }}>
                        ✓ No DLQ entries matching this filter.
                    </div>
                )}

                {/* Entry cards */}
                {!loading && entries.map(entry => {
                    const envId = entry.envelope_id ?? '';
                    const isReplaying = replaying === envId;
                    const color = STATUS_COLOR[entry.status] ?? '#64748b';
                    const canReplay = entry.status === 'pending' || entry.status === 'error';

                    const sentAt = entry.created_at ? new Date(entry.created_at) : null;
                    const diffMin = sentAt ? Math.floor((Date.now() - sentAt.getTime()) / 60000) : null;
                    const relTime = diffMin === null ? '—'
                        : diffMin < 60 ? `${diffMin}m ago`
                            : diffMin < 1440 ? `${Math.floor(diffMin / 60)}h ago`
                                : `${Math.floor(diffMin / 1440)}d ago`;

                    return (
                        <div
                            key={envId}
                            style={{
                                background: '#111827',
                                border: `1px solid ${entry.status === 'error' ? '#ef444430' : '#ffffff0a'}`,
                                borderRadius: 14,
                                padding: '14px 18px',
                                marginBottom: 10,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 16,
                            }}
                        >
                            {/* Status dot */}
                            <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />

                            {/* Main info */}
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                    {/* Source badge */}
                                    <span style={{
                                        background: '#1e293b', color: '#94a3b8',
                                        borderRadius: 6, fontSize: 10, fontWeight: 700,
                                        padding: '2px 7px', textTransform: 'uppercase',
                                    }}>{entry.source ?? '?'}</span>
                                    {/* Status badge */}
                                    <span style={{
                                        color, fontSize: 11, fontWeight: 700,
                                        textTransform: 'uppercase',
                                    }}>{STATUS_LABEL[entry.status] ?? entry.status}</span>
                                </div>
                                {/* Envelope ID */}
                                <div style={{
                                    fontSize: 12, color: '#475569',
                                    fontFamily: 'monospace', overflow: 'hidden',
                                    textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                }}>
                                    {envId || '(no envelope_id)'}
                                </div>
                                {/* Error reason */}
                                {entry.error_reason && (
                                    <div style={{
                                        marginTop: 4, fontSize: 11, color: '#ef4444',
                                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                    }}>
                                        {entry.error_reason}
                                    </div>
                                )}
                                {/* Applied: show trace_id */}
                                {entry.status === 'applied' && entry.replay_result && (
                                    <div style={{ marginTop: 4, fontSize: 11, color: '#10b981', fontFamily: 'monospace' }}>
                                        ✓ {entry.replay_result}
                                    </div>
                                )}
                                {/* Phase 362 — Payload preview (expandable) */}
                                {entry.payload_preview && (
                                    <div
                                        onClick={() => setExpandedId(expandedId === envId ? null : envId)}
                                        style={{
                                            marginTop: 4, fontSize: 11, color: '#475569',
                                            fontFamily: 'monospace', cursor: 'pointer',
                                            overflow: 'hidden',
                                            maxHeight: expandedId === envId ? 'none' : '18px',
                                            whiteSpace: expandedId === envId ? 'pre-wrap' : 'nowrap',
                                            textOverflow: expandedId === envId ? 'unset' : 'ellipsis',
                                            wordBreak: 'break-all',
                                        }}
                                    >
                                        📋 {entry.payload_preview}
                                    </div>
                                )}
                            </div>

                            {/* Right side */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
                                <span style={{ fontSize: 11, color: '#4b5563' }}>{relTime}</span>
                                {canReplay && (
                                    <button
                                        id={`dlq-replay-${envId.slice(-8)}`}
                                        onClick={() => handleReplay(envId)}
                                        disabled={isReplaying}
                                        style={{
                                            padding: '5px 14px',
                                            borderRadius: 8,
                                            border: 'none',
                                            background: isReplaying ? '#334155' : '#6366f1',
                                            color: '#fff',
                                            fontSize: 12,
                                            fontWeight: 600,
                                            cursor: isReplaying ? 'not-allowed' : 'pointer',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 6,
                                        }}
                                    >
                                        {isReplaying && (
                                            <span style={{
                                                display: 'inline-block',
                                                width: 10, height: 10,
                                                border: '2px solid rgba(255,255,255,0.4)',
                                                borderTopColor: '#fff',
                                                borderRadius: '50%',
                                                animation: 'spin 0.6s linear infinite',
                                            }} />
                                        )}
                                        {isReplaying ? 'Replaying…' : '▶ Replay'}
                                    </button>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
