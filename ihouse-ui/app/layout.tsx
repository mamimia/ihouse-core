import type { Metadata } from 'next';
import './globals.css';
import { LanguageProvider } from '../lib/LanguageContext';
import ThemeProvider from '../components/ThemeProvider';

export const metadata: Metadata = {
  title: 'Domaniqo',
  description: 'The deep operations platform for modern hospitality. Calm command for modern stays.',
};

/**
 * Phase 377 — Root Layout (shared shell)
 *
 * Provides: HTML shell, fonts, ThemeProvider, and LanguageProvider.
 * No sidebar, no auth wrapper — those live in route-group layouts:
 *   (public)/layout.tsx  — public pages (landing, login, early-access)
 *   (app)/layout.tsx     — protected pages (dashboard, bookings, admin, etc.)
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Manrope:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap"
        />
      </head>
      <body style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
        <ThemeProvider>
          <LanguageProvider>
            {children}
          </LanguageProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

