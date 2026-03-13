'use client';

/**
 * Pricing — Domaniqo Marketing Page
 *
 * "Investment" framing rather than "simple pricing."
 * Inspired by Your.Rentals /simple-pricing/ but elevated to
 * Domaniqo's premium positioning.
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
                maxWidth: 1040,
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

/* ── Pricing tier card ── */
function TierCard({
    name, subtitle, price, period, features, highlight = false, ctaLabel, ctaHref,
}: {
    name: string;
    subtitle: string;
    price: string;
    period: string;
    features: string[];
    highlight?: boolean;
    ctaLabel: string;
    ctaHref: string;
}) {
    return (
        <div style={{
            background: highlight ? 'rgba(51,64,54,0.15)' : 'var(--color-elevated)',
            border: highlight
                ? '1px solid rgba(51,64,54,0.4)'
                : '1px solid rgba(234,229,222,0.06)',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-8)',
            display: 'flex',
            flexDirection: 'column',
            position: 'relative',
            overflow: 'hidden',
        }}>
            {highlight && (
                <div style={{
                    position: 'absolute',
                    top: 0,
                    insetInline: 0,
                    height: 3,
                    background: 'var(--color-moss)',
                }}/>
            )}

            <div style={{
                fontFamily: 'var(--font-brand)',
                fontSize: 'var(--text-xl)',
                fontWeight: 700,
                color: 'var(--color-stone)',
                marginBottom: 'var(--space-1)',
            }}>
                {name}
            </div>
            <div style={{
                fontSize: 'var(--text-sm)',
                color: 'rgba(234,229,222,0.4)',
                marginBottom: 'var(--space-6)',
            }}>
                {subtitle}
            </div>

            <div style={{ marginBottom: 'var(--space-6)' }}>
                <span style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'var(--text-3xl)',
                    color: highlight ? 'var(--color-stone)' : 'var(--color-copper)',
                }}>
                    {price}
                </span>
                <span style={{
                    fontSize: 'var(--text-sm)',
                    color: 'rgba(234,229,222,0.35)',
                    marginInlineStart: 'var(--space-2)',
                }}>
                    {period}
                </span>
            </div>

            <ul style={{
                listStyle: 'none',
                padding: 0,
                margin: 0,
                flex: 1,
                marginBottom: 'var(--space-8)',
            }}>
                {features.map((f, i) => (
                    <li key={i} style={{
                        fontSize: 'var(--text-sm)',
                        color: 'rgba(234,229,222,0.55)',
                        lineHeight: 1.6,
                        paddingBlock: 'var(--space-2)',
                        borderBottom: '1px solid rgba(234,229,222,0.04)',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 'var(--space-3)',
                    }}>
                        <span style={{ color: 'var(--color-moss)', fontSize: 14, flexShrink: 0 }}>✓</span>
                        {f}
                    </li>
                ))}
            </ul>

            <Link
                href={ctaHref}
                style={{
                    background: highlight ? 'var(--color-moss)' : 'transparent',
                    color: highlight ? 'var(--color-white)' : 'var(--color-stone)',
                    border: highlight ? 'none' : '1px solid rgba(234,229,222,0.15)',
                    padding: '12px 28px',
                    borderRadius: 'var(--radius-full)',
                    fontSize: 'var(--text-sm)',
                    fontWeight: 600,
                    fontFamily: 'var(--font-brand)',
                    textDecoration: 'none',
                    textAlign: 'center',
                    transition: 'opacity var(--transition-fast)',
                    boxShadow: highlight ? 'var(--shadow-glow-moss)' : 'none',
                    minHeight: 44,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}
            >
                {ctaLabel}
            </Link>
        </div>
    );
}

/* ── FAQ item ── */
function FaqItem({ q, a }: { q: string; a: string }) {
    return (
        <div style={{
            borderBottom: '1px solid rgba(234,229,222,0.06)',
            paddingBlock: 'var(--space-5)',
        }}>
            <div style={{
                fontFamily: 'var(--font-brand)',
                fontSize: 'var(--text-base)',
                fontWeight: 600,
                color: 'var(--color-stone)',
                marginBottom: 'var(--space-2)',
            }}>
                {q}
            </div>
            <div style={{
                fontSize: 'var(--text-sm)',
                color: 'rgba(234,229,222,0.4)',
                lineHeight: 1.7,
            }}>
                {a}
            </div>
        </div>
    );
}

/* ── Main page ── */
export default function PricingPage() {
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
                id="pricing-hero"
                style={{
                    paddingTop: 'calc(var(--header-height) + var(--space-16))',
                    paddingBottom: 'var(--space-10)',
                    textAlign: 'center',
                    paddingInline: 'var(--space-6)',
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
                    Investment
                </div>
                <h1 style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-3xl), 6vw, var(--text-4xl))',
                    fontWeight: 400,
                    fontStyle: 'italic',
                    color: 'var(--color-stone)',
                    lineHeight: 1.15,
                    maxWidth: 600,
                    marginInline: 'auto',
                    marginBottom: 'var(--space-5)',
                    opacity: 0,
                    animation: 'fadeUp 800ms 400ms ease forwards',
                }}>
                    Clarity has a price. Chaos costs more.
                </h1>
                <p style={{
                    fontSize: 'var(--text-lg)',
                    color: 'rgba(234,229,222,0.45)',
                    maxWidth: 520,
                    marginInline: 'auto',
                    lineHeight: 1.6,
                    opacity: 0,
                    animation: 'fadeUp 800ms 600ms ease forwards',
                }}>
                    Transparent, straightforward plans. 
                    No hidden fees. No per-channel charges. No surprises.
                </p>
            </section>

            {/* ═══ TIERS ═══ */}
            <Section id="tiers">
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 'var(--space-6)',
                    alignItems: 'stretch',
                }}>
                    <TierCard
                        name="Operator"
                        subtitle="For teams managing up to 10 properties"
                        price="Contact us"
                        period=""
                        features={[
                            'Multi-OTA sync (all 14+ channels)',
                            'Unified booking management',
                            'Calendar & availability control',
                            'Task management with SLA tracking',
                            'Guest portal & check-in flows',
                            'Financial overview & reporting',
                            'Email & push notifications',
                            'Up to 5 team members',
                        ]}
                        ctaLabel="Get in Touch"
                        ctaHref="/early-access"
                    />

                    <TierCard
                        name="Portfolio"
                        subtitle="For operations managing 10–50 properties"
                        price="Contact us"
                        period=""
                        highlight
                        features={[
                            'Everything in Operator',
                            'Owner portal & statements',
                            'Multi-channel notifications (LINE, WhatsApp, Telegram)',
                            'AI copilot for managers & workers',
                            'Revenue forecasting & analytics',
                            'Anomaly detection & morning briefings',
                            'Priority support',
                            'Unlimited team members',
                        ]}
                        ctaLabel="Request Early Access →"
                        ctaHref="/early-access"
                    />

                    <TierCard
                        name="Enterprise"
                        subtitle="For large-scale hospitality operations"
                        price="Custom"
                        period=""
                        features={[
                            'Everything in Portfolio',
                            'Dedicated integration support',
                            'Custom OTA adapter development',
                            'On-premise deployment option',
                            'SLA guarantees',
                            'Custom reporting & dashboards',
                            'API access for third-party integrations',
                            'Dedicated account manager',
                        ]}
                        ctaLabel="Talk to Us"
                        ctaHref="/early-access"
                    />
                </div>
            </Section>

            {/* ═══ WHAT'S INCLUDED ═══ */}
            <Section id="included" style={{ textAlign: 'center' }}>
                <SectionLabel>Every plan includes</SectionLabel>
                <h2 style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                    fontWeight: 400,
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-10)',
                }}>
                    No per-channel fees. No booking commissions.
                </h2>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: 'var(--space-6)',
                    maxWidth: 800,
                    marginInline: 'auto',
                    textAlign: 'center',
                }}>
                    {[
                        { icon: '🔗', label: 'All channels included' },
                        { icon: '🏠', label: 'Unlimited properties' },
                        { icon: '📱', label: 'Mobile-optimized' },
                        { icon: '🌍', label: 'Multi-language (EN/TH/HE)' },
                        { icon: '🔒', label: 'Role-based access' },
                        { icon: '📊', label: 'Core analytics' },
                    ].map(item => (
                        <div key={item.label}>
                            <div style={{ fontSize: 28, marginBottom: 'var(--space-2)' }}>{item.icon}</div>
                            <div style={{
                                fontSize: 'var(--text-sm)',
                                color: 'rgba(234,229,222,0.5)',
                            }}>
                                {item.label}
                            </div>
                        </div>
                    ))}
                </div>
            </Section>

            {/* ═══ FAQ ═══ */}
            <Section id="faq">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>Questions</SectionLabel>
                    <h2 style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                        fontWeight: 400,
                        color: 'var(--color-stone)',
                    }}>
                        Common questions, honest answers.
                    </h2>
                </div>

                <div style={{ maxWidth: 700, marginInline: 'auto' }}>
                    <FaqItem
                        q="Is there a free trial?"
                        a="We're currently in early access. Selected operators get full platform access during the early access period. No credit card required to apply."
                    />
                    <FaqItem
                        q="Do you charge per booking or per channel?"
                        a="No. Domaniqo uses a flat subscription model. All channels, all bookings, all properties are included in your plan. No hidden commissions."
                    />
                    <FaqItem
                        q="What if I need channels you don't support yet?"
                        a="Our outbound sync pipeline is designed for extensibility. We actively build new OTA adapters based on operator demand. Enterprise plans include custom adapter development."
                    />
                    <FaqItem
                        q="Can I switch plans later?"
                        a="Yes. Upgrade or adjust your plan as your portfolio grows. No lock-in contracts."
                    />
                    <FaqItem
                        q="What currencies do you support?"
                        a="Domaniqo handles multi-currency bookings natively. Financial reporting supports all major currencies with exchange rate tracking."
                    />
                </div>
            </Section>

            {/* ═══ CTA ═══ */}
            <Section id="pricing-cta" style={{ textAlign: 'center', paddingBottom: 'var(--space-16)' }}>
                <div style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-2xl), 5vw, var(--text-3xl))',
                    fontWeight: 400,
                    fontStyle: 'italic',
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-4)',
                }}>
                    The cost of clarity is always less than the cost of confusion.
                </div>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.35)',
                    marginBottom: 'var(--space-8)',
                }}>
                    Talk to us about the right plan for your operations.
                </p>
                <Link
                    href="/early-access"
                    id="pricing-cta-bottom"
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
