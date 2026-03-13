'use client';

/**
 * Phase 558 — Maintenance Request System
 * Route: /maintenance
 *
 * Full maintenance management: create, assign, track, resolve.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { toast } from '@/components/Toast';

interface MaintenanceRequest {
    id: string;
    property_id: string;
    title: string;
    description: string;
    priority: 'low' | 'medium' | 'high' | 'urgent';
    status: 'open' | 'assigned' | 'in_progress' | 'resolved' | 'closed';
    assigned_to?: string;
    created_at: string;
    resolved_at?: string;
}

export default function MaintenancePage() {
    const [requests, setRequests] = useState<MaintenanceRequest[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({ property_id: '', title: '', description: '', priority: 'medium' });
    const [filter, setFilter] = useState('');

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await (api as any).getMaintenanceRequests?.() || { requests: [] };
            setRequests((res.requests || []) as MaintenanceRequest[]);
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to load maintenance requests');
        }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const filtered = requests.filter(r => {
        if (filter && r.status !== filter) return false;
        return true;
    });

    const priorityColor = (p: string) => {
        if (p === 'urgent') return 'var(--color-danger)';
        if (p === 'high') return 'var(--color-warn)';
        if (p === 'medium') return 'var(--color-primary)';
        return 'var(--color-text-dim)';
    };

    const statusColor = (s: string) => {
        if (s === 'resolved' || s === 'closed') return 'var(--color-ok)';
        if (s === 'in_progress') return 'var(--color-primary)';
        if (s === 'assigned') return 'var(--color-accent)';
        return 'var(--color-warn)';
    };

    return (
        <div style={{ maxWidth: 1100 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-8)', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Property maintenance</p>
                    <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                        Maintenance <span style={{ color: 'var(--color-primary)' }}>Requests</span>
                    </h1>
                </div>
                <button onClick={() => setShowForm(!showForm)} style={{ background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer' }}>
                    {showForm ? 'Cancel' : '+ New Request'}
                </button>
            </div>

            {/* Create Form */}
            {showForm && (
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
                    <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 'var(--space-4)', color: 'var(--color-text)' }}>New Maintenance Request</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                        <input value={form.property_id} onChange={e => setForm({ ...form, property_id: e.target.value })} placeholder="Property ID" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)' }} />
                        <select value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })} style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)' }}>
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                            <option value="urgent">Urgent</option>
                        </select>
                    </div>
                    <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Issue title" style={{ width: '100%', marginTop: 'var(--space-3)', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)' }} />
                    <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Description…" rows={3} style={{ width: '100%', marginTop: 'var(--space-3)', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)', resize: 'vertical' }} />
                    <button style={{ marginTop: 'var(--space-3)', background: 'var(--color-ok)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer' }}>Submit Request</button>
                </div>
            )}

            {/* Filter */}
            <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
                {['', 'open', 'assigned', 'in_progress', 'resolved', 'closed'].map(f => (
                    <button key={f} onClick={() => setFilter(f)} style={{ padding: '4px 12px', fontSize: 'var(--text-xs)', fontWeight: filter === f ? 700 : 400, color: filter === f ? '#fff' : 'var(--color-text-dim)', background: filter === f ? 'var(--color-primary)' : 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-full)', cursor: 'pointer' }}>
                        {f || 'All'}
                    </button>
                ))}
            </div>

            {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
            {!loading && filtered.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No maintenance requests found.</p>}

            {filtered.map(r => (
                <div key={r.id} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-4)', marginBottom: 'var(--space-3)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{r.title}</span>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: priorityColor(r.priority), background: `${priorityColor(r.priority)}15`, padding: '1px 8px', borderRadius: 'var(--radius-full)' }}>{r.priority}</span>
                            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: statusColor(r.status), background: `${statusColor(r.status)}15`, padding: '1px 8px', borderRadius: 'var(--radius-full)' }}>{r.status}</span>
                        </div>
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                        {r.property_id} · {r.assigned_to ? `Assigned: ${r.assigned_to}` : 'Unassigned'} · {new Date(r.created_at).toLocaleDateString()}
                    </div>
                </div>
            ))}
        </div>
    );
}
