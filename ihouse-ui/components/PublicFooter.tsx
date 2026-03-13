/**
 * PublicFooter — Updated with new page links
 *
 * Minimal footer with organized link columns for all public pages.
 * D monogram + copyright + tagline + email.
 */

import Link from 'next/link';
import DMonogram from './DMonogram';

const FOOTER_LINKS = [
    {
        title: 'Product',
        links: [
            { label: 'Platform', href: '/platform' },
            { label: 'Channels', href: '/channels' },
            { label: 'Inbox', href: '/inbox' },
            { label: 'Reviews', href: '/reviews' },
        ],
    },
    {
        title: 'Company',
        links: [
            { label: 'About', href: '/about' },
            { label: 'Pricing', href: '/pricing' },
            { label: 'Early Access', href: '/early-access' },
        ],
    },
];

export default function PublicFooter() {
    const year = new Date().getFullYear();

    return (
        <footer
            id="public-footer"
            style={{
                background: 'var(--color-midnight)',
                borderTop: '1px solid rgba(234,229,222,0.06)',
                padding: 'var(--space-10) var(--space-6)',
            }}
        >
            <div style={{
                maxWidth: 960,
                marginInline: 'auto',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: 'var(--space-8)',
                marginBottom: 'var(--space-10)',
            }}>
                {/* Brand column */}
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
                        <DMonogram size={22} color="rgba(234,229,222,0.25)" strokeWidth={1.4} />
                        <span style={{
                            fontFamily: 'var(--font-display)',
                            fontSize: 'var(--text-base)',
                            color: 'rgba(234,229,222,0.25)',
                            letterSpacing: '-0.02em',
                        }}>
                            Domaniqo
                        </span>
                    </div>
                    <div style={{
                        fontSize: 'var(--text-xs)',
                        color: 'rgba(234,229,222,0.15)',
                        lineHeight: 1.6,
                        maxWidth: 200,
                    }}>
                        The deep operations platform for modern hospitality.
                    </div>
                </div>

                {/* Link columns */}
                {FOOTER_LINKS.map(col => (
                    <div key={col.title}>
                        <div style={{
                            fontFamily: 'var(--font-brand)',
                            fontSize: 'var(--text-xs)',
                            fontWeight: 700,
                            color: 'rgba(234,229,222,0.35)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.08em',
                            marginBottom: 'var(--space-4)',
                        }}>
                            {col.title}
                        </div>
                        {col.links.map(link => (
                            <Link
                                key={link.href}
                                href={link.href}
                                style={{
                                    display: 'block',
                                    fontSize: 'var(--text-sm)',
                                    color: 'rgba(234,229,222,0.3)',
                                    textDecoration: 'none',
                                    paddingBlock: 'var(--space-1)',
                                    transition: 'color var(--transition-fast)',
                                    minHeight: 'auto',
                                    minWidth: 'auto',
                                }}
                            >
                                {link.label}
                            </Link>
                        ))}
                    </div>
                ))}

                {/* Contact column */}
                <div>
                    <div style={{
                        fontFamily: 'var(--font-brand)',
                        fontSize: 'var(--text-xs)',
                        fontWeight: 700,
                        color: 'rgba(234,229,222,0.35)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.08em',
                        marginBottom: 'var(--space-4)',
                    }}>
                        Contact
                    </div>
                    <a
                        href="mailto:info@domaniqo.com"
                        style={{
                            fontSize: 'var(--text-sm)',
                            color: 'var(--color-copper)',
                            opacity: 0.5,
                            textDecoration: 'none',
                            minHeight: 'auto',
                            minWidth: 'auto',
                        }}
                    >
                        info@domaniqo.com
                    </a>
                </div>
            </div>

            {/* Copyright */}
            <div style={{
                textAlign: 'center',
                borderTop: '1px solid rgba(234,229,222,0.04)',
                paddingTop: 'var(--space-6)',
            }}>
                <div style={{
                    fontSize: 'var(--text-xs)',
                    color: 'rgba(234,229,222,0.1)',
                }}>
                    © {year} Domaniqo. All rights reserved.
                </div>
            </div>
        </footer>
    );
}
