'use client';

/**
 * Phase 874 — SignedInShell
 *
 * Canonical minimal header for all signed-in public surfaces:
 *   /welcome, /my-properties, /profile, /no-access
 *
 * Renders: D monogram + wordmark | nav link(s) | Sign out
 * Sign out: clears ihouse_token cookie + Supabase session → home.
 *
 * Usage:
 *   <SignedInShell />          — renders the fixed header
 *   <SignedInShell back="/welcome" backLabel="Home" />  — with back link
 *
 * Pages must add paddingTop: 'var(--signed-in-shell-height, 56px)'
 * to their top-level container so content clears the fixed bar.
 */

import { useState } from 'react';
import Link from 'next/link';
import DMonogram from './DMonogram';
import { supabase } from '@/lib/supabaseClient';
import { performClientLogout } from '@/lib/api';

interface Props {
    /** Optional back navigation shown left of wordmark */
    back?: string;
    backLabel?: string;
}

export default function SignedInShell({ back, backLabel = '← Back' }: Props) {
    const [signingOut, setSigningOut] = useState(false);

    const handleSignOut = async () => {
        if (signingOut) return;
        setSigningOut(true);
        try {
            await supabase?.auth.signOut();
        } catch { /* ignore */ }
        performClientLogout('/');
    };

    return (
        <nav
            id="signed-in-shell"
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                zIndex: 90,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 24px',
                height: 'var(--signed-in-shell-height, 52px)',
                background: 'rgba(13,15,20,0.92)',
                backdropFilter: 'blur(12px) saturate(1.4)',
                borderBottom: '1px solid rgba(234,229,222,0.05)',
            }}
        >
            {/* Left: back link or logo */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                {back ? (
                    <Link
                        href={back}
                        style={{
                            fontSize: 13,
                            color: 'rgba(234,229,222,0.4)',
                            textDecoration: 'none',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            transition: 'color 0.15s',
                        }}
                    >
                        {backLabel}
                    </Link>
                ) : null}
                <Link
                    href="/welcome"
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        textDecoration: 'none',
                    }}
                >
                    <DMonogram size={20} color="var(--color-stone)" strokeWidth={1.6} />
                    <span style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 15,
                        color: 'var(--color-stone)',
                        letterSpacing: '-0.02em',
                    }}>
                        Domaniqo
                    </span>
                </Link>
            </div>

            {/* Right: sign out */}
            <button
                onClick={handleSignOut}
                disabled={signingOut}
                style={{
                    background: 'none',
                    border: 'none',
                    color: 'rgba(234,229,222,0.35)',
                    fontSize: 13,
                    cursor: signingOut ? 'wait' : 'pointer',
                    fontFamily: 'var(--font-sans, inherit)',
                    padding: '4px 0',
                    transition: 'color 0.2s',
                    opacity: signingOut ? 0.5 : 1,
                }}
            >
                {signingOut ? 'Signing out…' : 'Sign out'}
            </button>
        </nav>
    );
}

/** CSS var for pages to use as top padding. Value matches nav height. */
export const SHELL_TOP_PADDING = '60px'; // 52px nav + 8px breathe
