import type { Metadata } from 'next';
import './globals.css';
import { LanguageProvider } from '../lib/LanguageContext';
import Sidebar from '../components/Sidebar';
import ClientProviders from '../components/ClientProviders';

export const metadata: Metadata = {
  title: 'Domaniqo — Operations',
  description: 'Property operations platform — calm command for modern hospitality.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link
          rel="preconnect"
          href="https://fonts.googleapis.com"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap"
        />
      </head>
      <body style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
        <LanguageProvider>
          <div style={{ display: 'flex', minHeight: '100vh' }}>
            <Sidebar />

            {/* Main content area */}
            <main style={{
              marginLeft: 'var(--sidebar-width)',
              flex: 1,
              padding: 'var(--space-8)',
              maxWidth: 'var(--content-max)',
            }}>
              <ClientProviders>
                {children}
              </ClientProviders>
            </main>
          </div>
        </LanguageProvider>
      </body>
    </html>
  );
}
