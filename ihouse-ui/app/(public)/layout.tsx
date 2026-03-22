'use client';

/**
 * Phase 379 / Phase 860 — Public Layout
 *
 * Layout for unauthenticated public-facing pages (landing, login, early-access).
 * No sidebar, no auth guard. Includes PublicNav and PublicFooter.
 *
 * Phase 860: Landing page (/) has its own nav/footer/splash,
 * so PublicNav and PublicFooter are hidden on the root route.
 *
 * Phase 873: Signed-in surfaces (/welcome, /my-properties, /profile, /no-access)
 * must NOT render the marketing nav — they have their own minimal signed-in shell.
 */

import { usePathname } from 'next/navigation';
import PublicNav from '../../components/PublicNav';
import PublicFooter from '../../components/PublicFooter';

// Routes that are signed-in surfaces: suppress marketing nav/footer entirely
const SIGNED_IN_PREFIXES = ['/welcome', '/my-properties', '/profile', '/no-access'];

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStandalone = pathname === '/' || pathname === '/privacy' || pathname === '/terms';
  const isSignedInSurface = SIGNED_IN_PREFIXES.some(p => pathname === p || pathname.startsWith(p + '/'));

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {!isStandalone && !isSignedInSurface && <PublicNav />}
      <div style={{ flex: 1 }}>
        {children}
      </div>
      {!isStandalone && !isSignedInSurface && <PublicFooter />}
    </div>
  );
}

