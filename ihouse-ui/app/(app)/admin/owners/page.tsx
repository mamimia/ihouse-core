'use client';

/**
 * Phase 844 v3 — Admin Owners Page
 * Phase 1021-D — Owner model unification: Linked Account & Portal Access section
 *
 * Manage property owners: create, edit, link to properties,
 * link to/unlink from a system login account (tenant_permissions).
 *
 * UI design (Phase 1021):
 *   - Owners surface = canonical home for business profile + portal access management
 *   - "Linked Account & Portal Access" section is editable here
 *   - Manage Staff shows a read-only summary that links here
 *
 * Route: /admin/owners
 */

import { useEffect, useState, useCallback } from 'react';
import { getToken } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LinkedAccount {
    user_id: string;
    display_name: string;
    email: string;
    is_active: boolean;
}

interface Owner {
    id: string;
    tenant_id: string;
    name: string;
    phone: string | null;
    email: string | null;
    notes: string | null;
    user_id: string | null;           // Phase 1021: optional link to login account
    created_at: string;
    property_ids: string[];
    property_count: number;
    linked_account: LinkedAccount | null; // Phase 1021: enriched from tenant_permissions
}

interface PropertyOption {
    id: string;
    property_id: string;
    display_name?: string;
    name?: string;
    city?: string;
}

interface LinkableStaff {
    user_id: string;
    display_name: string;
    email: string;
    is_active: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const API = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

async function apiFetch<T = any>(path: string, init?: RequestInit): Promise<T> {
    const token = getToken();
    const res = await fetch(`${API}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(init?.headers || {}),
        },
    });
    if (!res.ok) {
        const body = await res.text();
        let msg = body || `HTTP ${res.status}`;
        try {
            const parsed = JSON.parse(body);
            msg = parsed.detail || parsed.message || msg;
        } catch { /* not JSON */ }
        throw new Error(msg);
    }
    return res.json() as Promise<T>;
}


// ---------------------------------------------------------------------------
// Add Owner Modal
// ---------------------------------------------------------------------------

function AddOwnerModal({
    properties,
    onClose,
    onCreated,
}: {
    properties: PropertyOption[];
    onClose: () => void;
    onCreated: (owner: Owner) => void;
}) {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [phone, setPhone] = useState('');
    const [notes, setNotes] = useState('');
    const [selectedProps, setSelectedProps] = useState<string[]>([]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const toggle = (pid: string) => setSelectedProps(prev =>
        prev.includes(pid) ? prev.filter(p => p !== pid) : [...prev, pid]
    );

    const handleSave = async () => {
        if (!name.trim()) { setError('Name is required.'); return; }
        setSaving(true);
        setError('');
        try {
            const created = await apiFetch('/admin/owners', {
                method: 'POST',
                body: JSON.stringify({ name: name.trim(), email: email.trim() || null, phone: phone.trim() || null, notes: notes.trim() || null, property_ids: selectedProps }),
            });
            const warnings: string[] = created.warnings || [];
            const skipped: { property_id: string; reason: string }[] = created.skipped_properties || [];
            if (warnings.length > 0 || skipped.length > 0) {
                const msg = [
                    `Owner "${created.name}" was created.`,
                    ...warnings,
                    ...skipped.map((s: { property_id: string; reason: string }) =>
                        `Property ${s.property_id}: ${s.reason}`
                    ),
                ].join('\n');
                setError(msg);
                onCreated(created);
                setSaving(false);
                return;
            }
            onCreated(created);
            onClose();
        } catch (e: any) {
            setError(e.message ?? 'Failed to create owner.');
        }
        setSaving(false);
    };

    const iStyle: React.CSSProperties = {
        width: '100%', boxSizing: 'border-box',
        background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-sm)', color: 'var(--color-text)', fontSize: 'var(--text-sm)',
        padding: '8px 12px',
    };
    const lStyle: React.CSSProperties = {
        fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)',
        fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
        marginBottom: 4, display: 'block',
    };

    return (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            onClick={onClose}>
            <div onClick={e => e.stopPropagation()} style={{
                width: 520, maxWidth: '95vw', maxHeight: '90vh', overflowY: 'auto',
                background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--color-border)', padding: 'var(--space-8)',
                display: 'flex', flexDirection: 'column', gap: 'var(--space-5)',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                        Add Owner
                    </div>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: 'var(--color-text-dim)' }}>✕</button>
                </div>

                <div>
                    <label style={lStyle}>Name *</label>
                    <input style={iStyle} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Sarah Chen" autoFocus />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
                    <div>
                        <label style={lStyle}>Email</label>
                        <input style={iStyle} type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="owner@example.com" />
                    </div>
                    <div>
                        <label style={lStyle}>Phone</label>
                        <input style={iStyle} value={phone} onChange={e => setPhone(e.target.value)} placeholder="+66 81 234 5678" />
                    </div>
                </div>
                <div>
                    <label style={lStyle}>Notes</label>
                    <textarea style={{ ...iStyle, resize: 'vertical', minHeight: 60 }} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Any relevant info about this owner…" />
                </div>

                <div>
                    <label style={lStyle}>Assign to Properties</label>
                    {properties.length === 0 ? (
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>No properties loaded.</div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', maxHeight: 200, overflowY: 'auto' }}>
                            {properties.map(prop => (
                                <label key={prop.property_id || prop.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', cursor: 'pointer' }}>
                                    <input
                                        type="checkbox"
                                        checked={selectedProps.includes(prop.property_id || prop.id)}
                                        onChange={() => toggle(prop.property_id || prop.id)}
                                    />
                                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                                        {prop.display_name || prop.name || prop.id}
                                        {prop.city && <span style={{ color: 'var(--color-text-faint)' }}> · {prop.city}</span>}
                                    </span>
                                </label>
                            ))}
                        </div>
                    )}
                </div>

                {error && <div style={{ color: 'var(--color-error, #ef4444)', fontSize: 'var(--text-sm)', whiteSpace: 'pre-wrap' }}>{error}</div>}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-3)' }}>
                    <button onClick={onClose} style={{
                        background: 'none', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)',
                        color: 'var(--color-text-dim)', padding: '8px 20px', fontSize: 'var(--text-sm)', cursor: 'pointer',
                    }}>Cancel</button>
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        style={{
                            background: saving ? 'var(--color-border)' : 'var(--color-primary)', border: 'none',
                            borderRadius: 'var(--radius-md)', color: '#fff', padding: '8px 24px',
                            fontSize: 'var(--text-sm)', fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer',
                            boxShadow: saving ? 'none' : '0 2px 8px rgba(99,102,241,0.35)',
                        }}
                    >{saving ? 'Creating…' : 'Create Owner'}</button>
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Confirmation Modal (reusable)
// ---------------------------------------------------------------------------

function ConfirmModal({ message, onConfirm, onCancel, confirmLabel = 'Delete', danger = true }: {
    message: string; onConfirm: () => void; onCancel: () => void;
    confirmLabel?: string; danger?: boolean;
}) {
    return (
        <div style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex',
            alignItems: 'center', justifyContent: 'center', zIndex: 9999,
        }} onClick={onCancel}>
            <div onClick={e => e.stopPropagation()} style={{
                background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
                maxWidth: 430, width: '90%', boxShadow: 'var(--shadow-lg)',
            }}>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', marginBottom: 'var(--space-4)', lineHeight: 1.6 }}>
                    {message}
                </div>
                <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end' }}>
                    <button onClick={onCancel} style={{
                        padding: '6px 16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)',
                        background: 'var(--color-surface)', color: 'var(--color-text)', cursor: 'pointer', fontSize: 'var(--text-sm)',
                    }}>Cancel</button>
                    <button onClick={onConfirm} style={{
                        padding: '6px 16px', borderRadius: 'var(--radius-md)', border: 'none',
                        background: danger ? 'var(--color-danger)' : 'var(--color-primary)',
                        color: '#fff', cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 600,
                    }}>{confirmLabel}</button>
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Phase 1021-D: Linked Account & Portal Access section
// ---------------------------------------------------------------------------

function LinkedAccountSection({
    owner,
    onUpdated,
}: {
    owner: Owner;
    onUpdated: (updated: Owner) => void;
}) {
    const [linkableStaff, setLinkableStaff] = useState<LinkableStaff[]>([]);
    const [staffLoading, setStaffLoading] = useState(false);
    const [showLinkDropdown, setShowLinkDropdown] = useState(false);
    const [selectedUserId, setSelectedUserId] = useState('');
    const [linking, setLinking] = useState(false);
    const [unlinking, setUnlinking] = useState(false);
    const [showUnlinkConfirm, setShowUnlinkConfirm] = useState(false);
    const [linkError, setLinkError] = useState('');

    const loadLinkableStaff = async () => {
        setStaffLoading(true);
        try {
            const res = await apiFetch<{ staff: LinkableStaff[] }>('/admin/owners/linkable-staff');
            setLinkableStaff(res.staff || []);
        } catch {
            setLinkableStaff([]);
        }
        setStaffLoading(false);
    };

    const handleOpenLinkDropdown = () => {
        setShowLinkDropdown(true);
        setSelectedUserId('');
        setLinkError('');
        loadLinkableStaff();
    };

    const handleLink = async () => {
        if (!selectedUserId) return;
        setLinking(true);
        setLinkError('');
        try {
            const updated = await apiFetch<Owner>(`/admin/owners/${owner.id}`, {
                method: 'PATCH',
                body: JSON.stringify({ user_id: selectedUserId }),
            });
            onUpdated({ ...owner, ...updated });
            setShowLinkDropdown(false);
        } catch (e: any) {
            setLinkError(e.message || 'Link failed.');
        }
        setLinking(false);
    };

    const handleUnlink = async () => {
        setShowUnlinkConfirm(false);
        setUnlinking(true);
        setLinkError('');
        try {
            const updated = await apiFetch<Owner & { unlink_warning?: string }>(`/admin/owners/${owner.id}`, {
                method: 'PATCH',
                body: JSON.stringify({ user_id: '__unlink__' }),
            });
            // Show unlink_warning if returned (transient server field, not stored on Owner)
            if (updated.unlink_warning) {
                setLinkError(`ℹ️ ${updated.unlink_warning}`);
            }
            onUpdated({ ...owner, ...updated, user_id: null, linked_account: null });
        } catch (e: any) {
            setLinkError(e.message || 'Unlink failed.');
        }
        setUnlinking(false);
    };

    const sectionLabel: React.CSSProperties = {
        fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)',
        textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-2)',
    };

    const linked = owner.linked_account;

    return (
        <div>
            <div style={sectionLabel}>Linked Account & Portal Access</div>
            <div style={{
                padding: 'var(--space-4)',
                background: 'var(--color-surface)',
                border: `1px solid ${linked ? 'rgba(74,124,89,0.3)' : 'var(--color-border)'}`,
                borderRadius: 'var(--radius-md)',
                display: 'flex', flexDirection: 'column', gap: 'var(--space-3)',
            }}>

                {/* Not linked state */}
                {!linked && !showLinkDropdown && (
                    <>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 13 }}>○</span>
                            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                                No app account linked
                            </span>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--color-text-faint)', lineHeight: 1.5 }}>
                            This owner is a contact-only record with no login. They cannot access the owner portal.
                            Link to a staff account with role = Owner to enable portal access.
                        </div>
                        <div>
                            <button
                                onClick={handleOpenLinkDropdown}
                                style={{
                                    padding: '6px 14px', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                                    background: 'var(--color-surface-2)', border: '1px solid var(--color-primary)',
                                    color: 'var(--color-primary)', fontSize: 'var(--text-xs)', fontWeight: 600,
                                }}
                            >
                                + Link to Staff Account
                            </button>
                        </div>
                    </>
                )}

                {/* Link dropdown */}
                {!linked && showLinkDropdown && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)' }}>
                            Select a staff account with role = Owner that is not yet linked to another profile:
                        </div>
                        {staffLoading ? (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>Loading staff…</div>
                        ) : linkableStaff.length === 0 ? (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                                No linkable owner-role accounts found.
                                Create a staff member with role = Owner in Manage Staff first.
                            </div>
                        ) : (
                            <select
                                value={selectedUserId}
                                onChange={e => setSelectedUserId(e.target.value)}
                                style={{
                                    padding: '6px 10px', borderRadius: 'var(--radius-md)',
                                    border: '1px solid var(--color-border)',
                                    background: 'var(--color-bg)', color: 'var(--color-text)',
                                    fontSize: 'var(--text-sm)', width: '100%',
                                }}
                            >
                                <option value="">— select staff account —</option>
                                {linkableStaff.map(s => (
                                    <option key={s.user_id} value={s.user_id}>
                                        {s.display_name || s.email || s.user_id}
                                        {s.email && s.display_name ? ` (${s.email})` : ''}
                                        {!s.is_active ? ' [inactive]' : ''}
                                    </option>
                                ))}
                            </select>
                        )}
                        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                            <button
                                onClick={handleLink}
                                disabled={!selectedUserId || linking}
                                style={{
                                    padding: '6px 14px', borderRadius: 'var(--radius-sm)', cursor: selectedUserId ? 'pointer' : 'default',
                                    background: selectedUserId ? 'var(--color-primary)' : 'var(--color-border)',
                                    border: 'none', color: '#fff', fontSize: 'var(--text-xs)', fontWeight: 600,
                                    opacity: linking ? 0.6 : 1,
                                }}
                            >
                                {linking ? 'Linking…' : 'Link Account'}
                            </button>
                            <button
                                onClick={() => { setShowLinkDropdown(false); setLinkError(''); }}
                                style={{
                                    padding: '6px 12px', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                                    background: 'none', border: '1px solid var(--color-border)',
                                    color: 'var(--color-text-dim)', fontSize: 'var(--text-xs)',
                                }}
                            >Cancel</button>
                        </div>
                    </div>
                )}

                {/* Linked state */}
                {linked && (
                    <>
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-3)' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span style={{ fontSize: 13, color: 'var(--color-ok, #4A7C59)' }}>✓</span>
                                    <span style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)' }}>
                                        {linked.display_name || 'Unnamed account'}
                                    </span>
                                    {!linked.is_active && (
                                        <span style={{ fontSize: 10, background: 'rgba(196,91,74,0.12)', color: 'var(--color-alert, #C45B4A)', padding: '1px 6px', borderRadius: 100, fontWeight: 600 }}>
                                            INACTIVE
                                        </span>
                                    )}
                                </div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                                    {linked.email || linked.user_id}
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--color-ok, #4A7C59)', fontWeight: 500 }}>
                                    Portal access active — can log in at /owner
                                </div>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', alignItems: 'flex-end', flexShrink: 0 }}>
                                <a
                                    href={`/admin/staff/${linked.user_id}`}
                                    style={{
                                        fontSize: 11, padding: '4px 10px', borderRadius: 'var(--radius-sm)',
                                        border: '1px solid var(--color-border)', color: 'var(--color-text-dim)',
                                        background: 'var(--color-surface-2)', textDecoration: 'none',
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    Open in Staff →
                                </a>
                                <button
                                    onClick={() => setShowUnlinkConfirm(true)}
                                    disabled={unlinking}
                                    style={{
                                        fontSize: 11, padding: '4px 10px', borderRadius: 'var(--radius-sm)',
                                        border: '1px solid rgba(196,91,74,0.4)', color: 'rgba(196,91,74,0.8)',
                                        background: 'none', cursor: 'pointer', whiteSpace: 'nowrap',
                                    }}
                                >
                                    {unlinking ? 'Unlinking…' : 'Unlink Account'}
                                </button>
                            </div>
                        </div>
                    </>
                )}

                {/* Error / warning display */}
                {linkError && (
                    <div style={{
                        fontSize: 11, padding: '8px 12px', borderRadius: 'var(--radius-sm)',
                        background: linkError.startsWith('ℹ️') ? 'rgba(74,124,89,0.07)' : 'rgba(196,91,74,0.07)',
                        border: `1px solid ${linkError.startsWith('ℹ️') ? 'rgba(74,124,89,0.25)' : 'rgba(196,91,74,0.25)'}`,
                        color: linkError.startsWith('ℹ️') ? 'var(--color-ok, #4A7C59)' : 'rgba(196,91,74,0.9)',
                        lineHeight: 1.5,
                    }}>
                        {linkError}
                    </div>
                )}
            </div>

            {/* Unlink confirmation modal */}
            {showUnlinkConfirm && (
                <ConfirmModal
                    danger={false}
                    confirmLabel="Yes, Unlink"
                    message={
                        `You are about to unlink the owner "${owner.name}" from the account "${linked?.display_name || linked?.email}".` +
                        `\n\nImportant: this does NOT automatically remove the user's owner portal property access. ` +
                        `Portal access (owner_portal_access records) must be managed separately.` +
                        `\n\nAre you sure?`
                    }
                    onConfirm={handleUnlink}
                    onCancel={() => setShowUnlinkConfirm(false)}
                />
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Owner Row (with inline editing, delete confirm, property management)
// Phase 1021-D: added linked_account indicator in row header + LinkedAccountSection in expanded area
// ---------------------------------------------------------------------------

function OwnerRow({ owner, onDelete, onUpdate, properties }: {
    owner: Owner;
    onDelete: (id: string) => void;
    onUpdate: (updated: Owner) => void;
    properties: PropertyOption[];
}) {
    const [expanded, setExpanded] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [editing, setEditing] = useState(false);
    const [editName, setEditName] = useState(owner.name);
    const [editEmail, setEditEmail] = useState(owner.email || '');
    const [editPhone, setEditPhone] = useState(owner.phone || '');
    const [editNotes, setEditNotes] = useState(owner.notes || '');
    const [editSaving, setEditSaving] = useState(false);
    const [editError, setEditError] = useState('');
    const [assigning, setAssigning] = useState(false);
    const [assignPropId, setAssignPropId] = useState('');

    const propNames = owner.property_ids.map(pid => {
        const p = properties.find(x => x.property_id === pid || x.id === pid);
        return { pid, label: p?.display_name || p?.name || pid };
    });

    const availableProps = properties.filter(p =>
        !owner.property_ids.includes(p.property_id) && !owner.property_ids.includes(p.id)
    );

    const handleDelete = async () => {
        setShowDeleteConfirm(false);
        setDeleting(true);
        try {
            await apiFetch(`/admin/owners/${owner.id}`, { method: 'DELETE' });
            onDelete(owner.id);
        } catch (e: any) {
            setEditError(`Delete failed: ${e.message || 'unknown error'}`);
        }
        setDeleting(false);
    };

    const handleEditSave = async () => {
        if (!editName.trim()) { setEditError('Name is required.'); return; }
        setEditSaving(true);
        setEditError('');
        try {
            const updated = await apiFetch(`/admin/owners/${owner.id}`, {
                method: 'PATCH',
                body: JSON.stringify({ name: editName.trim(), email: editEmail.trim() || null, phone: editPhone.trim() || null, notes: editNotes.trim() || null }),
            });
            onUpdate({ ...owner, ...updated, property_ids: owner.property_ids, property_count: owner.property_count });
            setEditing(false);
        } catch (e: any) {
            setEditError(`Save failed: ${e.message || 'unknown error'}`);
        }
        setEditSaving(false);
    };

    const handleAssignProperty = async () => {
        if (!assignPropId) return;
        setAssigning(true);
        setEditError('');
        try {
            await apiFetch(`/admin/owners/${owner.id}/properties`, { method: 'POST', body: JSON.stringify({ property_id: assignPropId }) });
            onUpdate({ ...owner, property_ids: [...owner.property_ids, assignPropId], property_count: owner.property_count + 1 });
            setAssignPropId('');
        } catch (e: any) {
            setEditError(`Assign failed: ${e.message || 'unknown error'}`);
        }
        setAssigning(false);
    };

    const handleRemoveProperty = async (pid: string) => {
        setEditError('');
        try {
            await apiFetch(`/admin/owners/${owner.id}/properties/${pid}`, { method: 'DELETE' });
            onUpdate({ ...owner, property_ids: owner.property_ids.filter(p => p !== pid), property_count: Math.max(0, owner.property_count - 1) });
        } catch (e: any) {
            setEditError(`Remove failed: ${e.message || 'unknown error'}`);
        }
    };

    const iStyle: React.CSSProperties = {
        padding: '6px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)',
        background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', width: '100%',
    };

    const isLinked = !!owner.linked_account;

    return (
        <>
            {showDeleteConfirm && (
                <ConfirmModal
                    message={`Are you sure you want to delete owner "${owner.name}"? This action cannot be undone. All property assignments for this owner will also be removed.`}
                    onConfirm={handleDelete}
                    onCancel={() => setShowDeleteConfirm(false)}
                />
            )}
            <div style={{
                background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)',
                display: 'flex', flexDirection: 'column', gap: 'var(--space-2)',
                transition: 'border-color 0.15s',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', flex: 1, cursor: 'pointer' }}
                         onClick={() => setExpanded(v => !v)}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontWeight: 700, color: 'var(--color-text)', fontSize: 'var(--text-sm)' }}>{owner.name}</span>
                            {/* Phase 1021-D: linked/unlinked badge in row */}
                            {isLinked ? (
                                <span style={{
                                    fontSize: 10, padding: '2px 7px', borderRadius: 100,
                                    background: 'rgba(74,124,89,0.1)', border: '1px solid rgba(74,124,89,0.3)',
                                    color: 'var(--color-ok, #4A7C59)', fontWeight: 600,
                                }}>
                                    ✓ Portal access linked
                                </span>
                            ) : (
                                <span style={{
                                    fontSize: 10, padding: '2px 7px', borderRadius: 100,
                                    background: 'rgba(181,110,69,0.08)', border: '1px solid rgba(181,110,69,0.25)',
                                    color: 'rgba(181,110,69,0.9)', fontWeight: 600,
                                }}>
                                    Contact only
                                </span>
                            )}
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                            {owner.email && <span>✉ {owner.email}</span>}
                            {owner.phone && <span>📞 {owner.phone}</span>}
                            <span style={{ color: 'var(--color-primary)' }}>{owner.property_count} propert{owner.property_count !== 1 ? 'ies' : 'y'}</span>
                        </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        <button onClick={() => { setEditing(true); setExpanded(true); }} style={{
                            fontSize: 'var(--text-xs)', color: 'var(--color-primary)', background: 'none',
                            border: '1px solid var(--color-primary)', borderRadius: 'var(--radius-full)',
                            padding: '2px 10px', cursor: 'pointer',
                        }}>✎ Edit</button>
                        <button onClick={() => setShowDeleteConfirm(true)} disabled={deleting} title="Delete owner" style={{
                            fontSize: 'var(--text-xs)', color: 'var(--color-danger)', background: 'none',
                            border: '1px solid var(--color-danger)', borderRadius: 'var(--radius-full)',
                            padding: '2px 10px', cursor: 'pointer', opacity: deleting ? 0.5 : 1,
                        }}>{deleting ? '…' : '✕ Delete'}</button>
                    </div>
                </div>

                {editError && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-danger)', background: 'rgba(239,68,68,0.08)',
                        padding: '6px 10px', borderRadius: 'var(--radius-md)', border: '1px solid rgba(239,68,68,0.2)',
                        whiteSpace: 'pre-wrap' }}>
                        {editError}
                    </div>
                )}

                {expanded && (
                    <div style={{ paddingTop: 'var(--space-3)', borderTop: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>

                        {/* Edit fields */}
                        {editing && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                                <div>
                                    <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Name *</label>
                                    <input style={iStyle} value={editName} onChange={e => setEditName(e.target.value)} />
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                    <div>
                                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Email</label>
                                        <input style={iStyle} value={editEmail} onChange={e => setEditEmail(e.target.value)} type="email" />
                                    </div>
                                    <div>
                                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Phone</label>
                                        <input style={iStyle} value={editPhone} onChange={e => setEditPhone(e.target.value)} />
                                    </div>
                                </div>
                                <div>
                                    <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Notes</label>
                                    <textarea style={{ ...iStyle, minHeight: 60, resize: 'vertical' as const }} value={editNotes} onChange={e => setEditNotes(e.target.value)} />
                                </div>
                                <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                                    <button onClick={handleEditSave} disabled={editSaving} style={{
                                        padding: '6px 16px', borderRadius: 'var(--radius-md)', border: 'none',
                                        background: 'var(--color-primary)', color: '#fff', cursor: 'pointer', fontSize: 'var(--text-sm)', fontWeight: 600,
                                        opacity: editSaving ? 0.6 : 1,
                                    }}>{editSaving ? 'Saving…' : 'Save Changes'}</button>
                                    <button onClick={() => { setEditing(false); setEditError(''); }} style={{
                                        padding: '6px 16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)',
                                        background: 'none', color: 'var(--color-text)', cursor: 'pointer', fontSize: 'var(--text-sm)',
                                    }}>Cancel</button>
                                </div>
                            </div>
                        )}

                        {/* Assigned Properties */}
                        <div>
                            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)',
                                textTransform: 'uppercase' as const, letterSpacing: '0.05em', marginBottom: 'var(--space-2)' }}>Assigned Properties</div>
                            {propNames.length === 0 ? (
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>No properties assigned.</div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                                    {propNames.map(({ pid, label }) => (
                                        <div key={pid} style={{
                                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                            fontSize: 'var(--text-xs)', background: 'var(--color-surface-2)',
                                            border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '4px 10px',
                                        }}>
                                            <span style={{ color: 'var(--color-text)' }}>🏠 {label}</span>
                                            <button onClick={() => handleRemoveProperty(pid)} style={{
                                                background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-faint)', fontSize: 11, padding: '2px 6px',
                                            }} title="Remove property">✕</button>
                                        </div>
                                    ))}
                                </div>
                            )}
                            {availableProps.length > 0 && (
                                <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)', alignItems: 'center' }}>
                                    <select value={assignPropId} onChange={e => setAssignPropId(e.target.value)} style={{ ...iStyle, flex: 1 }}>
                                        <option value="">— assign property —</option>
                                        {availableProps.map(p => (
                                            <option key={p.property_id || p.id} value={p.property_id || p.id}>
                                                {p.display_name || p.name || p.property_id || p.id}
                                            </option>
                                        ))}
                                    </select>
                                    <button onClick={handleAssignProperty} disabled={!assignPropId || assigning} style={{
                                        padding: '6px 12px', borderRadius: 'var(--radius-md)', border: 'none',
                                        background: assignPropId ? 'var(--color-primary)' : 'var(--color-border)',
                                        color: '#fff', cursor: assignPropId ? 'pointer' : 'default',
                                        fontSize: 'var(--text-xs)', fontWeight: 600, whiteSpace: 'nowrap' as const,
                                    }}>{assigning ? '…' : '+ Assign'}</button>
                                </div>
                            )}
                        </div>

                        {/* Phase 1021-D: Linked Account & Portal Access (editable canonical home) */}
                        <LinkedAccountSection
                            owner={owner}
                            onUpdated={onUpdate}
                        />

                        {!editing && owner.notes && (
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontStyle: 'italic' }}>{owner.notes}</div>
                        )}
                    </div>
                )}
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function OwnersPage() {
    const [owners, setOwners] = useState<Owner[]>([]);
    const [properties, setProperties] = useState<PropertyOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);
    const [loadError, setLoadError] = useState('');

    const load = useCallback(async () => {
        setLoading(true);
        setLoadError('');
        try {
            const [ownersRes, propsRes] = await Promise.allSettled([
                apiFetch('/admin/owners'),
                apiFetch('/properties'),
            ]);
            if (ownersRes.status === 'fulfilled') {
                setOwners(ownersRes.value?.owners ?? []);
            } else {
                setLoadError('Failed to load owners.');
            }
            if (propsRes.status === 'fulfilled') {
                const raw = propsRes.value?.properties ?? propsRes.value ?? [];
                setProperties(Array.isArray(raw) ? raw : []);
            }
        } catch (e: any) {
            setLoadError(e.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleDelete = (id: string) => setOwners(prev => prev.filter(o => o.id !== id));

    return (
        <div style={{ maxWidth: 900 }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-8)' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-1)' }}>
                        Property management
                    </p>
                    <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                        Owners <span style={{ color: 'var(--color-primary)' }}>({owners.length})</span>
                    </h1>
                </div>
                <button
                    id="add-owner-btn"
                    onClick={() => setShowAdd(true)}
                    style={{
                        background: 'var(--color-primary)', color: '#fff', border: 'none',
                        borderRadius: 'var(--radius-md)', padding: '10px 20px',
                        fontSize: 'var(--text-sm)', fontWeight: 700, cursor: 'pointer',
                        boxShadow: '0 2px 12px rgba(99,102,241,0.35)', transition: 'all 0.15s',
                    }}
                >+ Add Owner</button>
            </div>

            {loadError && (
                <div style={{
                    background: 'var(--color-surface)', border: '1px solid var(--color-warn)',
                    borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)', marginBottom: 'var(--space-6)',
                    fontSize: 'var(--text-sm)', color: 'var(--color-warn)',
                }}>
                    ⚠ {loadError}
                </div>
            )}

            {loading ? (
                <div style={{ color: 'var(--color-text-dim)', padding: 'var(--space-8) 0' }}>Loading…</div>
            ) : owners.length === 0 && !loadError ? (
                <div style={{
                    background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-lg)', padding: 'var(--space-12)',
                    textAlign: 'center', color: 'var(--color-text-dim)',
                }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>🏠</div>
                    <div style={{ fontWeight: 600, marginBottom: 8 }}>No owners yet</div>
                    <div style={{ fontSize: 'var(--text-sm)', marginBottom: 20 }}>Create your first owner and assign them to properties.</div>
                    <button
                        onClick={() => setShowAdd(true)}
                        style={{
                            background: 'var(--color-primary)', color: '#fff', border: 'none',
                            borderRadius: 'var(--radius-md)', padding: '8px 20px',
                            fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer',
                        }}
                    >+ Add First Owner</button>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {owners.map(owner => (
                        <OwnerRow key={owner.id} owner={owner} onDelete={handleDelete}
                            onUpdate={(updated) => setOwners(prev => prev.map(o => o.id === updated.id ? updated : o))}
                            properties={properties} />
                    ))}
                </div>
            )}

            {showAdd && (
                <AddOwnerModal
                    properties={properties}
                    onClose={() => setShowAdd(false)}
                    onCreated={owner => {
                        setOwners(prev => [owner, ...prev]);
                        setShowAdd(false);
                    }}
                />
            )}

            <div style={{ marginTop: 'var(--space-8)', paddingTop: 'var(--space-5)', borderTop: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                Domaniqo · Owners Admin · Phase 844 v3 / 1021-D
            </div>
        </div>
    );
}
