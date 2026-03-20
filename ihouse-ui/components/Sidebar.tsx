'use client';

/**
 * Phase 526 — Enhanced Sidebar (replaces Phase 260)
 * Phase 860 — Responsive 3-mode: full sidebar / compact rail / mobile drawer
 *
 * Props:
 *   collapsed — when true, renders icon-only rail (64px) with CSS tooltips
 *   onClose   — optional, called when a link is clicked in drawer mode
 */

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useLanguage } from '../lib/LanguageContext';
import { usePreview } from '../lib/PreviewContext';
import LogoutButton from './LogoutButton';
import LanguageSwitcher from './LanguageSwitcher';
import PreviewAsSelector from './PreviewAsSelector';
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
  { key: 'nav.more',        href: '/admin/more',       icon: '⋮', roles: ['admin', 'manager'] },
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
    if (payload.display_name && typeof payload.display_name === 'string')
      return payload.display_name.split(' ')[0];
    if (payload.full_name && typeof payload.full_name === 'string')
      return payload.full_name.split(' ')[0];
    return ROLE_DISPLAY[payload.role] || 'there';
  } catch { return ROLE_DISPLAY[role] || 'there'; }
}

interface SidebarProps {
  collapsed?: boolean;
  onClose?: () => void;
  /** 'fixed' (default) = normal fixed sidebar; 'drawer' = relative, for use inside a slide-in wrapper */
  mode?: 'fixed' | 'drawer';
}

export default function Sidebar({ collapsed = false, onClose, mode = 'fixed' }: SidebarProps) {
  const { t } = useLanguage();
  const pathname = usePathname();
  const { getEffectiveRole } = usePreview();

  const role = getEffectiveRole(getUserRole()) as Role;
  const name = getGreetingName(role);
  const hour = typeof window !== 'undefined' ? new Date().getHours() : 9;
  const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const isActive = (href: string) => {
    if (href === '/dashboard') return pathname === '/dashboard' || pathname === '/';
    return pathname?.startsWith(href);
  };

  const sidebarWidth = collapsed ? '64px' : 'var(--sidebar-width, 220px)';

  return (
    <>
      {/* Tooltip styles — only used in collapsed mode */}
      {collapsed && (
        <style>{`
          .rail-link { position: relative; }
          .rail-link .rail-tooltip {
            position: absolute;
            left: 100%;
            top: 50%;
            transform: translateY(-50%);
            margin-left: 8px;
            padding: 6px 12px;
            background: var(--color-midnight, #171A1F);
            color: var(--color-white, #F8F6F2);
            font-size: 12px;
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            border-radius: 6px;
            white-space: nowrap;
            pointer-events: none;
            opacity: 0;
            transition: opacity 150ms;
            z-index: 100;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
          }
          .rail-link:hover .rail-tooltip { opacity: 1; }
        `}</style>
      )}

      <nav style={{
        width: sidebarWidth,
        minWidth: sidebarWidth,
        background: 'var(--color-surface)',
        borderRight: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        padding: collapsed ? 'var(--space-4) 0' : 'var(--space-6) 0',
        ...(mode === 'drawer'
          ? { position: 'relative' as const, height: '100%' }
          : { position: 'fixed' as const, top: 0, left: 0, height: '100vh', zIndex: 40 }
        ),
        transition: 'width 200ms ease',
        overflowX: 'hidden',
        overflowY: 'auto',
      }}>
        {/* Logo / Brand */}
        {collapsed ? (
          /* Collapsed: single monogram */
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 48,
            marginBottom: 'var(--space-4)',
            flexShrink: 0,
          }}>
            <img
              src="/domaniqo-monogram-midnight.svg"
              alt="Domaniqo"
              width={34}
              height={34}
              style={{ display: 'block' }}
            />
          </div>
        ) : (
          /* Expanded: full logo + greeting */
          <div style={{ padding: '0 var(--space-6)', marginBottom: 'var(--space-8)', flexShrink: 0 }}>
            <div style={{
              position: 'relative',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              marginLeft: '-4px',
              marginBottom: 16,
              fontSize: 'var(--text-base)',
              fontWeight: 700,
              fontFamily: "'Manrope', sans-serif",
              color: 'var(--color-midnight)',
              letterSpacing: '-0.01em',
            }}>
              <img
                src="/domaniqo-monogram-midnight.svg"
                alt=""
                width={22}
                height={22}
                style={{ display: 'block', flexShrink: 0 }}
              />
              Domaniqo
              <div style={{
                position: 'absolute',
                right: 0,
                top: '100%',
                marginTop: 2,
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-faint)',
                fontWeight: 400,
                letterSpacing: 'normal',
                whiteSpace: 'nowrap',
              }}>
                Operations Platform
              </div>
            </div>
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
        )}

        {/* Nav links */}
        {NAV_ITEMS.filter(item => item.roles.includes(role)).map(({ key, href, icon }) => {
          const active = isActive(href);
          const label = t(key);

          if (collapsed) {
            return (
              <Link
                key={href}
                href={href}
                className="rail-link"
                onClick={onClose}
                title={label}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: 44,
                  fontSize: '1.15em',
                  color: active ? 'var(--color-primary)' : 'var(--color-text-dim)',
                  background: active ? 'rgba(59,130,246,0.06)' : 'transparent',
                  borderRight: active ? '2px solid var(--color-primary)' : '2px solid transparent',
                  transition: 'all var(--transition-fast)',
                  textDecoration: 'none',
                  opacity: active ? 1 : 0.7,
                }}
              >
                <span>{icon}</span>
                <span className="rail-tooltip">{label}</span>
              </Link>
            );
          }

          return (
            <Link key={href} href={href} onClick={onClose} style={{
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
              {label}
            </Link>
          );
        })}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Bottom section */}
        {collapsed ? (
          /* Collapsed bottom: just logout icon */
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 4,
            paddingBottom: 'var(--space-2)',
          }}>
            <div style={{
              height: 1,
              width: '80%',
              background: 'var(--color-border)',
              margin: '4px 0',
            }} />
            <button
              id="logout-btn-rail"
              onClick={async () => {
                const { api } = await import('../lib/api');
                await api.logout();
              }}
              className="rail-link"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 44,
                height: 44,
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontSize: '1.15em',
                color: 'var(--color-text-dim)',
                borderRadius: 8,
                transition: 'color 0.15s',
                position: 'relative',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-error, #ef4444)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-text-dim)'; }}
              title="Logout"
            >
              ↩
              <span className="rail-tooltip">Logout</span>
            </button>
          </div>
        ) : (
          /* Expanded bottom: full controls */
          <>
            <PreviewAsSelector />
            <LanguageSwitcher />
            <div style={{ height: 1, background: 'var(--color-border)', margin: '8px 0' }} />
            <LogoutButton />
          </>
        )}
      </nav>
    </>
  );
}
