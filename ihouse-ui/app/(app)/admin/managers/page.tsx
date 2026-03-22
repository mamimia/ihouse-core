'use client';

/**
 * Phase 862 P33 — Admin Managers & Capabilities Page
 * Route: /admin/managers
 *
 * Allows admins to view all managers in their tenant and
 * delegate/revoke individual capabilities per manager.
 */

import { useState, useEffect, useCallback } from 'react';

interface ManagerCapabilities {
    [key: string]: boolean;
}

interface Manager {
    user_id: string;
    email: string;
    full_name: string;
    is_active: boolean;
    capabilities: ManagerCapabilities;
}

const CAPABILITY_LABELS: Record<string, { label: string; description: string; icon: string }> = {
    financial:    { label: 'Financial',    description: 'View / export financial reports',      icon: '💰' },
    staffing:     { label: 'Staffing',     description: 'Invite / deactivate workers',          icon: '👥' },
    properties:   { label: 'Properties',   description: 'Edit property details & listings',     icon: '🏠' },
    bookings:     { label: 'Bookings',     description: 'Modify bookings & cancellations',      icon: '📋' },
    maintenance:  { label: 'Maintenance',  description: 'Approve maintenance, assign priority', icon: '🔧' },
    settings:     { label: 'Settings',     description: 'Edit tenant settings',                 icon: '⚙️' },
    intake:       { label: 'Intake',       description: 'Review & approve intake requests',     icon: '📥' },
};

const ALL_CAPS = Object.keys(CAPABILITY_LABELS);

function getToken(): string {
    return document.cookie
        .split('; ')
        .find(c => c.startsWith('ihouse_token='))
        ?.split('=')[1] || '';
}

const API_BASE = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE || '')
    : '';

export default function AdminManagersPage() {
    const [managers, setManagers] = useState<Manager[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [saving, setSaving] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState('');

    const fetchManagers = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const token = getToken();
            const res = await fetch(`${API_BASE}/admin/managers`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            const body = await res.json();
            const data = body?.data || body;
            if (!res.ok) {
                setError(data?.error || 'Failed to load managers');
                return;
            }
            setManagers(data.managers || []);
        } catch {
            setError('Failed to load managers');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchManagers(); }, [fetchManagers]);

    const toggleCapability = async (userId: string, cap: string, currentValue: boolean) => {
        setSaving(userId);
        setSuccessMsg('');
        try {
            const token = getToken();
            const res = await fetch(`${API_BASE}/admin/managers/${userId}/capabilities`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ capabilities: { [cap]: !currentValue } }),
            });
            if (res.ok) {
                // Update local state
                setManagers(prev => prev.map(m =>
                    m.user_id === userId
                        ? { ...m, capabilities: { ...m.capabilities, [cap]: !currentValue } }
                        : m
                ));
                setSuccessMsg(`Updated ${CAPABILITY_LABELS[cap]?.label || cap} for ${userId.slice(0, 8)}…`);
                setTimeout(() => setSuccessMsg(''), 2500);
            } else {
                const body = await res.json();
                setError(body?.error || 'Failed to update capability');
            }
        } catch {
            setError('Failed to update capability');
        } finally {
            setSaving(null);
        }
    };

    // Styles
    const card: React.CSSProperties = {
        background: 'var(--color-surface, #fff)',
        border: '1px solid var(--color-border, #e5e5e5)',
        borderRadius: 'var(--radius-lg, 16px)',
        padding: 'var(--space-5, 20px)',
        marginBottom: 'var(--space-4, 16px)',
    };

    const badge: React.CSSProperties = {
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 10px',
        borderRadius: '6px',
        fontSize: '12px',
        fontWeight: 600,
    };

    return (
        <div style={{ maxWidth: 800, margin: '0 auto', padding: 'var(--space-6, 24px)' }}>
            <div style={{ marginBottom: 'var(--space-6, 24px)' }}>
                <h1 style={{
                    fontSize: 'var(--text-2xl, 24px)',
                    fontWeight: 700,
                    color: 'var(--color-text, #1a1a1a)',
                    marginBottom: 'var(--space-2, 8px)',
                }}>
                    Manager Capabilities
                </h1>
                <p style={{
                    fontSize: 'var(--text-sm, 14px)',
                    color: 'var(--color-text-dim, #666)',
                }}>
                    Delegate specific capabilities to each operational manager.
                    Two managers in the same organization can have different access levels.
                </p>
            </div>

            {/* Messages */}
            {error && (
                <div style={{
                    background: '#FEE2E2',
                    border: '1px solid #FECACA',
                    borderRadius: '10px',
                    padding: '10px 16px',
                    color: '#DC2626',
                    fontSize: '14px',
                    marginBottom: 'var(--space-4, 16px)',
                }}>
                    ⚠ {error}
                </div>
            )}
            {successMsg && (
                <div style={{
                    background: '#DCFCE7',
                    border: '1px solid #BBF7D0',
                    borderRadius: '10px',
                    padding: '10px 16px',
                    color: '#16A34A',
                    fontSize: '14px',
                    marginBottom: 'var(--space-4, 16px)',
                }}>
                    ✓ {successMsg}
                </div>
            )}

            {/* Loading */}
            {loading && (
                <div style={{ textAlign: 'center', padding: 'var(--space-8, 32px) 0', color: 'var(--color-text-dim, #666)' }}>
                    Loading managers…
                </div>
            )}

            {/* No managers */}
            {!loading && managers.length === 0 && !error && (
                <div style={{
                    ...card,
                    textAlign: 'center',
                    color: 'var(--color-text-dim, #666)',
                    padding: 'var(--space-10, 48px)',
                }}>
                    No operational managers found in this organization.
                </div>
            )}

            {/* Manager cards */}
            {managers.map(manager => (
                <div key={manager.user_id} style={card}>
                    {/* Header */}
                    <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: 'var(--space-4, 16px)',
                    }}>
                        <div>
                            <div style={{
                                fontSize: 'var(--text-base, 16px)',
                                fontWeight: 600,
                                color: 'var(--color-text, #1a1a1a)',
                            }}>
                                {manager.full_name || manager.email || 'Unnamed Manager'}
                            </div>
                            {manager.full_name && manager.email && (
                                <div style={{
                                    fontSize: 'var(--text-xs, 12px)',
                                    color: 'var(--color-text-dim, #666)',
                                    marginTop: '2px',
                                }}>
                                    {manager.email}
                                </div>
                            )}
                        </div>
                        <span style={{
                            ...badge,
                            background: manager.is_active ? '#DCFCE7' : '#FEE2E2',
                            color: manager.is_active ? '#16A34A' : '#DC2626',
                        }}>
                            {manager.is_active ? '● Active' : '● Inactive'}
                        </span>
                    </div>

                    {/* Capabilities grid */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                        gap: 'var(--space-3, 12px)',
                    }}>
                        {ALL_CAPS.map(cap => {
                            const meta = CAPABILITY_LABELS[cap];
                            const enabled = manager.capabilities[cap] === true;
                            const isSaving = saving === manager.user_id;

                            return (
                                <button
                                    key={cap}
                                    id={`cap-${manager.user_id.slice(0, 8)}-${cap}`}
                                    onClick={() => toggleCapability(manager.user_id, cap, enabled)}
                                    disabled={isSaving}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '8px',
                                        padding: '10px 14px',
                                        background: enabled
                                            ? 'rgba(22,163,74,0.06)'
                                            : 'var(--color-surface-2, #f5f5f5)',
                                        border: `1px solid ${enabled ? 'rgba(22,163,74,0.2)' : 'var(--color-border, #e5e5e5)'}`,
                                        borderRadius: '10px',
                                        cursor: isSaving ? 'wait' : 'pointer',
                                        opacity: isSaving ? 0.6 : 1,
                                        transition: 'all 0.15s',
                                        textAlign: 'left',
                                        width: '100%',
                                    }}
                                >
                                    <span style={{ fontSize: '16px' }}>{meta.icon}</span>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{
                                            fontSize: '13px',
                                            fontWeight: 600,
                                            color: enabled ? '#16A34A' : 'var(--color-text, #1a1a1a)',
                                        }}>
                                            {meta.label}
                                        </div>
                                        <div style={{
                                            fontSize: '11px',
                                            color: 'var(--color-text-dim, #888)',
                                            whiteSpace: 'nowrap',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                        }}>
                                            {meta.description}
                                        </div>
                                    </div>
                                    <div style={{
                                        width: 18, height: 18,
                                        borderRadius: '4px',
                                        border: `2px solid ${enabled ? '#16A34A' : '#ccc'}`,
                                        background: enabled ? '#16A34A' : 'transparent',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        fontSize: '12px',
                                        color: '#fff',
                                        flexShrink: 0,
                                    }}>
                                        {enabled ? '✓' : ''}
                                    </div>
                                </button>
                            );
                        })}
                    </div>

                    {/* User ID */}
                    <div style={{
                        marginTop: 'var(--space-3, 12px)',
                        fontSize: '11px',
                        color: 'var(--color-text-faint, #aaa)',
                        fontFamily: 'monospace',
                    }}>
                        ID: {manager.user_id}
                    </div>
                </div>
            ))}
        </div>
    );
}
