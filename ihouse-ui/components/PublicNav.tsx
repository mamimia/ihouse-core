'use client';

/**
 * Phase 379 — PublicNav
 *
 * Fixed navigation for public pages: D monogram + wordmark, anchor links, CTA.
 * Mobile: icon-only + CTA. RTL-aware.
 * Backdrop blur, graceful scroll behavior.
 */

import { useState, useEffect } from 'react';
import Link from 'next/link';
import DMonogram from './DMonogram';

const NAV_LINKS = [
    { label: 'Platform', href: '/platform' },
    { label: 'Channels', href: '/channels' },
    { label: 'Pricing', href: '/pricing' },
    { label: 'About', href: '/about' },
];

export default function PublicNav() {
    const [scrolled, setScrolled] = useState(false);

    useEffect(() => {
        const handler = () => setScrolled(window.scrollY > 40);
        window.addEventListener('scroll', handler, { passive: true });
        return () => window.removeEventListener('scroll', handler);
    }, []);

    return (
        <nav
            id="public-nav"
            style={{
                position: 'fixed',
                top: 0,
                insetInline: 0,
                zIndex: 90,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 var(--space-6)',
                height: 'var(--header-height)',
                background: scrolled
                    ? 'rgba(23,26,31,0.85)'
                    : 'transparent',
                backdropFilter: scrolled ? 'blur(12px) saturate(1.4)' : 'none',
                transition: 'background var(--transition-base), backdrop-filter var(--transition-base)',
                borderBottom: scrolled ? '1px solid rgba(234,229,222,0.06)' : '1px solid transparent',
            }}
        >
            {/* Logo */}
            <Link
                href="/"
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-3)',
                    textDecoration: 'none',
                }}
            >
                <DMonogram size={26} color="var(--color-stone)" strokeWidth={1.6} />
                <span style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'var(--text-lg)',
                    color: 'var(--color-stone)',
                    letterSpacing: '-0.02em',
                }}>
                    Domaniqo
                </span>
            </Link>

            {/* Links — hidden on mobile */}
            <div className="hide-mobile" style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-8)',
            }}>
                {NAV_LINKS.map(link => (
                    <Link
                        key={link.href}
                        href={link.href}
                        style={{
                            fontSize: 'var(--text-sm)',
                            color: 'rgba(234,229,222,0.55)',
                            textDecoration: 'none',
                            letterSpacing: '0.03em',
                            fontWeight: 500,
                            transition: 'color var(--transition-fast)',
                        }}
                    >
                        {link.label}
                    </Link>
                ))}
            </div>

            {/* CTA */}
            <Link
                href="/onboard/connect"
                id="nav-cta-get-started"
                style={{
                    background: 'var(--color-moss)',
                    color: 'var(--color-white)',
                    padding: '8px 20px',
                    borderRadius: 'var(--radius-full)',
                    fontSize: 'var(--text-sm)',
                    fontWeight: 600,
                    fontFamily: 'var(--font-brand)',
                    textDecoration: 'none',
                    transition: 'opacity var(--transition-fast), box-shadow var(--transition-fast)',
                    boxShadow: 'var(--shadow-glow-moss)',
                    minHeight: 36,
                    display: 'inline-flex',
                    alignItems: 'center',
                }}
            >
                Get Started
            </Link>
        </nav>
    );
}
