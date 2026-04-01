'use client';

/**
 * Phase 1033 — Admin Preview As Selector (Person-Specific, All Roles)
 *
 * Two-step flow for all roles:
 *   Step 1: Choose role
 *   Step 2: Choose specific person in that role
 *
 * No generic role-level fallback.
 * If no users exist for a role: "No users available" shown, ↗ blocked.
 */

import { useEffect, useState, useCallback } from 'react';

const ACTABLE_ROLES = [
    { value: 'manager',          label: 'Ops Manager' },
    { value: 'owner',            label: 'Owner' },
    { value: 'cleaner',          label: 'Cleaner' },
    { value: 'checkin',          label: 'Check-in Staff' },
    { value: 'checkout',         label: 'Check-out Staff' },
    { value: 'checkin_checkout', label: 'Check-in & Check-out' },
    { value: 'maintenance',      label: 'Maintenance' },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

type UserOption = { user_id: string; display_name: string };

export default function PreviewAsSelector() {
    const [isAdmin, setIsAdmin] = useState(false);
    const [mounted, setMounted] = useState(false);
    const [previewActive, setPreviewActive] = useState(false);
    const [previewLabel, setPreviewLabel] = useState('');

    useEffect(() => {
        setMounted(true);
        try {
            const token = localStorage.getItem('ihouse_token');
            if (token) {
                const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
                if (payload.role === 'admin') setIsAdmin(true);
            }
            const stored = sessionStorage.getItem('ihouse_preview_role');
            if (stored) {
                setPreviewActive(true);
                const name = sessionStorage.getItem('ihouse_preview_display_name') || '';
                const labelMap: Record<string, string> = {
                    manager: 'Ops Manager', owner: 'Owner', cleaner: 'Cleaner',
                    checkin: 'Check-in Staff', checkout: 'Check-out Staff',
                    checkin_checkout: 'Check-in & Check-out', maintenance: 'Maintenance',
                };
                const role = labelMap[stored] || stored;
                setPreviewLabel(name ? `${role} · ${name}` : role);
            }
        } catch { }
    }, []);

    if (!mounted || !isAdmin) return null;

    if (previewActive) {
        return (
            <div style={{ padding: 'var(--space-2) var(--space-6)', marginTop: 'var(--space-4)' }}>
                <div style={{
                    background: 'rgba(234, 179, 8, 0.15)', border: '1px solid rgba(234, 179, 8, 0.4)',
                    padding: '8px 12px', borderRadius: 'var(--radius-sm)',
                    display: 'flex', flexDirection: 'column', gap: 6,
                }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: '#EAB308', fontWeight: 600 }}>
                        👀 PREVIEWING
                    </span>
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', fontWeight: 600, textTransform: 'capitalize' }}>
                        {previewLabel}
                    </span>
                    <button
                        onClick={() => {
                            sessionStorage.removeItem('ihouse_preview_role');
                            sessionStorage.removeItem('ihouse_preview_display_name');
                            sessionStorage.removeItem('ihouse_preview_user_id');
                            window.location.reload();
                        }}
                        style={{
                            marginTop: 4, background: 'var(--color-surface, #fff)', color: 'var(--color-text-dim)',
                            border: '1px solid var(--color-border)', borderRadius: 4, padding: '4px 0',
                            fontSize: '10px', fontWeight: 600, cursor: 'pointer',
                        }}
                    >
                        STOP PREVIEW
                    </button>
                </div>
            </div>
        );
    }

    return <PreviewAsSelectorOpen />;
}

function PreviewAsSelectorOpen() {
    const [selectedRole, setSelectedRole] = useState('');
    const [selectedUser, setSelectedUser] = useState<UserOption | null>(null);
    const [users, setUsers] = useState<UserOption[]>([]);
    const [usersLoading, setUsersLoading] = useState(false);

    const fetchUsers = useCallback(async (role: string) => {
        setUsers([]);
        setSelectedUser(null);
        if (!role) return;
        setUsersLoading(true);
        try {
            const token = localStorage.getItem('ihouse_token');
            const res = await fetch(`${API_BASE}/auth/act-as/users?role=${encodeURIComponent(role)}`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            const body = await res.json();
            setUsers(body?.data?.users ?? body?.users ?? []);
        } catch {
            setUsers([]);
        } finally {
            setUsersLoading(false);
        }
    }, []);

    const handleRoleChange = (role: string) => {
        setSelectedRole(role);
        setSelectedUser(null);
        fetchUsers(role);
    };

    const handleOpen = () => {
        if (!selectedRole || !selectedUser) return;
        const displayName = selectedUser.display_name;
        const url = `/preview?role=${encodeURIComponent(selectedRole)}&name=${encodeURIComponent(displayName)}&user_id=${encodeURIComponent(selectedUser.user_id)}`;
        window.open(url, '_blank');
    };

    return (
        <div style={{ padding: 'var(--space-2) var(--space-6)', margin: 'var(--space-2) 0' }}>
            <div style={{
                fontSize: '10px', fontWeight: 600, color: 'var(--color-text-faint)',
                textTransform: 'uppercase', marginBottom: 6, letterSpacing: '0.04em',
            }}>
                Admin Tools
            </div>

            {/* Step 1: Role */}
            <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <select
                    value={selectedRole}
                    onChange={(e) => handleRoleChange(e.target.value)}
                    style={{
                        flex: 1, height: 28, padding: '0 8px',
                        borderRadius: 'var(--radius-sm, 6px)',
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-surface-2)',
                        color: 'var(--color-text)', fontSize: 'var(--text-xs)',
                        outline: 'none', cursor: 'pointer',
                        appearance: 'none' as const, boxSizing: 'border-box' as const, lineHeight: 1,
                    }}
                >
                    <option value="" disabled>👀 Preview UI As...</option>
                    {ACTABLE_ROLES.map(r => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                </select>
            </div>

            {/* Step 2: Person picker */}
            {selectedRole && (
                <div style={{ marginTop: 6 }}>
                    {usersLoading ? (
                        <div style={{ fontSize: 10, color: 'var(--color-text-faint)', padding: '4px 0' }}>
                            Loading users…
                        </div>
                    ) : users.length === 0 ? (
                        <div style={{
                            fontSize: 10, color: '#EAB308', padding: '4px 6px',
                            background: 'rgba(234,179,8,0.08)', borderRadius: 4,
                        }}>
                            No active users for this role
                        </div>
                    ) : (
                        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                            <select
                                value={selectedUser?.user_id ?? ''}
                                onChange={(e) => {
                                    const u = users.find(u => u.user_id === e.target.value) ?? null;
                                    setSelectedUser(u);
                                }}
                                style={{
                                    flex: 1, height: 28, padding: '0 8px',
                                    borderRadius: 'var(--radius-sm, 6px)',
                                    border: '1px solid rgba(234,179,8,0.4)',
                                    background: 'rgba(234,179,8,0.08)',
                                    color: 'var(--color-text)', fontSize: 'var(--text-xs)',
                                    outline: 'none', cursor: 'pointer',
                                    appearance: 'none' as const, boxSizing: 'border-box' as const, lineHeight: 1,
                                }}
                            >
                                <option value="" disabled>Choose person…</option>
                                {users.map(u => (
                                    <option key={u.user_id} value={u.user_id}>
                                        {u.display_name}
                                    </option>
                                ))}
                            </select>
                            <button
                                onClick={handleOpen}
                                disabled={!selectedUser}
                                title="Open preview in new tab"
                                style={{
                                    padding: 4, background: 'none', border: 'none',
                                    color: selectedUser ? 'var(--color-text)' : 'var(--color-text-dim)',
                                    fontSize: 14, lineHeight: 1,
                                    cursor: selectedUser ? 'pointer' : 'not-allowed',
                                    opacity: selectedUser ? 0.6 : 0.2,
                                    transition: 'opacity 0.15s', flexShrink: 0,
                                }}
                            >
                                ↗
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
