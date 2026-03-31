'use client';

/**
 * DraftGuard — Phase 1033 access control.
 *
 * Allows admin and manager roles (including Preview As manager and Act As manager).
 * Blocks all other roles (owner, worker, cleaner, etc.) with redirect to /manager Hub.
 *
 * Phase 1033 Alerts / Stream / Team are real product surfaces — they must be
 * accessible to the manager role in all session modes (direct, preview, act_as).
 *
 * Allowed: admin, manager (including preview_role=manager, act_as manager JWT)
 * Blocked → /manager: owner, worker, cleaner, and any unrecognised role
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getTabToken } from '../lib/tokenStore';

const ALLOWED_ROLES = new Set(['admin', 'manager']);

function getEffectiveRole(): string {
    if (typeof window === 'undefined') return '';
    try {
        // Preview As role takes priority (set in sessionStorage by PreviewAsSelector)
        const preview = sessionStorage.getItem('ihouse_preview_role');
        if (preview) return preview;

        const token = getTabToken();
        if (!token) return '';
        const payload = JSON.parse(atob(token.split('.')[1] || '{}'));
        return (payload.role as string) || '';
    } catch {
        return '';
    }
}

export default function DraftGuard({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const [allowed, setAllowed] = useState(false);

    useEffect(() => {
        const role = getEffectiveRole();
        if (ALLOWED_ROLES.has(role)) {
            setAllowed(true);
        } else {
            // Not admin or manager — redirect to Hub
            router.replace('/manager');
        }
    }, [router]);

    if (!allowed) {
        return null;
    }

    return <>{children}</>;
}
