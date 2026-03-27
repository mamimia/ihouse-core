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
    // Phase 957: Disabled structural forcing to respect ThemeProvider globally.
    return null;

    return null;
}
