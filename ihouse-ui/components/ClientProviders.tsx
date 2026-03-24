/*
 * Phase 367 — Client Providers Wrapper
 * Phase 863 — Added PreviewBanner for Preview Mode indicator
 * Phase 870 — Added ActAsProvider and ActAsBanner for Act As sessions
 *
 * Client component wrapper for ErrorBoundary, OfflineBanner, PreviewBanner, ActAsBanner.
 * Must be a separate 'use client' component since root layout is a server component.
 */
'use client';

import ErrorBoundary from './ErrorBoundary';
import OfflineBanner from './OfflineBanner';
import PreviewBanner from './PreviewBanner';
import ActAsBanner from './ActAsBanner';
import MutationGuard from './MutationGuard';
import { PreviewProvider } from '../lib/PreviewContext';
import { ActAsProvider } from '../lib/ActAsContext';

export default function ClientProviders({ children }: { children: React.ReactNode }) {
    return (
        <ErrorBoundary>
            <PreviewProvider>
                <ActAsProvider>
                    <OfflineBanner />
                    <PreviewBanner />
                    <ActAsBanner />
                    <MutationGuard>
                        {children}
                    </MutationGuard>
                </ActAsProvider>
            </PreviewProvider>
        </ErrorBoundary>
    );
}
