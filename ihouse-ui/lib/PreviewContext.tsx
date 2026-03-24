'use client';

/**
 * Phase 846 — Admin Preview As Context
 * Phase 863 — Honesty + Safety Hardening: added isPreviewActive for mutation disabling
 * Phase 867 — Preview audit trail: emit PREVIEW_OPENED/CLOSED to backend
 * 
 * Provides a context for Admins to simulate other roles across the UI.
 * When isPreviewActive is true, all mutation controls must be disabled.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';

type Role = 'admin' | 'manager' | 'owner' | 'worker' | 'cleaner' | 'checkin' | 'checkout' | 'checkin_checkout' | 'maintenance' | null;

interface PreviewContextType {
    previewRole: Role;
    /** True when preview mode is active — all mutations must be disabled */
    isPreviewActive: boolean;
    setPreviewRole: (role: Role) => void;
    clearPreview: () => void;
    getEffectiveRole: (realRole: string) => string;
}

const PreviewContext = createContext<PreviewContextType | undefined>(undefined);

// ---------------------------------------------------------------------------
// Phase 867 — Preview audit helper (best-effort, fire-and-forget)
// ---------------------------------------------------------------------------

const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

function emitPreviewAudit(action: 'PREVIEW_OPENED' | 'PREVIEW_CLOSED', previewRole: string, route?: string) {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('ihouse_token');
    if (!token) return;

    // Fire-and-forget — never block UI for audit
    fetch(`${API_BASE}/admin/preview/audit`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...(action === 'PREVIEW_CLOSED'
                ? {} // No preview role header when closing
                : { 'X-Preview-Role': previewRole }),
        },
        body: JSON.stringify({ action, preview_role: previewRole, route: route || window.location.pathname }),
    }).catch(() => {
        // Best-effort — swallow all errors
    });
}

export function PreviewProvider({ children }: { children: React.ReactNode }) {
    const [previewRole, setPreviewRole] = useState<Role>(null);

    // Load from sessionStorage on mount
    useEffect(() => {
        try {
            const stored = sessionStorage.getItem('ihouse_preview_role');
            if (stored) setPreviewRole(stored as Role);
        } catch {}
    }, []);

    const handleSetRole = (role: Role) => {
        const prevRole = previewRole;

        try {
            if (role) {
                sessionStorage.setItem('ihouse_preview_role', role);
            } else {
                sessionStorage.removeItem('ihouse_preview_role');
            }
        } catch {}

        // Phase 867 — Emit audit events
        if (role && !prevRole) {
            // Opening preview
            emitPreviewAudit('PREVIEW_OPENED', role);
        } else if (!role && prevRole) {
            // Closing preview
            emitPreviewAudit('PREVIEW_CLOSED', prevRole);
        } else if (role && prevRole && role !== prevRole) {
            // Switching target — close old, open new
            emitPreviewAudit('PREVIEW_CLOSED', prevRole);
            emitPreviewAudit('PREVIEW_OPENED', role);
        }

        setPreviewRole(role);
        
        // Temporary for 846: force reload so non-reactive parts (like raw local storage readers) update
        // In 847 we will do proper JWT simulation.
        window.location.reload();
    };

    const getEffectiveRole = (realRole: string) => {
        if (realRole === 'admin' && previewRole) {
            return previewRole;
        }
        return realRole;
    };

    const isPreviewActive = previewRole !== null;

    return (
        <PreviewContext.Provider value={{ 
            previewRole,
            isPreviewActive,
            setPreviewRole: handleSetRole, 
            clearPreview: () => handleSetRole(null),
            getEffectiveRole
        }}>
            {children}
        </PreviewContext.Provider>
    );
}

export function usePreview() {
    const ctx = useContext(PreviewContext);
    if (!ctx) return { previewRole: null, isPreviewActive: false, setPreviewRole: () => {}, clearPreview: () => {}, getEffectiveRole: (r: string) => r };
    return ctx;
}
