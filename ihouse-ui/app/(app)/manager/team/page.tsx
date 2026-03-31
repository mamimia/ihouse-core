'use client';

/**
 * Phase 1033 Step 3 — /manager/team
 *
 * Team coverage view. Shows all workers assigned to supervised properties,
 * grouped by property and lane, with open task counts and coverage gaps.
 *
 * Data: /manager/team (existing endpoint, now auth-fixed in this phase).
 */

import { useState, useEffect, useCallback } from 'react';
import DraftGuard from '@/components/DraftGuard';
import { apiFetch } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types from /manager/team response
// ---------------------------------------------------------------------------

type Worker = {
    user_id: string;
    display_name: string;
    role: string;
    is_active: boolean;
    lane: string;
    designation: string;
    open_tasks: number;
    comm_preference?: Record<string, unknown>;
};

type Property = {
    property_id: string;
    workers: Worker[];
    coverage_gaps: string[];
    lane_coverage: Record<string, Record<string, string>>;
};

type TeamResponse = {
    manager_id: string;
    role: string;
    properties: Property[];
    total_workers: number;
};

// ---------------------------------------------------------------------------
// Lane display
// ---------------------------------------------------------------------------

const LANE_LABELS: Record<string, { label: string; icon: string }> = {
    CLEANING:         { label: 'Cleaning',   icon: '🧹' },
    MAINTENANCE:      { label: 'Maintenance', icon: '🔧' },
    CHECKIN_CHECKOUT: { label: 'Check-in/out', icon: '🔑' },
};

function laneLabel(lane: string): { label: string; icon: string } {
    return LANE_LABELS[lane] || { label: lane, icon: '·' };
}

function designationColor(des: string): string {
    if (des === 'Primary') return '#22c55e';
    if (des === 'Backup') return '#f59e0b';
    return '#6b7280';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

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
            setErr((e as any)?.message || 'Failed to load team data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const totalWorkers = data?.total_workers ?? 0;
    const totalGaps = data?.properties.reduce((acc, p) => acc + p.coverage_gaps.length, 0) ?? 0;

    return (
        <DraftGuard>
            <div style={{ maxWidth: 960 }}>
                {/* Header */}
                <div style={{ marginBottom: 24 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
                        <div>
                            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.1em', marginBottom: 4 }}>
                                OPERATIONAL MANAGER
                            </div>
                            <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--color-text)', letterSpacing: '-0.04em', marginBottom: 4 }}>
                                Team
                            </h1>
                            <div style={{ fontSize: 13, color: 'var(--color-text-dim)' }}>
                                Worker coverage · Lane assignments · Open task load
                            </div>
                        </div>
                        <button onClick={load} style={{ background: 'transparent', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '7px 14px', fontSize: 12, fontWeight: 600, color: 'var(--color-text-dim)', cursor: 'pointer' }}>
                            ↻ Refresh
                        </button>
                    </div>
                </div>

                {/* Stats */}
                {!loading && data && (
                    <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
                        <div style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 'var(--radius-lg)', padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{ fontSize: 20 }}>👥</span>
                            <div>
                                <div style={{ fontSize: 22, fontWeight: 800, color: '#6366f1', lineHeight: 1 }}>{totalWorkers}</div>
                                <div style={{ fontSize: 10, fontWeight: 700, color: '#6366f1', opacity: 0.8, letterSpacing: '0.06em' }}>WORKERS</div>
                            </div>
                        </div>
                        <div style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 'var(--radius-lg)', padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{ fontSize: 20 }}>🏠</span>
                            <div>
                                <div style={{ fontSize: 22, fontWeight: 800, color: '#22c55e', lineHeight: 1 }}>{data.properties.length}</div>
                                <div style={{ fontSize: 10, fontWeight: 700, color: '#22c55e', opacity: 0.8, letterSpacing: '0.06em' }}>PROPERTIES</div>
                            </div>
                        </div>
                        {totalGaps > 0 && (
                            <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-lg)', padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 10 }}>
                                <span style={{ fontSize: 20 }}>⚠️</span>
                                <div>
                                    <div style={{ fontSize: 22, fontWeight: 800, color: '#ef4444', lineHeight: 1 }}>{totalGaps}</div>
                                    <div style={{ fontSize: 10, fontWeight: 700, color: '#ef4444', opacity: 0.8, letterSpacing: '0.06em' }}>COVERAGE GAPS</div>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* States */}
                {loading && <div style={{ color: 'var(--color-text-faint)', padding: '32px 0', textAlign: 'center', fontSize: 13 }}>Loading team data…</div>}
                {!loading && err && (
                    <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-lg)', padding: '16px 20px', color: '#ef4444', fontSize: 13 }}>⚠ {err}</div>
                )}
                {!loading && data && data.properties.length === 0 && (
                    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xl)', padding: '40px', textAlign: 'center' }}>
                        <div style={{ fontSize: 28, marginBottom: 8 }}>👥</div>
                        <div style={{ fontWeight: 700, color: 'var(--color-text-dim)', fontSize: 14 }}>No properties assigned</div>
                        <div style={{ fontSize: 12, color: 'var(--color-text-faint)', marginTop: 4 }}>Set up property assignments to see team coverage here</div>
                    </div>
                )}

                {/* Properties */}
                {!loading && data?.properties.map(prop => {
                    const hasGaps = prop.coverage_gaps.length > 0;
                    const laneGroups: Record<string, Worker[]> = {};
                    prop.workers.forEach(w => {
                        if (!laneGroups[w.lane]) laneGroups[w.lane] = [];
                        laneGroups[w.lane].push(w);
                    });

                    return (
                        <div key={prop.property_id} style={{ background: 'var(--color-surface)', border: `1px solid ${hasGaps ? 'rgba(239,68,68,0.3)' : 'var(--color-border)'}`, borderRadius: 'var(--radius-xl)', marginBottom: 16, overflow: 'hidden' }}>
                            {/* Property header */}
                            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', background: hasGaps ? 'rgba(239,68,68,0.04)' : 'transparent' }}>
                                <div>
                                    <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--color-text)' }}>
                                        {prop.property_id.slice(0, 20)}…
                                    </div>
                                    <div style={{ fontSize: 11, color: 'var(--color-text-faint)', marginTop: 2 }}>
                                        {prop.workers.length} worker{prop.workers.length !== 1 ? 's' : ''}
                                    </div>
                                </div>
                                {hasGaps && (
                                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                        {prop.coverage_gaps.map(g => {
                                            const info = laneLabel(g);
                                            return (
                                                <span key={g} style={{ fontSize: 10, fontWeight: 700, color: '#ef4444', background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.2)', padding: '2px 8px', borderRadius: 'var(--radius-full)', letterSpacing: '0.05em' }}>
                                                    {info.icon} {info.label} — no Primary
                                                </span>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>

                            {/* Lanes */}
                            {Object.entries(laneGroups).map(([lane, workers]) => {
                                const info = laneLabel(lane);
                                return (
                                    <div key={lane} style={{ borderBottom: '1px solid var(--color-border)' }}>
                                        <div style={{ padding: '10px 20px 6px', fontSize: 10, fontWeight: 700, color: 'var(--color-text-faint)', letterSpacing: '0.08em', display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <span>{info.icon}</span>
                                            {info.label.toUpperCase()}
                                        </div>
                                        {workers.map(w => (
                                            <div key={`${w.user_id}_${w.lane}`} style={{ padding: '8px 20px', display: 'flex', alignItems: 'center', gap: 12, borderTop: '1px solid var(--color-border)' }}>
                                                {/* Avatar */}
                                                <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--color-primary)20', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, color: 'var(--color-primary)', flexShrink: 0 }}>
                                                    {(w.display_name || 'W')[0].toUpperCase()}
                                                </div>
                                                <div style={{ flex: 1, minWidth: 0 }}>
                                                    <div style={{ fontSize: 13, fontWeight: 600, color: w.is_active ? 'var(--color-text)' : 'var(--color-text-faint)' }}>
                                                        {w.display_name}
                                                        {!w.is_active && <span style={{ fontSize: 10, color: 'var(--color-text-faint)', marginInlineStart: 6 }}>(inactive)</span>}
                                                    </div>
                                                    <div style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>{w.role}</div>
                                                </div>
                                                <span style={{ fontSize: 11, fontWeight: 700, color: designationColor(w.designation), background: `${designationColor(w.designation)}15`, padding: '2px 8px', borderRadius: 'var(--radius-full)', letterSpacing: '0.04em', flexShrink: 0 }}>
                                                    {w.designation}
                                                </span>
                                                {w.open_tasks > 0 && (
                                                    <span style={{ fontSize: 11, fontWeight: 700, color: '#6366f1', background: 'rgba(99,102,241,0.12)', padding: '2px 8px', borderRadius: 'var(--radius-full)', flexShrink: 0 }}>
                                                        {w.open_tasks} tasks
                                                    </span>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                );
                            })}
                        </div>
                    );
                })}
            </div>
        </DraftGuard>
    );
}
