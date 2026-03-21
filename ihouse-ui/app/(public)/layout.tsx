'use client';

/**
 * Phase 379 / Phase 860 — Public Layout
 *
 * Layout for unauthenticated public-facing pages (landing, login, early-access).
 * No sidebar, no auth guard. Includes PublicNav and PublicFooter.
 *
 * Phase 860: Landing page (/) has its own nav/footer/splash,
 * so PublicNav and PublicFooter are hidden on the root route.
 */

import { usePathname } from 'next/navigation';
import PublicNav from '../../components/PublicNav';
import PublicFooter from '../../components/PublicFooter';

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStandalone = pathname === '/' || pathname === '/privacy' || pathname === '/terms';

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {!isStandalone && <PublicNav />}
      <div style={{ flex: 1 }}>
        {children}
      </div>
      {!isStandalone && <PublicFooter />}
    </div>
  );
}
