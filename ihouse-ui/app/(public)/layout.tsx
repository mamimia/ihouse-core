/**
 * Phase 379 — Public Layout
 *
 * Layout for unauthenticated public-facing pages (landing, login, early-access).
 * No sidebar, no auth guard. Includes PublicNav and PublicFooter.
 */

import type { Metadata } from 'next';
import PublicNav from '../../components/PublicNav';
import PublicFooter from '../../components/PublicFooter';

export const metadata: Metadata = {
  title: 'Domaniqo — The deep operations platform for modern hospitality',
  description: 'Calm command for modern stays. Domaniqo brings clarity to property operations across booking, tasks, finance, and guest experience.',
  openGraph: {
    title: 'Domaniqo',
    description: 'The deep operations platform for modern hospitality.',
    type: 'website',
  },
};

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <PublicNav />
      <div style={{ flex: 1 }}>
        {children}
      </div>
      <PublicFooter />
    </div>
  );
}
