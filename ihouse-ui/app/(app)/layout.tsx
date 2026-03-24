/**
 * Phase 376 — Protected App Layout
 * Phase 550 — Toast Provider
 * Phase 551 — Skeleton Styles
 * Phase 552 — Breadcrumbs
 * Phase 870 — ActAsProvider wraps entire shell (sidebar + content both need context)
 */

import AdaptiveShell from '../../components/AdaptiveShell';
import ClientProviders from '../../components/ClientProviders';
import ActAsWrapper from '../../components/ActAsWrapper';
import { ToastProvider } from '../../components/Toast';
import { SkeletonStyles } from '../../components/Skeleton';
import Breadcrumbs from '../../components/Breadcrumbs';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <ActAsWrapper>
        <AdaptiveShell>
          <ClientProviders>
            <ToastProvider>
              <SkeletonStyles />
              <Breadcrumbs />
              {children}
            </ToastProvider>
          </ClientProviders>
        </AdaptiveShell>
      </ActAsWrapper>
    </div>
  );
}
