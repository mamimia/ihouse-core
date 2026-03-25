'use client';

/**
 * Phase 864 — Act As Selector (Sidebar Entry Point)
 *
 * Product model: mirrors Preview As selector interaction.
 *  - Dropdown + ↗ open button (Safari-safe window.open from button click)
 *  - Opens Act As session in a NEW TAB — admin tab stays untouched
 *  - The new tab receives the scoped JWT and opens the role surface
 *
 * Admin tab is NEVER modified. No token swap. No page reload.
 * The admin can keep working while one or more Act As tabs are open.
 *
 * Product rule: Preview As = see only (yellow). Act As = do (red).
 */

import { useState, useRef } from 'react';
import { useActAs } from '../lib/ActAsContext';

const ACTABLE_ROLES = [
    { value: 'manager', label: 'Ops Manager' },
    { value: 'owner', label: 'Owner' },
    { value: 'cleaner', label: 'Cleaner' },
    { value: 'checkin', label: 'Check-in Staff' },
    { value: 'checkout', label: 'Check-out Staff' },
    { value: 'checkin_checkout', label: 'Check-in & Check-out' },
    { value: 'maintenance', label: 'Maintenance' },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

export default function ActAsSelector() {
    const { isAvailable, isActing, session, endActAs } = useActAs();
    const [selectedRole, setSelectedRole] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    // Store the token from the API response so the ↗ button can use it
    const pendingTokenRef = useRef<{ token: string; role: string } | null>(null);

    // While acting (only visible in the act-as tab, not admin tab), show status
    if (isActing && session) {
        return (
            <div style={{ padding: 'var(--space-2) var(--space-6)', marginTop: 4 }}>
                <div style={{
                    background: 'rgba(239, 68, 68, 0.12)',
                    border: '1px solid rgba(239, 68, 68, 0.35)',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: '#EF4444', fontWeight: 700 }}>
                        🔴 ACTING AS
                    </span>
                    <span style={{
                        fontSize: 'var(--text-sm)',
                        color: 'var(--color-text)',
                        textTransform: 'capitalize',
                        fontWeight: 600,
                    }}>
                        {session.actingAsRole.replace('_', ' ')}
                    </span>
                    <button
                        onClick={() => endActAs()}
                        style={{
                            marginTop: 4,
                            background: 'rgba(239, 68, 68, 0.2)',
                            color: '#EF4444',
                            border: '1px solid rgba(239, 68, 68, 0.4)',
                            borderRadius: 4,
                            padding: '4px 0',
                            fontSize: '10px',
                            fontWeight: 700,
                            cursor: 'pointer',
                            textTransform: 'uppercase',
                            letterSpacing: '0.03em',
                        }}
                    >
                        END SESSION
                    </button>
                </div>
            </div>
        );
    }

    // Not available (non-admin, production, or already acting in this tab)
    if (!isAvailable) return null;

    /**
     * Phase 864 — Two-step flow (Safari-safe):
     * 1. User selects role from dropdown
     * 2. User clicks ↗ button → calls /auth/act-as/start → opens new tab with token
     *
     * window.open MUST be called from a direct button click handler,
     * not from an async callback, otherwise Safari blocks it as a popup.
     * So we call the API first, store the result, then open.
     */
    const handleOpen = async () => {
        if (!selectedRole) return;

        setLoading(true);
        setError('');

        try {
            const currentToken = localStorage.getItem('ihouse_token');
            if (!currentToken) {
                setError('Not authenticated');
                setLoading(false);
                return;
            }

            const res = await fetch(`${API_BASE}/auth/act-as/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${currentToken}`,
                },
                body: JSON.stringify({ target_role: selectedRole, ttl_seconds: 3600 }),
            });

            const body = await res.json();

            if (!res.ok) {
                const msg = body?.error?.message || body?.detail || 'Failed to start Act As';
                setError(msg);
                setTimeout(() => setError(''), 5000);
                setLoading(false);
                return;
            }

            const data = body?.data ?? body;
            const actAsToken = data.token;

            if (!actAsToken) {
                setError('No token received from server');
                setLoading(false);
                return;
            }

            // Open the new tab with the token — admin tab is unchanged
            // The /act-as landing page will store the token and redirect
            const url = `/act-as?token=${encodeURIComponent(actAsToken)}&role=${encodeURIComponent(selectedRole)}`;
            window.open(url, '_blank');

            // Reset UI in admin tab
            setSelectedRole('');
            setLoading(false);
        } catch (exc) {
            setError(`Network error: ${exc}`);
            setTimeout(() => setError(''), 5000);
            setLoading(false);
        }
    };

    return (
        <div style={{ padding: '0 var(--space-6)', marginTop: 4 }}>
            <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <select
                    value={selectedRole}
                    onChange={(e) => setSelectedRole(e.target.value)}
                    disabled={loading}
                    style={{
                        flex: 1,
                        height: 28,
                        padding: '0 8px',
                        borderRadius: 'var(--radius-sm, 6px)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        background: 'rgba(239, 68, 68, 0.06)',
                        color: 'var(--color-text)',
                        fontSize: 'var(--text-xs)',
                        outline: 'none',
                        cursor: loading ? 'wait' : 'pointer',
                        appearance: 'none' as const,
                        boxSizing: 'border-box' as const,
                        lineHeight: 1,
                        opacity: loading ? 0.6 : 1,
                    }}
                >
                    <option value="" disabled>
                        {loading ? '⏳ Starting...' : '🔴 Act As... (QA only)'}
                    </option>
                    {ACTABLE_ROLES.map(r => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                </select>
                <button
                    onClick={handleOpen}
                    disabled={!selectedRole || loading}
                    title="Open Act As session in new tab"
                    style={{
                        padding: 4,
                        background: 'none',
                        border: 'none',
                        color: selectedRole ? '#EF4444' : 'var(--color-text-dim)',
                        fontSize: 14,
                        lineHeight: 1,
                        cursor: (selectedRole && !loading) ? 'pointer' : 'not-allowed',
                        opacity: (selectedRole && !loading) ? 0.8 : 0.2,
                        transition: 'opacity 0.15s',
                        flexShrink: 0,
                    }}
                >
                    ↗
                </button>
            </div>
            {error && (
                <div style={{
                    marginTop: 4,
                    fontSize: 10,
                    color: '#EF4444',
                    padding: '4px 6px',
                    background: 'rgba(239,68,68,0.1)',
                    borderRadius: 4,
                }}>
                    {error}
                </div>
            )}
        </div>
    );
}
