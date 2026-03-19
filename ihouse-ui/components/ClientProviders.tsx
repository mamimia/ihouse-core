/*
 * Phase 367 — Client Providers Wrapper
 *
 * Client component wrapper for ErrorBoundary and OfflineBanner.
 * Must be a separate 'use client' component since root layout is a server component.
 */
'use client';

import ErrorBoundary from './ErrorBoundary';
import OfflineBanner from './OfflineBanner';
import { PreviewProvider } from '../lib/PreviewContext';
import PreviewAsSelector from './PreviewAsSelector';

export default function ClientProviders({ children }: { children: React.ReactNode }) {
    return (
        <ErrorBoundary>
            <PreviewProvider>
                <OfflineBanner />
                <PreviewAsSelector />
                {children}
            </PreviewProvider>
        </ErrorBoundary>
    );
}
