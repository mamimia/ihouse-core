'use client';

/**
 * Unified Communications — Domaniqo Marketing Page
 *
 * Marketing page for the unified inbox and messaging features.
 * Covers multi-channel routing, scheduled messages, and operational
 * communication across LINE, WhatsApp, Telegram, SMS, Email.
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

/* ── Channel badge ── */
function ChannelBadge({ name, icon }: { name: string; icon: string }) {
    return (
        <div style={{
            background: 'var(--color-elevated)',
            border: '1px solid rgba(234,229,222,0.06)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-5) var(--space-6)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-3)',
            transition: 'border-color var(--transition-base)',
        }}>
            <span style={{ fontSize: 24 }}>{icon}</span>
            <div>
                <div style={{
                    fontFamily: 'var(--font-brand)',
                    fontSize: 'var(--text-sm)',
                    fontWeight: 700,
                    color: 'var(--color-stone)',
                }}>
                    {name}
                </div>
                <div style={{
                    fontSize: 'var(--text-xs)',
                    color: 'rgba(234,229,222,0.3)',
                }}>
                    Connected
                </div>
            </div>
        </div>
    );
}

/* ── Feature block ── */
function FeatureBlock({ icon, title, desc }: { icon: string; title: string; desc: string }) {
    return (
        <div style={{
            background: 'var(--color-elevated)',
            border: '1px solid rgba(234,229,222,0.06)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-6)',
        }}>
            <div style={{ fontSize: 28, marginBottom: 'var(--space-3)' }}>{icon}</div>
            <div style={{
                fontFamily: 'var(--font-brand)',
                fontSize: 'var(--text-lg)',
                fontWeight: 700,
                color: 'var(--color-stone)',
                marginBottom: 'var(--space-2)',
            }}>
                {title}
            </div>
            <div style={{
                fontSize: 'var(--text-sm)',
                color: 'rgba(234,229,222,0.45)',
                lineHeight: 1.6,
            }}>
                {desc}
            </div>
        </div>
    );
}

/* ── Main page ── */
export default function InboxPage() {
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
                id="inbox-hero"
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
                    Domaniqo Inbox
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
                    One thread. Every channel.
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
                    Stop switching between apps. Domaniqo&apos;s unified inbox brings 
                    every guest conversation, team notification, and operational message 
                    into one calm surface.
                </p>

                <Link
                    href="/early-access"
                    id="inbox-cta-hero"
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

            {/* ═══ CHANNEL GRID ═══ */}
            <Section id="channels">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>Connected channels</SectionLabel>
                    <h2 style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                        fontWeight: 400,
                        color: 'var(--color-stone)',
                    }}>
                        Five channels. One inbox.
                    </h2>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                    gap: 'var(--space-3)',
                    maxWidth: 700,
                    marginInline: 'auto',
                }}>
                    <ChannelBadge name="LINE" icon="💚" />
                    <ChannelBadge name="WhatsApp" icon="💬" />
                    <ChannelBadge name="Telegram" icon="✈️" />
                    <ChannelBadge name="SMS" icon="📱" />
                    <ChannelBadge name="Email" icon="📧" />
                </div>
            </Section>

            {/* ═══ FEATURES ═══ */}
            <Section id="inbox-features">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>Capabilities</SectionLabel>
                    <h2 style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                        fontWeight: 400,
                        color: 'var(--color-stone)',
                    }}>
                        Communication as an operational tool.
                    </h2>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 'var(--space-4)',
                }}>
                    <FeatureBlock
                        icon="📥"
                        title="Unified Inbox"
                        desc="Every message from every channel converges into one timeline. Guest inquiries, OTA messages, team communications — one place, one context."
                    />
                    <FeatureBlock
                        icon="⏱️"
                        title="Scheduled Messages"
                        desc="Automated guest messages triggered by booking events: confirmation, pre-arrival, check-in instructions, checkout reminders, review requests."
                    />
                    <FeatureBlock
                        icon="📋"
                        title="Message Templates"
                        desc="Pre-built templates for common scenarios. Personalized with booking data, property details, and guest names. Consistent communication, effortless."
                    />
                    <FeatureBlock
                        icon="🔔"
                        title="SLA-Linked Notifications"
                        desc="Task notifications routed to the right person on their preferred channel. Acknowledge via LINE. Complete via WhatsApp. Escalate via email."
                    />
                    <FeatureBlock
                        icon="📊"
                        title="Delivery Tracking"
                        desc="Every message tracked: sent, delivered, read. Failed deliveries surfaced immediately. Full message history per guest, per booking."
                    />
                    <FeatureBlock
                        icon="🤖"
                        title="AI Message Copilot"
                        desc="Contextual message suggestions powered by booking data, guest history, and operational signals. The right message, at the right time."
                    />
                </div>
            </Section>

            {/* ═══ HOW IT FITS ═══ */}
            <Section id="inbox-flow" style={{ textAlign: 'center' }}>
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
                    Communication is operations.
                    <br />
                    Operations is communication.
                </div>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.4)',
                    maxWidth: 560,
                    marginInline: 'auto',
                    lineHeight: 1.7,
                }}>
                    In Domaniqo, messages aren&apos;t separate from operations — they&apos;re part of 
                    the same flow. A booking creates a task. A task creates a notification. 
                    A notification triggers an acknowledgement. The full loop, visible and traceable.
                </p>
            </Section>

            {/* ═══ CTA ═══ */}
            <Section id="inbox-cta" style={{ textAlign: 'center', paddingBottom: 'var(--space-16)' }}>
                <div style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-2xl), 5vw, var(--text-3xl))',
                    fontWeight: 400,
                    fontStyle: 'italic',
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-6)',
                }}>
                    Never miss a message again.
                </div>
                <Link
                    href="/early-access"
                    id="inbox-cta-bottom"
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
