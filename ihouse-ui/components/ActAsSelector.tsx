'use client';

/**
 * Phase 1033 — Act As Selector (All Roles Person-Specific)
 *
 * All roles now use a two-step flow:
 *   Step 1: Choose role
 *   Step 2: Choose specific person in that role
 *
 * There is NO generic role-level fallback.
 * If a role has no active users, the ↗ button is blocked and
 * "No users available for this role" is shown.
 *
 * Token minted with sub = target_user_id for full identity-scoped QA.
 */

import { useState, useCallback } from 'react';
import { useActAs } from '../lib/ActAsContext';

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

export default function ActAsSelector() {
    const { isAvailable, isActing, session, endActAs } = useActAs();
    const [selectedRole, setSelectedRole] = useState('');
    const [selectedUser, setSelectedUser] = useState<UserOption | null>(null);
    const [users, setUsers] = useState<UserOption[]>([]);
    const [usersLoading, setUsersLoading] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

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
            const list: UserOption[] = (body?.data?.users ?? body?.users ?? []);
            setUsers(list);
        } catch {
            setUsers([]);
        } finally {
            setUsersLoading(false);
        }
    }, []);

    const handleRoleChange = (role: string) => {
        setSelectedRole(role);
        setSelectedUser(null);
        setError('');
        fetchUsers(role);
    };

    // While acting, show status banner
    if (isActing && session) {
        const personName = typeof window !== 'undefined'
            ? (sessionStorage.getItem('ihouse_act_as_display_name') || '')
            : '';
        const rolePart = session.actingAsRole.replace('_', ' ');
        const label = personName ? `${rolePart} · ${personName}` : rolePart;

        return (
            <div style={{ padding: 'var(--space-2) var(--space-6)', marginTop: 4 }}>
                <div style={{
                    background: 'rgba(239, 68, 68, 0.12)',
                    border: '1px solid rgba(239, 68, 68, 0.35)',
                    padding: '8px 12px', borderRadius: 'var(--radius-sm)',
                    display: 'flex', flexDirection: 'column', gap: 6,
                }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: '#EF4444', fontWeight: 700 }}>
                        🔴 ACTING AS
                    </span>
                    <span style={{
                        fontSize: 'var(--text-sm)', color: 'var(--color-text)',
                        fontWeight: 600, textTransform: 'capitalize',
                    }}>
                        {label}
                    </span>
                    <button
                        onClick={() => endActAs()}
                        style={{
                            marginTop: 4, background: 'rgba(239, 68, 68, 0.2)', color: '#EF4444',
                            border: '1px solid rgba(239, 68, 68, 0.4)', borderRadius: 4,
                            padding: '4px 0', fontSize: '10px', fontWeight: 700,
                            cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.03em',
                        }}
                    >
                        END SESSION
                    </button>
                </div>
            </div>
        );
    }

    if (!isAvailable) return null;

    const canOpen = selectedRole && selectedUser !== null;

    const handleOpen = async () => {
        if (!canOpen) return;

        const popup = window.open('about:blank', '_blank');
        if (!popup) {
            setError('Popup blocked. Please allow popups for this site.');
            return;
        }

        setLoading(true);
        setError('');

        try {
            const currentToken = localStorage.getItem('ihouse_token');
            if (!currentToken) {
                popup.close();
                setError('Not authenticated');
                setLoading(false);
                return;
            }

            const res = await fetch(`${API_BASE}/auth/act-as/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${currentToken}`,
                },
                body: JSON.stringify({
                    target_role: selectedRole,
                    target_user_id: selectedUser!.user_id,
                    ttl_seconds: 3600,
                }),
            });

            const data = await res.json();

            if (!res.ok) {
                const msg = data?.error?.message || data?.detail || 'Failed to start Act As';
                popup.close();
                setError(msg);
                setTimeout(() => setError(''), 6000);
                setLoading(false);
                return;
            }

            const payload = data?.data ?? data;
            const actAsToken = payload.token;
            if (!actAsToken) {
                popup.close();
                setError('No token received from server');
                setLoading(false);
                return;
            }

            const displayName = selectedUser!.display_name;
            const url = `/act-as?token=${encodeURIComponent(actAsToken)}&role=${encodeURIComponent(selectedRole)}&name=${encodeURIComponent(displayName)}`;
            popup.location.href = url;

            // Reset
            setSelectedRole('');
            setSelectedUser(null);
            setUsers([]);
            setLoading(false);
        } catch (exc) {
            popup.close();
            setError(`Network error: ${exc}`);
            setTimeout(() => setError(''), 6000);
            setLoading(false);
        }
    };

    return (
        <div style={{ padding: '0 var(--space-6)', marginTop: 4 }}>

            {/* Step 1: Role selector */}
            <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <select
                    value={selectedRole}
                    onChange={(e) => handleRoleChange(e.target.value)}
                    disabled={loading}
                    style={{
                        flex: 1, height: 28, padding: '0 8px',
                        borderRadius: 'var(--radius-sm, 6px)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        background: 'rgba(239, 68, 68, 0.06)',
                        color: 'var(--color-text)', fontSize: 'var(--text-xs)',
                        outline: 'none', cursor: loading ? 'wait' : 'pointer',
                        appearance: 'none' as const, boxSizing: 'border-box' as const,
                        lineHeight: 1, opacity: loading ? 0.6 : 1,
                    }}
                >
                    <option value="" disabled>
                        {loading ? '⏳ Starting...' : '🔴 Act As... (QA only)'}
                    </option>
                    {ACTABLE_ROLES.map(r => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                </select>
            </div>

            {/* Step 2: Person picker — always shown when role is selected */}
            {selectedRole && (
                <div style={{ marginTop: 6 }}>
                    {usersLoading ? (
                        <div style={{ fontSize: 10, color: 'var(--color-text-faint)', padding: '4px 0' }}>
                            Loading users…
                        </div>
                    ) : users.length === 0 ? (
                        <div style={{
                            fontSize: 10, color: '#EF4444', padding: '4px 6px',
                            background: 'rgba(239,68,68,0.08)', borderRadius: 4,
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
                                    border: '1px solid rgba(239, 68, 68, 0.4)',
                                    background: 'rgba(239, 68, 68, 0.08)',
                                    color: 'var(--color-text)', fontSize: 'var(--text-xs)',
                                    outline: 'none', cursor: 'pointer',
                                    appearance: 'none' as const, boxSizing: 'border-box' as const,
                                    lineHeight: 1,
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
                                disabled={!selectedUser || loading}
                                title="Open Act As session in new tab"
                                style={{
                                    padding: 4, background: 'none', border: 'none',
                                    color: selectedUser ? '#EF4444' : 'var(--color-text-dim)',
                                    fontSize: 14, lineHeight: 1,
                                    cursor: (selectedUser && !loading) ? 'pointer' : 'not-allowed',
                                    opacity: (selectedUser && !loading) ? 0.8 : 0.2,
                                    transition: 'opacity 0.15s', flexShrink: 0,
                                }}
                            >
                                ↗
                            </button>
                        </div>
                    )}
                </div>
            )}

            {error && (
                <div style={{
                    marginTop: 4, fontSize: 10, color: '#EF4444',
                    padding: '4px 6px', background: 'rgba(239,68,68,0.1)', borderRadius: 4,
                }}>
                    {error}
                </div>
            )}
        </div>
    );
}
