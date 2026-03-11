'use client';

/**
 * Phase 260 — Sidebar (client component)
 * Needed because layout.tsx must be a Server Component for Next.js metadata,
 * but the sidebar needs useLanguage() (client context).
 */

import { useLanguage } from '../lib/LanguageContext';
import LogoutButton from './LogoutButton';
import LanguageSwitcher from './LanguageSwitcher';
import { TranslationKey } from '../lib/translations';

const NAV_ITEMS: { key: TranslationKey; href: string; icon: string }[] = [
  { key: 'nav.dashboard', href: '/dashboard', icon: '▪' },
  { key: 'nav.tasks',     href: '/tasks',     icon: '✓' },
  { key: 'nav.bookings',  href: '/bookings',  icon: '📅' },
  { key: 'nav.calendar',  href: '/calendar',  icon: '📆' },
  { key: 'nav.financial', href: '/financial', icon: '₿' },
  { key: 'nav.owner',     href: '/owner',     icon: '🏠' },
  { key: 'nav.manager',   href: '/manager',   icon: '📋' },
  { key: 'nav.guests',    href: '/guests',    icon: '👤' },
  { key: 'nav.admin',     href: '/admin',     icon: '⚙' },
];

export default function Sidebar() {
  const { t } = useLanguage();

  return (
    <nav style={{
      width: 'var(--sidebar-width)',
      background: 'var(--color-surface)',
      borderRight: '1px solid var(--color-border)',
      display: 'flex',
      flexDirection: 'column',
      padding: 'var(--space-6) 0',
      position: 'fixed',
      top: 0,
      left: 0,
      height: '100vh',
      zIndex: 40,
    }}>
      {/* Logo */}
      <div style={{ padding: '0 var(--space-6)', marginBottom: 'var(--space-8)' }}>
        <div style={{
          fontSize: 'var(--text-base)',
          fontWeight: 700,
          fontFamily: "'Manrope', sans-serif",
          color: 'var(--color-midnight)',
          letterSpacing: '-0.01em',
        }}>
          Domaniqo
        </div>
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 2 }}>
          Operations Platform
        </div>
      </div>

      {/* Nav links */}
      {NAV_ITEMS.map(({ key, href, icon }) => (
        <a key={href} href={href} style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-3)',
          padding: 'var(--space-3) var(--space-6)',
          fontSize: 'var(--text-sm)',
          color: 'var(--color-text-dim)',
          transition: 'all var(--transition-fast)',
          fontFamily: "'Inter', sans-serif",
          textDecoration: 'none',
        }}>
          <span style={{ fontSize: '1em', opacity: 0.65 }}>{icon}</span>
          {t(key)}
        </a>
      ))}

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Language switcher */}
      <LanguageSwitcher />

      {/* Divider */}
      <div style={{ height: 1, background: 'var(--color-border)', margin: '8px 0' }} />

      {/* Logout */}
      <LogoutButton />
    </nav>
  );
}
