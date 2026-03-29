'use client';

/**
 * Phase 999 — Admin Early Checkout Page
 * Route: /admin/bookings/[id]/early-checkout
 *
 * Full early checkout management surface for admin and authorized managers.
 * Hosts the EarlyCheckoutPanel component with booking context header.
 */

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { EarlyCheckoutPanel } from '@/components/EarlyCheckoutPanel';

export default function AdminEarlyCheckoutPage() {
    const params = useParams();
    const bookingId = params?.id as string;

    return (
        <div style={{ maxWidth: 680, paddingBottom: 'var(--space-12)' }}>
            {/* Breadcrumb */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-6)', fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                <Link href="/bookings" style={{ color: 'var(--color-text-dim)', textDecoration: 'none' }}>Bookings</Link>
                <span>›</span>
                <Link href={`/bookings/${bookingId}`} style={{ color: 'var(--color-text-dim)', textDecoration: 'none', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>
                    {bookingId?.slice(0, 16)}…
                </Link>
                <span>›</span>
                <span>Early Check-out</span>
            </div>

            {/* Panel */}
            <EarlyCheckoutPanel bookingId={bookingId} embedded={false} />
        </div>
    );
}
