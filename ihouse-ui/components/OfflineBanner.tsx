/*
 * Phase 367 — Offline Status Banner
 *
 * Shows a non-intrusive banner when the browser loses network connectivity.
 * Auto-hides when connectivity is restored.
 */
'use client';

import { useEffect, useState } from 'react';

export default function OfflineBanner() {
    const [isOffline, setIsOffline] = useState(false);

    useEffect(() => {
        const handleOnline = () => setIsOffline(false);
        const handleOffline = () => setIsOffline(true);

        // Check initial state
        if (typeof navigator !== 'undefined' && !navigator.onLine) {
            setIsOffline(true);
        }

        window.addEventListener('online', handleOnline);
        window.addEventListener('offline', handleOffline);

        return () => {
            window.removeEventListener('online', handleOnline);
            window.removeEventListener('offline', handleOffline);
        };
    }, []);

    if (!isOffline) return null;

    return (
        <div
            id="offline-banner"
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                zIndex: 10000,
                background: 'linear-gradient(90deg, #dc2626, #ef4444)',
                color: '#fff',
                textAlign: 'center',
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: 600,
                fontFamily: "'Inter', system-ui, sans-serif",
                letterSpacing: '0.02em',
                animation: 'slideDown 0.3s ease',
            }}
        >
            <style>{`
                @keyframes slideDown {
                    from { transform: translateY(-100%); }
                    to { transform: translateY(0); }
                }
            `}</style>
            📡 You are offline — some features may be unavailable
        </div>
    );
}
