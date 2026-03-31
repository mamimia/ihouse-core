'use client';

/**
 * Phase 1033 Step 3 — /manager/team (REAL operational surface)
 *
 * Shows:
 * 1. Summary stats: workers, properties, total gaps
 * 2. Property-level coverage: per-lane Primary/Backup matrix + gap alerts
 * 3. Worker list per lane with designation badge + open task count
 * 4. Cross-property worker roster (all workers under this manager)
 * 5. Distinct empty state vs populated state
 */

import { useState, useEffect, useCallback } from 'react';
import DraftGuard from '@/components/DraftGuard';
import { apiFetch } from '@/lib/api';

// ─── Types ──────────────────────────────────────────────────────────────────

type Contact = { line?: string; phone?: string; email?: string };

type Worker = {
    user_id: string;
    display_name: string;
    role: string;
    is_active: boolean;
    lane: string;
    priority: number;
    designation: string;
    open_tasks: number;
    contact?: Contact;
};

type LaneCoverage = {
    has_primary: boolean;
    primary_user_id?: string;
    backup_user_id?: string;
};

type Property = {
    property_id: string;
    property_name: string;
    workers: Worker[];
    coverage_gaps: string[];
    lane_coverage: Record<string, LaneCoverage>;
};

type TeamResponse = {
    manager_id: string;
    role: string;
    properties: Property[];
    total_workers: number;
    total_properties: number;
};

// ─── Constants ──────────────────────────────────────────────────────────────

const LANES = ['CLEANING', 'MAINTENANCE', 'CHECKIN_CHECKOUT'] as const;

const LANE_META: Record<string, { label: string; icon: string; color: string }> = {
    CLEANING:         { label: 'Cleaning',    icon: '🧹', color: '#6366f1' },
    MAINTENANCE:      { label: 'Maintenance', icon: '🔧', color: '#f59e0b' },
    CHECKIN_CHECKOUT: { label: 'Check-in/out', icon: '🔑', color: '#22c55e' },
};

// ─── Helper components ───────────────────────────────────────────────────────

function StatCard({ icon, value, label, color, alert }: {
    icon: string; value: number | string; label: string; color: string; alert?: boolean;
}) {
    return (
        <div style={{
            background: alert ? `rgba(239,68,68,0.08)` : `${color}14`,
            border: `1px solid ${alert ? 'rgba(239,68,68,0.25)' : `${color}33`}`,
            borderRadius: 12, padding: '14px 20px',
            display: 'flex', alignItems: 'center', gap: 12, minWidth: 130,
        }}>
            <span style={{ fontSize: 22 }}>{icon}</span>
            <div>
                <div style={{ fontSize: 24, fontWeight: 800, color: alert ? '#ef4444' : color, lineHeight: 1 }}>{value}</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: alert ? '#ef4444' : color, opacity: 0.75, letterSpacing: '0.07em', marginTop: 2 }}>{label}</div>
            </div>
        </div>
    );
}

function DesignationBadge({ designation, priority }: { designation: string; priority: number }) {
    const isPrimary = priority === 1;
    const color = isPrimary ? '#22c55e' : priority === 2 ? '#f59e0b' : '#6b7280';
    const icon = isPrimary ? '⭐' : '🔵';
    return (
        <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
            background: `${color}18`, color, border: `1px solid ${color}44`,
            letterSpacing: '0.04em', flexShrink: 0, whiteSpace: 'nowrap',
        }}>
            {icon} {designation}
        </span>
    );
}

function TaskBadge({ count }: { count: number }) {
    if (count === 0) return null;
    return (
        <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
            background: 'rgba(99,102,241,0.12)', color: '#6366f1',
            border: '1px solid rgba(99,102,241,0.25)', flexShrink: 0,
        }}>
            {count} task{count !== 1 ? 's' : ''}
        </span>
    );
}

function Avatar({ name }: { name: string }) {
    return (
        <div style={{
            width: 32, height: 32, borderRadius: '50%',
            background: 'rgba(99,102,241,0.12)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, fontWeight: 700, color: '#6366f1', flexShrink: 0,
        }}>
            {(name || '?')[0].toUpperCase()}
        </div>
    );
}

// ─── Coverage matrix for a single property ──────────────────────────────────

function PropertyCard({ prop, workerMap }: { prop: Property; workerMap: Map<string, Worker> }) {
    const [expanded, setExpanded] = useState(true);
    const hasGaps = prop.coverage_gaps.length > 0;
    const totalTasks = prop.workers.reduce((s, w) => s + (w.open_tasks || 0), 0);

    // Group workers by lane
    const byLane: Record<string, Worker[]> = {};
    prop.workers.forEach(w => {
        if (!byLane[w.lane]) byLane[w.lane] = [];
        byLane[w.lane].push(w);
    });

    return (
        <div style={{
            background: 'var(--color-surface)', borderRadius: 14,
            border: `1px solid ${hasGaps ? 'rgba(239,68,68,0.35)' : 'var(--color-border)'}`,
            marginBottom: 16, overflow: 'hidden',
            boxShadow: hasGaps ? '0 0 0 1px rgba(239,68,68,0.10)' : 'none',
        }}>
            {/* Property header */}
            <div
                onClick={() => setExpanded(v => !v)}
                style={{
                    padding: '14px 20px', cursor: 'pointer',
                    background: hasGaps ? 'rgba(239,68,68,0.03)' : 'var(--color-surface-2)',
                    borderBottom: expanded ? '1px solid var(--color-border)' : 'none',
                    display: 'flex', alignItems: 'center', gap: 14, userSelect: 'none',
                }}
            >
                <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--color-text)' }}>
                        {prop.property_name}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--color-text-faint)', marginTop: 2 }}>
                        {prop.workers.length} worker{prop.workers.length !== 1 ? 's' : ''}
                        {totalTasks > 0 && <> · {totalTasks} open task{totalTasks !== 1 ? 's' : ''}</>}
                    </div>
                </div>

                {/* Gap pills */}
                {hasGaps && (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {prop.coverage_gaps.map(gap => {
                            const m = LANE_META[gap];
                            return (
                                <span key={gap} style={{
                                    fontSize: 10, fontWeight: 700, padding: '2px 8px',
                                    borderRadius: 99, background: 'rgba(239,68,68,0.10)',
                                    border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444',
                                    letterSpacing: '0.05em', whiteSpace: 'nowrap',
                                }}>
                                    {m?.icon ?? '⚠'} {m?.label ?? gap} — No Primary
                                </span>
                            );
                        })}
                    </div>
                )}

                {/* Lane coverage dots — quick glance */}
                <div style={{ display: 'flex', gap: 5 }}>
                    {LANES.map(lane => {
                        const cov = prop.lane_coverage[lane];
                        const m = LANE_META[lane];
                        const color = !cov?.has_primary ? '#ef4444' : cov.backup_user_id ? '#22c55e' : '#f59e0b';
                        const title = !cov?.has_primary
                            ? `${m.label}: No Primary`
                            : cov.backup_user_id
                            ? `${m.label}: Primary + Backup`
                            : `${m.label}: Primary only`;
                        return (
                            <div key={lane} title={title} style={{
                                width: 10, height: 10, borderRadius: '50%',
                                background: color, border: `1px solid ${color}88`,
                            }} />
                        );
                    })}
                </div>

                <span style={{ fontSize: 12, color: 'var(--color-text-faint)' }}>
                    {expanded ? '▲' : '▼'}
                </span>
            </div>

            {expanded && (
                <div>
                    {/* Lane coverage matrix */}
                    <div style={{
                        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
                        borderBottom: '1px solid var(--color-border)',
                    }}>
                        {LANES.map((lane, i) => {
                            const cov = prop.lane_coverage[lane];
                            const m = LANE_META[lane];
                            const primaryWorker = cov?.primary_user_id ? workerMap.get(cov.primary_user_id) : undefined;
                            const backupWorker = cov?.backup_user_id ? workerMap.get(cov.backup_user_id) : undefined;
                            const isGap = !cov?.has_primary;

                            return (
                                <div key={lane} style={{
                                    padding: '12px 16px',
                                    borderRight: i < 2 ? '1px solid var(--color-border)' : 'none',
                                    background: isGap ? 'rgba(239,68,68,0.03)' : 'transparent',
                                }}>
                                    <div style={{
                                        fontSize: 10, fontWeight: 700, letterSpacing: '0.07em',
                                        color: m.color, marginBottom: 8,
                                        display: 'flex', alignItems: 'center', gap: 4,
                                    }}>
                                        {m.icon} {m.label.toUpperCase()}
                                    </div>

                                    {isGap ? (
                                        <div style={{ fontSize: 11, color: '#ef4444', fontWeight: 600 }}>
                                            ⚠ No Primary assigned
                                        </div>
                                    ) : (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                            {primaryWorker && (
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                    <span style={{ fontSize: 10, color: '#22c55e', fontWeight: 700 }}>⭐</span>
                                                    <span style={{ fontSize: 12, color: 'var(--color-text)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                        {primaryWorker.display_name}
                                                    </span>
                                                </div>
                                            )}
                                            {backupWorker && (
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                    <span style={{ fontSize: 10, color: '#f59e0b', fontWeight: 700 }}>🔵</span>
                                                    <span style={{ fontSize: 12, color: 'var(--color-text-faint)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                        {backupWorker.display_name}
                                                    </span>
                                                </div>
                                            )}
                                            {!backupWorker && (
                                                <div style={{ fontSize: 10, color: 'var(--color-text-faint)', fontStyle: 'italic' }}>
                                                    No backup
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* Worker rows */}
                    {prop.workers.length > 0 && (
                        <div>
                            {prop.workers.map(w => {
                                const m = LANE_META[w.lane];
                                return (
                                    <div key={`${w.user_id}_${w.lane}`} style={{
                                        padding: '10px 20px', display: 'flex', alignItems: 'center',
                                        gap: 12, borderTop: '1px solid var(--color-border)',
                                        opacity: w.is_active ? 1 : 0.55,
                                    }}>
                                        <Avatar name={w.display_name} />
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>
                                                {w.display_name}
                                                {!w.is_active && (
                                                    <span style={{ fontSize: 10, color: 'var(--color-text-faint)', marginLeft: 6 }}>(inactive)</span>
                                                )}
                                            </div>
                                            <div style={{ fontSize: 11, color: 'var(--color-text-faint)', marginTop: 1 }}>
                                                {m?.icon} {m?.label ?? w.lane}
                                            </div>
                                        </div>
                                        <DesignationBadge designation={w.designation} priority={w.priority} />
                                        <TaskBadge count={w.open_tasks} />
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ─── Worker roster (cross-property summary) ──────────────────────────────────

function WorkerRoster({ properties }: { properties: Property[] }) {
    // Deduplicate workers across properties, aggregate their assignments
    const workerMap = new Map<string, {
        display_name: string; role: string; is_active: boolean;
        assignments: { property_name: string; lane: string; designation: string; tasks: number }[];
        totalTasks: number;
    }>();

    properties.forEach(prop => {
        prop.workers.forEach(w => {
            if (!workerMap.has(w.user_id)) {
                workerMap.set(w.user_id, {
                    display_name: w.display_name, role: w.role,
                    is_active: w.is_active, assignments: [], totalTasks: 0,
                });
            }
            const entry = workerMap.get(w.user_id)!;
            entry.assignments.push({
                property_name: prop.property_name,
                lane: w.lane, designation: w.designation, tasks: w.open_tasks,
            });
            entry.totalTasks += w.open_tasks;
        });
    });

    const workers = Array.from(workerMap.entries()).sort(
        (a, b) => b[1].totalTasks - a[1].totalTasks
    );

    if (workers.length === 0) return null;

    return (
        <div style={{ marginTop: 32 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>
                All Workers ({workers.length})
            </div>
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, overflow: 'hidden' }}>
                {workers.map(([uid, w], i) => (
                    <div key={uid} style={{
                        padding: '12px 20px', display: 'flex', alignItems: 'flex-start', gap: 14,
                        borderTop: i > 0 ? '1px solid var(--color-border)' : 'none',
                        opacity: w.is_active ? 1 : 0.6,
                    }}>
                        <Avatar name={w.display_name} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>
                                {w.display_name}
                                {!w.is_active && <span style={{ fontSize: 10, color: 'var(--color-text-faint)', marginLeft: 6 }}>(inactive)</span>}
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 10px', marginTop: 4 }}>
                                {w.assignments.map((a, j) => (
                                    <span key={j} style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>
                                        {LANE_META[a.lane]?.icon} {a.property_name}
                                        {' · '}{a.designation}
                                        {a.tasks > 0 && <span style={{ color: '#6366f1', fontWeight: 700 }}> ({a.tasks})</span>}
                                    </span>
                                ))}
                            </div>
                        </div>
                        {w.totalTasks > 0 && (
                            <span style={{
                                fontSize: 12, fontWeight: 700, padding: '3px 10px',
                                borderRadius: 99, background: 'rgba(99,102,241,0.12)',
                                color: '#6366f1', border: '1px solid rgba(99,102,241,0.25)',
                                flexShrink: 0, alignSelf: 'center',
                            }}>
                                {w.totalTasks} task{w.totalTasks !== 1 ? 's' : ''}
                            </span>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function TeamPage() {
    const [data, setData] = useState<TeamResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState('');

    const load = useCallback(async () => {
        setLoading(true); setErr('');
        try {
            const res = await apiFetch<TeamResponse>('/manager/team');
            setData(res);
        } catch (e: any) {
            setErr(e?.message || 'Failed to load team data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    // Build a flat worker lookup for the coverage matrix
    const workerMap = new Map<string, Worker>();
    data?.properties.forEach(prop => prop.workers.forEach(w => {
        if (!workerMap.has(w.user_id)) workerMap.set(w.user_id, w);
    }));

    const totalGaps = data?.properties.reduce((s, p) => s + p.coverage_gaps.length, 0) ?? 0;
    const isEmpty = !loading && data && data.properties.length === 0;
    const isPopulated = !loading && data && data.properties.length > 0;

    return (
        <DraftGuard>
            <div style={{ maxWidth: 960 }}>

                {/* ── Header ── */}
                <div style={{ marginBottom: 24, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
                    <div>
                        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.1em', marginBottom: 4 }}>
                            OPERATIONAL MANAGER
                        </div>
                        <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--color-text)', letterSpacing: '-0.04em', margin: 0 }}>
                            Team
                        </h1>
                        <div style={{ fontSize: 13, color: 'var(--color-text-dim)', marginTop: 4 }}>
                            Coverage · Assignments · Open task load
                        </div>
                    </div>
                    <button
                        onClick={load}
                        style={{
                            background: 'transparent', border: '1px solid var(--color-border)',
                            borderRadius: 8, padding: '7px 14px', fontSize: 12,
                            fontWeight: 600, color: 'var(--color-text-dim)', cursor: 'pointer',
                        }}
                    >
                        ↻ Refresh
                    </button>
                </div>

                {/* ── Loading ── */}
                {loading && (
                    <div style={{ color: 'var(--color-text-faint)', padding: '48px 0', textAlign: 'center', fontSize: 13 }}>
                        Loading team data…
                    </div>
                )}

                {/* ── Error ── */}
                {!loading && err && (
                    <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 12, padding: '16px 20px', color: '#ef4444', fontSize: 13 }}>
                        ⚠ {err}
                    </div>
                )}

                {/* ── Empty state ── */}
                {isEmpty && (
                    <div style={{
                        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                        borderRadius: 16, padding: '56px 32px', textAlign: 'center',
                    }}>
                        <div style={{ fontSize: 36, marginBottom: 12 }}>👥</div>
                        <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--color-text-dim)', marginBottom: 6 }}>
                            No properties assigned yet
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--color-text-faint)', maxWidth: 320, margin: '0 auto' }}>
                            When properties are assigned to this manager, worker coverage and task load will appear here.
                        </div>
                        <div style={{ marginTop: 24, display: 'flex', justifyContent: 'center', gap: 16 }}>
                            {(['CLEANING', 'MAINTENANCE', 'CHECKIN_CHECKOUT'] as const).map(lane => {
                                const m = LANE_META[lane];
                                return (
                                    <div key={lane} style={{ fontSize: 12, color: 'var(--color-text-faint)', display: 'flex', alignItems: 'center', gap: 4 }}>
                                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-border)' }} />
                                        {m.icon} {m.label}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* ── Populated state ── */}
                {isPopulated && (
                    <>
                        {/* Stat cards */}
                        <div style={{ display: 'flex', gap: 12, marginBottom: 28, flexWrap: 'wrap' }}>
                            <StatCard icon="👥" value={data!.total_workers} label="WORKERS" color="#6366f1" />
                            <StatCard icon="🏠" value={data!.total_properties ?? data!.properties.length} label="PROPERTIES" color="#22c55e" />
                            {totalGaps > 0 && (
                                <StatCard icon="⚠️" value={totalGaps} label="COVERAGE GAPS" color="#ef4444" alert />
                            )}
                            {totalGaps === 0 && (
                                <StatCard icon="✅" value="Full" label="COVERAGE" color="#22c55e" />
                            )}
                        </div>

                        {/* Legend */}
                        <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap', fontSize: 11, color: 'var(--color-text-faint)' }}>
                            <span>⭐ Primary worker</span>
                            <span>🔵 Backup worker</span>
                            <span style={{ color: '#ef4444' }}>⚠ Gap — no Primary</span>
                            <span style={{ color: '#6366f1' }}>Tasks = open task count</span>
                        </div>

                        {/* Property cards */}
                        {data!.properties.map(prop => (
                            <PropertyCard key={prop.property_id} prop={prop} workerMap={workerMap} />
                        ))}

                        {/* Cross-property worker roster */}
                        <WorkerRoster properties={data!.properties} />
                    </>
                )}

            </div>
        </DraftGuard>
    );
}
