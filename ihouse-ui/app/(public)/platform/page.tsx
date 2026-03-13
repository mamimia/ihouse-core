'use client';

/**
 * Platform — Domaniqo Marketing Page
 *
 * Deep dive into the 7 product modules.
 * Merges concepts from Your.Rentals' "Make it Simple" + "Make More Time"
 * + "Maximize Earnings" into one comprehensive platform overview.
 */

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

/* ── Module card ── */
function ModuleCard({
    name, moduleName, desc, color, features,
}: {
    name: string;
    moduleName: string;
    desc: string;
    color: string;
    features: string[];
}) {
    return (
        <div style={{
            background: 'var(--color-elevated)',
            border: '1px solid rgba(234,229,222,0.06)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-6)',
            position: 'relative',
            overflow: 'hidden',
        }}>
            <div style={{
                position: 'absolute',
                top: 0,
                insetInline: 0,
                height: 3,
                background: color,
                opacity: 0.6,
            }}/>
            <div style={{
                fontFamily: 'var(--font-brand)',
                fontSize: 'var(--text-lg)',
                fontWeight: 700,
                color: 'var(--color-stone)',
                marginBottom: 'var(--space-1)',
            }}>
                Domaniqo <em style={{ fontStyle: 'italic', color: 'var(--color-copper)' }}>{moduleName}</em>
            </div>
            <div style={{
                fontSize: 'var(--text-sm)',
                color: 'rgba(234,229,222,0.4)',
                lineHeight: 1.6,
                marginBottom: 'var(--space-5)',
            }}>
                {desc}
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {features.map((f, i) => (
                    <li key={i} style={{
                        fontSize: 'var(--text-xs)',
                        color: 'rgba(234,229,222,0.45)',
                        paddingBlock: 'var(--space-1)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-2)',
                    }}>
                        <span style={{ color, fontSize: 10, flexShrink: 0 }}>●</span>
                        {f}
                    </li>
                ))}
            </ul>
        </div>
    );
}

/* ── Value stat ── */
function ValueStat({ value, label }: { value: string; label: string }) {
    return (
        <div style={{ textAlign: 'center' }}>
            <div style={{
                fontFamily: 'var(--font-display)',
                fontSize: 'var(--text-3xl)',
                color: 'var(--color-copper)',
                marginBottom: 'var(--space-1)',
            }}>
                {value}
            </div>
            <div style={{
                fontSize: 'var(--text-sm)',
                color: 'rgba(234,229,222,0.35)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
            }}>
                {label}
            </div>
        </div>
    );
}

/* ── Flow step ── */
function FlowStep({ number, title, desc }: { number: string; title: string; desc: string }) {
    return (
        <div style={{
            display: 'flex',
            gap: 'var(--space-5)',
            alignItems: 'flex-start',
            paddingBlock: 'var(--space-4)',
        }}>
            <div style={{
                width: 40,
                height: 40,
                borderRadius: 'var(--radius-full)',
                border: '1px solid var(--color-copper)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-copper)',
                flexShrink: 0,
            }}>
                {number}
            </div>
            <div>
                <div style={{
                    fontFamily: 'var(--font-brand)',
                    fontSize: 'var(--text-base)',
                    fontWeight: 700,
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-1)',
                }}>
                    {title}
                </div>
                <div style={{
                    fontSize: 'var(--text-sm)',
                    color: 'rgba(234,229,222,0.4)',
                    lineHeight: 1.6,
                }}>
                    {desc}
                </div>
            </div>
        </div>
    );
}

/* ── Main page ── */
export default function PlatformPage() {
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
                id="platform-hero"
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
                    fontFamily: 'var(--font-mono)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--color-copper)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.12em',
                    marginBottom: 'var(--space-3)',
                    opacity: 0,
                    animation: 'fadeUp 800ms 200ms ease forwards',
                }}>
                    The Platform
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
                    Seven modules. One operating layer.
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
                    Domaniqo replaces scattered tools with a single system where 
                    bookings, operations, finance, and guest experience are unified 
                    under one calm surface.
                </p>
            </section>

            {/* ═══ MODULES ═══ */}
            <Section id="modules">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>System architecture</SectionLabel>
                    <h2 style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                        fontWeight: 400,
                        color: 'var(--color-stone)',
                    }}>
                        Each module handles a distinct domain. Together, they form a complete operating system.
                    </h2>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 'var(--space-4)',
                }}>
                    <ModuleCard
                        name="Core" moduleName="Core"
                        desc="The foundation. Property data, configuration, booking records, availability, and the canonical truth layer."
                        color="var(--color-moss)"
                        features={['Property management', 'Booking records', 'Availability engine', 'Configuration & settings']}
                    />
                    <ModuleCard
                        name="Stays" moduleName="Stays"
                        desc="Reservation lifecycle. Booking sync, channel management, rate integrity, conflict detection, and guest-stay continuity."
                        color="var(--color-moss)"
                        features={['Multi-OTA sync', 'Conflict detection', 'Rate management', 'Booking timeline']}
                    />
                    <ModuleCard
                        name="Ops" moduleName="Ops"
                        desc="Task orchestration. Cleaning, maintenance, prep — tracked with SLA enforcement, worker assignment, and completion verification."
                        color="var(--color-sage)"
                        features={['Task automation', 'SLA tracking', 'Worker assignment', 'Escalation engine']}
                    />
                    <ModuleCard
                        name="Guests" moduleName="Guests"
                        desc="Guest experience. Profiles, check-in flows, welcome sequences, feedback collection, service standards, pre-arrival workflows."
                        color="var(--color-sage)"
                        features={['Guest profiles', 'Check-in flows', 'Feedback & NPS', 'Pre-arrival automation']}
                    />
                    <ModuleCard
                        name="Inbox" moduleName="Inbox"
                        desc="Unified communications. Every message, every channel — LINE, WhatsApp, Telegram, SMS, email — one operational thread."
                        color="var(--color-olive)"
                        features={['Unified inbox', 'Multi-channel routing', 'Message templates', 'Delivery tracking']}
                    />
                    <ModuleCard
                        name="Teams" moduleName="Teams"
                        desc="Team coordination. Roles, permissions, assignments, accountability, escalation paths, availability scheduling."
                        color="var(--color-olive)"
                        features={['Role-based access', 'Worker scheduling', 'Performance tracking', 'Multi-device surfaces']}
                    />
                    <ModuleCard
                        name="Pulse" moduleName="Pulse"
                        desc="Operational intelligence. Anomaly detection, health monitoring, financial dashboards, revenue forecasting, trend analysis."
                        color="var(--color-copper)"
                        features={['Revenue analytics', 'Anomaly detection', 'Morning briefings', 'AI copilot']}
                    />
                </div>
            </Section>

            {/* ═══ OPERATIONAL FLOW ═══ */}
            <Section id="flow">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>How it works</SectionLabel>
                    <h2 style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                        fontWeight: 400,
                        color: 'var(--color-stone)',
                    }}>
                        From scattered chaos to calm command.
                    </h2>
                </div>

                <div style={{ maxWidth: 640, marginInline: 'auto' }}>
                    <FlowStep
                        number="01"
                        title="Connect your channels"
                        desc="Link your OTA accounts. Domaniqo begins syncing bookings, availability, and rates across all connected platforms."
                    />
                    <FlowStep
                        number="02"
                        title="Configure your operations"
                        desc="Define properties, set task templates, assign team roles, configure notification channels. One-time setup, ongoing clarity."
                    />
                    <FlowStep
                        number="03"
                        title="Operations run automatically"
                        desc="Bookings create tasks. Tasks trigger notifications. SLAs start counting. The morning briefing tells you what needs attention today."
                    />
                    <FlowStep
                        number="04"
                        title="See everything, trust every number"
                        desc="Financial dashboards with confidence levels. Sync health at a glance. Anomalies surfaced before they become crises."
                    />
                </div>
            </Section>

            {/* ═══ VALUE STRIP ═══ */}
            <Section id="value-stats">
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: 'var(--space-8)',
                    maxWidth: 800,
                    marginInline: 'auto',
                    paddingBlock: 'var(--space-10)',
                    borderTop: '1px solid rgba(234,229,222,0.06)',
                    borderBottom: '1px solid rgba(234,229,222,0.06)',
                }}>
                    <ValueStat value="14+" label="OTA Integrations" />
                    <ValueStat value="7" label="Product Modules" />
                    <ValueStat value="5" label="Notification Channels" />
                    <ValueStat value="3" label="Languages" />
                </div>
            </Section>

            {/* ═══ THREE PROMISES ═══ */}
            <Section id="promises">
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 'var(--space-8)',
                }}>
                    <div>
                        <h3 style={{
                            fontFamily: 'var(--font-display)',
                            fontSize: 'var(--text-xl)',
                            fontWeight: 400,
                            color: 'var(--color-stone)',
                            marginBottom: 'var(--space-3)',
                        }}>
                            Simplify your operations.
                        </h3>
                        <p style={{
                            fontSize: 'var(--text-sm)',
                            color: 'rgba(234,229,222,0.4)',
                            lineHeight: 1.7,
                        }}>
                            Replace five to twelve disconnected tools with one system. 
                            One login. One truth. One calm surface for every operational question.
                        </p>
                    </div>
                    <div>
                        <h3 style={{
                            fontFamily: 'var(--font-display)',
                            fontSize: 'var(--text-xl)',
                            fontWeight: 400,
                            color: 'var(--color-stone)',
                            marginBottom: 'var(--space-3)',
                        }}>
                            Reclaim your time.
                        </h3>
                        <p style={{
                            fontSize: 'var(--text-sm)',
                            color: 'rgba(234,229,222,0.4)',
                            lineHeight: 1.7,
                        }}>
                            Automated task generation, scheduled messaging, SLA notifications, 
                            and morning briefings. Focus on hospitality, not administration.
                        </p>
                    </div>
                    <div>
                        <h3 style={{
                            fontFamily: 'var(--font-display)',
                            fontSize: 'var(--text-xl)',
                            fontWeight: 400,
                            color: 'var(--color-stone)',
                            marginBottom: 'var(--space-3)',
                        }}>
                            Maximize your revenue.
                        </h3>
                        <p style={{
                            fontSize: 'var(--text-sm)',
                            color: 'rgba(234,229,222,0.4)',
                            lineHeight: 1.7,
                        }}>
                            Revenue analytics, OTA performance comparison, occupancy trends, 
                            and cashflow projections. Know your numbers — and trust them.
                        </p>
                    </div>
                </div>
            </Section>

            {/* ═══ CTA ═══ */}
            <Section id="platform-cta" style={{ textAlign: 'center', paddingBottom: 'var(--space-16)' }}>
                <div style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-2xl), 5vw, var(--text-3xl))',
                    fontWeight: 400,
                    fontStyle: 'italic',
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-6)',
                }}>
                    One platform. Every surface. Full clarity.
                </div>
                <Link
                    href="/early-access"
                    id="platform-cta-bottom"
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
