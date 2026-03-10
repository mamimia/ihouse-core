import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'iHouse Core — Operations',
  description: 'Property management operations dashboard for iHouse Core',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div style={{ display: 'flex', minHeight: '100vh' }}>
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
                fontSize: 'var(--text-lg)',
                fontWeight: 700,
                color: 'var(--color-primary)',
                letterSpacing: '-0.02em',
              }}>
                iHouse<span style={{ color: 'var(--color-text-dim)', fontWeight: 400 }}> Core</span>
              </div>
            </div>
            {/* Nav links */}
            {[
              { label: 'Dashboard', href: '/dashboard', icon: '⬛' },
              { label: 'Tasks', href: '/tasks', icon: '✓' },
              { label: 'Bookings', href: '/bookings', icon: '📅' },
              { label: 'Financial', href: '/financial', icon: '₿' },
              { label: 'Admin', href: '/admin', icon: '⚙' },
            ].map(({ label, href, icon }) => (
              <a key={href} href={href} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                padding: 'var(--space-3) var(--space-6)',
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text-dim)',
                transition: 'all var(--transition-fast)',
              }}>
                <span style={{ fontSize: '1em', opacity: 0.7 }}>{icon}</span>
                {label}
              </a>
            ))}
          </nav>

          {/* Main content area */}
          <main style={{
            marginLeft: 'var(--sidebar-width)',
            flex: 1,
            padding: 'var(--space-8)',
            maxWidth: 'var(--content-max)',
          }}>
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
