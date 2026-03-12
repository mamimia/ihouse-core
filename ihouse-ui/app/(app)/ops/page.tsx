'use client';

/**
 * Phase 386 — Mobile Ops Command Surface
 * Route: /ops
 *
 * Mobile-first operational command view for Operations Managers.
 * Shows today's critical summary: urgent tasks, SLA risk, arrivals,
 * departures, alert feed, and quick actions.
 *
 * Data from existing endpoints:
 *  - GET /tasks (urgent, SLA-at-risk)
 *  - GET /bookings (today's arrivals/departures)
 */

import { useEffect, useState, useCallback } from 'react';
import { api, Booking } from '../../../lib/api';
import { useLanguage } from '../../../lib/LanguageContext';

// ---------------------------------------------------------------------------
// Types (minimal – reuse what the API returns)
// ---------------------------------------------------------------------------

interface OpsTask {
    task_id: string;
    title: string;
    kind: string;
    priority: string;
    status: string;
    property_id: string;
    due_date: string;
    due_time?: string;
    created_at: string;
    ack_sla_minutes?: number;
    worker_role?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isoToday(): string {
    return new Date().toISOString().slice(0, 10);
}

function priorityColor(p: string): string {
    switch (p?.toUpperCase()) {
        case 'CRITICAL': return 'var(--color-danger, #ef4444)';
        case 'HIGH': return '#f97316';
        case 'MEDIUM': return 'var(--color-primary, #3b82f6)';
        default: return 'var(--color-text-dim, #6b7280)';
    }
}

function statusLabel(s: string): string {
    const m: Record<string, string> = {
        pending: 'Pending',
        acknowledged: "Ack'd",
        in_progress: 'In Progress',
        completed: 'Done',
        canceled: 'Canceled',
    };
    return m[s] ?? s;
}

function kindEmoji(k: string): string {
    const m: Record<string, string> = {
        CLEANING: '🧹', CHECKIN_PREP: '🏠', CHECKOUT_PREP: '📦',
        MAINTENANCE: '🔧', INSPECTION: '🔍',
    };
    return m[k] ?? '📋';
}

function isOverdue(task: OpsTask): boolean {
    if (!task.due_date || task.status === 'completed' || task.status === 'canceled') return false;
    const due = new Date(task.due_time
        ? `${task.due_date}T${task.due_time}`
        : `${task.due_date}T23:59:59`);
    return new Date() > due;
}

function fmtShortTime(iso: string): string {
    try { return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }); }
    catch { return iso; }
}

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------

function StatCard({ label, value, sub, color, icon }: {
    label: string; value: number | string; sub?: string;
    color?: string; icon: string;
}) {
    return (
        <div style={{
            background: 'var(--color-surface, #1a1f2e)',
            border: '1px solid var(--color-border, #ffffff12)',
            borderRadius: 'var(--radius-lg, 16px)',
            padding: 'var(--space-4, 16px)',
            display: 'flex', flexDirection: 'column', gap: 'var(--space-1, 4px)',
        }}>
            <div style={{ fontSize: 'var(--text-xs, 11px)', color: 'var(--color-text-dim, #6b7280)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {icon} {label}
            </div>
            <div style={{
                fontSize: 'var(--text-2xl, 28px)', fontWeight: 800,
                color: color ?? 'var(--color-text, #f9fafb)',
                fontVariantNumeric: 'tabular-nums',
            }}>
                {value}
            </div>
            {sub && (
                <div style={{ fontSize: 'var(--text-xs, 11px)', color: 'var(--color-text-faint, #4b5563)' }}>
                    {sub}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Task Row (compact for ops feed)
// ---------------------------------------------------------------------------

function TaskRow({ task, onTap }: { task: OpsTask; onTap: () => void }) {
    const overdue = isOverdue(task);
    return (
        <div
            id={`ops-task-${task.task_id}`}
            onClick={onTap}
            style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-3, 12px)',
                padding: 'var(--space-3, 12px) var(--space-4, 16px)',
                background: overdue ? 'rgba(239,68,68,0.06)' : 'transparent',
                borderBottom: '1px solid var(--color-border, #ffffff08)',
                cursor: 'pointer',
                transition: 'background var(--transition-fast, 0.15s)',
            }}
        >
            {/* Priority bar */}
            <div style={{
                width: 4, height: 36, borderRadius: 99,
                background: priorityColor(task.priority),
                flexShrink: 0,
            }} />

            {/* Info */}
            <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                    fontSize: 'var(--text-sm, 14px)', fontWeight: 600,
                    color: 'var(--color-text, #f9fafb)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                    {kindEmoji(task.kind)} {task.title}
                </div>
                <div style={{
                    fontSize: 'var(--text-xs, 11px)',
                    color: 'var(--color-text-dim, #6b7280)',
                    display: 'flex', gap: 'var(--space-2, 8px)', marginTop: 2,
                }}>
                    <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>
                        {task.property_id}
                    </span>
                    {task.due_time && (
                        <span>⏰ {fmtShortTime(`${task.due_date}T${task.due_time}`)}</span>
                    )}
                </div>
            </div>

            {/* Badges */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
                <span style={{
                    fontSize: 'var(--text-xs, 10px)', fontWeight: 700,
                    color: '#fff', background: priorityColor(task.priority),
                    borderRadius: 99, padding: '2px 8px',
                }}>
                    {task.priority}
                </span>
                {overdue && (
                    <span style={{
                        fontSize: 'var(--text-xs, 10px)', fontWeight: 700,
                        color: 'var(--color-danger, #ef4444)',
                    }}>
                        ⚠ OVERDUE
                    </span>
                )}
            </div>

            <div style={{ color: 'var(--color-text-faint, #4b5563)', fontSize: 18, flexShrink: 0 }}>›</div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Booking Row (arrival / departure)
// ---------------------------------------------------------------------------

function BookingRow({ booking, type }: { booking: Booking; type: 'arrival' | 'departure' }) {
    return (
        <div
            id={`ops-booking-${booking.booking_id}`}
            onClick={() => window.open(`/bookings/${booking.booking_id}`, '_blank')}
            style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-3, 12px)',
                padding: 'var(--space-3, 12px) var(--space-4, 16px)',
                borderBottom: '1px solid var(--color-border, #ffffff08)',
                cursor: 'pointer',
            }}
        >
            <span style={{ fontSize: 20, flexShrink: 0 }}>
                {type === 'arrival' ? '🛬' : '🛫'}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                    fontSize: 'var(--text-sm, 14px)', fontWeight: 600,
                    color: 'var(--color-text, #f9fafb)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                    {booking.source ?? 'Direct'} · {booking.property_id}
                </div>
                <div style={{
                    fontSize: 'var(--text-xs, 11px)',
                    color: 'var(--color-text-dim, #6b7280)',
                    fontFamily: 'var(--font-mono, monospace)',
                }}>
                    {((booking as unknown as Record<string, string>).booking_ref) ?? booking.booking_id.slice(0, 12) + '…'}
                </div>
            </div>
            <span style={{
                fontSize: 'var(--text-xs, 11px)', fontWeight: 600,
                color: type === 'arrival' ? '#22c55e' : '#f59e0b',
                background: type === 'arrival' ? '#22c55e18' : '#f59e0b18',
                borderRadius: 99, padding: '2px 10px',
            }}>
                {type === 'arrival' ? 'Check-in' : 'Check-out'}
            </span>
            <div style={{ color: 'var(--color-text-faint, #4b5563)', fontSize: 18, flexShrink: 0 }}>›</div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Section
// ---------------------------------------------------------------------------

function Section({ title, count, children, icon }: {
    title: string; count?: number; icon: string;
    children: React.ReactNode;
}) {
    return (
        <div style={{ marginBottom: 'var(--space-5, 20px)' }}>
            <div style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-2, 8px)',
                padding: '0 var(--space-4, 16px)',
                marginBottom: 'var(--space-2, 8px)',
            }}>
                <span style={{ fontSize: 16 }}>{icon}</span>
                <span style={{
                    fontSize: 'var(--text-xs, 11px)', fontWeight: 700,
                    color: 'var(--color-text-dim, #6b7280)',
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                }}>
                    {title}
                </span>
                {count !== undefined && count > 0 && (
                    <span style={{
                        background: 'var(--color-surface-3, #1f2937)',
                        color: 'var(--color-text-dim, #9ca3af)',
                        borderRadius: 99, fontSize: 10, fontWeight: 700,
                        padding: '1px 7px',
                    }}>
                        {count}
                    </span>
                )}
            </div>
            <div style={{
                background: 'var(--color-surface, #1a1f2e)',
                border: '1px solid var(--color-border, #ffffff12)',
                borderRadius: 'var(--radius-lg, 16px)',
                overflow: 'hidden',
            }}>
                {children}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function OpsPage() {
    const { t } = useLanguage();
    const today = isoToday();

    const [tasks, setTasks] = useState<OpsTask[]>([]);
    const [arrivals, setArrivals] = useState<Booking[]>([]);
    const [departures, setDepartures] = useState<Booking[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setError(null);
        try {
            const [taskResp, bookResp] = await Promise.all([
                api.getTasks({ limit: 100 }),
                api.getBookings({ check_in_from: today, check_in_to: today, limit: 200 }),
            ]);

            setTasks((taskResp.tasks ?? []) as OpsTask[]);

            const allBookings: Booking[] = bookResp.bookings ?? [];
            setArrivals(allBookings.filter(b => b.check_in === today && b.status === 'active'));
            setDepartures(allBookings.filter(b => b.check_out === today && b.status === 'active'));
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load ops data');
        } finally {
            setLoading(false);
        }
    }, [today]);

    useEffect(() => { load(); }, [load]);

    // Derived stats
    const critical = tasks.filter(t => t.priority === 'CRITICAL' && t.status === 'pending');
    const overdue = tasks.filter(t => isOverdue(t) && t.status !== 'completed' && t.status !== 'canceled');
    const pending = tasks.filter(t => t.status === 'pending');
    const inProgress = tasks.filter(t => t.status === 'acknowledged' || t.status === 'in_progress');

    // Urgent feed: CRITICAL first, then HIGH, then overdue, max 20
    const urgentFeed = [...tasks]
        .filter(t => t.status !== 'completed' && t.status !== 'canceled')
        .sort((a, b) => {
            const pm: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
            const oa = isOverdue(a) ? -1 : 0;
            const ob = isOverdue(b) ? -1 : 0;
            return oa - ob || (pm[a.priority] ?? 9) - (pm[b.priority] ?? 9);
        })
        .slice(0, 20);

    const now = new Date();
    const greeting = now.getHours() < 12 ? 'Good morning' : now.getHours() < 18 ? 'Good afternoon' : 'Good evening';

    return (
        <>
            <style>{`
                @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.5} }
                @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
                @keyframes slideDown { from{opacity:0;transform:translateY(-12px)} to{opacity:1;transform:translateY(0)} }
            `}</style>

            <div style={{
                minHeight: '100vh',
                paddingBottom: 'var(--space-8, 32px)',
                animation: 'fadeIn 300ms ease',
            }}>
                {/* Header */}
                <div style={{
                    padding: 'var(--space-5, 20px) var(--space-4, 16px) var(--space-3, 12px)',
                    background: 'linear-gradient(180deg, var(--color-surface, #111827) 0%, transparent 100%)',
                    position: 'sticky', top: 0, zIndex: 30,
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-2, 8px)' }}>
                        <div>
                            <h1 style={{
                                fontSize: 'var(--text-xl, 22px)', fontWeight: 800,
                                color: 'var(--color-text, #f9fafb)', margin: 0,
                                letterSpacing: '-0.03em',
                            }}>
                                {greeting}
                            </h1>
                            <p style={{
                                fontSize: 'var(--text-sm, 13px)',
                                color: 'var(--color-text-dim, #6b7280)',
                                margin: '2px 0 0',
                            }}>
                                Ops Command · {now.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
                            </p>
                        </div>

                        {/* Alert badges */}
                        <div style={{ display: 'flex', gap: 'var(--space-2, 8px)', flexWrap: 'wrap' }}>
                            {critical.length > 0 && (
                                <div style={{
                                    background: 'var(--color-danger, #ef4444)',
                                    color: '#fff', borderRadius: 99,
                                    padding: '4px 10px', fontSize: 12, fontWeight: 700,
                                    animation: 'pulse 1.5s infinite',
                                    boxShadow: '0 0 16px rgba(239,68,68,0.4)',
                                }}>
                                    {critical.length} CRITICAL
                                </div>
                            )}
                            {overdue.length > 0 && (
                                <div style={{
                                    background: 'rgba(239,68,68,0.12)',
                                    color: 'var(--color-danger, #ef4444)',
                                    border: '1px solid rgba(239,68,68,0.4)',
                                    borderRadius: 99, padding: '4px 10px',
                                    fontSize: 12, fontWeight: 600,
                                }}>
                                    {overdue.length} overdue
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div style={{
                        margin: '0 var(--space-4, 16px) var(--space-4, 16px)',
                        background: 'rgba(239,68,68,0.08)',
                        border: '1px solid rgba(239,68,68,0.3)',
                        borderRadius: 'var(--radius-md, 12px)',
                        padding: 'var(--space-3, 12px) var(--space-4, 14px)',
                        fontSize: 'var(--text-sm, 14px)',
                        color: 'var(--color-danger, #ef4444)',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    }}>
                        <span>⚠ {error}</span>
                        <button
                            onClick={load}
                            style={{
                                background: 'none', border: '1px solid var(--color-danger, #ef4444)',
                                color: 'var(--color-danger, #ef4444)',
                                borderRadius: 8, padding: '4px 10px', fontSize: 12, cursor: 'pointer',
                            }}
                        >Retry</button>
                    </div>
                )}

                {/* Loading skeleton */}
                {loading && (
                    <div style={{ padding: '0 var(--space-4, 16px)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3, 12px)' }}>
                        {[1, 2, 3, 4].map(i => (
                            <div key={i} style={{
                                height: 80, background: 'var(--color-surface, #1a1f2e)',
                                borderRadius: 'var(--radius-lg, 16px)',
                                animation: 'pulse 1.5s infinite',
                            }} />
                        ))}
                    </div>
                )}

                {!loading && (
                    <>
                        {/* Stats Grid */}
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 140px), 1fr))',
                            gap: 'var(--space-3, 12px)',
                            padding: '0 var(--space-4, 16px)',
                            marginBottom: 'var(--space-5, 20px)',
                        }}>
                            <StatCard
                                icon="🔴"
                                label="Critical"
                                value={critical.length}
                                color={critical.length > 0 ? 'var(--color-danger, #ef4444)' : undefined}
                                sub={critical.length > 0 ? 'needs immediate ack' : 'all clear'}
                            />
                            <StatCard
                                icon="⏳"
                                label="Pending"
                                value={pending.length}
                                sub={`${inProgress.length} in progress`}
                            />
                            <StatCard
                                icon="🛬"
                                label="Arrivals"
                                value={arrivals.length}
                                color={arrivals.length > 0 ? '#22c55e' : undefined}
                                sub="today"
                            />
                            <StatCard
                                icon="🛫"
                                label="Departures"
                                value={departures.length}
                                color={departures.length > 0 ? '#f59e0b' : undefined}
                                sub="today"
                            />
                        </div>

                        {/* Urgent Tasks Feed */}
                        {urgentFeed.length > 0 && (
                            <Section title="Task Feed" count={urgentFeed.length} icon="⚡">
                                {urgentFeed.map(task => (
                                    <TaskRow
                                        key={task.task_id}
                                        task={task}
                                        onTap={() => window.open(`/tasks/${task.task_id}`, '_blank')}
                                    />
                                ))}
                            </Section>
                        )}

                        {urgentFeed.length === 0 && (
                            <div style={{
                                textAlign: 'center', padding: 'var(--space-8, 40px) var(--space-4, 16px)',
                                color: 'var(--color-text-faint, #4b5563)',
                            }}>
                                <div style={{ fontSize: 48, marginBottom: 'var(--space-3, 12px)' }}>✅</div>
                                <div style={{
                                    fontSize: 'var(--text-lg, 18px)', fontWeight: 600,
                                    color: 'var(--color-text-dim, #6b7280)',
                                }}>
                                    All clear
                                </div>
                                <div style={{ fontSize: 'var(--text-sm, 14px)', marginTop: 'var(--space-1, 4px)' }}>
                                    No open tasks requiring attention
                                </div>
                            </div>
                        )}

                        {/* Today's Arrivals */}
                        {arrivals.length > 0 && (
                            <Section title="Today's Arrivals" count={arrivals.length} icon="🛬">
                                {arrivals.map(b => (
                                    <BookingRow key={b.booking_id} booking={b} type="arrival" />
                                ))}
                            </Section>
                        )}

                        {/* Today's Departures */}
                        {departures.length > 0 && (
                            <Section title="Today's Departures" count={departures.length} icon="🛫">
                                {departures.map(b => (
                                    <BookingRow key={b.booking_id} booking={b} type="departure" />
                                ))}
                            </Section>
                        )}

                        {/* Footer */}
                        <div style={{
                            textAlign: 'center',
                            fontSize: 'var(--text-xs, 11px)',
                            color: 'var(--color-text-faint, #374151)',
                            padding: 'var(--space-6, 24px) var(--space-4, 16px)',
                        }}>
                            Domaniqo — Ops Command · Phase 386 · {today}
                        </div>
                    </>
                )}
            </div>
        </>
    );
}
