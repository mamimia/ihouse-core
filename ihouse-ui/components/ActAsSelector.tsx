'use client';

/**
 * Phase 870 — Act As Selector (Sidebar Entry Point)
 *
 * Placed in the sidebar below Preview As, with clear visual separation.
 * Only visible to admin users in non-production environments.
 *
 * Product rule: Preview As = see only (yellow). Act As = do (red).
 */

import { useState } from 'react';
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

/**
 * Phase 864 — Canonical route map for Act As landing.
 * Must match admin-preview-and-act-as.md and preview/page.tsx PREVIEW_ROUTES.
 */
const ROLE_ROUTES: Record<string, string> = {
    manager:          '/dashboard',
    owner:            '/owner',
    cleaner:          '/ops/cleaner',
    checkin:          '/ops/checkin',
    checkout:         '/ops/checkout',
    checkin_checkout: '/ops/checkin-checkout',
    maintenance:      '/ops/maintenance',
};

export default function ActAsSelector() {
    const { isAvailable, isActing, session, startActAs, endActAs } = useActAs();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // While acting, show compact session status in sidebar
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

    // Not available (non-admin, production, or already acting)
    if (!isAvailable) return null;

    return (
        <div style={{ padding: '0 var(--space-6)', marginTop: 4 }}>
            <select
                value=""
                onChange={async (e) => {
                    const val = e.target.value;
                    if (!val) return;
                    setLoading(true);
                    setError('');
                    const result = await startActAs(val);
                    setLoading(false);
                    if (!result.ok) {
                        setError(result.error || 'Failed');
                        setTimeout(() => setError(''), 5000);
                    } else {
                        // Phase 864 — redirect to role-appropriate surface
                        const target = ROLE_ROUTES[val] || '/dashboard';
                        window.location.href = target;
                    }
                }}
                disabled={loading}
                style={{
                    padding: '6px 8px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    background: 'rgba(239, 68, 68, 0.06)',
                    color: 'var(--color-text)',
                    fontSize: 'var(--text-xs)',
                    outline: 'none',
                    cursor: loading ? 'wait' : 'pointer',
                    width: '100%',
                    appearance: 'none' as const,
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
