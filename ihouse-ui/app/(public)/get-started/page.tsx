'use client';

/**
 * Phase 856B — Get Started / Intake Page
 * Route: /get-started
 *
 * Replaces the disconnected /early-access (Formspree) + /register (auto-provision) paths.
 *
 * Flow:
 *   1. User fills name, email, company, portfolio info, message
 *   2. Data is submitted to backend POST /intake/request
 *   3. Backend saves to DB (leads/intake table) and returns a reference ID
 *   4. User sees a confirmation — no account provisioned automatically
 *   5. Admin reviews and converts to Pipeline A or B invite
 *
 * Phase 856B scope: POST to /intake/request backend endpoint.
 * The backend endpoint is created in this phase.
 *
 * Design is intentionally aligned with /early-access (same brand panel layout)
 * but collects richer data and stores it internally instead of Formspree.
 */

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import DMonogram from '../../../components/DMonogram';

const PORTFOLIO_OPTIONS = [
    { value: '', label: 'Portfolio size (optional)' },
    { value: '1-5', label: '1–5 listings' },
    { value: '5-20', label: '5–20 listings' },
    { value: '20+', label: '20+ listings' },
];

function GetStartedForm() {
    const searchParams = useSearchParams();
    const prefillEmail = searchParams?.get('email') || '';

    const [name, setName] = useState('');
    const [email, setEmail] = useState(prefillEmail);
    const [company, setCompany] = useState('');
    const [portfolio, setPortfolio] = useState('');
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);
    const [submitted, setSubmitted] = useState(false);
    const [referenceId, setReferenceId] = useState('');
    const [error, setError] = useState<string | null>(null);

    // Sync prefill if URL param arrives after mount
    useEffect(() => {
        if (prefillEmail && !email) setEmail(prefillEmail);
    }, [prefillEmail]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!email.trim()) { setError('Email is required'); return; }
        if (!name.trim()) { setError('Name is required'); return; }
        setError(null);
        setLoading(true);
        try {
            const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
            const resp = await fetch(`${BASE}/intake/request`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name.trim(),
                    email: email.trim(),
                    company: company.trim(),
                    portfolio_size: portfolio,
                    message: message.trim(),
                    source: 'get-started',
                }),
            });
            const body = await resp.json();
            if (!resp.ok) {
                setError(body?.message || body?.error || 'Something went wrong. Please email info@domaniqo.com.');
                return;
            }
            setReferenceId(body?.data?.reference_id || body?.reference_id || '');
            setSubmitted(true);
        } catch {
            setError('Network error. Please email info@domaniqo.com directly.');
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
            {/* Left: Brand panel */}
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
                    Get Started
                </div>
                <p style={{
                    fontSize: 'var(--text-base)',
                    color: 'rgba(234,229,222,0.35)',
                    textAlign: 'center',
                    maxWidth: 360,
                    lineHeight: 1.6,
                }}>
                    Tell us about your property operations.
                    We&apos;ll review your request and reach out with next steps.
                </p>

                <div style={{
                    marginTop: 'var(--space-8)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--space-4)',
                    maxWidth: 320,
                    width: '100%',
                }}>
                    {[
                        { icon: '✓', text: 'Reviewed by our team within 24 hours' },
                        { icon: '✓', text: 'No account auto-created — you stay in control' },
                        { icon: '✓', text: 'Invited to the platform once approved' },
                    ].map(item => (
                        <div key={item.text} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                            <span style={{ color: 'var(--color-copper)', fontWeight: 700, fontSize: 14, flexShrink: 0, paddingTop: 2 }}>{item.icon}</span>
                            <span style={{ fontSize: 'var(--text-sm)', color: 'rgba(234,229,222,0.4)', lineHeight: 1.5 }}>{item.text}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Right: Form panel */}
            <div style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 'var(--space-8) var(--space-6)',
            }}>
                <div style={{ width: '100%', maxWidth: 440 }}>
                    {submitted ? (
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: 48, marginBottom: 'var(--space-4)' }}>✅</div>
                            <h2 style={{
                                fontFamily: 'var(--font-display)',
                                fontSize: 'var(--text-2xl)',
                                color: 'var(--color-stone)',
                                marginBottom: 'var(--space-3)',
                            }}>
                                Request received
                            </h2>
                            <p style={{
                                fontSize: 'var(--text-base)',
                                color: 'rgba(234,229,222,0.4)',
                                lineHeight: 1.6,
                                marginBottom: 'var(--space-2)',
                            }}>
                                We&apos;ve received your request and will be in touch soon at the email you provided.
                            </p>
                            {referenceId && (
                                <p style={{
                                    fontSize: 'var(--text-xs)',
                                    color: 'rgba(234,229,222,0.2)',
                                    fontFamily: 'var(--font-mono)',
                                    marginBottom: 'var(--space-6)',
                                }}>
                                    Reference: {referenceId}
                                </p>
                            )}
                            <a
                                href="/"
                                style={{
                                    display: 'inline-block',
                                    marginTop: 'var(--space-2)',
                                    fontSize: 'var(--text-sm)',
                                    color: 'var(--color-copper)',
                                    textDecoration: 'none',
                                }}
                            >
                                ← Back to Domaniqo
                            </a>
                        </div>
                    ) : (
                        <>
                            <h1 style={{
                                fontFamily: 'var(--font-display)',
                                fontSize: 'var(--text-2xl)',
                                color: 'var(--color-stone)',
                                marginBottom: 'var(--space-2)',
                            }}>
                                Request Access
                            </h1>
                            <p style={{
                                fontSize: 'var(--text-sm)',
                                color: 'rgba(234,229,222,0.4)',
                                marginBottom: 'var(--space-6)',
                                lineHeight: 1.6,
                            }}>
                                Tell us about your property operations and we&apos;ll reach out with access details.
                            </p>

                            <form onSubmit={handleSubmit} style={{
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 'var(--space-4)',
                            }}>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                                    <div>
                                        <label style={labelStyle}>Name *</label>
                                        <input
                                            id="input-name"
                                            type="text"
                                            value={name}
                                            onChange={e => setName(e.target.value)}
                                            placeholder="Your name"
                                            required
                                            disabled={loading}
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
                                            disabled={loading}
                                            style={inputStyle}
                                        />
                                    </div>
                                </div>

                                <div>
                                    <label style={labelStyle}>Company / Property Group</label>
                                    <input
                                        id="input-company"
                                        type="text"
                                        value={company}
                                        onChange={e => setCompany(e.target.value)}
                                        placeholder="Your company or portfolio name"
                                        disabled={loading}
                                        style={inputStyle}
                                    />
                                </div>

                                <div>
                                    <label style={labelStyle}>Portfolio Size</label>
                                    <select
                                        id="input-portfolio"
                                        value={portfolio}
                                        onChange={e => setPortfolio(e.target.value)}
                                        disabled={loading}
                                        style={{ ...inputStyle, appearance: 'auto' as const }}
                                    >
                                        {PORTFOLIO_OPTIONS.map(opt => (
                                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                                        ))}
                                    </select>
                                </div>

                                <div>
                                    <label style={labelStyle}>Tell us more (optional)</label>
                                    <textarea
                                        id="input-message"
                                        value={message}
                                        onChange={e => setMessage(e.target.value)}
                                        placeholder="Which OTAs do you use? Any specific needs?"
                                        rows={4}
                                        disabled={loading}
                                        style={{ ...inputStyle, resize: 'none' }}
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
                                    id="btn-submit-get-started"
                                    type="submit"
                                    disabled={loading || !email.trim() || !name.trim()}
                                    style={{
                                        padding: '14px',
                                        background: 'var(--color-moss)',
                                        border: 'none',
                                        borderRadius: 'var(--radius-md)',
                                        color: 'var(--color-white)',
                                        fontSize: 'var(--text-base)',
                                        fontWeight: 600,
                                        fontFamily: 'var(--font-brand)',
                                        cursor: loading || !email.trim() || !name.trim() ? 'not-allowed' : 'pointer',
                                        opacity: loading || !email.trim() || !name.trim() ? 0.4 : 1,
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
                                Already have an account?{' '}
                                <a href="/login" style={{ color: 'rgba(234,229,222,0.35)', textDecoration: 'underline' }}>
                                    Sign in
                                </a>
                                {' '}· Or email info@domaniqo.com
                            </p>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

export default function GetStartedPage() {
    return (
        <Suspense fallback={null}>
            <GetStartedForm />
        </Suspense>
    );
}
