'use client';

/**
 * /admin/bookings — Booking area landing page.
 *
 * This route exists primarily so that breadcrumbs from
 * /admin/bookings/intake don't produce a 404 when the user
 * clicks "Bookings" in the breadcrumb trail.
 *
 * Renders quick links to the main booking surfaces:
 * - Bookings list (/bookings)
 * - Booking Intake (/admin/bookings/intake)
 */

import { useRouter } from 'next/navigation';

export default function AdminBookingsPage() {
  const router = useRouter();

  const cardStyle: React.CSSProperties = {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-lg)',
    padding: 'var(--space-5)',
    cursor: 'pointer',
    transition: 'border-color 0.2s, transform 0.15s',
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-4)',
  };

  return (
    <div style={{ maxWidth: 700, margin: '0 auto' }}>
      <div style={{ marginBottom: 'var(--space-5)' }}>
        <p style={{
          fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)',
          textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>
          Booking Management
        </p>
        <h1 style={{
          fontSize: 'var(--text-2xl)', fontWeight: 700,
          color: 'var(--color-text)', letterSpacing: '-0.03em',
        }}>
          Bookings
        </h1>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        {/* View All Bookings */}
        <div
          onClick={() => router.push('/bookings')}
          style={cardStyle}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--color-primary)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.transform = 'none'; }}
        >
          <div style={{ fontSize: 'var(--text-2xl)' }}>📋</div>
          <div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)' }}>View All Bookings</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Browse, search, and manage existing bookings</div>
          </div>
          <span style={{ marginLeft: 'auto', color: 'var(--color-text-faint)', fontSize: 'var(--text-lg)' }}>→</span>
        </div>

        {/* Add New Booking */}
        <div
          onClick={() => router.push('/admin/bookings/intake')}
          style={cardStyle}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--color-primary)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.transform = 'none'; }}
        >
          <div style={{ fontSize: 'var(--text-2xl)' }}>✍️</div>
          <div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)' }}>Add New Booking</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>Manual entry, iCal import, or CSV upload</div>
          </div>
          <span style={{ marginLeft: 'auto', color: 'var(--color-text-faint)', fontSize: 'var(--text-lg)' }}>→</span>
        </div>
      </div>
    </div>
  );
}
