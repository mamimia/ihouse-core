'use client';

/**
 * Phase 190 — Manager Activity Feed
 * Route: /manager
 *
 * Real-time audit trail of all operator/worker mutations.
 * Reads from GET /admin/audit (Phase 189 audit_events table).
 *
 * Sections:
 *   - Live Activity Feed — all recent mutations, filterable by entity type
 *   - Quick Stats — mutation counts by action type
 *   - Booking Lookup — enter a booking_id to see its full audit trail
 */

import { useEffect, useState, useCallback } from 'react';
import { api, AuditEvent } from '@/lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtTime(iso: string): string {
    try {
        const d = new Date(iso);
        const now = new Date();
        const diffMs = now.getTime() - d.getTime();
        const diffMin = Math.floor(diffMs / 60000);
        if (diffMin < 1) return 'just now';
        if (diffMin < 60) return `${diffMin}m ago`;
        const diffH = Math.floor(diffMin / 60);
        if (diffH < 24) return `${diffH}h ago`;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
        return iso;
    }
}

function fmtFull(iso: string): string {
    try {
        return new Date(iso).toLocaleString('en-US', {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
        });
    } catch { return iso; }
}

// ---------------------------------------------------------------------------
// Action badge
// ---------------------------------------------------------------------------

const ACTION_STYLES: Record<string, { bg: string; color: string; icon: string }> = {
    TASK_ACKNOWLEDGED: { bg: 'rgba(59,130,246,0.12)', color: '#60a5fa', icon: '👁' },
    TASK_COMPLETED: { bg: 'rgba(16,185,129,0.12)', color: '#34d399', icon: '✓' },
    BOOKING_FLAGS_UPDATED: { bg: 'rgba(245,158,11,0.12)', color: '#fbbf24', icon: '⚑' },
};

function ActionBadge({ action }: { action: string }) {
    const s = ACTION_STYLES[action] ?? { bg: 'rgba(100,100,100,0.12)', color: 'var(--color-text-dim)', icon: '·' };
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            fontSize: 'var(--text-xs)', fontWeight: 700,
            padding: '2px 8px', borderRadius: 'var(--radius-full)',
            background: s.bg, color: s.color,
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.04em',
            whiteSpace: 'nowrap',
        }}>
            <span style={{ fontSize: 10 }}>{s.icon}</span>
            {action.replace(/_/g, ' ')}
        </span>
    );
}

function EntityChip({ type, id }: { type: string; id: string }) {
    const isTask = type === 'task';
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            fontSize: 'var(--text-xs)',
            color: isTask ? 'var(--color-primary)' : 'var(--color-accent)',
        }}>
            <span style={{ opacity: 0.6 }}>{isTask ? '⚙' : '📋'} {type}</span>
            <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.8 }}>
                {id.length > 16 ? id.slice(0, 16) + '…' : id}
            </span>
        </span>
    );
}

// ---------------------------------------------------------------------------
// Payload viewer
// ---------------------------------------------------------------------------

function PayloadBlock({ payload }: { payload: Record<string, unknown> }) {
    const keys = Object.keys(payload).filter(k => payload[k] !== null && payload[k] !== undefined);
    if (keys.length === 0) return <span style={{ color: 'var(--color-text-faint)', fontSize: 'var(--text-xs)' }}>—</span>;
    return (
        <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)' }}>
            {keys.map(k => (
                <span key={k} style={{ marginRight: 10 }}>
                    <span style={{ color: 'var(--color-text-faint)' }}>{k}:</span>
                    {' '}
                    <span style={{ color: 'var(--color-text)' }}>{String(payload[k])}</span>
                </span>
            ))}
        </span>
    );
}

// ---------------------------------------------------------------------------
// Stat metric
// ---------------------------------------------------------------------------

function MetricChip({ label, value, color }: { label: string; value: number; color: string }) {
    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-4) var(--space-5)',
            display: 'flex', flexDirection: 'column', gap: 'var(--space-1)',
            minWidth: 120,
        }}>
            <span style={{
                fontSize: 'var(--text-2xl)', fontWeight: 700,
                color, fontVariantNumeric: 'tabular-nums',
                lineHeight: 1.1,
            }}>{value}</span>
            <span style={{
                fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)',
                textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>{label}</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Audit row
// ---------------------------------------------------------------------------

function AuditRow({ ev, isNew }: { ev: AuditEvent; isNew: boolean }) {
    const [open, setOpen] = useState(false);
    return (
        <div
            onClick={() => setOpen(o => !o)}
            style={{
                borderBottom: '1px solid var(--color-border)',
                cursor: 'pointer',
                transition: 'background var(--transition-fast)',
                background: isNew ? 'rgba(99,102,241,0.04)' : 'transparent',
                borderLeft: isNew ? '2px solid var(--color-primary)' : '2px solid transparent',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
            onMouseLeave={e => (e.currentTarget.style.background = isNew ? 'rgba(99,102,241,0.04)' : 'transparent')}
        >
            {/* Main row */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: '160px 1fr 180px 80px',
                gap: 'var(--space-4)',
                padding: 'var(--space-3) var(--space-5)',
                alignItems: 'center',
            }}>
                <ActionBadge action={ev.action} />
                <EntityChip type={ev.entity_type} id={ev.entity_id} />
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
                    {ev.actor_id.length > 20 ? ev.actor_id.slice(0, 20) + '…' : ev.actor_id}
                </span>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textAlign: 'right' }}
                    title={fmtFull(ev.occurred_at)}>
                    {fmtTime(ev.occurred_at)}
                </span>
            </div>

            {/* Expanded payload */}
            {open && (
                <div style={{
                    padding: 'var(--space-2) var(--space-5) var(--space-3)',
                    background: 'var(--color-surface-2)',
                    borderTop: '1px solid var(--color-border)',
                }}>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-1)' }}>
                        Payload · {fmtFull(ev.occurred_at)}
                    </div>
                    <PayloadBlock payload={ev.payload} />
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Booking audit lookup panel
// ---------------------------------------------------------------------------

function BookingAuditLookup() {
    const [bookingId, setBookingId] = useState('');
    const [events, setEvents] = useState<AuditEvent[] | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const lookup = async () => {
        if (!bookingId.trim()) return;
        setLoading(true); setError(null); setEvents(null);
        try {
            const res = await api.getAuditEvents({ entity_type: 'booking', entity_id: bookingId.trim(), limit: 50 });
            setEvents(res.events);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to load');
        } finally {
            setLoading(false);
        }
    };

    const inputStyle: React.CSSProperties = {
        background: 'var(--color-bg)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        color: 'var(--color-text)',
        padding: 'var(--space-2) var(--space-3)',
        fontSize: 'var(--text-sm)',
        fontFamily: 'var(--font-mono)',
        outline: 'none',
        flex: 1,
    };

    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-6)',
        }}>
            <h2 style={{
                fontSize: 'var(--text-sm)', fontWeight: 600,
                color: 'var(--color-text-dim)', textTransform: 'uppercase',
                letterSpacing: '0.08em', marginBottom: 'var(--space-4)',
            }}>Booking Audit Lookup</h2>

            <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                <input
                    id="audit-lookup-booking-id"
                    placeholder="Enter booking_id…"
                    value={bookingId}
                    onChange={e => setBookingId(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && lookup()}
                    style={inputStyle}
                />
                <button
                    id="audit-lookup-submit"
                    onClick={lookup}
                    disabled={loading || !bookingId.trim()}
                    style={{
                        background: 'var(--color-primary)',
                        color: '#fff', border: 'none',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-2) var(--space-5)',
                        fontSize: 'var(--text-sm)', fontWeight: 600,
                        opacity: loading || !bookingId.trim() ? 0.6 : 1,
                        cursor: loading || !bookingId.trim() ? 'not-allowed' : 'pointer',
                        transition: 'opacity var(--transition-fast)',
                    }}
                >
                    {loading ? '…' : 'Look up'}
                </button>
            </div>

            {error && (
                <div style={{ color: 'var(--color-danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-3)' }}>
                    ⚠ {error}
                </div>
            )}

            {events !== null && (
                events.length === 0
                    ? <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>No audit events found for this booking.</p>
                    : (
                        <div style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                            {/* Header */}
                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: '160px 1fr 180px 80px',
                                gap: 'var(--space-4)',
                                padding: 'var(--space-2) var(--space-5)',
                                background: 'var(--color-surface-2)',
                                borderBottom: '1px solid var(--color-border)',
                            }}>
                                {['Action', 'Entity', 'Actor', 'When'].map(h => (
                                    <span key={h} style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</span>
                                ))}
                            </div>
                            {events.map(ev => <AuditRow key={ev.id} ev={ev} isNew={false} />)}
                        </div>
                    )
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ManagerPage() {
    const [events, setEvents] = useState<AuditEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [entityFilter, setEntityFilter] = useState<'all' | 'task' | 'booking'>('all');
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
    const [prevIds, setPrevIds] = useState<Set<number>>(new Set());

    const load = useCallback(async () => {
        setLoading(true); setError(null);
        try {
            const params: Parameters<typeof api.getAuditEvents>[0] = { limit: 100 };
            if (entityFilter !== 'all') params.entity_type = entityFilter;
            const res = await api.getAuditEvents(params);
            setEvents(res.events);
            setLastRefresh(new Date());
            setPrevIds(prev => new Set([...prev, ...res.events.map(e => e.id)]));
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to load audit events');
        } finally {
            setLoading(false);
        }
    }, [entityFilter]);

    useEffect(() => { load(); }, [load]);

    // Derived stats
    const acknowledged = events.filter(e => e.action === 'TASK_ACKNOWLEDGED').length;
    const completed = events.filter(e => e.action === 'TASK_COMPLETED').length;
    const flagged = events.filter(e => e.action === 'BOOKING_FLAGS_UPDATED').length;

    const btnBase: React.CSSProperties = {
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-full)',
        padding: 'var(--space-1) var(--space-4)',
        fontSize: 'var(--text-xs)',
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all var(--transition-fast)',
        letterSpacing: '0.04em',
    };

    return (
        <div style={{ maxWidth: 1100 }}>
            <style>{`
                @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
            `}</style>

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-8)' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-1)' }}>
                        Manager view · {lastRefresh ? lastRefresh.toLocaleTimeString() : 'loading…'}
                    </p>
                    <h1 style={{
                        fontSize: 'var(--text-3xl)', fontWeight: 700,
                        letterSpacing: '-0.03em', lineHeight: 1.1,
                    }}>
                        Activity <span style={{ color: 'var(--color-primary)' }}>Feed</span>
                    </h1>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                        Every operator and worker mutation — who did what, when.
                    </p>
                </div>
                <button
                    id="manager-refresh"
                    onClick={load}
                    disabled={loading}
                    style={{
                        background: loading ? 'var(--color-surface-3)' : 'var(--color-primary)',
                        color: '#fff', border: 'none',
                        borderRadius: 'var(--radius-md)',
                        padding: 'var(--space-2) var(--space-5)',
                        fontSize: 'var(--text-sm)', fontWeight: 600,
                        opacity: loading ? 0.7 : 1,
                        cursor: loading ? 'not-allowed' : 'pointer',
                        transition: 'all var(--transition-fast)',
                    }}
                >
                    {loading ? '⟳  Refreshing…' : '↺  Refresh'}
                </button>
            </div>

            {/* Stat row */}
            <div style={{ display: 'flex', gap: 'var(--space-4)', marginBottom: 'var(--space-8)', flexWrap: 'wrap' }}>
                <MetricChip label="Total events" value={events.length} color="var(--color-text)" />
                <MetricChip label="Task acked" value={acknowledged} color="#60a5fa" />
                <MetricChip label="Task completed" value={completed} color="#34d399" />
                <MetricChip label="Flags updated" value={flagged} color="#fbbf24" />
            </div>

            {/* Activity feed */}
            <div style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
                marginBottom: 'var(--space-8)',
            }}>
                {/* Feed header */}
                <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: 'var(--space-4) var(--space-5)',
                    borderBottom: '1px solid var(--color-border)',
                    background: 'var(--color-surface-2)',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                        <h2 style={{
                            fontSize: 'var(--text-sm)', fontWeight: 600,
                            color: 'var(--color-text-dim)', textTransform: 'uppercase',
                            letterSpacing: '0.08em',
                        }}>Live Mutations</h2>
                        <span style={{
                            fontSize: 'var(--text-xs)', fontWeight: 700,
                            padding: '1px 8px', borderRadius: 'var(--radius-full)',
                            background: 'var(--color-surface-3)',
                            color: 'var(--color-text-dim)',
                        }}>{events.length}</span>
                    </div>
                    {/* Entity filter pills */}
                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                        {(['all', 'task', 'booking'] as const).map(f => (
                            <button
                                key={f}
                                id={`filter-${f}`}
                                onClick={() => setEntityFilter(f)}
                                style={{
                                    ...btnBase,
                                    background: entityFilter === f ? 'var(--color-primary)' : 'transparent',
                                    color: entityFilter === f ? '#fff' : 'var(--color-text-dim)',
                                    borderColor: entityFilter === f ? 'var(--color-primary)' : 'var(--color-border)',
                                }}
                            >
                                {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1) + 's'}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Column headers */}
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: '160px 1fr 180px 80px',
                    gap: 'var(--space-4)',
                    padding: 'var(--space-2) var(--space-5)',
                    borderBottom: '1px solid var(--color-border)',
                    background: 'var(--color-surface-2)',
                }}>
                    {['Action', 'Entity', 'Actor', 'When'].map(h => (
                        <span key={h} style={{
                            fontSize: 'var(--text-xs)', fontWeight: 600,
                            color: 'var(--color-text-dim)', textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                        }}>{h}</span>
                    ))}
                </div>

                {/* Error */}
                {error && (
                    <div style={{
                        padding: 'var(--space-4) var(--space-5)',
                        color: 'var(--color-danger)',
                        fontSize: 'var(--text-sm)',
                        background: 'rgba(239,68,68,0.06)',
                        borderBottom: '1px solid var(--color-border)',
                    }}>⚠ {error}</div>
                )}

                {/* Loading skeletons */}
                {loading && events.length === 0 && (
                    Array.from({ length: 6 }).map((_, i) => (
                        <div key={i} style={{
                            display: 'grid', gridTemplateColumns: '160px 1fr 180px 80px',
                            gap: 'var(--space-4)', padding: 'var(--space-3) var(--space-5)',
                            borderBottom: '1px solid var(--color-border)',
                            alignItems: 'center',
                        }}>
                            {[100, 200, 140, 50].map((w, j) => (
                                <div key={j} style={{
                                    height: 12, width: w, background: 'var(--color-surface-3)',
                                    borderRadius: 4, animation: 'pulse 1.5s infinite',
                                }} />
                            ))}
                        </div>
                    ))
                )}

                {/* Empty */}
                {!loading && events.length === 0 && !error && (
                    <div style={{ padding: 'var(--space-16)', textAlign: 'center', color: 'var(--color-text-dim)' }}>
                        <div style={{ fontSize: '2rem', marginBottom: 'var(--space-3)' }}>📋</div>
                        <div style={{ fontWeight: 600 }}>No mutations yet</div>
                        <div style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-2)' }}>
                            Audit events will appear here as operators take actions.
                        </div>
                    </div>
                )}

                {/* Rows */}
                {events.map(ev => (
                    <AuditRow
                        key={ev.id}
                        ev={ev}
                        isNew={!prevIds.has(ev.id)}
                    />
                ))}
            </div>

            {/* Booking Audit Lookup */}
            <BookingAuditLookup />

            {/* Footer */}
            <div style={{
                marginTop: 'var(--space-10)',
                paddingTop: 'var(--space-6)',
                borderTop: '1px solid var(--color-border)',
                fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)',
                display: 'flex', justifyContent: 'space-between',
            }}>
                <span>iHouse Core — Manager Activity Feed · Phase 190</span>
                <span>Source: audit_events table · actor_id = JWT sub</span>
            </div>
        </div>
    );
}
