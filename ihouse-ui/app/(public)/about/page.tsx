'use client';

/**
 * About — Domaniqo Marketing Page
 *
 * Origin story, philosophy, principles, and contact.
 * Inspired by Your.Rentals /about-your-rentals/ but told through
 * Domaniqo's calm, architectural narrative.
 */

import Link from 'next/link';
import DMonogram from '../../../components/DMonogram';

/* ── Section wrapper ── */
function Section({
    id, children, style = {},
}: {
    id: string;
    children: React.ReactNode;
    style?: React.CSSProperties;
}) {
    return (
        <section
            id={id}
            style={{
                padding: 'var(--space-16) var(--space-6)',
                maxWidth: 960,
                marginInline: 'auto',
                ...style,
            }}
        >
            {children}
        </section>
    );
}

/* ── Section label ── */
function SectionLabel({ children }: { children: React.ReactNode }) {
    return (
        <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-copper)',
            textTransform: 'uppercase',
            letterSpacing: '0.12em',
            marginBottom: 'var(--space-3)',
        }}>
            {children}
        </div>
    );
}

/* ── Principle card ── */
function PrincipleCard({ title, desc }: { title: string; desc: string }) {
    return (
        <div style={{
            background: 'var(--color-elevated)',
            border: '1px solid rgba(234,229,222,0.06)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-6)',
        }}>
            <div style={{
                fontFamily: 'var(--font-brand)',
                fontSize: 'var(--text-base)',
                fontWeight: 700,
                color: 'var(--color-stone)',
                marginBottom: 'var(--space-2)',
            }}>
                {title}
            </div>
            <div style={{
                fontSize: 'var(--text-sm)',
                color: 'rgba(234,229,222,0.4)',
                lineHeight: 1.7,
            }}>
                {desc}
            </div>
        </div>
    );
}

/* ── Timeline item ── */
function TimelineItem({ year, title, desc }: { year: string; title: string; desc: string }) {
    return (
        <div style={{
            display: 'flex',
            gap: 'var(--space-5)',
            alignItems: 'flex-start',
            paddingBlock: 'var(--space-4)',
            borderBottom: '1px solid rgba(234,229,222,0.04)',
        }}>
            <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-copper)',
                opacity: 0.7,
                minWidth: 48,
                flexShrink: 0,
                paddingTop: 2,
            }}>
                {year}
            </div>
            <div>
                <div style={{
                    fontFamily: 'var(--font-brand)',
                    fontSize: 'var(--text-sm)',
                    fontWeight: 700,
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-1)',
                }}>
                    {title}
                </div>
                <div style={{
                    fontSize: 'var(--text-sm)',
                    color: 'rgba(234,229,222,0.35)',
                    lineHeight: 1.6,
                }}>
                    {desc}
                </div>
            </div>
        </div>
    );
}

/* ── Main page ── */
export default function AboutPage() {
    return (
        <div
            className="grain-overlay"
            style={{
                background: 'var(--color-midnight)',
                color: 'var(--color-stone)',
                minHeight: '100vh',
            }}
        >
            {/* ═══ HERO ═══ */}
            <section
                id="about-hero"
                style={{
                    minHeight: '70vh',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center',
                    padding: 'calc(var(--header-height) + var(--space-16)) var(--space-6) var(--space-16)',
                }}
            >
                <div style={{
                    marginBottom: 'var(--space-6)',
                    opacity: 0,
                    animation: 'fadeUp 800ms 200ms ease forwards',
                }}>
                    <DMonogram size={56} color="var(--color-copper)" strokeWidth={1.2} />
                </div>

                <h1 style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-3xl), 6vw, var(--text-4xl))',
                    fontWeight: 400,
                    fontStyle: 'italic',
                    color: 'var(--color-stone)',
                    lineHeight: 1.15,
                    maxWidth: 600,
                    marginBottom: 'var(--space-5)',
                    opacity: 0,
                    animation: 'fadeUp 800ms 400ms ease forwards',
                }}>
                    Built by operators. For operators.
                </h1>

                <p style={{
                    fontSize: 'var(--text-lg)',
                    color: 'rgba(234,229,222,0.45)',
                    maxWidth: 560,
                    lineHeight: 1.6,
                    opacity: 0,
                    animation: 'fadeUp 800ms 600ms ease forwards',
                }}>
                    Domaniqo was born from the realization that hospitality 
                    operations deserved a system as thoughtful as the experience 
                    they deliver to guests.
                </p>
            </section>

            {/* ═══ STORY ═══ */}
            <Section id="story" style={{ textAlign: 'center' }}>
                <div style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-2xl), 4vw, var(--text-3xl))',
                    fontWeight: 400,
                    color: 'var(--color-stone)',
                    lineHeight: 1.3,
                    maxWidth: 640,
                    marginInline: 'auto',
                    marginBottom: 'var(--space-6)',
                }}>
                    &ldquo;You cannot control what you cannot see.
                    <br />
                    You cannot trust what you cannot trace.&rdquo;
                </div>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.4)',
                    maxWidth: 600,
                    marginInline: 'auto',
                    lineHeight: 1.7,
                    marginBottom: 'var(--space-6)',
                }}>
                    Booking tools exist. Channel managers exist. Cleaning apps exist. 
                    But the layer underneath — the one that holds the truth about 
                    what is actually happening across your properties, your teams, 
                    your finances, and your guests — that layer was always missing.
                </p>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.35)',
                    maxWidth: 600,
                    marginInline: 'auto',
                    lineHeight: 1.7,
                }}>
                    Operators filled the gap with spreadsheets, group chats, and hope.
                    Domaniqo was built to close that gap. Not another booking tool — 
                    the operating layer beneath all of them. Where canonical truth is built, 
                    anomalies surface early, and every number is honest about its own certainty.
                </p>
            </Section>

            {/* ═══ JOURNEY ═══ */}
            <Section id="journey">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>Journey</SectionLabel>
                    <h2 style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                        fontWeight: 400,
                        color: 'var(--color-stone)',
                    }}>
                        From first line to full platform.
                    </h2>
                </div>

                <div style={{ maxWidth: 640, marginInline: 'auto' }}>
                    <TimelineItem
                        year="2025"
                        title="The idea takes shape"
                        desc="After years of managing villa operations with disconnected tools, the frustration crystallised into a mission: build the operating layer hospitality deserves."
                    />
                    <TimelineItem
                        year="2025"
                        title="Architecture defined"
                        desc="Event-sourced booking core, multi-OTA normalizer, SLA engine, multi-tenant permissions — the technical foundations designed for depth, not speed."
                    />
                    <TimelineItem
                        year="2026"
                        title="374+ development phases completed"
                        desc="Systematic, contract-tested development across 14 OTA adapters, 7 product modules, 5 notification channels, and 3 languages."
                    />
                    <TimelineItem
                        year="2026"
                        title="Early access begins"
                        desc="Selected operators invited to work with the platform. Real-world validation. Real-world feedback. Building toward general availability."
                    />
                </div>
            </Section>

            {/* ═══ PRINCIPLES ═══ */}
            <Section id="principles">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>Every decision follows six principles</SectionLabel>
                    <h2 style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                        fontWeight: 400,
                        color: 'var(--color-stone)',
                    }}>
                        Built with intention.
                    </h2>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                    gap: 'var(--space-4)',
                }}>
                    <PrincipleCard
                        title="Calm"
                        desc="Never frantic. Never noisy. Operational clarity, not chaos. The interface earns trust through restraint."
                    />
                    <PrincipleCard
                        title="Precision"
                        desc="Everything deliberate. Every element placed with intent. No feature exists without a clear operational purpose."
                    />
                    <PrincipleCard
                        title="Hospitality"
                        desc="Warmth and human relevance. Not cold enterprise machinery. The platform serves people who serve guests."
                    />
                    <PrincipleCard
                        title="Command"
                        desc="An operating layer, not a helper app. Quiet authority over every property, every channel, every number."
                    />
                    <PrincipleCard
                        title="Elegance"
                        desc="Refined, controlled, timeless. No shortcuts in craft. Beauty in the way data is presented and decisions are supported."
                    />
                    <PrincipleCard
                        title="Honesty"
                        desc="Data states what it knows — and what it doesn't. Confidence levels on every number. No false certainty."
                    />
                </div>
            </Section>

            {/* ═══ CONTACT ═══ */}
            <Section id="contact" style={{ textAlign: 'center' }}>
                <SectionLabel>Get in touch</SectionLabel>
                <h2 style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                    fontWeight: 400,
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-6)',
                }}>
                    We&apos;d love to hear from you.
                </h2>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.4)',
                    maxWidth: 480,
                    marginInline: 'auto',
                    lineHeight: 1.7,
                    marginBottom: 'var(--space-8)',
                }}>
                    Whether you&apos;re managing five properties or fifty, if you value 
                    operational clarity and calm command — we want to talk.
                </p>

                <div style={{ display: 'flex', gap: 'var(--space-4)', justifyContent: 'center', flexWrap: 'wrap' }}>
                    <Link
                        href="/early-access"
                        id="about-cta"
                        style={{
                            background: 'var(--color-moss)',
                            color: 'var(--color-white)',
                            padding: '14px 32px',
                            borderRadius: 'var(--radius-full)',
                            fontSize: 'var(--text-base)',
                            fontWeight: 600,
                            fontFamily: 'var(--font-brand)',
                            textDecoration: 'none',
                            boxShadow: 'var(--shadow-glow-moss)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            minHeight: 48,
                        }}
                    >
                        Request Early Access →
                    </Link>
                    <a
                        href="mailto:info@domaniqo.com"
                        style={{
                            border: '1px solid rgba(234,229,222,0.12)',
                            color: 'var(--color-stone)',
                            padding: '14px 32px',
                            borderRadius: 'var(--radius-full)',
                            fontSize: 'var(--text-base)',
                            fontWeight: 500,
                            textDecoration: 'none',
                            display: 'inline-flex',
                            alignItems: 'center',
                            minHeight: 48,
                        }}
                    >
                        info@domaniqo.com
                    </a>
                </div>
            </Section>
        </div>
    );
}
