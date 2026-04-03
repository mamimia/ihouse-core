'use client';

/**
 * Phase 844 — Admin Layout
 * Phase 973 audit fix (Sonia/06): Admin-only role guard added.
 *
 * Wraps all /admin/* pages with AdminNav + forces light theme
 * by setting data-theme="light" on <html> element.
 * This overrides @media (prefers-color-scheme: dark) in tokens.css
 * which checks :root:not([data-theme="light"]).
 *
 * Role guard: middleware grants FULL_ACCESS to both 'admin' and 'manager'.
 * This layout adds a secondary guard that redirects non-admin roles
 * away from /admin/* pages. Managers land on /manager (their correct home),
 * not /no-access, since they're trusted operators not unauthorized callers.
 *
 * This closes the gap where a manager could reach /admin/dlq, /admin/audit,
 * /admin/integrations, etc. by direct URL — surfaces that have operational
 * controls (DLQ replay, bulk operations) appropriate only for admins.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AdminNav from '../../../components/AdminNav';

function getTokenRole(): string | null {
    if (typeof window === 'undefined') return null;
    try {
        const token = localStorage.getItem('ihouse_token') || document.cookie
            .split('; ')
            .find(r => r.startsWith('ihouse_token='))
            ?.split('=')[1] || '';
        if (!token) return null;
        const payload = JSON.parse(atob(token.split('.')[1]));
        return (payload.role || '').toLowerCase();
    } catch { return null; }
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
    const router = useRouter();

    useEffect(() => {
        const role = getTokenRole();
        // Only allow role=admin. Managers (and any other FULL_ACCESS role) are redirected
        // to their correct surface. This is a belt-and-suspenders guard — middleware already
        // allows both admin and manager, but admin/* pages have operational controls that
        // are not appropriate for manager-level access.
        if (role !== null && role !== 'admin') {
            router.replace('/manager');
        }
    }, [router]);

    // Phase 957: Disabled structural data-theme override to let ThemeProvider govern everything globally.

    return (
        <div style={{ width: '100%' }}>
            {children}
        </div>
    );
}

