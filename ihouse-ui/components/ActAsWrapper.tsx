'use client';

/**
 * Phase 870 — ActAs Wrapper
 *
 * Thin 'use client' component that wraps children with ActAsProvider.
 * Placed at the layout level so both Sidebar (inside AdaptiveShell) and
 * content area (inside ClientProviders) share the same ActAs context.
 */

import { ActAsProvider } from '../lib/ActAsContext';

export default function ActAsWrapper({ children }: { children: React.ReactNode }) {
    return <ActAsProvider>{children}</ActAsProvider>;
}
