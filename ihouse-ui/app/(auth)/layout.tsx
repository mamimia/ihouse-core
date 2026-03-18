/**
 * (auth) Layout — Phase 838/839
 *
 * Auth-specific layout for login, register, password reset.
 * Does NOT include PublicNav (no "Get Started", no marketing links).
 * No sidebar, no footer.
 *
 * Navigation rule:
 *   Auth pages = bare shell. Only AuthCard internals provide branding.
 *   Language switcher is the only global nav element on auth pages.
 *   PublicNav belongs to the marketing site only.
 */

import CompactLangSwitcher from '../../components/CompactLangSwitcher';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* Minimal auth nav — only language control, no marketing CTA */}
      <div style={{ position: 'fixed', top: 12, right: 14, zIndex: 999 }}>
        <CompactLangSwitcher theme="dark" />
      </div>
      {children}
    </>
  );
}
