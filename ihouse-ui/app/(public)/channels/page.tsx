'use client';

/**
 * Connected Channels — Domaniqo Marketing Page
 *
 * Showcases the multi-OTA integration architecture.
 * Inspired by Your.Rentals channel-manager but told through
 * Domaniqo's engineering-first, calm-command lens.
 */

import Link from 'next/link';
import DMonogram from '../../../components/DMonogram';

/* ── Shared section wrapper ── */
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

/* ── Section heading ── */
function SectionHeading({ children }: { children: React.ReactNode }) {
    return (
        <h2 style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
            fontWeight: 400,
            color: 'var(--color-stone)',
            marginBottom: 'var(--space-6)',
        }}>
            {children}
        </h2>
    );
}

/* ── Channel logo pill ── */
function ChannelPill({ name, font, weight = 700, size = 14, spacing = '0.3px' }: {
    name: string;
    font: string;
    weight?: number;
    size?: number;
    spacing?: string;
}) {
    return (
        <div style={{
            background: 'var(--color-elevated)',
            border: '1px solid rgba(234,229,222,0.06)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-4) var(--space-5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 64,
            transition: 'border-color var(--transition-base)',
        }}>
            <span style={{
                fontFamily: font,
                fontWeight: weight,
                fontSize: size,
                letterSpacing: spacing,
                color: 'var(--color-stone)',
                opacity: 0.7,
            }}>
                {name}
            </span>
        </div>
    );
}

/* ── Step card ── */
function StepCard({ number, title, desc }: { number: string; title: string; desc: string }) {
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

/* ── Feature card ── */
function FeatureCard({ icon, title, desc }: { icon: string; title: string; desc: string }) {
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

/* ── Main page ── */
export default function ChannelsPage() {
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
                id="channels-hero"
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
                    <DMonogram size={48} color="var(--color-copper)" strokeWidth={1.2} />
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
                    Every channel. One truth.
                </h1>

                <p style={{
                    fontSize: 'var(--text-lg)',
                    color: 'rgba(234,229,222,0.45)',
                    maxWidth: 560,
                    lineHeight: 1.6,
                    marginBottom: 'var(--space-8)',
                    opacity: 0,
                    animation: 'fadeUp 800ms 600ms ease forwards',
                }}>
                    Domaniqo syncs with the booking platforms your operations depend on. 
                    Every sync is auditable. Every failure is surfaced. No silent drift.
                </p>

                <Link
                    href="/early-access"
                    id="channels-cta-hero"
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
                        opacity: 0,
                        animation: 'fadeUp 800ms 800ms ease forwards',
                    }}
                >
                    Request Early Access →
                </Link>
            </section>

            {/* ═══ PHILOSOPHY ═══ */}
            <Section id="channel-philosophy" style={{ textAlign: 'center' }}>
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
                    Not just connected.
                    <br />
                    Transparently synchronized.
                </div>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.4)',
                    maxWidth: 560,
                    marginInline: 'auto',
                    lineHeight: 1.7,
                }}>
                    Most channel managers push data outward and hope it arrives. 
                    Domaniqo tracks every sync, logs every response, and surfaces 
                    failures the moment they happen — not when a double booking appears.
                </p>
            </Section>

            {/* ═══ CHANNEL GRID ═══ */}
            <Section id="channel-grid">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>Connected platforms</SectionLabel>
                    <SectionHeading>14+ OTA integrations and growing.</SectionHeading>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                    gap: 'var(--space-3)',
                }}>
                    <ChannelPill name="airbnb" font="'Nunito Sans', sans-serif" weight={700} size={14} />
                    <ChannelPill name="Booking.com" font="'Montserrat', sans-serif" weight={700} size={12} spacing="0.5px" />
                    <ChannelPill name="Expedia" font="'DM Sans', sans-serif" weight={700} size={14} />
                    <ChannelPill name="VRBO" font="'Raleway', sans-serif" weight={800} size={16} spacing="2px" />
                    <ChannelPill name="agoda" font="'Quicksand', sans-serif" weight={700} size={14} />
                    <ChannelPill name="Trip.com" font="'DM Sans', sans-serif" weight={600} size={14} />
                    <ChannelPill name="traveloka" font="'Poppins', sans-serif" weight={600} size={13} />
                    <ChannelPill name="Rakuten" font="'Outfit', sans-serif" weight={700} size={14} />
                    <ChannelPill name="despegar" font="'Montserrat', sans-serif" weight={600} size={13} />
                    <ChannelPill name="Klook" font="'Nunito Sans', sans-serif" weight={800} size={16} spacing="0.5px" />
                    <ChannelPill name="MakeMyTrip" font="'Poppins', sans-serif" weight={700} size={11} />
                    <ChannelPill name="Google VR" font="'DM Sans', sans-serif" weight={500} size={12} />
                    <ChannelPill name="Hostelworld" font="'Raleway', sans-serif" weight={700} size={12} spacing="0.5px" />
                    <ChannelPill name="HotelBeds" font="'Montserrat', sans-serif" weight={600} size={12} />
                </div>

                <p style={{
                    fontSize: 'var(--text-xs)',
                    color: 'rgba(234,229,222,0.2)',
                    textAlign: 'center',
                    marginTop: 'var(--space-6)',
                }}>
                    Channel names and trademarks belong to their respective owners.
                </p>
            </Section>

            {/* ═══ HOW SYNC WORKS ═══ */}
            <Section id="sync-pipeline">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>Sync pipeline</SectionLabel>
                    <SectionHeading>Four stages. Full transparency.</SectionHeading>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                    gap: 'var(--space-6)',
                }}>
                    <StepCard
                        number="01"
                        title="Ingest & Normalize"
                        desc="Bookings arrive from each OTA in their native format. Domaniqo normalizes every payload into one canonical schema — dates, currencies, guest data, status."
                    />
                    <StepCard
                        number="02"
                        title="Detect & Resolve"
                        desc="Conflicts, duplicates, and amendments are detected automatically. Idempotent ingestion ensures no event processes twice. Change history is preserved."
                    />
                    <StepCard
                        number="03"
                        title="Push & Track"
                        desc="Availability and rates pushed outward to every connected channel. Rate-limited with exponential backoff. Every response logged. Every failure surfaced."
                    />
                    <StepCard
                        number="04"
                        title="Monitor & Alert"
                        desc="Dead-letter queue inspection, sync health dashboards, and real-time alerts. Know the exact status of every channel connection at any moment."
                    />
                </div>
            </Section>

            {/* ═══ WHY DIFFERENT ═══ */}
            <Section id="channel-difference">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>Why Domaniqo is different</SectionLabel>
                    <SectionHeading>Channel management with engineering depth.</SectionHeading>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 'var(--space-4)',
                }}>
                    <FeatureCard
                        icon="🔍"
                        title="Auditable Sync Log"
                        desc="Every push, every response, every retry — logged and queryable. Full history of what was sent, when, and what came back."
                    />
                    <FeatureCard
                        icon="🛡️"
                        title="Conflict Detection"
                        desc="When two OTAs disagree on the same booking, Domaniqo catches it immediately. Automatic resolution or escalation — never silent drift."
                    />
                    <FeatureCard
                        icon="📊"
                        title="Channel Health Dashboard"
                        desc="Real-time health indicators for every integration. Last successful sync, error rate, latency — visible at a glance on your operations dashboard."
                    />
                    <FeatureCard
                        icon="🔄"
                        title="DLQ Inspection"
                        desc="Failed events don't disappear. The dead-letter queue captures every failure with full context for replay, debug, and resolution."
                    />
                    <FeatureCard
                        icon="⚡"
                        title="Rate-Limited Push"
                        desc="Each OTA has different rate limits. Domaniqo respects them all — exponential backoff, per-provider throttling, zero banned connections."
                    />
                    <FeatureCard
                        icon="🗓️"
                        title="iCal Fallback"
                        desc="For channels without API access, iCal sync provides reliable calendar synchronization as a transparent fallback layer."
                    />
                </div>
            </Section>

            {/* ═══ CTA ═══ */}
            <Section id="channels-cta" style={{ textAlign: 'center', paddingBottom: 'var(--space-16)' }}>
                <div style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-2xl), 5vw, var(--text-3xl))',
                    fontWeight: 400,
                    fontStyle: 'italic',
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-6)',
                }}>
                    Ready to sync with confidence?
                </div>
                <Link
                    href="/early-access"
                    id="channels-cta-bottom"
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
                    Request Early Access →
                </Link>
            </Section>
        </div>
    );
}
