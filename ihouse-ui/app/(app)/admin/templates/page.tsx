'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface TaskTemplate {
    id: string;
    name: string;
    kind: string;
    description: string;
    active: boolean;
    created_at: string;
}

export default function TaskTemplatesPage() {
    const [templates, setTemplates] = useState<TaskTemplate[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [formName, setFormName] = useState('');
    const [formKind, setFormKind] = useState('CLEANING');
    const [formDesc, setFormDesc] = useState('');
    const [notice, setNotice] = useState<string | null>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getTaskTemplates();
            setTemplates((res.templates || []) as TaskTemplate[]);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleCreate = async () => {
        try {
            await api.createTaskTemplate({ name: formName, kind: formKind, description: formDesc });
            showNotice('✓ Template created');
            setShowForm(false); setFormName(''); setFormDesc('');
            await load();
        } catch { showNotice('✗ Failed to create'); }
    };

    const handleDelete = async (id: string) => {
        try {
            await api.deleteTaskTemplate(id);
            showNotice('✓ Template removed');
            await load();
        } catch { showNotice('✗ Failed to delete'); }
    };

    const KINDS = ['CLEANING', 'CHECKIN_PREP', 'CHECKOUT_VERIFY', 'MAINTENANCE', 'GENERAL', 'GUEST_WELCOME'];

    return (
        <div style={{ maxWidth: 900 }}>
            <div style={{ marginBottom: 'var(--space-8)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Operations templates</p>
                    <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                        Task <span style={{ color: 'var(--color-primary)' }}>Templates</span>
                    </h1>
                </div>
                <button onClick={() => setShowForm(!showForm)} style={{ background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer' }}>
                    {showForm ? '✕ Cancel' : '＋ New Template'}
                </button>
            </div>

            {notice && <div style={{ position: 'fixed', bottom: 'var(--space-6)', right: 'var(--space-6)', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)', fontSize: 'var(--text-sm)', color: 'var(--color-text)', boxShadow: '0 8px 32px rgba(0,0,0,0.4)', zIndex: 100 }}>{notice}</div>}

            {showForm && (
                <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
                        <input value={formName} onChange={e => setFormName(e.target.value)} placeholder="Template name" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', color: 'var(--color-text)', fontSize: 'var(--text-sm)' }} />
                        <select value={formKind} onChange={e => setFormKind(e.target.value)} style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', color: 'var(--color-text)', fontSize: 'var(--text-sm)' }}>
                            {KINDS.map(k => <option key={k} value={k}>{k}</option>)}
                        </select>
                    </div>
                    <input value={formDesc} onChange={e => setFormDesc(e.target.value)} placeholder="Description" style={{ width: '100%', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)', boxSizing: 'border-box' }} />
                    <button onClick={handleCreate} disabled={!formName} style={{ background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-5)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: formName ? 'pointer' : 'not-allowed', opacity: formName ? 1 : 0.5 }}>Create Template</button>
                </div>
            )}

            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                {!loading && templates.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No templates yet. Create one above.</p>}
                {templates.map(t => (
                    <div key={t.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                        <div>
                            <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{t.name}</div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{t.kind} · {t.description || '—'}</div>
                        </div>
                        <button onClick={() => handleDelete(t.id)} style={{ background: 'transparent', border: '1px solid var(--color-danger)', color: 'var(--color-danger)', borderRadius: 'var(--radius-md)', padding: '2px 12px', fontSize: 'var(--text-xs)', cursor: 'pointer' }}>Remove</button>
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                Domaniqo — Task Templates · Phase 512
            </div>
        </div>
    );
}
