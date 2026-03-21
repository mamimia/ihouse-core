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
function FeatureCard({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
    return (
        <div style={{
            background: 'var(--color-elevated)',
            border: '1px solid rgba(234,229,222,0.06)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-6)',
            transition: 'border-color var(--transition-base)',
        }}>
            <div className="brand-ico">{icon}</div>
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
                    Every booking source. One truth.
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
                    Domaniqo brings in booking data from the platforms you already use. 
                    Every import is auditable. Every discrepancy is surfaced. No silent drift.
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
                    Transparently imported.
                </div>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.4)',
                    maxWidth: 560,
                    marginInline: 'auto',
                    lineHeight: 1.7,
                }}>
                    Most tools leave you guessing about your booking data. 
                    Domaniqo tracks every import, logs every source, and surfaces 
                    discrepancies the moment they appear — not when a double booking shows up.
                </p>
            </Section>

            {/* ═══ CHANNEL GRID ═══ */}
            <Section id="channel-grid">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>Connected platforms</SectionLabel>
                    <SectionHeading>Booking data from 14+ platforms.</SectionHeading>
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
                        desc="Booking data arrives from each platform in its native format. Domaniqo normalizes every record into one canonical schema — dates, currencies, guest data, status."
                    />
                    <StepCard
                        number="02"
                        title="Detect & Resolve"
                        desc="Conflicts, duplicates, and amendments are detected automatically. Idempotent ingestion ensures no event processes twice. Change history is preserved."
                    />
                    <StepCard
                        number="03"
                        title="Connect & Monitor"
                        desc="Calendar feeds and booking sources connected to your properties. Each connection is monitored for health, latency, and completeness."
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
                    <SectionHeading>Booking visibility with engineering depth.</SectionHeading>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 'var(--space-4)',
                }}>
                    <FeatureCard
                        icon={<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>}
                        title="Auditable Sync Log"
                        desc="Every push, every response, every retry — logged and queryable. Full history of what was sent, when, and what came back."
                    />
                    <FeatureCard
                        icon={<svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>}
                        title="Conflict Detection"
                        desc="When two OTAs disagree on the same booking, Domaniqo catches it immediately. Automatic resolution or escalation — never silent drift."
                    />
                    <FeatureCard
                        icon={<svg viewBox="0 0 24 24"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>}
                        title="Channel Health Dashboard"
                        desc="Real-time health indicators for every integration. Last successful sync, error rate, latency — visible at a glance on your operations dashboard."
                    />
                    <FeatureCard
                        icon={<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>}
                        title="DLQ Inspection"
                        desc="Failed events don't disappear. The dead-letter queue captures every failure with full context for replay, debug, and resolution."
                    />
                    <FeatureCard
                        icon={<svg viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>}
                        title="Source Health Monitoring"
                        desc="Each booking source has different data patterns. Domaniqo monitors them all — connection health, data freshness, zero missed bookings."
                    />
                    <FeatureCard
                        icon={<svg viewBox="0 0 24 24"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>}
                        title="iCal Fallback"
                        desc="For platforms without direct data feeds, iCal calendar sync provides reliable booking visibility as a lightweight connection layer."
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
                    Ready for full booking visibility?
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
