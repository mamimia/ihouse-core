/**
 * Phase 376 — Protected App Layout
 * Phase 550 — Toast Provider
 * Phase 551 — Skeleton Styles
 * Phase 552 — Breadcrumbs
 */

import AdaptiveShell from '../../components/AdaptiveShell';
import ClientProviders from '../../components/ClientProviders';
import { ToastProvider } from '../../components/Toast';
import { SkeletonStyles } from '../../components/Skeleton';
import Breadcrumbs from '../../components/Breadcrumbs';
import ForceLight from '../../components/ForceLight';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <ForceLight />
      <AdaptiveShell>
        <ClientProviders>
          <ToastProvider>
            <SkeletonStyles />
            <Breadcrumbs />
            {children}
          </ToastProvider>
        </ClientProviders>
      </AdaptiveShell>
    </div>
  );
}
