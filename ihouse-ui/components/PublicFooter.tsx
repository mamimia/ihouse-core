/**
 * Phase 379 — PublicFooter
 *
 * Minimal footer for public pages.
 * D monogram + copyright + tagline + email.
 */

import DMonogram from './DMonogram';

export default function PublicFooter() {
    const year = new Date().getFullYear();

    return (
        <footer
            id="public-footer"
            style={{
                background: 'var(--color-midnight)',
                borderTop: '1px solid rgba(234,229,222,0.06)',
                padding: 'var(--space-10) var(--space-6)',
                textAlign: 'center',
            }}
        >
            <DMonogram size={28} color="rgba(234,229,222,0.15)" strokeWidth={1.4} />

            <div style={{
                fontFamily: 'var(--font-display)',
                fontSize: 'var(--text-lg)',
                color: 'rgba(234,229,222,0.25)',
                letterSpacing: '-0.02em',
                marginTop: 'var(--space-3)',
                marginBottom: 'var(--space-2)',
            }}>
                Domaniqo
            </div>

            <div style={{
                fontSize: 'var(--text-xs)',
                color: 'rgba(234,229,222,0.15)',
                marginBottom: 'var(--space-3)',
            }}>
                The deep operations platform for modern hospitality.
            </div>

            <a
                href="mailto:info@domaniqo.com"
                style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-copper)',
                    opacity: 0.5,
                    textDecoration: 'none',
                    transition: 'opacity var(--transition-fast)',
                }}
                onMouseOver={e => (e.currentTarget.style.opacity = '0.8')}
                onMouseOut={e => (e.currentTarget.style.opacity = '0.5')}
            >
                info@domaniqo.com
            </a>

            <div style={{
                fontSize: 'var(--text-xs)',
                color: 'rgba(234,229,222,0.1)',
                marginTop: 'var(--space-6)',
            }}>
                © {year} Domaniqo. All rights reserved.
            </div>
        </footer>
    );
}
