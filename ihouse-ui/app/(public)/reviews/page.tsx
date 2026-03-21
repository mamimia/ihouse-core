'use client';

/**
 * Guest Intelligence — Domaniqo Marketing Page
 *
 * Marketing page for review management + guest feedback.
 * Shows how Domaniqo aggregates reviews, tracks NPS,
 * and turns feedback into operational insight.
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

/* ── Insight card ── */
function InsightCard({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
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

/* ── Review source pill ── */
function SourcePill({ name }: { name: string }) {
    return (
        <div style={{
            background: 'var(--color-elevated)',
            border: '1px solid rgba(234,229,222,0.06)',
            borderRadius: 'var(--radius-full)',
            padding: 'var(--space-2) var(--space-5)',
            fontSize: 'var(--text-sm)',
            color: 'rgba(234,229,222,0.55)',
            fontFamily: 'var(--font-brand)',
            fontWeight: 600,
        }}>
            {name}
        </div>
    );
}

/* ── Main page ── */
export default function ReviewsPage() {
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
                id="reviews-hero"
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
                    Guest Intelligence
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
                    Every voice. Every insight. Every improvement.
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
                    Reviews aren&apos;t just ratings — they&apos;re operational intelligence. 
                    Domaniqo aggregates guest feedback from every channel and turns it 
                    into actionable insights for your team.
                </p>

                <Link
                    href="/early-access"
                    id="reviews-cta-hero"
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

            {/* ═══ REVIEW SOURCES ═══ */}
            <Section id="sources" style={{ textAlign: 'center' }}>
                <SectionLabel>Reviews from everywhere</SectionLabel>
                <h2 style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                    fontWeight: 400,
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-8)',
                }}>
                    Aggregated from all connected channels.
                </h2>

                <div style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 'var(--space-3)',
                    justifyContent: 'center',
                }}>
                    <SourcePill name="Airbnb" />
                    <SourcePill name="Booking.com" />
                    <SourcePill name="Expedia" />
                    <SourcePill name="VRBO" />
                    <SourcePill name="Agoda" />
                    <SourcePill name="Trip.com" />
                    <SourcePill name="Google" />
                    <SourcePill name="Direct" />
                </div>
            </Section>

            {/* ═══ CORE FEATURES ═══ */}
            <Section id="review-features">
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
                    <SectionLabel>Capabilities</SectionLabel>
                    <h2 style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 'clamp(var(--text-xl), 3.5vw, var(--text-2xl))',
                        fontWeight: 400,
                        color: 'var(--color-stone)',
                    }}>
                        From raw feedback to operational insight.
                    </h2>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 'var(--space-4)',
                }}>
                    <InsightCard
                        icon={<svg viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>}
                        title="Unified Review Dashboard"
                        desc="Every review from every OTA in one view. Filter by property, channel, rating, or date. Spot trends across your entire portfolio."
                    />
                    <InsightCard
                        icon={<svg viewBox="0 0 24 24"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>}
                        title="NPS & Satisfaction Tracking"
                        desc="Net Promoter Score calculated per property and across your portfolio. Track guest satisfaction over time with clear trend indicators."
                    />
                    <InsightCard
                        icon={<svg viewBox="0 0 24 24"><path d="m3 21 1.9-5.7a8.5 8.5 0 1 1 3.8 3.8z"/></svg>}
                        title="Response Management"
                        desc="Reply to reviews across all channels from one place. AI-assisted response suggestions that match your brand voice and address specific guest concerns."
                    />
                    <InsightCard
                        icon={<svg viewBox="0 0 24 24"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>}
                        title="Sentiment Analysis"
                        desc="Automated categorization of feedback themes: cleanliness, location, check-in experience, amenities. Know exactly what guests praise and what needs attention."
                    />
                    <InsightCard
                        icon={<svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>}
                        title="Linked to Operations"
                        desc="Reviews linked to specific bookings and tasks. A cleaning complaint triggers a task template review. A connectivity issue creates a maintenance ticket."
                    />
                    <InsightCard
                        icon={<svg viewBox="0 0 24 24"><path d="M3 3v18h18"/><rect width="4" height="7" x="7" y="10" rx="1"/><rect width="4" height="12" x="15" y="5" rx="1"/></svg>}
                        title="Property Benchmarking"
                        desc="Compare guest satisfaction across your properties. Identify top performers and underperformers. Set improvement targets with data-backed clarity."
                    />
                </div>
            </Section>

            {/* ═══ FEEDBACK LOOP ═══ */}
            <Section id="feedback-loop" style={{ textAlign: 'center' }}>
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
                    The guest speaks.
                    <br />
                    The system listens.
                    <br />
                    Operations improve.
                </div>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.4)',
                    maxWidth: 560,
                    marginInline: 'auto',
                    lineHeight: 1.7,
                }}>
                    Domaniqo closes the loop between guest experience and operational execution. 
                    Every piece of feedback feeds back into task templates, team assignments, 
                    and property standards — continuously improving the stay experience.
                </p>
            </Section>

            {/* ═══ CTA ═══ */}
            <Section id="reviews-cta" style={{ textAlign: 'center', paddingBottom: 'var(--space-16)' }}>
                <div style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'clamp(var(--text-2xl), 5vw, var(--text-3xl))',
                    fontWeight: 400,
                    fontStyle: 'italic',
                    color: 'var(--color-stone)',
                    marginBottom: 'var(--space-6)',
                }}>
                    Turn every review into better operations.
                </div>
                <Link
                    href="/early-access"
                    id="reviews-cta-bottom"
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
