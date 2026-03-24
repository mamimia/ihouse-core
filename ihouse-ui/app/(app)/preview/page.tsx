'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

export function PreviewPageContent() {
    const searchParams = useSearchParams();
    const [msg, setMsg] = useState('Entering Preview Mode...');

    useEffect(() => {
        const role = searchParams?.get('role');
        if (role) {
            sessionStorage.setItem('ihouse_preview_role', role);

            // Canonical route map — must match admin-preview-and-act-as.md
            const PREVIEW_ROUTES: Record<string, string> = {
                manager:          '/dashboard',
                owner:            '/owner',
                cleaner:          '/ops/cleaner',
                checkin:          '/ops/checkin',
                checkout:         '/ops/checkout',
                checkin_checkout: '/ops/checkin',  // TEMPORARY — no combined surface yet. Phase 865 will resolve this. Combined target is NOT identical to check-in.
                maintenance:      '/ops/maintenance',
            };
            const target = PREVIEW_ROUTES[role] ?? '/dashboard';

            setTimeout(() => {
                window.location.href = target;
            }, 600);
        } else {
            setMsg('No role specified.');
        }
    }, [searchParams]);

    return (
        <div style={{
            minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--color-surface, #1e2329)', color: 'var(--color-text)'
        }}>
            <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 32, marginBottom: 16 }}>👁</div>
                <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>{msg}</div>
                <p style={{ fontSize: 14, color: 'var(--color-text-dim)' }}>
                    Read-only view — no actions will be performed
                </p>
            </div>
        </div>
    );
}

import { Suspense } from 'react';
export default function PreviewPage() {
    return (
        <Suspense fallback={<div style={{ minHeight: '100vh', background: 'var(--color-surface, #1e2329)' }} />}>
            <PreviewPageContent />
        </Suspense>
    );
}
