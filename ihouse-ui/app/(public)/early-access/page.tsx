'use client';

/**
 * Phase 380 — Early Access Form
 * Route: /early-access
 *
 * Split-screen form (brand left, form right) with Formspree integration.
 * Responsive: stacks on mobile.
 */

import { useState } from 'react';
import DMonogram from '../../../components/DMonogram';

const FORMSPREE_URL = 'https://formspree.io/f/xldrgdzr';

export default function EarlyAccessPage() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [company, setCompany] = useState('');
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);
    const [submitted, setSubmitted] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!email.trim()) { setError('Email is required'); return; }
        setError(null);
        setLoading(true);
        try {
            const resp = await fetch(FORMSPREE_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify({
                    name: name.trim(),
                    email: email.trim(),
                    company: company.trim(),
                    message: message.trim(),
                    _subject: `Domaniqo Early Access: ${name.trim() || email.trim()}`,
                }),
            });
            if (!resp.ok) throw new Error('Form submission failed');
            setSubmitted(true);
        } catch {
            setError('Something went wrong. Please email info@domaniqo.com directly.');
        } finally {
            setLoading(false);
        }
    };

    const inputStyle: React.CSSProperties = {
        width: '100%',
        padding: '12px 14px',
        background: 'var(--color-midnight)',
        border: '1px solid rgba(234,229,222,0.1)',
        borderRadius: 'var(--radius-md)',
        color: 'var(--color-stone)',
        fontSize: 'var(--text-sm)',
        fontFamily: 'var(--font-sans)',
        transition: 'border-color var(--transition-fast)',
        outline: 'none',
        boxSizing: 'border-box' as const,
    };

    const labelStyle: React.CSSProperties = {
        display: 'block',
        fontSize: 'var(--text-xs)',
        fontWeight: 600,
        color: 'rgba(234,229,222,0.5)',
        marginBottom: 'var(--space-2)',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
    };

    return (
        <div
            className="grain-overlay"
            style={{
                minHeight: '100vh',
                background: 'var(--color-midnight)',
                display: 'flex',
                paddingTop: 'var(--header-height)',
            }}
        >
            {/* Left: Brand panel — hidden on mobile */}
            <div
                className="hide-mobile"
                style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 'var(--space-10)',
                    borderInlineEnd: '1px solid rgba(234,229,222,0.04)',
                }}
            >
                <DMonogram size={64} color="var(--color-stone)" strokeWidth={1.2} />
                <div style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 'var(--text-3xl)',
                    color: 'var(--color-stone)',
                    marginTop: 'var(--space-6)',
                    marginBottom: 'var(--space-3)',
                    textAlign: 'center',
                }}>
                    See every stay.
                </div>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.35)',
                    textAlign: 'center',
                    maxWidth: 360,
                    lineHeight: 1.6,
                }}>
                    Join the early access program for Domaniqo&apos;s
                    deep operations platform.
                </p>
            </div>

            {/* Right: Form panel */}
            <div style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 'var(--space-8) var(--space-6)',
            }}>
                <div style={{ width: '100%', maxWidth: 420 }}>
                    {submitted ? (
                        /* Success state */
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: 48, marginBottom: 'var(--space-4)' }}>✓</div>
                            <h2 style={{
                                fontFamily: 'var(--font-display)',
                                fontSize: 'var(--text-2xl)',
                                color: 'var(--color-stone)',
                                marginBottom: 'var(--space-3)',
                            }}>
                                Thank you
                            </h2>
                            <p style={{
                                fontSize: 'var(--text-base)',
                                color: 'rgba(234,229,222,0.4)',
                                lineHeight: 1.6,
                            }}>
                                We&apos;ve received your request. We&apos;ll be in touch soon
                                at the email you provided.
                            </p>
                            <a
                                href="/"
                                style={{
                                    display: 'inline-block',
                                    marginTop: 'var(--space-6)',
                                    fontSize: 'var(--text-sm)',
                                    color: 'var(--color-copper)',
                                    textDecoration: 'none',
                                }}
                            >
                                ← Back to Domaniqo
                            </a>
                        </div>
                    ) : (
                        /* Form */
                        <>
                            <h1 style={{
                                fontFamily: 'var(--font-display)',
                                fontSize: 'var(--text-2xl)',
                                color: 'var(--color-stone)',
                                marginBottom: 'var(--space-2)',
                            }}>
                                Request Early Access
                            </h1>
                            <p style={{
                                fontSize: 'var(--text-sm)',
                                color: 'rgba(234,229,222,0.4)',
                                marginBottom: 'var(--space-6)',
                                lineHeight: 1.6,
                            }}>
                                Tell us about your property operations and we&apos;ll reach out
                                with access details.
                            </p>

                            <form onSubmit={handleSubmit} style={{
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 'var(--space-4)',
                            }}>
                                <div>
                                    <label style={labelStyle}>Name</label>
                                    <input
                                        id="input-name"
                                        type="text"
                                        value={name}
                                        onChange={e => setName(e.target.value)}
                                        placeholder="Your name"
                                        style={inputStyle}
                                    />
                                </div>

                                <div>
                                    <label style={labelStyle}>Email *</label>
                                    <input
                                        id="input-email"
                                        type="email"
                                        value={email}
                                        onChange={e => setEmail(e.target.value)}
                                        placeholder="you@example.com"
                                        required
                                        style={inputStyle}
                                    />
                                </div>

                                <div>
                                    <label style={labelStyle}>Company / Property Group</label>
                                    <input
                                        id="input-company"
                                        type="text"
                                        value={company}
                                        onChange={e => setCompany(e.target.value)}
                                        placeholder="Your company or property name"
                                        style={inputStyle}
                                    />
                                </div>

                                <div>
                                    <label style={labelStyle}>Tell us more (optional)</label>
                                    <textarea
                                        id="input-message"
                                        value={message}
                                        onChange={e => setMessage(e.target.value)}
                                        placeholder="How many properties? Which OTAs? Any specific needs?"
                                        rows={4}
                                        style={{
                                            ...inputStyle,
                                            resize: 'none',
                                        }}
                                    />
                                </div>

                                {error && (
                                    <div style={{
                                        background: 'rgba(155,58,58,0.1)',
                                        border: '1px solid rgba(155,58,58,0.25)',
                                        borderRadius: 'var(--radius-md)',
                                        padding: '10px 14px',
                                        fontSize: 'var(--text-sm)',
                                        color: '#EF4444',
                                    }}>
                                        {error}
                                    </div>
                                )}

                                <button
                                    id="btn-submit-early-access"
                                    type="submit"
                                    disabled={loading || !email.trim()}
                                    style={{
                                        padding: '14px',
                                        background: 'var(--color-moss)',
                                        border: 'none',
                                        borderRadius: 'var(--radius-md)',
                                        color: 'var(--color-white)',
                                        fontSize: 'var(--text-base)',
                                        fontWeight: 600,
                                        fontFamily: 'var(--font-brand)',
                                        cursor: loading || !email.trim() ? 'not-allowed' : 'pointer',
                                        opacity: loading || !email.trim() ? 0.4 : 1,
                                        transition: 'all var(--transition-fast)',
                                        boxShadow: 'var(--shadow-glow-moss)',
                                        marginTop: 'var(--space-2)',
                                        minHeight: 48,
                                    }}
                                >
                                    {loading ? 'Submitting…' : 'Submit Request →'}
                                </button>
                            </form>

                            <p style={{
                                fontSize: 'var(--text-xs)',
                                color: 'rgba(234,229,222,0.2)',
                                marginTop: 'var(--space-4)',
                                textAlign: 'center',
                            }}>
                                Or email directly: info@domaniqo.com
                            </p>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
