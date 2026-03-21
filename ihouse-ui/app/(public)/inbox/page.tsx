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
function ChannelBadge({ name, icon }: { name: string; icon: React.ReactNode }) {
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
            <div className="brand-ico" style={{ marginBottom: 0 }}>{icon}</div>
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
function FeatureBlock({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
    return (
        <div style={{
            background: 'var(--color-elevated)',
            border: '1px solid rgba(234,229,222,0.06)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-6)',
        }}>
            <div className="brand-ico">{icon}</div>
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
                    <ChannelBadge name="LINE" icon={<svg viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>} />
                    <ChannelBadge name="WhatsApp" icon={<svg viewBox="0 0 24 24"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>} />
                    <ChannelBadge name="Telegram" icon={<svg viewBox="0 0 24 24"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>} />
                    <ChannelBadge name="SMS" icon={<svg viewBox="0 0 24 24"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/></svg>} />
                    <ChannelBadge name="Email" icon={<svg viewBox="0 0 24 24"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>} />
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
                        icon={<svg viewBox="0 0 24 24"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>}
                        title="Unified Inbox"
                        desc="Every message from every channel converges into one timeline. Guest inquiries, OTA messages, team communications — one place, one context."
                    />
                    <FeatureBlock
                        icon={<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>}
                        title="Scheduled Messages"
                        desc="Automated guest messages triggered by booking events: confirmation, pre-arrival, check-in instructions, checkout reminders, review requests."
                    />
                    <FeatureBlock
                        icon={<svg viewBox="0 0 24 24"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>}
                        title="Message Templates"
                        desc="Pre-built templates for common scenarios. Personalized with booking data, property details, and guest names. Consistent communication, effortless."
                    />
                    <FeatureBlock
                        icon={<svg viewBox="0 0 24 24"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>}
                        title="SLA-Linked Notifications"
                        desc="Task notifications routed to the right person on their preferred channel. Acknowledge via LINE. Complete via WhatsApp. Escalate via email."
                    />
                    <FeatureBlock
                        icon={<svg viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>}
                        title="Delivery Tracking"
                        desc="Every message tracked: sent, delivered, read. Failed deliveries surfaced immediately. Full message history per guest, per booking."
                    />
                    <FeatureBlock
                        icon={<svg viewBox="0 0 24 24"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>}
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
