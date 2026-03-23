'use client';

/**
 * Phase 846 — Admin Preview As Context
 * 
 * Provides a context for Admins to simulate other roles across the UI.
 * This is the scaffolding phase. Actual JWT simulation happens in Phase 847.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';

type Role = 'admin' | 'manager' | 'owner' | 'worker' | 'cleaner' | 'checkin' | 'checkout' | 'checkin_checkout' | 'maintenance' | null;

interface PreviewContextType {
    previewRole: Role;
    setPreviewRole: (role: Role) => void;
    clearPreview: () => void;
    getEffectiveRole: (realRole: string) => string;
}

const PreviewContext = createContext<PreviewContextType | undefined>(undefined);

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
        try {
            if (role) {
                sessionStorage.setItem('ihouse_preview_role', role);
            } else {
                sessionStorage.removeItem('ihouse_preview_role');
            }
        } catch {}
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

    return (
        <PreviewContext.Provider value={{ 
            previewRole, 
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
    if (!ctx) return { previewRole: null, setPreviewRole: () => {}, clearPreview: () => {}, getEffectiveRole: (r: string) => r };
    return ctx;
}
