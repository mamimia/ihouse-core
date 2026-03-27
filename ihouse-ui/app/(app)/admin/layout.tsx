'use client';

/**
 * Phase 844 — Admin Layout
 * 
 * Wraps all /admin/* pages with AdminNav + forces light theme
 * by setting data-theme="light" on <html> element.
 * This overrides @media (prefers-color-scheme: dark) in tokens.css
 * which checks :root:not([data-theme="light"]).
 */

import { useEffect } from 'react';
import AdminNav from '../../../components/AdminNav';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
    // Phase 957: Disabled structural data-theme override to let ThemeProvider govern everything globally.

    return (
        <div style={{ width: '100%' }}>
            {children}
        </div>
    );
}
