/*
 * Phase 367 — Client Providers Wrapper
 * Phase 863 — Added PreviewBanner for Preview Mode indicator
 *
 * Client component wrapper for ErrorBoundary, OfflineBanner, and PreviewBanner.
 * Must be a separate 'use client' component since root layout is a server component.
 */
'use client';

import ErrorBoundary from './ErrorBoundary';
import OfflineBanner from './OfflineBanner';
import PreviewBanner from './PreviewBanner';
import MutationGuard from './MutationGuard';
import { PreviewProvider } from '../lib/PreviewContext';

export default function ClientProviders({ children }: { children: React.ReactNode }) {
    return (
        <ErrorBoundary>
            <PreviewProvider>
                <OfflineBanner />
                <PreviewBanner />
                <MutationGuard>
                    {children}
                </MutationGuard>
            </PreviewProvider>
        </ErrorBoundary>
    );
}

