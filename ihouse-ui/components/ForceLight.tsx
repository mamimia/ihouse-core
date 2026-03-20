'use client';

/**
 * Phase 844 — Force light theme for internal app pages.
 * Phase 859 — Fixed: no longer causes flicker race with ThemeProvider.
 *
 * The root layout.tsx handles FOUC via inline script.
 * This component only handles client-side navigation transitions.
 * Uses direct DOM setAttribute once on mount — no state, no re-renders.
 */

import { useEffect, useRef } from 'react';

export default function ForceLight() {
    const prevTheme = useRef<string | null>(null);

    useEffect(() => {
        // Save previous theme and apply light once
        prevTheme.current = document.documentElement.getAttribute('data-theme');
        document.documentElement.setAttribute('data-theme', 'light');

        return () => {
            // Restore on unmount (navigating away from app section)
            const stored = localStorage.getItem('domaniqo-theme');
            const fallback = (stored === 'light' || stored === 'dark') ? stored : 'dark';
            document.documentElement.setAttribute('data-theme', fallback);
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // Run once only

    return null;
}
