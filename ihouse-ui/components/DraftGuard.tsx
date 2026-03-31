'use client';

/**
 * DraftGuard — Phase 1033 freeze protection.
 *
 * Blocks direct URL access to 1033 draft pages for non-admin users.
 * Redirects to /manager (Hub) immediately on mount if role !== 'admin'.
 *
 * This is a TEMPORARY protection step only.
 * It is NOT the final access model for OM Baseline pages.
 * It must be replaced before any 1033 page goes live for real users.
 *
 * Allowed: admin
 * Blocked (redirected to /manager): manager, owner, worker, and any other role
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getTabToken } from '../lib/tokenStore';

function getJwtRole(): string {
    if (typeof window === 'undefined') return '';
    try {
        const token = getTabToken();
        if (!token) return '';
        const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
        // Honour preview role if set (matches Sidebar behaviour)
        const preview = sessionStorage.getItem('ihouse_preview_role');
        return preview || (payload.role as string) || '';
    } catch {
        return '';
    }
}

export default function DraftGuard({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const [allowed, setAllowed] = useState(false);

    useEffect(() => {
        const role = getJwtRole();
        if (role === 'admin') {
            setAllowed(true);
        } else {
            // Non-admin: redirect immediately back to the manager Hub
            router.replace('/manager');
        }
    }, [router]);

    if (!allowed) {
        // Render nothing while the redirect resolves — no flash of content
        return null;
    }

    return <>{children}</>;
}
