'use client';

/**
 * Phase 186 — Logout Button
 *
 * Client component: POSTs /auth/logout (server clears cookie),
 * then clears localStorage + client cookie + redirects to /login.
 */

import { api } from '../lib/api';

interface LogoutButtonProps {
    style?: React.CSSProperties;
}

export default function LogoutButton({ style }: LogoutButtonProps) {
    const handleLogout = async () => {
        await api.logout();   // calls POST /auth/logout + performClientLogout
    };

    return (
        <button
            id="logout-btn"
            onClick={handleLogout}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 24px',
                background: 'transparent',
                border: 'none',
                borderTop: '1px solid var(--color-border)',
                width: '100%',
                textAlign: 'left',
                fontSize: 'var(--text-sm)',
                color: 'var(--color-text-dim)',
                cursor: 'pointer',
                transition: 'color 0.15s',
                ...style,
            }}
            onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-error, #ef4444)';
            }}
            onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-text-dim)';
            }}
        >
            <span style={{ opacity: 0.7 }}>↩</span>
            Logout
        </button>
    );
}
