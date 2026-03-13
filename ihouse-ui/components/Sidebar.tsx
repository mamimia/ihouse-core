'use client';

/**
 * Phase 526 — Enhanced Sidebar (replaces Phase 260)
 *
 * Changes from original:
 *  - Added Worker + Ops links
 *  - Active link highlighting via usePathname()
 *  - Settings link at bottom
 */

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useLanguage } from '../lib/LanguageContext';
import LogoutButton from './LogoutButton';
import LanguageSwitcher from './LanguageSwitcher';
import { TranslationKey } from '../lib/translations';

type Role = 'admin' | 'manager' | 'owner' | 'worker';

const NAV_ITEMS: { key: TranslationKey; href: string; icon: string; roles: Role[] }[] = [
  { key: 'nav.dashboard', href: '/dashboard', icon: '▪', roles: ['admin', 'manager', 'owner', 'worker'] },
  { key: 'nav.tasks',     href: '/tasks',     icon: '✓', roles: ['admin', 'manager', 'worker'] },
  { key: 'nav.bookings',  href: '/bookings',  icon: '📅', roles: ['admin', 'manager', 'owner'] },
  { key: 'nav.calendar',  href: '/calendar',  icon: '📆', roles: ['admin', 'manager', 'owner'] },
  { key: 'nav.financial', href: '/financial', icon: '₿', roles: ['admin', 'manager', 'owner'] },
  { key: 'nav.owner',     href: '/owner',     icon: '🏠', roles: ['admin', 'owner'] },
  { key: 'nav.manager',   href: '/manager',   icon: '📋', roles: ['admin', 'manager'] },
  { key: 'nav.guests',    href: '/guests',    icon: '👤', roles: ['admin', 'manager'] },
  { key: 'nav.admin',     href: '/admin',     icon: '⚙', roles: ['admin'] },
];

function getUserRole(): Role {
  if (typeof window === 'undefined') return 'manager';
  try {
    const token = localStorage.getItem('ihouse_token');
    if (!token) return 'manager';
    const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
    return (payload.role as Role) || 'manager';
  } catch { return 'manager'; }
}

export default function Sidebar() {
  const { t } = useLanguage();
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/dashboard') return pathname === '/dashboard' || pathname === '/';
    return pathname?.startsWith(href);
  };

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

      {/* Nav links — filtered by role (Phase 553) */}
      {NAV_ITEMS.filter(item => item.roles.includes(getUserRole())).map(({ key, href, icon }) => {
        const active = isActive(href);
        return (
          <Link key={href} href={href} style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-3)',
            padding: 'var(--space-3) var(--space-6)',
            fontSize: 'var(--text-sm)',
            color: active ? 'var(--color-primary)' : 'var(--color-text-dim)',
            background: active ? 'rgba(59,130,246,0.06)' : 'transparent',
            borderRight: active ? '2px solid var(--color-primary)' : '2px solid transparent',
            transition: 'all var(--transition-fast)',
            fontFamily: "'Inter', sans-serif",
            fontWeight: active ? 600 : 400,
            textDecoration: 'none',
          }}>
            <span style={{ fontSize: '1em', opacity: active ? 1 : 0.65 }}>{icon}</span>
            {t(key)}
          </Link>
        );
      })}

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
