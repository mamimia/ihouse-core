/**
 * Phase 376 — Protected App Layout
 *
 * Layout for authenticated operational pages.
 * Uses AdaptiveShell for responsive navigation:
 *   Desktop: sidebar + content
 *   Tablet: collapsible sidebar
 *   Mobile: bottom navigation
 */

import AdaptiveShell from '../../components/AdaptiveShell';
import ClientProviders from '../../components/ClientProviders';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <AdaptiveShell>
        <ClientProviders>
          {children}
        </ClientProviders>
      </AdaptiveShell>
    </div>
  );
}
