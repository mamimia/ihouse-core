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
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', 'light');
        return () => {
            document.documentElement.removeAttribute('data-theme');
        };
    }, []);

    return (
        <div style={{ width: '100%' }}>
            {children}
        </div>
    );
}
