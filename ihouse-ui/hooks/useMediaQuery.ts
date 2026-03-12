/**
 * Phase 376 — useMediaQuery Hook
 *
 * Lightweight client-side hook wrapping window.matchMedia.
 * SSR-safe: returns false during server-side rendering.
 */
'use client';

import { useState, useEffect } from 'react';

export function useMediaQuery(query: string): boolean {
    const [matches, setMatches] = useState(false);

    useEffect(() => {
        if (typeof window === 'undefined') return;

        const mql = window.matchMedia(query);
        setMatches(mql.matches);

        const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
        mql.addEventListener('change', handler);
        return () => mql.removeEventListener('change', handler);
    }, [query]);

    return matches;
}

/* Predefined breakpoints matching tokens.css */
export const BREAKPOINTS = {
    mobile: '(max-width: 767px)',
    tablet: '(min-width: 768px) and (max-width: 1023px)',
    desktop: '(min-width: 1024px)',
    tabletUp: '(min-width: 768px)',
} as const;

export function useIsMobile() { return useMediaQuery(BREAKPOINTS.mobile); }
export function useIsTablet() { return useMediaQuery(BREAKPOINTS.tablet); }
export function useIsDesktop() { return useMediaQuery(BREAKPOINTS.desktop); }
