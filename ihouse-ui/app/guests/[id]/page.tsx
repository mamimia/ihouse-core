'use client';

/**
 * Phase 193 — Guest Profile UI
 * Route: /guests/[id]
 *
 * Guest detail page with inline edit → PATCH.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { api, Guest } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(s: string | undefined | null) {
    if (!s) return '—';
    return new Date(s).toLocaleString('en-US', {
        day: 'numeric', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}

// ---------------------------------------------------------------------------
// Editable field row
// ---------------------------------------------------------------------------

function FieldRow({
    label, value, editing, onChange,
    type = 'text', placeholder, required,
}: {
    label: string; value: string; editing: boolean;
    onChange: (v: string) => void;
    type?: string; placeholder?: string; required?: boolean;
}) {
    return (
        <div style={{
            display: 'grid', gridTemplateColumns: '160px 1fr',
            alignItems: 'center', gap: 'var(--space-4)',
            padding: 'var(--space-4) 0',
            borderBottom: '1px solid var(--color-border)',
        }}>
            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {label}{required && ' *'}
            </span>
            {editing ? (
                <input
                    type={type}
                    value={value}
                    onChange={e => onChange(e.target.value)}
                    placeholder={placeholder}
                    style={{
                        padding: '6px 10px', background: 'var(--color-surface-2)',
                        border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)',
                        color: 'var(--color-text)', fontSize: 'var(--text-sm)', width: '100%',
                        boxSizing: 'border-box',
                    }}
                />
            ) : (
                <span style={{ fontSize: 'var(--text-sm)', color: value ? 'var(--color-text)' : 'var(--color-muted)' }}>
                    {value || '—'}
                </span>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function GuestDetailPage() {
    const params = useParams();
    const id = params?.id as string;

    const [guest, setGuest] = useState<Guest | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);

    // Editable form state
    const [form, setForm] = useState({
        full_name: '', email: '', phone: '',
        nationality: '', passport_no: '', notes: '',
    });

    useEffect(() => {
        if (!id) return;
        (async () => {
            setLoading(true); setError(null);
            try {
                const g = await api.getGuest(id);
                setGuest(g);
                setForm({
                    full_name: g.full_name ?? '',
                    email: g.email ?? '',
                    phone: g.phone ?? '',
                    nationality: g.nationality ?? '',
                    passport_no: g.passport_no ?? '',
                    notes: g.notes ?? '',
                });
            } catch {
                setError('Guest not found or access denied.');
            } finally {
                setLoading(false);
            }
        })();
    }, [id]);

    const startEdit = () => { setSaveError(null); setEditing(true); };
    const cancelEdit = () => {
        if (!guest) return;
        setForm({
            full_name: guest.full_name ?? '',
            email: guest.email ?? '',
            phone: guest.phone ?? '',
            nationality: guest.nationality ?? '',
            passport_no: guest.passport_no ?? '',
            notes: guest.notes ?? '',
        });
        setEditing(false);
    };

    const save = async () => {
        if (!form.full_name.trim()) { setSaveError('Full name is required.'); return; }
        setSaving(true); setSaveError(null);
        try {
            const updated = await api.patchGuest(id, {
                full_name: form.full_name.trim(),
                email: form.email || null,
                phone: form.phone || null,
                nationality: form.nationality || null,
                passport_no: form.passport_no || null,
                notes: form.notes || null,
            });
            setGuest(updated);
            setEditing(false);
        } catch {
            setSaveError('Failed to save changes — please try again.');
        } finally {
            setSaving(false);
        }
    };

    const set = (k: keyof typeof form) => (v: string) => setForm(f => ({ ...f, [k]: v }));

    // ---------------------------------------------------------------------------
    // Render
    // ---------------------------------------------------------------------------

    if (loading) {
        return (
            <div style={{ padding: 'var(--space-8)', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>
                Loading guest…
            </div>
        );
    }

    if (error || !guest) {
        return (
            <div style={{ padding: 'var(--space-8)' }}>
                <a href="/guests" style={{ color: 'var(--color-primary)', fontSize: 'var(--text-sm)', textDecoration: 'none' }}>← Back to Guests</a>
                <div style={{ marginTop: 'var(--space-6)', color: 'var(--color-danger)', fontSize: 'var(--text-sm)' }}>{error ?? 'Guest not found.'}</div>
            </div>
        );
    }

    return (
        <div style={{ minHeight: '100vh', background: 'var(--color-bg)', padding: 'var(--space-8) var(--space-6)' }}>
            <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }`}</style>

            {/* Back link */}
            <a href="/guests" style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 'var(--space-6)' }}>
                ← Guest Directory
            </a>

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-4)', marginBottom: 'var(--space-8)', animation: 'fadeIn .3s ease' }}>
                <div>
                    <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--color-text)', margin: 0 }}>
                        {guest.full_name}
                    </h1>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                        {guest.id}
                    </p>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginTop: 2 }}>
                        Created {fmtDate(guest.created_at)} · Updated {fmtDate(guest.updated_at)}
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
                    {editing ? (
                        <>
                            <button onClick={save} disabled={saving} style={{ padding: '8px 18px', background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', fontWeight: 600, fontSize: 'var(--text-sm)', cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.7 : 1 }}>
                                {saving ? 'Saving…' : 'Save Changes'}
                            </button>
                            <button onClick={cancelEdit} style={{ padding: '8px 16px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', cursor: 'pointer' }}>
                                Cancel
                            </button>
                        </>
                    ) : (
                        <button onClick={startEdit} style={{ padding: '8px 18px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontWeight: 600, fontSize: 'var(--text-sm)', cursor: 'pointer' }}>
                            ✎ Edit
                        </button>
                    )}
                </div>
            </div>

            {/* PII notice */}
            <div style={{ background: 'rgba(99,102,241,0.07)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)', marginBottom: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>🔒</span> This page contains personally identifiable information (PII). Handle with care.
            </div>

            {/* Save error */}
            {saveError && (
                <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)', marginBottom: 'var(--space-5)', fontSize: 'var(--text-xs)', color: 'var(--color-danger)' }}>
                    ⚠ {saveError}
                </div>
            )}

            {/* Detail card */}
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: '0 var(--space-6)', animation: 'fadeIn .3s ease' }}>
                <FieldRow label="Full Name" value={form.full_name} editing={editing} onChange={set('full_name')} placeholder="Alice Smith" required />
                <FieldRow label="Email" value={form.email} editing={editing} onChange={set('email')} type="email" placeholder="alice@example.com" />
                <FieldRow label="Phone" value={form.phone} editing={editing} onChange={set('phone')} placeholder="+66 81 000 0000" />
                <FieldRow label="Nationality" value={form.nationality} editing={editing} onChange={set('nationality')} placeholder="TH" />
                <FieldRow label="Passport No" value={form.passport_no} editing={editing} onChange={set('passport_no')} placeholder="AA000000" />
                <FieldRow label="Notes" value={form.notes} editing={editing} onChange={set('notes')} placeholder="Internal notes…" />
            </div>
        </div>
    );
}
