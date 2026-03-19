'use client';

/**
 * Phase 846 — Admin Preview As Selector
 * 
 * Floating widget for admins to switch simulated roles.
 */

import { usePreview } from '../lib/PreviewContext';
import { useEffect, useState } from 'react';

export default function PreviewAsSelector() {
    const { previewRole, setPreviewRole, clearPreview } = usePreview();
    const [isAdmin, setIsAdmin] = useState(false);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        try {
            const token = localStorage.getItem('ihouse_token');
            if (token) {
                const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
                if (payload.role === 'admin') {
                    setIsAdmin(true);
                }
            }
        } catch { }
    }, []);

    if (!mounted || !isAdmin) return null;

    return (
        <div style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            zIndex: 9999,
            background: 'var(--color-surface, #1e2329)',
            border: `2px solid ${previewRole ? 'var(--color-warning)' : 'var(--color-primary)'}`,
            padding: 'var(--space-3) var(--space-4)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-xl)',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            maxWidth: 250,
        }}>
            <div style={{ 
                fontSize: 'var(--text-xs)', 
                fontWeight: 600, 
                color: previewRole ? 'var(--color-warning)' : 'var(--color-primary)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
            }}>
                <span>👀 Admin: Preview As</span>
                {previewRole && (
                    <span style={{ 
                        fontSize: 10, 
                        background: 'rgba(234, 179, 8, 0.2)', 
                        padding: '2px 4px', 
                        borderRadius: 4 
                    }}>
                        ACTIVE
                    </span>
                )}
            </div>
            <select 
                value={previewRole || ''} 
                onChange={(e) => {
                    const val = e.target.value;
                    if (val) setPreviewRole(val as any);
                    else clearPreview();
                }}
                style={{
                    padding: '6px 8px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text)',
                    fontSize: 'var(--text-sm)',
                    outline: 'none',
                    cursor: 'pointer',
                    width: '100%'
                }}
            >
                <option value="">Off (Real Admin)</option>
                <option value="manager">Manager</option>
                <option value="owner">Owner</option>
                <option value="worker">Worker (General)</option>
                <option value="cleaner">Cleaner</option>
                <option value="checkin_staff">Check-in Staff</option>
                <option value="maintenance">Maintenance</option>
            </select>
            {previewRole && (
                <div style={{ fontSize: '10px', color: 'var(--color-text-dim)', marginTop: 4 }}>
                    Simulating UI as <b>{previewRole}</b>. Stop preview to return to admin tasks.
                </div>
            )}
        </div>
    );
}
