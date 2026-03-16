'use client';

/**
 * Operational Core — Phase B: Staff Management (Manage Users)
 * Architecture source: .agent/architecture/manage-users.md
 *
 * Main View: User table with Name, Email, Role, Status, Last active, Permissions
 * Actions: Invite User, role assignment, permission flags
 * Sections: Active Users | Invite Modal | User Detail panel
 */

import { useEffect, useState, useCallback } from 'react';
import { getToken } from '@/lib/api';

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

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

type UserRecord = {
    id?: string;
    user_id: string;
    role: string;
    permissions?: Record<string, any>;
    display_name?: string;
    phone?: string;
    emergency_contact?: string;
    worker_id?: string;
    worker_role?: string;
    is_active?: boolean;
    created_at?: string;
    updated_at?: string;
};

const ROLES = ['admin', 'manager', 'cleaner', 'checkin_staff', 'maintenance'];
const ROLE_LABELS: Record<string, string> = {
    admin: 'Admin',
    manager: 'Operational Manager',
    cleaner: 'Cleaner',
    checkin_staff: 'Check-in Staff',
    maintenance: 'Maintenance',
};
const ROLE_COLORS: Record<string, { bg: string; text: string }> = {
    admin: { bg: 'rgba(130,80,223,0.15)', text: '#a371f7' },
    manager: { bg: 'rgba(56,158,214,0.15)', text: '#58a6ff' },
    cleaner: { bg: 'rgba(46,160,67,0.15)', text: '#3fb950' },
    checkin_staff: { bg: 'rgba(210,153,34,0.15)', text: '#d29922' },
    maintenance: { bg: 'rgba(248,81,73,0.15)', text: '#f85149' },
};

function RoleBadge({ role }: { role: string }) {
    const c = ROLE_COLORS[role] || { bg: 'rgba(110,118,129,0.15)', text: '#8b949e' };
    return (
        <span style={{
            display: 'inline-block', padding: '2px 10px', borderRadius: 12,
            background: c.bg, color: c.text,
            fontSize: 'var(--text-xs)', fontWeight: 600,
        }}>
            {ROLE_LABELS[role] || role}
        </span>
    );
}

function StatusDot({ active }: { active?: boolean }) {
    return (
        <span style={{
            display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
            background: active !== false ? '#3fb950' : '#8b949e',
            marginRight: 6,
        }} />
    );
}

// ========== Invite Modal ==========
function InviteModal({ onClose, onInvite }: {
    onClose: () => void;
    onInvite: (data: { user_id: string; role: string; display_name?: string; phone?: string; emergency_contact?: string }) => void;
}) {
    const [email, setEmail] = useState('');
    const [role, setRole] = useState('cleaner');
    const [displayName, setDisplayName] = useState('');
    const [phone, setPhone] = useState('');
    const [emergency, setEmergency] = useState('');

    const inputStyle = {
        width: '100%', background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-sm)', padding: '8px 12px', color: 'var(--color-text)',
        fontSize: 'var(--text-sm)', outline: 'none',
    };

    return (
        <div style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
            <div style={{
                background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--color-border)', padding: 'var(--space-6)',
                width: 440, maxHeight: '90vh', overflow: 'auto',
                boxShadow: '0 8px 40px rgba(0,0,0,0.4)',
            }}>
                <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)', marginBottom: 'var(--space-4)' }}>
                    Invite User
                </h2>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    <div>
                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Email *</label>
                        <input value={email} onChange={e => setEmail(e.target.value)} placeholder="user@company.com" style={inputStyle} />
                    </div>
                    <div>
                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Role *</label>
                        <select value={role} onChange={e => setRole(e.target.value)} style={{ ...inputStyle, cursor: 'pointer' }}>
                            {ROLES.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                        </select>
                    </div>
                    <div>
                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Full Name</label>
                        <input value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="Optional" style={inputStyle} />
                    </div>
                    <div>
                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Phone</label>
                        <input value={phone} onChange={e => setPhone(e.target.value)} placeholder="Optional" style={inputStyle} />
                    </div>
                    <div>
                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Emergency Contact</label>
                        <input value={emergency} onChange={e => setEmergency(e.target.value)} placeholder="Optional" style={inputStyle} />
                    </div>
                </div>

                <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-5)', justifyContent: 'flex-end' }}>
                    <button onClick={onClose} style={{
                        padding: '8px 20px', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-sm)',
                        background: 'transparent', color: 'var(--color-text-dim)', border: '1px solid var(--color-border)', cursor: 'pointer',
                    }}>Cancel</button>
                    <button onClick={() => {
                        if (!email.trim()) return;
                        onInvite({
                            user_id: email.trim(),
                            role,
                            ...(displayName.trim() ? { display_name: displayName.trim() } : {}),
                            ...(phone.trim() ? { phone: phone.trim() } : {}),
                            ...(emergency.trim() ? { emergency_contact: emergency.trim() } : {}),
                        });
                    }} style={{
                        padding: '8px 20px', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-sm)',
                        background: 'var(--color-primary)', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600,
                    }}>Add User</button>
                </div>
            </div>
        </div>
    );
}

// ========== User Detail Panel ==========
function UserDetailPanel({ user, onClose, onUpdate, onDeactivate }: {
    user: UserRecord;
    onClose: () => void;
    onUpdate: (userId: string, data: Record<string, any>) => void;
    onDeactivate: (userId: string) => void;
}) {
    const [editRole, setEditRole] = useState(user.role);
    const [canApprove, setCanApprove] = useState(!!user.permissions?.can_approve_access_requests);
    const [canOverride, setCanOverride] = useState(!!user.permissions?.can_booking_override);

    const sectionTitle = { fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase' as const, letterSpacing: '0.05em', marginBottom: 'var(--space-2)', marginTop: 'var(--space-4)' };
    const detailRow = { display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-sm)' };

    return (
        <div style={{
            position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 1000,
            width: 420, background: 'var(--color-surface)', borderLeft: '1px solid var(--color-border)',
            boxShadow: '-4px 0 30px rgba(0,0,0,0.3)', padding: 'var(--space-5)', overflow: 'auto',
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>User Detail</h2>
                <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--color-text-dim)', cursor: 'pointer', fontSize: 'var(--text-lg)' }}>✕</button>
            </div>

            {/* Profile */}
            <div style={sectionTitle}>Profile</div>
            <div style={detailRow}>
                <span style={{ color: 'var(--color-text-dim)' }}>Email</span>
                <span style={{ color: 'var(--color-text)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>{user.user_id}</span>
            </div>
            <div style={detailRow}>
                <span style={{ color: 'var(--color-text-dim)' }}>Name</span>
                <span style={{ color: 'var(--color-text)' }}>{user.display_name || '—'}</span>
            </div>
            <div style={detailRow}>
                <span style={{ color: 'var(--color-text-dim)' }}>Phone</span>
                <span style={{ color: 'var(--color-text)' }}>{user.phone || '—'}</span>
            </div>
            <div style={detailRow}>
                <span style={{ color: 'var(--color-text-dim)' }}>Emergency</span>
                <span style={{ color: 'var(--color-text)' }}>{user.emergency_contact || '—'}</span>
            </div>
            <div style={detailRow}>
                <span style={{ color: 'var(--color-text-dim)' }}>Status</span>
                <span><StatusDot active={user.is_active} />{user.is_active !== false ? 'Active' : 'Inactive'}</span>
            </div>

            {/* Role & Permissions */}
            <div style={sectionTitle}>Role & Permissions</div>
            <div style={{ marginBottom: 'var(--space-3)' }}>
                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Role</label>
                <select value={editRole} onChange={e => setEditRole(e.target.value)} style={{
                    width: '100%', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-sm)', padding: '6px 10px', color: 'var(--color-text)',
                    fontSize: 'var(--text-sm)', cursor: 'pointer',
                }}>
                    {ROLES.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                </select>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--text-sm)', color: 'var(--color-text)', cursor: 'pointer' }}>
                    <input type="checkbox" checked={canApprove} onChange={e => setCanApprove(e.target.checked)} />
                    Can approve access requests
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--text-sm)', color: 'var(--color-text)', cursor: 'pointer' }}>
                    <input type="checkbox" checked={canOverride} onChange={e => setCanOverride(e.target.checked)} />
                    Can override bookings
                </label>
            </div>

            <button onClick={() => onUpdate(user.user_id, {
                role: editRole,
                permissions: { can_approve_access_requests: canApprove, can_booking_override: canOverride },
            })} style={{
                width: '100%', marginTop: 'var(--space-4)', padding: '10px',
                background: 'var(--color-primary)', color: '#fff', border: 'none',
                borderRadius: 'var(--radius-sm)', fontWeight: 600, cursor: 'pointer', fontSize: 'var(--text-sm)',
            }}>
                Save Changes
            </button>

            {/* Security */}
            <div style={sectionTitle}>Security</div>
            <button onClick={() => { if (confirm('Deactivate this user? They will no longer be able to log in.')) onDeactivate(user.user_id); }}
                style={{
                    width: '100%', padding: '10px', background: 'rgba(248,81,73,0.1)',
                    color: '#f85149', border: '1px solid rgba(248,81,73,0.3)',
                    borderRadius: 'var(--radius-sm)', fontWeight: 600, cursor: 'pointer', fontSize: 'var(--text-sm)',
                }}>
                Deactivate Account
            </button>

            {/* Metadata */}
            <div style={{ marginTop: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                <div>Worker ID: {user.worker_id || '—'}</div>
                <div>Created: {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</div>
                <div>Updated: {user.updated_at ? new Date(user.updated_at).toLocaleDateString() : '—'}</div>
            </div>
        </div>
    );
}

// ========== Main Page ==========
export default function ManageUsersPage() {
    const [users, setUsers] = useState<UserRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [roleFilter, setRoleFilter] = useState('all');
    const [showInvite, setShowInvite] = useState(false);
    const [selectedUser, setSelectedUser] = useState<UserRecord | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch<any>('/permissions');
            setUsers(res.permissions || []);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleInvite = async (data: { user_id: string; role: string; display_name?: string; phone?: string; emergency_contact?: string }) => {
        try {
            await apiFetch('/permissions', {
                method: 'POST',
                body: JSON.stringify(data),
            });
            showNotice(`User ${data.user_id} added as ${ROLE_LABELS[data.role]}`);
            setShowInvite(false);
            load();
        } catch { showNotice('Failed to add user'); }
    };

    const handleUpdate = async (userId: string, data: Record<string, any>) => {
        try {
            await apiFetch('/permissions', {
                method: 'POST',
                body: JSON.stringify({ user_id: userId, ...data }),
            });
            showNotice(`Updated ${userId}`);
            setSelectedUser(null);
            load();
        } catch { showNotice('Update failed'); }
    };

    const handleDeactivate = async (userId: string) => {
        try {
            await apiFetch(`/permissions/${encodeURIComponent(userId)}`, { method: 'DELETE' });
            showNotice(`Deactivated ${userId}`);
            setSelectedUser(null);
            load();
        } catch { showNotice('Deactivation failed'); }
    };

    // Filtered and searched users
    const filtered = users.filter(u => {
        if (roleFilter !== 'all' && u.role !== roleFilter) return false;
        if (search) {
            const s = search.toLowerCase();
            return (u.user_id || '').toLowerCase().includes(s) ||
                   (u.display_name || '').toLowerCase().includes(s) ||
                   (u.worker_id || '').toLowerCase().includes(s);
        }
        return true;
    });

    const roleCounts = ROLES.reduce((acc, r) => {
        acc[r] = users.filter(u => u.role === r).length;
        return acc;
    }, {} as Record<string, number>);

    const cardStyle = {
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-5)',
    };

    return (
        <div style={{ maxWidth: 1100 }}>
            {/* Notice toast */}
            {notice && (
                <div style={{
                    position: 'fixed', top: 20, right: 20, zIndex: 999,
                    background: 'var(--color-surface)', border: '1px solid var(--color-primary)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)', color: 'var(--color-primary)', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                }}>
                    {notice}
                </div>
            )}

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-4)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Access Control</p>
                    <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
                        Manage Users
                    </h1>
                </div>
                <button onClick={() => setShowInvite(true)} style={{
                    padding: '10px 20px', borderRadius: 'var(--radius-md)',
                    background: 'var(--color-primary)', color: '#fff', border: 'none',
                    cursor: 'pointer', fontWeight: 600, fontSize: 'var(--text-sm)',
                }}>
                    + Invite User
                </button>
            </div>

            {/* Summary cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 'var(--space-3)', marginBottom: 'var(--space-5)' }}>
                <div style={cardStyle}>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Total</div>
                    <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-primary)', marginTop: 4 }}>{users.length}</div>
                </div>
                {ROLES.map(r => (
                    <div key={r} style={{ ...cardStyle, cursor: 'pointer', borderColor: roleFilter === r ? (ROLE_COLORS[r]?.text || 'var(--color-border)') : 'var(--color-border)' }}
                        onClick={() => setRoleFilter(roleFilter === r ? 'all' : r)}>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>{ROLE_LABELS[r]?.split(' ')[0]}</div>
                        <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: ROLE_COLORS[r]?.text || 'var(--color-text)', marginTop: 4 }}>{roleCounts[r] || 0}</div>
                    </div>
                ))}
            </div>

            {/* Search & filters */}
            <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                <input
                    value={search} onChange={e => setSearch(e.target.value)}
                    placeholder="Search by name or email…"
                    style={{
                        flex: 1, background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)', padding: '8px 14px', color: 'var(--color-text)',
                        fontSize: 'var(--text-sm)', outline: 'none',
                    }}
                />
                {roleFilter !== 'all' && (
                    <button onClick={() => setRoleFilter('all')} style={{
                        padding: '8px 14px', borderRadius: 'var(--radius-md)',
                        background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                        color: 'var(--color-text-dim)', cursor: 'pointer', fontSize: 'var(--text-xs)',
                    }}>
                        Clear filter ✕
                    </button>
                )}
            </div>

            {/* User table */}
            <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
                {/* Table header */}
                <div style={{
                    display: 'grid', gridTemplateColumns: '1fr 120px 80px 140px',
                    gap: 'var(--space-3)', padding: 'var(--space-3) var(--space-4)',
                    borderBottom: '1px solid var(--color-border)',
                    fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.04em',
                }}>
                    <div>User</div>
                    <div>Role</div>
                    <div>Status</div>
                    <div>Permissions</div>
                </div>

                {loading && <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</div>}

                {!loading && filtered.length === 0 && (
                    <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>
                        {search ? 'No users match your search' : 'No users yet. Click "Invite User" to add team members.'}
                    </div>
                )}

                {filtered.map(u => (
                    <div key={u.user_id}
                        onClick={() => setSelectedUser(u)}
                        style={{
                            display: 'grid', gridTemplateColumns: '1fr 120px 80px 140px',
                            gap: 'var(--space-3)', padding: 'var(--space-3) var(--space-4)',
                            borderBottom: '1px solid var(--color-border)',
                            cursor: 'pointer', transition: 'background 0.1s',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-surface-2)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                        <div>
                            <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                                {u.display_name || u.user_id}
                            </div>
                            {u.display_name && (
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>
                                    {u.user_id}
                                </div>
                            )}
                        </div>
                        <div><RoleBadge role={u.role} /></div>
                        <div style={{ fontSize: 'var(--text-sm)' }}>
                            <StatusDot active={u.is_active} />
                            {u.is_active !== false ? 'Active' : 'Off'}
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                            {u.permissions?.can_approve_access_requests && <span title="Can approve access requests">✓ Approve </span>}
                            {u.permissions?.can_booking_override && <span title="Can override bookings">✓ Override</span>}
                            {!u.permissions?.can_approve_access_requests && !u.permissions?.can_booking_override && '—'}
                        </div>
                    </div>
                ))}
            </div>

            {/* Invite Modal */}
            {showInvite && <InviteModal onClose={() => setShowInvite(false)} onInvite={handleInvite} />}

            {/* User Detail Panel */}
            {selectedUser && (
                <UserDetailPanel
                    user={selectedUser}
                    onClose={() => setSelectedUser(null)}
                    onUpdate={handleUpdate}
                    onDeactivate={handleDeactivate}
                />
            )}
        </div>
    );
}
