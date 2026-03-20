'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

export function PreviewPageContent() {
    const searchParams = useSearchParams();
    const [msg, setMsg] = useState('Initializing simulated session...');

    useEffect(() => {
        const role = searchParams?.get('role');
        if (role) {
            sessionStorage.setItem('ihouse_preview_role', role);
            
            // Redirect based on role
            setTimeout(() => {
                if (role === 'owner') window.location.href = '/owner';
                else if (role === 'manager') window.location.href = '/ops';
                else if (role === 'checkin_staff') window.location.href = '/ops/checkin';
                else if (['worker', 'cleaner', 'maintenance'].includes(role)) window.location.href = '/worker';
                else window.location.href = '/dashboard';
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
                <div style={{ fontSize: 32, marginBottom: 16 }}>👀</div>
                <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>{msg}</div>
                <p style={{ fontSize: 14, color: 'var(--color-text-dim)' }}>
                    Generating isolated session token...
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
