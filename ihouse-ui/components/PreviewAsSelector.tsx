'use client';

/**
 * Phase 875 — Admin Preview As Selector (Canonical Dropdown)
 * Phase 876 — Safari fix: window.open moved to button onClick (not select onChange)
 *
 * Embedded directly in the sidebar for admins.
 * Opens preview in a new tab leaving the admin session untouched.
 *
 * Dropdown targets follow the canonical preview-dropdown-matrix.md:
 * 7 targets — no "Worker" in user-facing language.
 */

import { usePreview } from '../lib/PreviewContext';
import { useEffect, useState } from 'react';

export default function PreviewAsSelector() {
    const { previewRole, clearPreview } = usePreview();
    const [isAdmin, setIsAdmin] = useState(false);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        try {
            const token = localStorage.getItem('ihouse_token');
            if (token) {
                const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
                if (payload.role === 'admin') setIsAdmin(true);
            }
        } catch { }
    }, []);

    if (!mounted || !isAdmin) return null;

    if (previewRole) {
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
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)', textTransform: 'capitalize' }}>
                        {previewRole.replace('_', ' ')}
                    </span>
                    <button
                        onClick={() => clearPreview()}
                        style={{
                            marginTop: 4, background: 'var(--color-surface, #fff)', color: 'var(--color-text-dim)',
                            border: '1px solid var(--color-border)', borderRadius: 4, padding: '4px 0',
                            fontSize: '10px', fontWeight: 600, cursor: 'pointer'
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

/**
 * Isolated sub-component so we can use local state for the selected role
 * without tangling it with the parent's admin/mount checks.
 *
 * Safari fix: window.open must be called from a direct button onClick,
 * not from a <select> onChange, otherwise Safari's popup blocker kills it.
 */
function PreviewAsSelectorOpen() {
    const [selectedRole, setSelectedRole] = useState('');

    const handleOpen = () => {
        if (!selectedRole) return;
        // Direct button click — Safari allows window.open here
        window.open('/preview?role=' + selectedRole, '_blank');
    };

    return (
        <div style={{ padding: 'var(--space-2) var(--space-6)', margin: 'var(--space-2) 0' }}>
            <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', marginBottom: 6, letterSpacing: '0.04em' }}>
                Admin Tools
            </div>
            <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <select
                    value={selectedRole}
                    onChange={(e) => setSelectedRole(e.target.value)}
                    style={{
                        flex: 1,
                        height: 28,
                        padding: '0 8px',
                        borderRadius: 'var(--radius-sm, 6px)',
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-surface-2)',
                        color: 'var(--color-text)',
                        fontSize: 'var(--text-xs)',
                        outline: 'none',
                        cursor: 'pointer',
                        appearance: 'none',
                        boxSizing: 'border-box',
                        lineHeight: 1,
                    }}
                >
                    <option value="" disabled>👀 Preview UI As...</option>
                    <option value="manager">Ops Manager</option>
                    <option value="owner">Owner</option>
                    <option value="cleaner">Cleaner</option>
                    <option value="checkin">Check-in Staff</option>
                    <option value="checkout">Check-out Staff</option>
                    <option value="checkin_checkout">Check-in &amp; Check-out</option>
                    <option value="maintenance">Maintenance</option>
                </select>
                <button
                    onClick={handleOpen}
                    disabled={!selectedRole}
                    title="Open preview in new tab"
                    style={{
                        width: 28,
                        height: 28,
                        padding: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: 'var(--radius-sm, 6px)',
                        border: '1px solid var(--color-border)',
                        background: 'transparent',
                        color: selectedRole ? 'var(--color-text)' : 'var(--color-text-dim)',
                        fontSize: 13,
                        lineHeight: 1,
                        cursor: selectedRole ? 'pointer' : 'not-allowed',
                        opacity: selectedRole ? 0.7 : 0.25,
                        transition: 'opacity 0.15s',
                        flexShrink: 0,
                        boxSizing: 'border-box',
                    }}
                >
                    ↗
                </button>
            </div>
        </div>
    );
}
