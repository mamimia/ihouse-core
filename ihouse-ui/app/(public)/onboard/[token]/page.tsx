'use client';

/**
 * Phase 388 — Property Owner Onboarding Flow
 * Route: /onboard/[token]
 *
 * Guided onboarding form for property owners: property details,
 * contact info, operational notes. Submission goes to admin review queue.
 */

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import DMonogram from '../../../../components/DMonogram';

export default function OnboardPage() {
    const params = useParams();
    const token = params?.token as string;
    const [valid, setValid] = useState<boolean | null>(null);
    const [step, setStep] = useState(1);
    const [submitted, setSubmitted] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    // Form state
    const [form, setForm] = useState({
        property_name: '',
        property_type: 'apartment',
        address: '',
        capacity: '',
        contact_name: '',
        contact_phone: '',
        contact_email: '',
        wifi_name: '',
        wifi_password: '',
        house_rules: '',
        special_notes: '',
    });

    const update = (field: string, value: string) =>
        setForm(prev => ({ ...prev, [field]: value }));

    useEffect(() => {
        if (!token) { setValid(false); return; }
        // Validate token
        const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
        fetch(`${API_BASE}/onboard/validate/${encodeURIComponent(token)}`)
            .then(r => setValid(r.ok))
            .catch(() => setValid(false));
    }, [token]);

    const handleSubmit = async () => {
        setSubmitting(true);
        try {
            const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
            await fetch(`${API_BASE}/onboard/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, ...form }),
            });
            setSubmitted(true);
        } catch {
            // Show error in real implementation
        } finally {
            setSubmitting(false);
        }
    };

    // Error state
    if (valid === false) {
        return (
            <div style={{
                minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column', gap: 'var(--space-4, 16px)', padding: 'var(--space-6, 24px)', textAlign: 'center',
            }}>
                <DMonogram size={48} />
                <h1 style={{ fontSize: 'var(--text-xl, 22px)', fontWeight: 800, color: 'var(--color-text, #f9fafb)', margin: 0 }}>
                    Invalid Onboarding Link
                </h1>
                <p style={{ fontSize: 'var(--text-sm, 14px)', color: 'var(--color-text-dim, #6b7280)', maxWidth: 340 }}>
                    This onboarding link is not valid. Please contact your property manager.
                </p>
            </div>
        );
    }

    // Loading
    if (valid === null) {
        return (
            <div style={{
                minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column', gap: 'var(--space-3, 12px)',
            }}>
                <DMonogram size={40} />
                <div style={{ fontSize: 'var(--text-sm, 14px)', color: 'var(--color-text-dim, #6b7280)', animation: 'pulse 1.5s infinite' }}>
                    Validating…
                </div>
                <style>{`@keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }`}</style>
            </div>
        );
    }

    // Success
    if (submitted) {
        return (
            <div style={{
                minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column', gap: 'var(--space-4, 16px)', padding: 'var(--space-6, 24px)', textAlign: 'center',
            }}>
                <div style={{ fontSize: 64 }}>🏠</div>
                <h1 style={{ fontSize: 'var(--text-xl, 22px)', fontWeight: 800, color: 'var(--color-text, #f9fafb)', margin: 0 }}>
                    Property Submitted!
                </h1>
                <p style={{ fontSize: 'var(--text-sm, 14px)', color: 'var(--color-text-dim, #6b7280)', maxWidth: 340 }}>
                    Your property information has been submitted for review. Our team will get back to you shortly.
                </p>
                <div style={{ fontSize: 'var(--text-xs, 11px)', color: 'var(--color-text-faint, #4b5563)', marginTop: 'var(--space-4, 16px)' }}>
                    info@domaniqo.com
                </div>
            </div>
        );
    }

    const inputStyle: React.CSSProperties = {
        width: '100%', background: 'var(--color-bg, #111827)',
        border: '1px solid var(--color-border, #374151)',
        borderRadius: 'var(--radius-md, 12px)',
        color: 'var(--color-text, #f9fafb)',
        fontSize: 14, padding: 'var(--space-3, 12px) var(--space-3, 14px)',
        outline: 'none', boxSizing: 'border-box' as const,
        fontFamily: 'var(--font-sans, inherit)',
    };

    const labelStyle: React.CSSProperties = {
        fontSize: 'var(--text-xs, 12px)', color: 'var(--color-text-dim, #9ca3af)',
        fontWeight: 600, marginBottom: 'var(--space-1, 6px)', display: 'block',
    };

    const totalSteps = 3;

    return (
        <>
            <style>{`@keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }`}</style>
            <div style={{
                maxWidth: 480, margin: '0 auto',
                padding: 'var(--space-5, 20px) var(--space-4, 16px)',
                minHeight: '100vh', animation: 'fadeIn 400ms ease',
            }}>
                {/* Header */}
                <div style={{ textAlign: 'center', marginBottom: 'var(--space-5, 20px)' }}>
                    <DMonogram size={36} />
                    <h1 style={{
                        fontSize: 'var(--text-xl, 22px)', fontWeight: 800,
                        color: 'var(--color-text, #f9fafb)',
                        margin: 'var(--space-3, 12px) 0 var(--space-1, 4px)',
                    }}>
                        Property Onboarding
                    </h1>
                    <p style={{ fontSize: 'var(--text-sm, 13px)', color: 'var(--color-text-dim, #6b7280)', margin: 0 }}>
                        Step {step} of {totalSteps}
                    </p>
                    {/* Progress bar */}
                    <div style={{
                        height: 4, background: 'var(--color-surface-3, #1f2937)',
                        borderRadius: 99, marginTop: 'var(--space-3, 12px)', overflow: 'hidden',
                    }}>
                        <div style={{
                            height: '100%', width: `${(step / totalSteps) * 100}%`,
                            background: 'var(--color-primary, #3b82f6)',
                            borderRadius: 99, transition: 'width 0.3s ease',
                        }} />
                    </div>
                </div>

                {/* Steps */}
                <div style={{
                    background: 'var(--color-surface, #1a1f2e)',
                    border: '1px solid var(--color-border, #ffffff12)',
                    borderRadius: 'var(--radius-lg, 16px)',
                    padding: 'var(--space-5, 24px)',
                    marginBottom: 'var(--space-4, 16px)',
                }}>
                    {step === 1 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                            <h2 style={{ fontSize: 'var(--text-lg, 18px)', fontWeight: 700, color: 'var(--color-text, #f9fafb)', margin: 0 }}>
                                🏠 Property Details
                            </h2>
                            <div>
                                <label style={labelStyle}>Property Name *</label>
                                <input id="onboard-name" value={form.property_name} onChange={e => update('property_name', e.target.value)} placeholder="e.g. Sunrise Villa" style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>Property Type</label>
                                <select id="onboard-type" value={form.property_type} onChange={e => update('property_type', e.target.value)} style={inputStyle}>
                                    <option value="apartment">Apartment</option>
                                    <option value="villa">Villa</option>
                                    <option value="house">House</option>
                                    <option value="condo">Condo</option>
                                    <option value="studio">Studio</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                            <div>
                                <label style={labelStyle}>Address</label>
                                <input id="onboard-address" value={form.address} onChange={e => update('address', e.target.value)} placeholder="Full property address" style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>Max Capacity (guests)</label>
                                <input id="onboard-capacity" type="number" value={form.capacity} onChange={e => update('capacity', e.target.value)} placeholder="e.g. 4" style={inputStyle} />
                            </div>
                        </div>
                    )}

                    {step === 2 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                            <h2 style={{ fontSize: 'var(--text-lg, 18px)', fontWeight: 700, color: 'var(--color-text, #f9fafb)', margin: 0 }}>
                                👤 Contact Information
                            </h2>
                            <div>
                                <label style={labelStyle}>Contact Name *</label>
                                <input id="onboard-contact" value={form.contact_name} onChange={e => update('contact_name', e.target.value)} style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>Phone</label>
                                <input id="onboard-phone" value={form.contact_phone} onChange={e => update('contact_phone', e.target.value)} placeholder="+66..." style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>Email</label>
                                <input id="onboard-email" type="email" value={form.contact_email} onChange={e => update('contact_email', e.target.value)} style={inputStyle} />
                            </div>
                        </div>
                    )}

                    {step === 3 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                            <h2 style={{ fontSize: 'var(--text-lg, 18px)', fontWeight: 700, color: 'var(--color-text, #f9fafb)', margin: 0 }}>
                                📋 Operational Details
                            </h2>
                            <div>
                                <label style={labelStyle}>Wi-Fi Network Name</label>
                                <input id="onboard-wifi" value={form.wifi_name} onChange={e => update('wifi_name', e.target.value)} style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>Wi-Fi Password</label>
                                <input id="onboard-wifi-pw" value={form.wifi_password} onChange={e => update('wifi_password', e.target.value)} style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>House Rules</label>
                                <textarea id="onboard-rules" value={form.house_rules} onChange={e => update('house_rules', e.target.value)} rows={3} placeholder="One rule per line" style={{ ...inputStyle, resize: 'none' }} />
                            </div>
                            <div>
                                <label style={labelStyle}>Special Notes</label>
                                <textarea id="onboard-notes" value={form.special_notes} onChange={e => update('special_notes', e.target.value)} rows={3} placeholder="Any additional information…" style={{ ...inputStyle, resize: 'none' }} />
                            </div>
                        </div>
                    )}
                </div>

                {/* Navigation */}
                <div style={{ display: 'flex', gap: 'var(--space-2, 8px)' }}>
                    {step > 1 && (
                        <button
                            onClick={() => setStep(s => s - 1)}
                            style={{
                                flex: 1, padding: 'var(--space-3, 14px)', borderRadius: 'var(--radius-md, 14px)',
                                border: '1px solid var(--color-border, #374151)', background: 'transparent',
                                color: 'var(--color-text-dim, #9ca3af)', fontWeight: 600, fontSize: 15, cursor: 'pointer',
                            }}
                        >
                            ← Back
                        </button>
                    )}
                    {step < totalSteps ? (
                        <button
                            onClick={() => setStep(s => s + 1)}
                            style={{
                                flex: 1, padding: 'var(--space-3, 14px)', borderRadius: 'var(--radius-md, 14px)',
                                border: 'none',
                                background: 'linear-gradient(135deg, var(--color-primary, #3b82f6), #2563eb)',
                                color: '#fff', fontWeight: 700, fontSize: 15, cursor: 'pointer',
                                boxShadow: '0 0 16px rgba(59,130,246,0.3)',
                            }}
                        >
                            Next →
                        </button>
                    ) : (
                        <button
                            id="onboard-submit"
                            disabled={submitting || !form.property_name}
                            onClick={handleSubmit}
                            style={{
                                flex: 1, padding: 'var(--space-3, 14px)', borderRadius: 'var(--radius-md, 14px)',
                                border: 'none',
                                background: submitting ? 'var(--color-surface-3, #1f2937)' : 'linear-gradient(135deg, #22c55e, #16a34a)',
                                color: submitting ? 'var(--color-text-dim, #6b7280)' : '#fff',
                                fontWeight: 700, fontSize: 15,
                                cursor: submitting ? 'not-allowed' : 'pointer',
                                boxShadow: '0 0 16px rgba(34,197,94,0.3)',
                            }}
                        >
                            {submitting ? 'Submitting…' : '✅ Submit Property'}
                        </button>
                    )}
                </div>

                <div style={{
                    textAlign: 'center', fontSize: 'var(--text-xs, 11px)',
                    color: 'var(--color-text-faint, #4b5563)',
                    padding: 'var(--space-6, 24px)',
                }}>
                    Powered by Domaniqo · info@domaniqo.com
                </div>
            </div>
        </>
    );
}
