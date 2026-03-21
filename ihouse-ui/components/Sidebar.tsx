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
import ThemeToggle from './ThemeToggle';
import PreviewAsSelector from './PreviewAsSelector';
import { TranslationKey } from '../lib/translations';

type Role = 'admin' | 'manager' | 'owner' | 'worker' | 'cleaner' | 'checkin_staff' | 'maintenance';

const IconDashboard = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>;
const IconTasks = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>;
const IconCleaning = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20"/><path d="M9 20h6"/><path d="M10 6A2 2 0 0 0 8 8v4h8V8a2 2 0 0 0-2-2z"/></svg>;
const IconBookings = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><path d="M8 14h.01"/><path d="M12 14h.01"/><path d="M16 14h.01"/><path d="M8 18h.01"/><path d="M12 18h.01"/><path d="M16 18h.01"/></svg>;
const IconCalendar = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>;
const IconFinancial = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>;
const IconOwner = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>;
const IconManager = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>;
const IconGuests = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>;
const IconProperties = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="m2 9 4-3 4 3v6h-8V9Z"/><path d="M14 9V6l4-3 4 3v15h-8v-6"/><path d="M18 10v2"/><path d="M18 14v2"/></svg>;
const IconStaff = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>;
const IconAdmin = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
const IconMore = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>;

const NAV_ITEMS: { key: TranslationKey; href: string; icon: React.ReactNode; roles: Role[] }[] = [
  { key: 'nav.dashboard',   href: '/dashboard',        icon: IconDashboard, roles: ['admin', 'manager', 'owner', 'worker', 'cleaner', 'checkin_staff', 'maintenance'] },
  { key: 'nav.tasks',       href: '/tasks',            icon: IconTasks, roles: ['admin', 'manager', 'worker', 'cleaner', 'checkin_staff', 'maintenance'] },
  { key: 'nav.cleaning' as TranslationKey, href: '/ops/cleaner', icon: IconCleaning, roles: ['worker', 'cleaner'] },
  { key: 'nav.bookings',    href: '/bookings',         icon: IconBookings, roles: ['admin', 'manager', 'owner'] },
  { key: 'nav.calendar',    href: '/calendar',         icon: IconCalendar, roles: ['admin', 'manager', 'owner'] },
  { key: 'nav.financial',   href: '/financial',        icon: IconFinancial, roles: ['admin', 'manager', 'owner'] },
  { key: 'nav.owner',       href: '/admin/owners',     icon: IconOwner, roles: ['admin'] },
  { key: 'nav.manager',     href: '/manager',          icon: IconManager, roles: ['admin', 'manager'] },
  { key: 'nav.guests',      href: '/guests',           icon: IconGuests, roles: ['admin', 'manager'] },
  { key: 'nav.properties',  href: '/admin/properties', icon: IconProperties, roles: ['admin', 'manager'] },
  { key: 'nav.staff',       href: '/admin/staff',      icon: IconStaff, roles: ['admin', 'manager'] },
  { key: 'nav.admin',       href: '/admin',            icon: IconAdmin, roles: ['admin'] },
  { key: 'nav.more',        href: '/admin/more',       icon: IconMore, roles: ['admin', 'manager'] },
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
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 var(--space-4)', marginTop: 8 }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Theme</span>
              <ThemeToggle />
            </div>
            <LanguageSwitcher />
            <div style={{ height: 1, background: 'var(--color-border)', margin: '8px 0' }} />
            <LogoutButton />
          </>
        )}
      </nav>
    </>
  );
}
