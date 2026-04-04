/**
 * Phase 376 — Protected App Layout
 * Phase 550 — Toast Provider
 * Phase 551 — Skeleton Styles
 * Phase 552 — Breadcrumbs
 * Phase 870 — ActAsProvider wraps entire shell (sidebar + content both need context)
 * Phase 1068 — OMUnreadProvider + OMUnreadPopup for OM unread badge + popup alerts
 */

import AdaptiveShell from '../../components/AdaptiveShell';
import ClientProviders from '../../components/ClientProviders';
import ActAsWrapper from '../../components/ActAsWrapper';
import { ToastProvider } from '../../components/Toast';
import { SkeletonStyles } from '../../components/Skeleton';
import Breadcrumbs from '../../components/Breadcrumbs';
import { OMUnreadProvider } from '../../contexts/OMUnreadContext';
import OMUnreadPopup from '../../components/OMUnreadPopup';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <ActAsWrapper>
        <OMUnreadProvider>
          <AdaptiveShell>
            <ClientProviders>
              <ToastProvider>
                <SkeletonStyles />
                <Breadcrumbs />
                {children}
              </ToastProvider>
            </ClientProviders>
          </AdaptiveShell>
          <OMUnreadPopup />
        </OMUnreadProvider>
      </ActAsWrapper>
    </div>
  );
}
