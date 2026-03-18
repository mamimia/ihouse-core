'use client';

/**
 * Phase 844 — Force light theme for internal app pages.
 * Dark mode is reserved for the public website/blog/landing only.
 * Admin/management surfaces always use the light (white) theme.
 */

import { useEffect } from 'react';

export default function ForceLight() {
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', 'light');
        return () => {
            // Restore system preference when navigating away from app pages
            const stored = localStorage.getItem('domaniqo-theme');
            if (stored) {
                document.documentElement.setAttribute('data-theme', stored === 'system' ? '' : stored);
            }
        };
    }, []);
    return null;
}
