'use client';

/**
 * Phase 864 — Act As Landing Page (New Tab)
 *
 * Mirrors the Preview As landing (/preview/page.tsx) interaction model:
 * 1. Admin tab calls /auth/act-as/start and gets a scoped JWT
 * 2. Admin tab opens window.open('/act-as?token=TOKEN&role=ROLE', '_blank')
 * 3. This page receives the token, stores it in localStorage, and redirects
 *    to the role-appropriate surface.
 *
 * The admin tab is NEVER modified — the act_as JWT only lives in this new tab.
 */

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { setActAsTabToken } from '../../../lib/tokenStore';

/** Canonical route map — must match admin-preview-and-act-as.md, roleRoute.ts, and preview/page.tsx */
const ROLE_ROUTES: Record<string, string> = {
    manager:          '/manager',
    owner:            '/owner',
    cleaner:          '/ops/cleaner',
    checkin:          '/ops/checkin',
    checkout:         '/ops/checkout',
    checkin_checkout: '/ops/checkin-checkout',
    maintenance:      '/ops/maintenance',
};

function ActAsLandingContent() {
    const searchParams = useSearchParams();
    const [msg, setMsg] = useState('Entering Act As session...');

    useEffect(() => {
        const token = searchParams?.get('token');
        const role  = searchParams?.get('role');

        if (!token || !role) {
            setMsg('Missing token or role. Please start Act As from the admin sidebar.');
            return;
        }

        // Store the act_as token in sessionStorage ONLY — tab-scoped, never touches
        // the admin's localStorage token. This is the root fix for parallel tab isolation.
        try {
            setActAsTabToken(token);
            sessionStorage.setItem('ihouse_act_as_original_token', '__new_tab__');
        } catch (e) {
            setMsg('Failed to set session. Check browser storage permissions.');
            return;
        }

        const target = ROLE_ROUTES[role] ?? '/dashboard';
        setMsg(`Opening ${role.replace('_', ' ')} interface...`);

        // Short delay for visual feedback, then redirect
        setTimeout(() => {
            window.location.href = target;
        }, 600);
    }, [searchParams]);

    return (
        <div style={{
            minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--color-surface, #1e2329)', color: 'var(--color-text)',
        }}>
            <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 32, marginBottom: 16 }}>🔴</div>
                <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>{msg}</div>
                <p style={{ fontSize: 14, color: 'var(--color-text-dim)' }}>
                    QA / Testing — Actions in this tab will be recorded with admin attribution
                </p>
            </div>
        </div>
    );
}

export default function ActAsPage() {
    return (
        <Suspense fallback={<div style={{ minHeight: '100vh', background: 'var(--color-surface, #1e2329)' }} />}>
            <ActAsLandingContent />
        </Suspense>
    );
}
