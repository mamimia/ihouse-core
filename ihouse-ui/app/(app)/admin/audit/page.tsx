'use client';

/**
 * Phase 539 — Audit Trail UI
 * Route: /admin/audit
 *
 * Filterable audit log viewer with user, action, entity, timestamp.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface AuditEntry {
    id: string;
    timestamp: string;
    user_id: string;
    action: string;
    entity_type: string;
    entity_id: string;
    details: string;
}

export default function AuditTrailPage() {
    const [entries, setEntries] = useState<AuditEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [actionFilter, setActionFilter] = useState('');

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getAuditLog?.(200) || { entries: [] };
            setEntries((res.entries || []) as AuditEntry[]);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const actions = [...new Set(entries.map(e => e.action))].sort();
    const filtered = entries.filter(e => {
        if (actionFilter && e.action !== actionFilter) return false;
        if (search) {
            const s = search.toLowerCase();
            return (
                e.user_id?.toLowerCase().includes(s) ||
                e.entity_id?.toLowerCase().includes(s) ||
                e.entity_type?.toLowerCase().includes(s) ||
                e.action?.toLowerCase().includes(s) ||
                e.details?.toLowerCase().includes(s)
            );
        }
        return true;
    });

    const actionColor = (a: string) => {
        if (a?.includes('create') || a?.includes('add')) return 'var(--color-ok)';
        if (a?.includes('delete') || a?.includes('remove')) return 'var(--color-danger)';
        if (a?.includes('update') || a?.includes('edit')) return 'var(--color-warn)';
        return 'var(--color-primary)';
    };

    return (
        <div style={{ maxWidth: 1100 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>System accountability</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Audit <span style={{ color: 'var(--color-primary)' }}>Trail</span>
                </h1>
            </div>

            <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-6)', flexWrap: 'wrap' }}>
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search user, entity, action…"
                    style={{ flex: 1, minWidth: 200, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)' }} />
                <select value={actionFilter} onChange={e => setActionFilter(e.target.value)}
                    style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)' }}>
                    <option value="">All Actions</option>
                    {actions.map(a => <option key={a} value={a}>{a}</option>)}
                </select>
                <button onClick={load} disabled={loading} style={{ background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-4)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer' }}>↺</button>
            </div>

            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 'var(--space-3)' }}>{filtered.length} entries</div>

            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '160px 100px 120px 120px 1fr', gap: 'var(--space-2)', padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    <div>Timestamp</div><div>User</div><div>Action</div><div>Entity</div><div>Details</div>
                </div>
                {loading && <div style={{ padding: 'var(--space-6)', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)', textAlign: 'center' }}>Loading…</div>}
                {!loading && filtered.length === 0 && <div style={{ padding: 'var(--space-6)', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)', textAlign: 'center' }}>No audit entries found.</div>}
                {filtered.slice(0, 100).map((e, i) => (
                    <div key={e.id || i} style={{ display: 'grid', gridTemplateColumns: '160px 100px 120px 120px 1fr', gap: 'var(--space-2)', padding: 'var(--space-2) var(--space-4)', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', alignItems: 'center' }}>
                        <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)' }}>{e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}</div>
                        <div style={{ color: 'var(--color-text)', fontWeight: 500 }}>{e.user_id || '—'}</div>
                        <div><span style={{ fontWeight: 700, color: actionColor(e.action), background: `${actionColor(e.action)}15`, padding: '1px 6px', borderRadius: 'var(--radius-full)' }}>{e.action}</span></div>
                        <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)' }}>{e.entity_type}/{e.entity_id?.slice(0, 8)}</div>
                        <div style={{ color: 'var(--color-text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.details || '—'}</div>
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>Domaniqo — Audit Trail · Phase 539</div>
        </div>
    );
}
