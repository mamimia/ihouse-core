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

type Role = 'admin' | 'manager' | 'owner' | 'worker' | 'cleaner' | 'checkin_staff' | 'maintenance';

const NAV_ITEMS: { key: TranslationKey; href: string; icon: string; roles: Role[] }[] = [
  { key: 'nav.dashboard',   href: '/dashboard',        icon: '▪', roles: ['admin', 'manager', 'owner', 'worker', 'cleaner', 'checkin_staff', 'maintenance'] },
  { key: 'nav.tasks',       href: '/tasks',            icon: '✓', roles: ['admin', 'manager', 'worker', 'cleaner', 'checkin_staff', 'maintenance'] },
  { key: 'nav.cleaning' as TranslationKey, href: '/ops/cleaner', icon: '🧹', roles: ['worker', 'cleaner'] },
  { key: 'nav.bookings',    href: '/bookings',         icon: '📅', roles: ['admin', 'manager', 'owner'] },
  { key: 'nav.calendar',    href: '/calendar',         icon: '📆', roles: ['admin', 'manager', 'owner'] },
  { key: 'nav.financial',   href: '/financial',        icon: '₿', roles: ['admin', 'manager', 'owner'] },
  { key: 'nav.owner',       href: '/admin/owners',     icon: '🏠', roles: ['admin'] },
  { key: 'nav.manager',     href: '/manager',          icon: '📋', roles: ['admin', 'manager'] },
  { key: 'nav.guests',      href: '/guests',           icon: '👤', roles: ['admin', 'manager'] },
  { key: 'nav.properties',  href: '/admin/properties', icon: '🏘', roles: ['admin', 'manager'] },
  { key: 'nav.staff',       href: '/admin/staff',      icon: '👥', roles: ['admin', 'manager'] },
  { key: 'nav.admin',       href: '/admin',            icon: '⚙', roles: ['admin'] },
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

/** Returns display name for greeting — in priority order:
 *  1. display_name from JWT (set on tenant_permissions)
 *  2. full_name from user_metadata (set on Supabase auth user)
 *  3. Role-based fallback e.g. "Admin", "Cleaner"
 */
const ROLE_DISPLAY: Record<string, string> = {
  admin: 'Admin', manager: 'Manager', owner: 'Owner',
  worker: 'Worker', cleaner: 'Cleaner',
  checkin_staff: 'Check-in', maintenance: 'Maintenance',
};

function getGreetingName(role: Role): string {
  if (typeof window === 'undefined') return ROLE_DISPLAY[role] || 'there';
  try {
    const token = localStorage.getItem('ihouse_token');
    if (!token) return ROLE_DISPLAY[role] || 'there';
    const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
    // Priority 1: display_name on the JWT (set from tenant_permissions)
    if (payload.display_name && typeof payload.display_name === 'string')
      return payload.display_name.split(' ')[0]; // first name only
    // Priority 2: full_name from Supabase user_metadata (stored in JWT sub metadata)
    if (payload.full_name && typeof payload.full_name === 'string')
      return payload.full_name.split(' ')[0];
    // Priority 3: role fallback
    return ROLE_DISPLAY[payload.role] || 'there';
  } catch { return ROLE_DISPLAY[role] || 'there'; }
}

export default function Sidebar() {
  const { t } = useLanguage();
  const pathname = usePathname();

  const role = getUserRole();
  const name = getGreetingName(role);
  const hour = typeof window !== 'undefined' ? new Date().getHours() : 9;
  const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

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
      {/* Logo + Personalized Greeting */}
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
        {/* Personalized greeting — Phase 840 */}
        <div style={{
          marginTop: 'var(--space-4)',
          paddingTop: 'var(--space-3)',
          borderTop: '1px solid var(--color-border)',
          fontSize: 'var(--text-xs)',
          color: 'var(--color-text-dim)',
          lineHeight: 1.4,
        }}>
          <span style={{ display: 'block', color: 'var(--color-text-faint)', fontStyle: 'italic' }}>
            {salutation},
          </span>
          <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>
            {name}
          </span>
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
