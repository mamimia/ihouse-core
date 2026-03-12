/*
 * Phase 372 — Admin Audit Log Frontend Page
 *
 * Route: /admin/audit
 * Displays audit trail events from the admin audit log endpoint.
 */
'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '../../../../lib/api';

interface AuditEntry {
    id: string;
    tenant_id: string;
    actor_id: string;
    action: string;
    entity_type: string;
    entity_id: string;
    created_at: string;
    payload?: Record<string, unknown>;
}

export default function AuditLogPage() {
    const [entries, setEntries] = useState<AuditEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const resp = await api.getAuditLog();
            const data = resp as unknown as { entries?: AuditEntry[] };
            setEntries(data.entries ?? []);
        } catch {
            setEntries([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const actionColor: Record<string, string> = {
        BOOKING_FLAGS_UPDATED: '#6366f1',
        TASK_STATUS_CHANGED: '#10b981',
        DLQ_REPLAYED: '#f59e0b',
        SETTINGS_UPDATED: '#ec4899',
    };

    return (
        <div style={{
            minHeight: '100vh',
            background: 'linear-gradient(135deg, #0f0c29, #1a1255, #0f0c29)',
            fontFamily: "'Inter', system-ui, sans-serif",
            color: '#e2e8f0',
            padding: '32px 24px',
        }}>
            <style>{`@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');`}</style>

            <div style={{ maxWidth: 960, margin: '0 auto' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
                    <div>
                        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, letterSpacing: '-0.02em' }}>
                            📋 Audit Log
                        </h1>
                        <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 13 }}>
                            System-wide activity trail — who did what, when
                        </p>
                    </div>
                    <button
                        id="audit-refresh"
                        onClick={load}
                        style={{
                            padding: '6px 14px', borderRadius: 99,
                            border: '1px solid #1e293b', background: '#0f172a',
                            color: '#64748b', fontSize: 12, cursor: 'pointer',
                        }}
                    >↻ Refresh</button>
                </div>

                {/* Loading skeleton */}
                {loading && entries.length === 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {[...Array(6)].map((_, i) => (
                            <div key={i} style={{
                                height: 56, borderRadius: 12,
                                background: 'linear-gradient(90deg, #1e293b 25%, #293548 50%, #1e293b 75%)',
                                backgroundSize: '200% 100%',
                            }} />
                        ))}
                    </div>
                )}

                {/* Entries */}
                {entries.map(e => (
                    <div
                        key={e.id}
                        style={{
                            background: '#111827',
                            border: '1px solid #ffffff0a',
                            borderRadius: 12, marginBottom: 6,
                            overflow: 'hidden',
                        }}
                    >
                        <div
                            onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
                            style={{
                                padding: '12px 16px',
                                display: 'flex', alignItems: 'center', gap: 12,
                                cursor: 'pointer',
                            }}
                        >
                            <div style={{
                                padding: '3px 8px', borderRadius: 6, fontSize: 10,
                                fontWeight: 600, textTransform: 'uppercase',
                                background: `${actionColor[e.action] ?? '#64748b'}20`,
                                color: actionColor[e.action] ?? '#94a3b8',
                            }}>{e.action}</div>
                            <span style={{ fontSize: 12, color: '#94a3b8' }}>
                                {e.entity_type}/{e.entity_id}
                            </span>
                            <span style={{ marginLeft: 'auto', fontSize: 11, color: '#475569' }}>
                                {new Date(e.created_at).toLocaleString()}
                            </span>
                            <span style={{ fontSize: 11, color: '#475569' }}>
                                by {e.actor_id?.slice(0, 8) ?? '?'}…
                            </span>
                        </div>
                        {expandedId === e.id && e.payload && (
                            <div style={{
                                borderTop: '1px solid #ffffff06',
                                padding: '10px 16px', fontSize: 11,
                                color: '#94a3b8', fontFamily: 'monospace',
                            }}>
                                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                                    {JSON.stringify(e.payload, null, 2)}
                                </pre>
                            </div>
                        )}
                    </div>
                ))}

                {/* Empty state */}
                {!loading && entries.length === 0 && (
                    <div style={{ textAlign: 'center', padding: '60px 0', color: '#475569', fontSize: 14 }}>
                        No audit entries found.
                    </div>
                )}
            </div>
        </div>
    );
}
