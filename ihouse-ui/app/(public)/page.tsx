'use client';

/**
 * Phase 379 — Domaniqo Public Landing Page
 *
 * Server-rendered landing page rebuilt inside Next.js.
 * Content inspired by domaniqo-site reference but rebuilt with Domaniqo tokens.
 * Sections: Hero, Origin, Platform, Capabilities, Trust, Status/CTA.
 */

import DMonogram from '../../components/DMonogram';
import Link from 'next/link';

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

/* ── Capability card ── */
function CapCard({ icon, title, desc }: { icon: string; title: string; desc: string }) {
    return (
        <div style={{
            background: 'var(--color-elevated)',
            border: '1px solid rgba(234,229,222,0.06)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-6)',
            transition: 'border-color var(--transition-base)',
        }}>
            <div style={{ fontSize: 28, marginBottom: 'var(--space-3)' }}>{icon}</div>
            <div style={{
                fontFamily: 'var(--font-brand)',
                fontSize: 'var(--text-lg)',
                fontWeight: 700,
                color: 'var(--color-stone)',
                marginBottom: 'var(--space-2)',
            }}>{title}</div>
            <div style={{
                fontSize: 'var(--text-sm)',
                color: 'rgba(234,229,222,0.45)',
                lineHeight: 1.6,
            }}>{desc}</div>
        </div>
    );
}

/* ── Pillar card ── */
function PillarCard({ number, title, desc }: { number: string; title: string; desc: string }) {
    return (
        <div style={{
            borderInlineStart: '2px solid var(--color-copper)',
            paddingInlineStart: 'var(--space-5)',
            paddingBlock: 'var(--space-3)',
        }}>
            <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-copper)',
                opacity: 0.6,
                marginBottom: 'var(--space-1)',
            }}>{number}</div>
            <div style={{
                fontFamily: 'var(--font-brand)',
                fontSize: 'var(--text-base)',
                fontWeight: 700,
                color: 'var(--color-stone)',
                marginBottom: 'var(--space-1)',
            }}>{title}</div>
            <div style={{
                fontSize: 'var(--text-sm)',
                color: 'rgba(234,229,222,0.4)',
                lineHeight: 1.6,
            }}>{desc}</div>
        </div>
    );
}

/* ── Main page ── */
export default function LandingPage() {
    return (
        <div
            className="grain-overlay"
            style={{
                background: 'var(--color-midnight)',
                color: 'var(--color-stone)',
                minHeight: '100vh',
                overflow: 'hidden',
            }}
        >
            {/* ═══ HERO ═══ */}
            <section
                id="hero"
                style={{
                    minHeight: '100vh',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center',
                    padding: 'calc(var(--header-height) + var(--space-10)) var(--space-6) var(--space-16)',
                    position: 'relative',
                }}
            >
                {/* Animated monogram */}
                <div style={{
                    marginBottom: 'var(--space-8)',
                    opacity: 0,
                    animation: 'fadeUp 800ms 200ms ease forwards',
                }}>
                    <DMonogram size={72} color="var(--color-stone)" strokeWidth={1.2} />
                </div>

                <h1 style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-3xl), 6vw, var(--text-4xl))',
                    fontWeight: 400,
                    fontStyle: 'italic',
                    color: 'var(--color-stone)',
                    lineHeight: 1.15,
                    maxWidth: 700,
                    marginBottom: 'var(--space-5)',
                    opacity: 0,
                    animation: 'fadeUp 800ms 400ms ease forwards',
                }}>
                    See every stay.
                </h1>

                <p style={{
                    fontSize: 'var(--text-lg)',
                    color: 'rgba(234,229,222,0.45)',
                    maxWidth: 520,
                    lineHeight: 1.6,
                    marginBottom: 'var(--space-8)',
                    opacity: 0,
                    animation: 'fadeUp 800ms 600ms ease forwards',
                }}>
                    The deep operations platform for modern hospitality.
                    Calm command across booking, tasks, finance, and guest experience.
                </p>

                <div style={{
                    display: 'flex',
                    gap: 'var(--space-4)',
                    opacity: 0,
                    animation: 'fadeUp 800ms 800ms ease forwards',
                    flexWrap: 'wrap',
                    justifyContent: 'center',
                }}>
                    <Link
                        href="/get-started"
                        id="hero-cta-get-started"
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
                            transition: 'opacity var(--transition-fast)',
                            minHeight: 48,
                            display: 'inline-flex',
                            alignItems: 'center',
                        }}
                    >
                        List Your Property
                    </Link>
                    <Link
                        href="/login"
                        style={{
                            border: '1px solid rgba(234,229,222,0.12)',
                            color: 'var(--color-stone)',
                            padding: '14px 32px',
                            borderRadius: 'var(--radius-full)',
                            fontSize: 'var(--text-base)',
                            fontWeight: 500,
                            textDecoration: 'none',
                            transition: 'border-color var(--transition-fast)',
                            minHeight: 48,
                            display: 'inline-flex',
                            alignItems: 'center',
                        }}
                    >
                        Sign in →
                    </Link>
                </div>

                {/* Scroll indicator */}
                <div style={{
                    position: 'absolute',
                    bottom: 'var(--space-8)',
                    opacity: 0.2,
                    fontSize: 24,
                    animation: 'pulse 2s infinite',
                }}>
                    ↓
                </div>
            </section>

            {/* ═══ ORIGIN / TENSION ═══ */}
            <Section id="origin" style={{ textAlign: 'center' }}>
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
                    Hospitality is people.
                    <br />
                    Operations should disappear.
                </div>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.4)',
                    maxWidth: 560,
                    marginInline: 'auto',
                    lineHeight: 1.7,
                }}>
                    Property managers juggle bookings across OTAs, coordinate field teams,
                    reconcile finances, and keep guests happy — often from scattered tools
                    that don&apos;t talk to each other. Domaniqo brings it all under one calm surface.
                </p>
            </Section>

            {/* ═══ PLATFORM ═══ */}
            <Section id="platform">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <div style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-copper)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.12em',
                        marginBottom: 'var(--space-3)',
                    }}>
                        The Platform
                    </div>
                    <h2 style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                        fontWeight: 400,
                        color: 'var(--color-stone)',
                    }}>
                        One system. Every surface.
                    </h2>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                    gap: 'var(--space-4)',
                }}>
                    {[
                        { icon: '📅', title: 'Unified Bookings', desc: 'Multi-OTA sync, conflict resolution, and chronological event history — one timeline for every stay.' },
                        { icon: '✓', title: 'Task Engine', desc: 'Auto-generated tasks from bookings, SLA tracking, escalation, and field-team mobile surfaces.' },
                        { icon: '💰', title: 'Financial Clarity', desc: 'Revenue aggregation, owner statements, cashflow projection, and multi-currency reconciliation.' },
                        { icon: '👤', title: 'Guest Experience', desc: 'Stay history, preference tracking, QR-based access portals, and connected communication channels.' },
                        { icon: '🏗', title: 'Operational Shell', desc: 'Adaptive layout — desktop command center, tablet review, mobile field action. One platform, every device.' },
                        { icon: '🔔', title: 'Connected Channels', desc: 'LINE, WhatsApp, Telegram notifications. Instant task alerts to the right person at the right time.' },
                    ].map(cap => (
                        <CapCard key={cap.title} {...cap} />
                    ))}
                </div>
            </Section>

            {/* ═══ CAPABILITIES ═══ */}
            <Section id="capabilities">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <div style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-copper)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.12em',
                        marginBottom: 'var(--space-3)',
                    }}>
                        Capabilities
                    </div>
                    <h2 style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                        fontWeight: 400,
                        color: 'var(--color-stone)',
                    }}>
                        Built deep, not wide.
                    </h2>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 'var(--space-6)',
                }}>
                    <PillarCard number="01" title="Multi-OTA Normalizer" desc="Booking.com, Airbnb, Agoda, Rakuten, Hotels.com — one canonical format." />
                    <PillarCard number="02" title="Event-Sourced Booking Core" desc="Append-only events, idempotent ingestion, conflict detection, full audit trail." />
                    <PillarCard number="03" title="SLA Escalation Engine" desc="5-minute critical ack window, timer-based escalation, deterministic state guards." />
                    <PillarCard number="04" title="Owner Financial Layer" desc="Per-property revenue, management fees, payout timelines, PDF statements." />
                    <PillarCard number="05" title="Portfolio Intelligence" desc="Cross-property dashboards, anomaly detection, morning briefings, AI copilot." />
                    <PillarCard number="06" title="Outbound Sync Pipeline" desc="Rate-limited channel push, retry with backoff, DLQ inspection, health monitoring." />
                </div>
            </Section>

            {/* ═══ TRUST ═══ */}
            <Section id="trust" style={{ textAlign: 'center' }}>
                <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-copper)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.12em',
                    marginBottom: 'var(--space-3)',
                }}>
                    Trust
                </div>
                <h2 style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                    fontWeight: 400,
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-6)',
                }}>
                    Quiet confidence, earned.
                </h2>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: 'var(--space-6)',
                    maxWidth: 700,
                    marginInline: 'auto',
                }}>
                    {[
                        { label: 'Contract Tests', value: '6,400+' },
                        { label: 'OTA Adapters', value: '10' },
                        { label: 'Development Phases', value: '374' },
                        { label: 'Languages', value: '3' },
                    ].map(stat => (
                        <div key={stat.label} style={{ textAlign: 'center' }}>
                            <div style={{
                                fontFamily: 'var(--font-display)',
                                fontSize: 'var(--text-3xl)',
                                color: 'var(--color-copper)',
                                marginBottom: 'var(--space-1)',
                            }}>{stat.value}</div>
                            <div style={{
                                fontSize: 'var(--text-sm)',
                                color: 'rgba(234,229,222,0.35)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.08em',
                            }}>{stat.label}</div>
                        </div>
                    ))}
                </div>
            </Section>

            {/* ═══ CTA ═══ */}
            <Section id="cta" style={{ textAlign: 'center', paddingBottom: 'var(--space-16)' }}>
                <div style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-2xl), 5vw, var(--text-3xl))',
                    fontWeight: 400,
                    fontStyle: 'italic',
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-6)',
                }}>
                    Ready to see every stay?
                </div>
                <Link
                    href="/get-started"
                    id="cta-get-started"
                    style={{
                        background: 'var(--color-moss)',
                        color: 'var(--color-white)',
                        padding: '16px 40px',
                        borderRadius: 'var(--radius-full)',
                        fontSize: 'var(--text-lg)',
                        fontWeight: 600,
                        fontFamily: 'var(--font-brand)',
                        textDecoration: 'none',
                        boxShadow: 'var(--shadow-glow-moss)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        minHeight: 52,
                    }}
                >
                    Start Free →
                </Link>
                <div style={{
                    fontSize: 'var(--text-xs)',
                    color: 'rgba(234,229,222,0.2)',
                    marginTop: 'var(--space-4)',
                }}>
                    info@domaniqo.com
                </div>
            </Section>
        </div>
    );
}
