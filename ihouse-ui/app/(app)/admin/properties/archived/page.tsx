'use client';

/**
 * Archived Properties — /admin/properties/archived
 * Lists all archived properties with Unarchive action per row.
 */

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { getToken } from '@/lib/api';

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

async function apiFetch<T = any>(path: string, init?: RequestInit): Promise<T> {
    const token = getToken();
    const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(init?.headers || {}),
        },
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
}

export default function ArchivedPropertiesPage() {
    const router = useRouter();
    const [properties, setProperties] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [unarchiving, setUnarchiving] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const data = await apiFetch('/properties?status=archived');
            setProperties(data?.properties ?? []);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleUnarchive = async (pid: string) => {
        setUnarchiving(pid);
        try {
            await apiFetch(`/properties/${pid}/unarchive`, { method: 'POST' });
            setProperties(prev => prev.filter(p => p.property_id !== pid));
        } catch { /* ignore */ }
        setUnarchiving(null);
    };

    return (
        <div style={{ maxWidth: 900 }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', marginBottom: 'var(--space-8)' }}>
                <button
                    onClick={() => router.push('/admin/properties')}
                    style={{ background: 'none', border: 'none', color: 'var(--color-text-dim)', cursor: 'pointer', fontSize: 'var(--text-lg)', padding: 0 }}
                >←</button>
                <div>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
                        Properties
                    </p>
                    <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em', margin: 0 }}>
                        Archived Properties{' '}
                        <span style={{ color: 'var(--color-warn)', fontSize: 'var(--text-lg)' }}>({properties.length})</span>
                    </h1>
                </div>
            </div>

            {/* Explanation */}
            <div style={{
                background: 'rgba(181,110,69,0.08)', border: '1px solid rgba(181,110,69,0.3)',
                borderRadius: 'var(--radius-md)', padding: 'var(--space-4) var(--space-5)',
                marginBottom: 'var(--space-6)', fontSize: 'var(--text-sm)', color: 'var(--color-warn)',
            }}>
                Archived properties are hidden from all active views, owner linkage, task assignment, and booking selection.
                Use <strong>Unarchive</strong> to restore a property to the active list.
                Property IDs are never reassigned, even after archiving or deletion.
            </div>

            {/* List */}
            {loading ? (
                <div style={{ color: 'var(--color-text-dim)', padding: 'var(--space-8) 0' }}>Loading…</div>
            ) : properties.length === 0 ? (
                <div style={{
                    background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-lg)', padding: 'var(--space-12)', textAlign: 'center',
                }}>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>✓</div>
                    <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: 8 }}>No archived properties</div>
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-faint)' }}>All properties are active.</div>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {properties.map(p => (
                        <div key={p.property_id} style={{
                            background: 'var(--color-surface)', border: '1px solid rgba(181,110,69,0.25)',
                            borderRadius: 'var(--radius-lg)', padding: 'var(--space-4) var(--space-5)',
                            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-4)',
                        }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                    <span style={{ fontWeight: 700, color: 'var(--color-text)', fontSize: 'var(--text-sm)' }}>
                                        {p.display_name || p.property_id}
                                    </span>
                                    <span style={{
                                        fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)',
                                        color: 'var(--color-text-faint)', background: 'var(--color-surface-2)',
                                        padding: '1px 8px', borderRadius: 'var(--radius-sm)',
                                    }}>{p.property_id}</span>
                                </div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', display: 'flex', gap: 'var(--space-3)' }}>
                                    {p.city && <span>📍 {p.city}{p.country ? `, ${p.country}` : ''}</span>}
                                    {p.archived_at && (
                                        <span>Archived {new Date(p.archived_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                                    )}
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 'var(--space-2)', flexShrink: 0 }}>
                                <button
                                    onClick={() => router.push(`/admin/properties/${p.property_id}`)}
                                    style={{
                                        padding: '6px 14px', borderRadius: 'var(--radius-md)',
                                        background: 'none', border: '1px solid var(--color-border)',
                                        color: 'var(--color-text-dim)', fontSize: 'var(--text-xs)', cursor: 'pointer',
                                    }}
                                >View</button>
                                <button
                                    onClick={() => handleUnarchive(p.property_id)}
                                    disabled={unarchiving === p.property_id}
                                    style={{
                                        padding: '6px 14px', borderRadius: 'var(--radius-md)',
                                        background: 'rgba(181,110,69,0.15)', border: '1px solid rgba(181,110,69,0.4)',
                                        color: 'var(--color-warn)', fontSize: 'var(--text-xs)', fontWeight: 700,
                                        cursor: unarchiving === p.property_id ? 'not-allowed' : 'pointer',
                                    }}
                                >{unarchiving === p.property_id ? 'Restoring…' : '↩ Unarchive'}</button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <div style={{ marginTop: 'var(--space-8)', paddingTop: 'var(--space-5)', borderTop: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                Domaniqo · Archived Properties · Phase 844
            </div>
        </div>
    );
}
