'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

// Phase 867 — Preview audit helper (mirrors PreviewContext.tsx)
const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

function emitPreviewAudit(action: 'PREVIEW_OPENED' | 'PREVIEW_CLOSED', previewRole: string, route: string) {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('ihouse_token');
    if (!token) return;
    fetch(`${API_BASE}/admin/preview/audit`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ action, preview_role: previewRole, route }),
    }).catch(() => {});
}

export function PreviewPageContent() {
    const searchParams = useSearchParams();
    const [msg, setMsg] = useState('Entering Preview Mode...');

    useEffect(() => {
        const role = searchParams?.get('role');
        const name = searchParams?.get('name') || '';
        const userId = searchParams?.get('user_id') || '';

        if (role) {
            sessionStorage.setItem('ihouse_preview_role', role);
            // Persist person identity so PreviewBanner shows "Ops Manager · Nana G"
            if (name) {
                sessionStorage.setItem('ihouse_preview_display_name', decodeURIComponent(name));
            } else {
                sessionStorage.removeItem('ihouse_preview_display_name');
            }
            if (userId) {
                sessionStorage.setItem('ihouse_preview_user_id', decodeURIComponent(userId));
            } else {
                sessionStorage.removeItem('ihouse_preview_user_id');
            }

            const PREVIEW_ROUTES: Record<string, string> = {
                manager:          '/manager',
                owner:            '/owner',
                cleaner:          '/ops/cleaner',
                checkin:          '/ops/checkin',
                checkout:         '/ops/checkout',
                checkin_checkout: '/ops/checkin-checkout',
                maintenance:      '/ops/maintenance',
            };
            const target = PREVIEW_ROUTES[role] ?? '/dashboard';
            emitPreviewAudit('PREVIEW_OPENED', role, target);

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
