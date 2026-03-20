'use client';

/**
 * Phase 858 — Progressive Get Started Wizard
 * Route: /get-started
 *
 * 10-step progressive wizard optimized for mobile-first.
 * Auth is deferred until step 7 (after first value moment).
 *
 * Steps:
 *   1. Portfolio size (1-5 / 5-20 / 20+)
 *   2. Platform selection (Airbnb, Booking, etc.)
 *   3. Import mode (link / manual / connect-coming-soon)
 *   4. Paste listing URLs
 *   5. Property preview / review (first value moment)
 *   6. Operational details (optional)
 *   7. Auth trigger (email/code or Google)
 *   8. Profile collection
 *   9. Review & submit
 *  10. Post-submit confirmation
 */

import { useState, useCallback, useEffect } from 'react';
import Link from 'next/link';
import DMonogram from '@/components/DMonogram';

/* ─────────── Constants ─────────── */

const STORAGE_KEY = 'domaniqo_get_started_state';
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

interface Platform {
    id: string;
    name: string;
    subtitle?: string;
    status: 'supported' | 'beta' | 'coming_soon';
    urlExample: string;
    icon: string;
}

const PLATFORMS: Platform[] = [
    { id: 'airbnb', name: 'Airbnb', status: 'supported', urlExample: 'https://www.airbnb.com/rooms/12345678', icon: '🏠' },
    { id: 'booking', name: 'Booking.com', status: 'supported', urlExample: 'https://www.booking.com/hotel/th/your-hotel.html', icon: '🔵' },
    { id: 'vrbo', name: 'Vrbo', subtitle: 'Vrbo.com, Abritel, FeWo-Direkt, Stayz', status: 'beta', urlExample: 'https://www.vrbo.com/12345', icon: '🌊' },
    { id: 'expedia', name: 'Expedia', subtitle: 'Hotels.com, Orbitz, Trivago', status: 'coming_soon', urlExample: '', icon: '✈️' },
    { id: 'agoda', name: 'Agoda', status: 'coming_soon', urlExample: '', icon: '🔴' },
    { id: 'other', name: 'Other', status: 'supported', urlExample: '', icon: '🌐' },
];

const PORTFOLIO_OPTIONS = [
    { id: '1-5', label: '1–5 properties', desc: 'Getting started' },
    { id: '5-20', label: '5–20 properties', desc: 'Growing portfolio' },
    { id: '20+', label: '20+ properties', desc: 'Established manager' },
];

type Step = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;
type ImportMode = 'link' | 'manual' | 'connect';

interface PropertyDraft {
    name: string;
    type: string;
    city: string;
    country: string;
    guests: string;
    bedrooms: string;
    beds: string;
    bathrooms: string;
    description: string;
    address: string;
    wifi_name: string;
    wifi_password: string;
    check_in: string;
    check_out: string;
    house_rules: string;
    source_url: string;
    source_platform: string;
}

const EMPTY_DRAFT: PropertyDraft = {
    name: '', type: '', city: '', country: '',
    guests: '', bedrooms: '', beds: '', bathrooms: '',
    description: '', address: '',
    wifi_name: '', wifi_password: '', check_in: '', check_out: '', house_rules: '',
    source_url: '', source_platform: '',
};

interface WizardState {
    step: Step;
    portfolioSize: string;
    selectedPlatforms: string[];
    importMode: ImportMode | '';
    urls: Record<string, string>;
    notListed: boolean;
    property: PropertyDraft;
    extracting: boolean;
    extractedCount: number;
}

/* ─────────── Styles ─────────── */

const card: React.CSSProperties = {
    background: 'var(--color-elevated, #1E2127)',
    border: '1px solid rgba(234,229,222,0.06)',
    borderRadius: 'var(--radius-lg, 16px)',
    padding: 'var(--space-6, 24px)',
};

const inputStyle: React.CSSProperties = {
    width: '100%', padding: '12px 14px',
    background: 'var(--color-midnight, #171A1F)',
    border: '1px solid rgba(234,229,222,0.1)',
    borderRadius: 'var(--radius-md, 12px)',
    color: 'var(--color-stone, #EAE5DE)',
    fontSize: 'var(--text-sm, 14px)',
    fontFamily: 'var(--font-sans, inherit)',
    outline: 'none', boxSizing: 'border-box' as const,
    transition: 'border-color 0.2s',
};

const label: React.CSSProperties = {
    display: 'block', fontSize: 'var(--text-xs, 12px)', fontWeight: 600,
    color: 'rgba(234,229,222,0.5)', marginBottom: 6,
    textTransform: 'uppercase', letterSpacing: '0.06em',
};

const primaryBtn: React.CSSProperties = {
    width: '100%', padding: '14px',
    background: 'var(--color-moss, #334036)', border: 'none',
    borderRadius: 'var(--radius-md, 12px)',
    color: 'var(--color-white, #F8F6F2)',
    fontSize: 'var(--text-base, 16px)', fontWeight: 600,
    fontFamily: 'var(--font-brand, inherit)',
    cursor: 'pointer', transition: 'all 0.2s', minHeight: 48,
};

const ghostBtn: React.CSSProperties = {
    ...primaryBtn,
    background: 'transparent',
    border: '1px solid rgba(234,229,222,0.12)',
    color: 'rgba(234,229,222,0.5)',
};

const disabledStyle = (disabled: boolean): React.CSSProperties => ({
    opacity: disabled ? 0.35 : 1,
    cursor: disabled ? 'not-allowed' : 'pointer',
});

/* ─────────── Page ─────────── */

export default function GetStartedWizard() {
    const [state, setState] = useState<WizardState>({
        step: 1,
        portfolioSize: '',
        selectedPlatforms: [],
        importMode: '',
        urls: {},
        notListed: false,
        property: { ...EMPTY_DRAFT },
        extracting: false,
        extractedCount: 0,
    });

    const [submitting, setSubmitting] = useState(false);
    const [submitResult, setSubmitResult] = useState<{ propertyId: string; refId?: string } | null>(null);

    // Persist wizard state to sessionStorage
    useEffect(() => {
        const saved = sessionStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                setState(prev => ({ ...prev, ...parsed, extracting: false }));
            } catch { /* ignore corrupt state */ }
        }
    }, []);

    useEffect(() => {
        if (state.step < 10) {
            const toSave = { ...state, extracting: false };
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
        }
    }, [state]);

    const setStep = (step: Step) => setState(prev => ({ ...prev, step }));
    const updateProperty = (key: keyof PropertyDraft, value: string) =>
        setState(prev => ({ ...prev, property: { ...prev.property, [key]: value } }));

    const togglePlatform = (id: string) => {
        setState(prev => {
            const set = new Set(prev.selectedPlatforms);
            if (set.has(id)) set.delete(id); else set.add(id);
            return { ...prev, selectedPlatforms: Array.from(set), notListed: false };
        });
    };

    const handleNotListed = () => {
        setState(prev => ({ ...prev, selectedPlatforms: [], notListed: true }));
    };

    const updateUrl = (platformId: string, url: string) => {
        setState(prev => ({ ...prev, urls: { ...prev.urls, [platformId]: url } }));
    };

    /* ─── URL Import ─── */
    const runImport = useCallback(async () => {
        const firstUrl = Object.values(state.urls).find(u => u.trim());
        if (!firstUrl) return;

        setState(prev => ({ ...prev, extracting: true }));
        try {
            const res = await fetch('/api/listing/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: firstUrl }),
            });
            const data = await res.json();

            if (data.success && data.extracted) {
                const ext = data.extracted;
                setState(prev => ({
                    ...prev,
                    extracting: false,
                    extractedCount: Object.keys(ext).length,
                    property: {
                        ...prev.property,
                        name: ext.display_name || prev.property.name,
                        type: ext.property_type || prev.property.type,
                        city: ext.city || prev.property.city,
                        country: ext.country || prev.property.country,
                        guests: ext.max_guests ? String(ext.max_guests) : prev.property.guests,
                        bedrooms: ext.bedrooms !== undefined ? String(ext.bedrooms) : prev.property.bedrooms,
                        beds: ext.beds ? String(ext.beds) : prev.property.beds,
                        bathrooms: ext.bathrooms ? String(ext.bathrooms) : prev.property.bathrooms,
                        description: ext.description || prev.property.description,
                        address: ext.address || prev.property.address,
                        source_url: firstUrl,
                        source_platform: data.source_platform || '',
                    },
                }));
            } else {
                // Import failed — continue with manual
                setState(prev => ({
                    ...prev,
                    extracting: false,
                    extractedCount: 0,
                    property: { ...prev.property, source_url: firstUrl },
                }));
            }
        } catch {
            setState(prev => ({
                ...prev,
                extracting: false,
                extractedCount: 0,
                property: { ...prev.property, source_url: Object.values(prev.urls).find(u => u.trim()) || '' },
            }));
        }
    }, [state.urls]);

    /* ─── Submit ─── */
    const handleSubmit = async () => {
        setSubmitting(true);
        try {
            const res = await fetch('/api/onboard', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    propertyName: state.property.name.trim(),
                    propertyType: state.property.type,
                    city: state.property.city,
                    country: state.property.country,
                    maxGuests: state.property.guests,
                    bedrooms: state.property.bedrooms,
                    beds: state.property.beds,
                    bathrooms: state.property.bathrooms,
                    address: state.property.address,
                    description: state.property.description,
                    sourceUrl: state.property.source_url,
                    sourcePlatform: state.property.source_platform,
                    channels: state.selectedPlatforms
                        .filter(id => state.urls[id]?.trim())
                        .map(id => ({ provider: id, url: state.urls[id] })),
                }),
            });
            const data = await res.json();

            if (data.success) {
                setSubmitResult({ propertyId: data.property_id, refId: data.property_id });
                sessionStorage.removeItem(STORAGE_KEY);
                setStep(10);
            } else if (data.conflict) {
                alert(`This listing is already submitted: ${data.message || 'Duplicate detected.'}`);
            } else {
                alert(data.error || 'Submission failed. Please try again.');
            }
        } catch {
            alert('Network error. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    /* ─── Progress ─── */
    const totalSteps = state.notListed || state.importMode === 'manual' ? 8 : 9;
    const displayStep = state.step <= totalSteps ? state.step : totalSteps;

    /* ─── Render ─── */
    return (
        <>
            <style>{`
                @keyframes fadeSlideIn { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
                .gs-fade { animation: fadeSlideIn 400ms ease both; }
                .gs-option { cursor:pointer; transition: all 0.2s; }
                .gs-option:hover { border-color: rgba(234,229,222,0.2) !important; }
                .gs-option.active { border-color: var(--color-copper, #B56E45) !important; background: rgba(181,110,69,0.06) !important; }
                .gs-input:focus { border-color: var(--color-copper, #B56E45) !important; }
            `}</style>

            <div
                className="grain-overlay"
                style={{
                    minHeight: '100vh',
                    background: 'var(--color-midnight, #171A1F)',
                    paddingTop: 'var(--header-height, 72px)',
                }}
            >
                <div style={{
                    maxWidth: 560, margin: '0 auto',
                    padding: 'var(--space-8, 32px) var(--space-4, 16px)',
                }}>
                    {/* Header */}
                    {state.step < 10 && (
                        <div className="gs-fade" style={{ textAlign: 'center', marginBottom: 'var(--space-6, 24px)' }}>
                            <DMonogram size={36} color="var(--color-stone, #EAE5DE)" strokeWidth={1.2} />
                            <h1 style={{
                                fontFamily: 'var(--font-display, serif)',
                                fontSize: 'var(--text-2xl, 28px)',
                                color: 'var(--color-stone, #EAE5DE)',
                                margin: '16px 0 6px', fontWeight: 400,
                            }}>
                                Get Started
                            </h1>

                            {/* Progress bar */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center', margin: '12px 0 8px' }}>
                                <span style={{ fontSize: 12, color: 'rgba(234,229,222,0.3)' }}>
                                    Step {displayStep} of {totalSteps}
                                </span>
                            </div>
                            <div style={{
                                height: 3, background: 'rgba(234,229,222,0.06)',
                                borderRadius: 99, overflow: 'hidden',
                            }}>
                                <div style={{
                                    height: '100%', width: `${(displayStep / totalSteps) * 100}%`,
                                    background: 'var(--color-copper, #B56E45)',
                                    borderRadius: 99, transition: 'width 0.4s ease',
                                }} />
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 1: Portfolio Size ═══════ */}
                    {state.step === 1 && (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            <p style={{
                                fontSize: 'var(--text-base, 16px)', color: 'var(--color-stone, #EAE5DE)',
                                fontWeight: 600, margin: '0 0 4px', textAlign: 'center',
                            }}>
                                How many properties do you manage?
                            </p>

                            {PORTFOLIO_OPTIONS.map(opt => (
                                <div
                                    key={opt.id}
                                    className={`gs-option ${state.portfolioSize === opt.id ? 'active' : ''}`}
                                    onClick={() => setState(prev => ({ ...prev, portfolioSize: opt.id }))}
                                    style={{ ...card, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14 }}
                                >
                                    <div style={{
                                        width: 22, height: 22, borderRadius: 11,
                                        border: `2px solid ${state.portfolioSize === opt.id ? 'var(--color-copper)' : 'rgba(234,229,222,0.15)'}`,
                                        background: state.portfolioSize === opt.id ? 'var(--color-copper)' : 'transparent',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        fontSize: 11, color: '#fff', fontWeight: 700, flexShrink: 0,
                                    }}>
                                        {state.portfolioSize === opt.id && '✓'}
                                    </div>
                                    <div>
                                        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-stone)' }}>{opt.label}</div>
                                        <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.3)', marginTop: 2 }}>{opt.desc}</div>
                                    </div>
                                </div>
                            ))}

                            <button
                                onClick={() => setStep(2)}
                                disabled={!state.portfolioSize}
                                style={{ ...primaryBtn, marginTop: 8, ...disabledStyle(!state.portfolioSize) }}
                            >
                                Continue →
                            </button>

                            <div style={{ textAlign: 'center', marginTop: 12 }}>
                                <Link href="/login" style={{ fontSize: 'var(--text-sm, 14px)', color: 'rgba(234,229,222,0.4)', textDecoration: 'none' }}>
                                    Already a user? <span style={{ textDecoration: 'underline' }}>Log in</span>
                                </Link>
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 2: Platform Selection ═══════ */}
                    {state.step === 2 && (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                            <p style={{
                                fontSize: 'var(--text-base, 16px)', color: 'var(--color-stone)',
                                fontWeight: 600, margin: '0 0 4px', textAlign: 'center',
                            }}>
                                Where are your properties listed?
                            </p>

                            {PLATFORMS.map(p => {
                                const isActive = state.selectedPlatforms.includes(p.id);
                                return (
                                    <div
                                        key={p.id}
                                        className={`gs-option ${isActive ? 'active' : ''}`}
                                        onClick={() => togglePlatform(p.id)}
                                        style={{ ...card, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14 }}
                                    >
                                        <div style={{
                                            width: 22, height: 22, borderRadius: 6,
                                            border: `2px solid ${isActive ? 'var(--color-copper)' : 'rgba(234,229,222,0.15)'}`,
                                            background: isActive ? 'var(--color-copper)' : 'transparent',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            fontSize: 12, color: '#fff', fontWeight: 700, flexShrink: 0,
                                        }}>
                                            {isActive && '✓'}
                                        </div>
                                        <span style={{ fontSize: 18, flexShrink: 0 }}>{p.icon}</span>
                                        <div style={{ flex: 1 }}>
                                            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-stone)' }}>
                                                {p.name}
                                                {p.status === 'beta' && (
                                                    <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-copper)', marginLeft: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Beta</span>
                                                )}
                                                {p.status === 'coming_soon' && (
                                                    <span style={{ fontSize: 10, fontWeight: 700, color: 'rgba(234,229,222,0.25)', marginLeft: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Coming soon</span>
                                                )}
                                            </div>
                                            {p.subtitle && (
                                                <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.25)', marginTop: 2 }}>{p.subtitle}</div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}

                            {/* Not listed option */}
                            <div
                                className={`gs-option ${state.notListed ? 'active' : ''}`}
                                onClick={handleNotListed}
                                style={{ ...card, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14, marginTop: 4 }}
                            >
                                <div style={{
                                    width: 22, height: 22, borderRadius: 6,
                                    border: `2px solid ${state.notListed ? 'var(--color-copper)' : 'rgba(234,229,222,0.15)'}`,
                                    background: state.notListed ? 'var(--color-copper)' : 'transparent',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: 12, color: '#fff', fontWeight: 700, flexShrink: 0,
                                }}>
                                    {state.notListed && '✓'}
                                </div>
                                <span style={{ fontSize: 18, flexShrink: 0 }}>📋</span>
                                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-stone)' }}>
                                    Not listed anywhere yet
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
                                <button onClick={() => setStep(1)} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
                                <button
                                    onClick={() => {
                                        if (state.notListed) {
                                            setState(prev => ({ ...prev, importMode: 'manual' }));
                                            setStep(5);
                                        } else {
                                            setStep(3);
                                        }
                                    }}
                                    disabled={state.selectedPlatforms.length === 0 && !state.notListed}
                                    style={{ ...primaryBtn, flex: 2, ...disabledStyle(state.selectedPlatforms.length === 0 && !state.notListed) }}
                                >
                                    Continue →
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 3: Import Mode ═══════ */}
                    {state.step === 3 && (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            <p style={{
                                fontSize: 'var(--text-base, 16px)', color: 'var(--color-stone)',
                                fontWeight: 600, margin: '0 0 4px', textAlign: 'center',
                            }}>
                                How would you like to add your property?
                            </p>

                            {/* Paste listing link */}
                            <div
                                className={`gs-option ${state.importMode === 'link' ? 'active' : ''}`}
                                onClick={() => setState(prev => ({ ...prev, importMode: 'link' }))}
                                style={{ ...card, padding: '16px 18px', cursor: 'pointer' }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
                                    <span style={{ fontSize: 20 }}>🔗</span>
                                    <div>
                                        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-stone)' }}>Paste listing link</div>
                                        <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.35)', marginTop: 2 }}>We'll import what we can from your listing page</div>
                                    </div>
                                </div>
                            </div>

                            {/* Manual entry */}
                            <div
                                className={`gs-option ${state.importMode === 'manual' ? 'active' : ''}`}
                                onClick={() => setState(prev => ({ ...prev, importMode: 'manual' }))}
                                style={{ ...card, padding: '16px 18px', cursor: 'pointer' }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
                                    <span style={{ fontSize: 20 }}>✏️</span>
                                    <div>
                                        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-stone)' }}>Set up manually</div>
                                        <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.35)', marginTop: 2 }}>Enter your property details yourself</div>
                                    </div>
                                </div>
                            </div>

                            {/* Connect account — Coming soon */}
                            <div
                                className="gs-option"
                                onClick={() => setState(prev => ({ ...prev, importMode: 'connect' }))}
                                style={{
                                    ...card, padding: '16px 18px', cursor: 'pointer',
                                    opacity: 0.5,
                                    ...(state.importMode === 'connect' ? { borderColor: 'var(--color-copper)', background: 'rgba(181,110,69,0.06)' } : {}),
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <span style={{ fontSize: 20 }}>🔌</span>
                                    <div>
                                        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-stone)' }}>
                                            Connect account
                                            <span style={{
                                                fontSize: 10, fontWeight: 700, color: 'rgba(234,229,222,0.3)',
                                                marginLeft: 8, textTransform: 'uppercase', letterSpacing: '0.06em',
                                                background: 'rgba(234,229,222,0.06)', padding: '2px 6px', borderRadius: 4,
                                            }}>Coming soon</span>
                                        </div>
                                        <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.25)', marginTop: 2 }}>
                                            Direct account connections are coming soon. For now, paste your listing link or set up manually.
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
                                <button onClick={() => setStep(2)} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
                                <button
                                    onClick={() => {
                                        if (state.importMode === 'link') setStep(4);
                                        else if (state.importMode === 'manual') setStep(5);
                                        else if (state.importMode === 'connect') {
                                            // Connect is coming soon — nudge to link import
                                            setState(prev => ({ ...prev, importMode: 'link' }));
                                            setStep(4);
                                        }
                                    }}
                                    disabled={!state.importMode}
                                    style={{ ...primaryBtn, flex: 2, ...disabledStyle(!state.importMode) }}
                                >
                                    Continue →
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 4: Paste Listing URLs ═══════ */}
                    {state.step === 4 && (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            <div style={card}>
                                <div style={{
                                    fontSize: 12, color: 'rgba(234,229,222,0.35)', marginBottom: 16,
                                    lineHeight: 1.6, padding: '10px 14px',
                                    background: 'rgba(181,110,69,0.06)', borderRadius: 'var(--radius-md, 12px)',
                                    border: '1px solid rgba(181,110,69,0.1)',
                                }}>
                                    <strong style={{ color: 'var(--color-copper)' }}>How it works:</strong> Paste the full URL of your listing page. We'll pull publicly available data (name, location, capacity) to speed up your setup.
                                </div>

                                {state.selectedPlatforms.map(platformId => {
                                    const platform = PLATFORMS.find(p => p.id === platformId);
                                    if (!platform) return null;
                                    return (
                                        <div key={platformId} style={{ marginBottom: 20 }}>
                                            <label style={label}>
                                                {platform.icon} {platform.name} Listing URL
                                            </label>
                                            <input
                                                className="gs-input"
                                                type="url"
                                                value={state.urls[platformId] || ''}
                                                onChange={e => updateUrl(platformId, e.target.value)}
                                                placeholder={platform.urlExample || 'Paste listing URL'}
                                                style={inputStyle}
                                            />
                                            {platform.urlExample && (
                                                <div style={{ fontSize: 11, color: 'rgba(234,229,222,0.2)', marginTop: 4 }}>
                                                    Example: {platform.urlExample}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>

                            <div style={{ display: 'flex', gap: 10 }}>
                                <button onClick={() => setStep(3)} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
                                <button
                                    onClick={async () => {
                                        const hasUrl = Object.values(state.urls).some(u => u.trim());
                                        if (hasUrl) {
                                            await runImport();
                                        }
                                        setStep(5);
                                    }}
                                    disabled={state.extracting}
                                    style={{ ...primaryBtn, flex: 2, opacity: state.extracting ? 0.7 : 1 }}
                                >
                                    {state.extracting
                                        ? '⏳ Extracting listing data...'
                                        : Object.values(state.urls).some(u => u.trim())
                                            ? 'Import & Review →'
                                            : 'Skip — Set Up Manually →'
                                    }
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 5: Property Preview / Review ═══════ */}
                    {state.step === 5 && (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            {state.extractedCount > 0 && (
                                <div style={{
                                    ...card, padding: '14px 18px',
                                    background: 'rgba(74,124,89,0.06)',
                                    border: '1px solid rgba(74,124,89,0.15)',
                                }}>
                                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ok, #4A7C59)' }}>
                                        ✅ {state.extractedCount} fields extracted from your listing
                                    </div>
                                    <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.35)', marginTop: 4 }}>
                                        Review and edit anything below before continuing.
                                    </div>
                                </div>
                            )}

                            <div style={card}>
                                <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-stone)', margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span style={{ fontSize: 16 }}>🏠</span> Property Details
                                </h3>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                                    <div>
                                        <label style={label}>Property Name *</label>
                                        <input className="gs-input" value={state.property.name} onChange={e => updateProperty('name', e.target.value)} placeholder="e.g. Sunrise Villa Phuket" style={inputStyle} />
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={label}>Property Type</label>
                                            <select value={state.property.type} onChange={e => updateProperty('type', e.target.value)} style={inputStyle}>
                                                <option value="">Select</option>
                                                <option value="apartment">Apartment</option>
                                                <option value="villa">Villa</option>
                                                <option value="house">House</option>
                                                <option value="condo">Condo</option>
                                                <option value="studio">Studio</option>
                                                <option value="hotel">Hotel / Resort</option>
                                                <option value="other">Other</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label style={label}>Max Guests</label>
                                            <input className="gs-input" type="number" value={state.property.guests} onChange={e => updateProperty('guests', e.target.value)} placeholder="6" style={inputStyle} />
                                        </div>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={label}>Bedrooms</label>
                                            <input className="gs-input" type="number" value={state.property.bedrooms} onChange={e => updateProperty('bedrooms', e.target.value)} placeholder="3" style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={label}>Beds</label>
                                            <input className="gs-input" type="number" value={state.property.beds} onChange={e => updateProperty('beds', e.target.value)} placeholder="4" style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={label}>Baths</label>
                                            <input className="gs-input" type="number" value={state.property.bathrooms} onChange={e => updateProperty('bathrooms', e.target.value)} placeholder="2" style={inputStyle} />
                                        </div>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={label}>City</label>
                                            <input className="gs-input" value={state.property.city} onChange={e => updateProperty('city', e.target.value)} placeholder="e.g. Phuket" style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={label}>Country</label>
                                            <input className="gs-input" value={state.property.country} onChange={e => updateProperty('country', e.target.value)} placeholder="e.g. Thailand" style={inputStyle} />
                                        </div>
                                    </div>
                                    <div>
                                        <label style={label}>Full Address</label>
                                        <input className="gs-input" value={state.property.address} onChange={e => updateProperty('address', e.target.value)} placeholder="Street address" style={inputStyle} />
                                    </div>
                                    <div>
                                        <label style={label}>Description</label>
                                        <textarea className="gs-input" value={state.property.description} onChange={e => updateProperty('description', e.target.value)} rows={3} placeholder="Brief property description..." style={{ ...inputStyle, resize: 'none' as const }} />
                                    </div>
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 10 }}>
                                <button onClick={() => {
                                    if (state.importMode === 'link') setStep(4);
                                    else if (state.notListed) setStep(2);
                                    else setStep(3);
                                }} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
                                <button
                                    onClick={() => setStep(6)}
                                    disabled={!state.property.name.trim()}
                                    style={{ ...primaryBtn, flex: 2, ...disabledStyle(!state.property.name.trim()) }}
                                >
                                    Continue →
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 6: Operational Details (Optional) ═══════ */}
                    {state.step === 6 && (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            <div style={card}>
                                <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-stone)', margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span style={{ fontSize: 16 }}>📋</span> Operational Details
                                </h3>
                                <p style={{ fontSize: 12, color: 'rgba(234,229,222,0.3)', margin: '0 0 16px' }}>
                                    Optional — you can always add these later.
                                </p>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={label}>WiFi Name</label>
                                            <input className="gs-input" value={state.property.wifi_name} onChange={e => updateProperty('wifi_name', e.target.value)} placeholder="Network name" style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={label}>WiFi Password</label>
                                            <input className="gs-input" value={state.property.wifi_password} onChange={e => updateProperty('wifi_password', e.target.value)} placeholder="Password" style={inputStyle} />
                                        </div>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={label}>Check-in Time</label>
                                            <input className="gs-input" type="time" value={state.property.check_in} onChange={e => updateProperty('check_in', e.target.value)} style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={label}>Check-out Time</label>
                                            <input className="gs-input" type="time" value={state.property.check_out} onChange={e => updateProperty('check_out', e.target.value)} style={inputStyle} />
                                        </div>
                                    </div>
                                    <div>
                                        <label style={label}>House Rules</label>
                                        <textarea className="gs-input" value={state.property.house_rules} onChange={e => updateProperty('house_rules', e.target.value)} rows={3} placeholder="One rule per line" style={{ ...inputStyle, resize: 'none' as const }} />
                                    </div>
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 10 }}>
                                <button onClick={() => setStep(5)} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
                                <button onClick={() => setStep(9)} style={{ ...primaryBtn, flex: 2 }}>
                                    Review & Submit →
                                </button>
                            </div>

                            <button
                                onClick={() => setStep(9)}
                                style={{ ...ghostBtn, fontSize: 'var(--text-sm, 14px)', color: 'rgba(234,229,222,0.3)' }}
                            >
                                Skip for now →
                            </button>
                        </div>
                    )}

                    {/* ═══════ Step 9: Review & Submit ═══════ */}
                    {state.step === 9 && (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            <p style={{
                                fontSize: 'var(--text-base, 16px)', color: 'var(--color-stone)',
                                fontWeight: 600, margin: '0 0 4px', textAlign: 'center',
                            }}>
                                Ready to submit?
                            </p>

                            {/* Property card */}
                            <div style={{ ...card, padding: '18px' }}>
                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                                    <div style={{
                                        width: 48, height: 48, borderRadius: 'var(--radius-md, 12px)',
                                        background: 'rgba(74,124,89,0.08)', display: 'flex',
                                        alignItems: 'center', justifyContent: 'center', fontSize: 24, flexShrink: 0,
                                    }}>🏠</div>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-stone)' }}>
                                            {state.property.name || 'Unnamed Property'}
                                        </div>
                                        <div style={{ fontSize: 13, color: 'rgba(234,229,222,0.4)', marginTop: 2 }}>
                                            {[state.property.city, state.property.country].filter(Boolean).join(', ') || 'No location set'}
                                        </div>
                                        {state.property.type && (
                                            <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.25)', marginTop: 4, textTransform: 'capitalize' }}>
                                                {state.property.type} · {state.property.guests ? `${state.property.guests} guests` : ''} {state.property.bedrooms ? `· ${state.property.bedrooms} bed` : ''}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                                    <button onClick={() => setStep(5)} style={{ ...ghostBtn, flex: 1, fontSize: 13, padding: '8px 12px', minHeight: 36 }}>
                                        ✏️ Edit
                                    </button>
                                </div>
                            </div>

                            {/* Info banner */}
                            <div style={{
                                padding: '12px 16px', background: 'rgba(181,110,69,0.05)',
                                border: '1px solid rgba(181,110,69,0.1)',
                                borderRadius: 'var(--radius-md, 12px)',
                                fontSize: 13, color: 'rgba(234,229,222,0.5)', lineHeight: 1.6,
                            }}>
                                By submitting, your property will be reviewed by our team. We'll contact you once it's approved and ready to manage on Domaniqo.
                            </div>

                            <button
                                onClick={handleSubmit}
                                disabled={submitting || !state.property.name.trim()}
                                style={{ ...primaryBtn, ...disabledStyle(submitting || !state.property.name.trim()) }}
                            >
                                {submitting ? 'Submitting…' : 'Submit for Review →'}
                            </button>

                            <button onClick={() => setStep(6)} style={{ ...ghostBtn, fontSize: 'var(--text-sm, 14px)' }}>
                                ← Back
                            </button>
                        </div>
                    )}

                    {/* ═══════ Step 10: Post-Submit Confirmation ═══════ */}
                    {state.step === 10 && (
                        <div className="gs-fade" style={{ textAlign: 'center', padding: 'var(--space-8, 32px) 0' }}>
                            <DMonogram size={36} color="var(--color-stone, #EAE5DE)" strokeWidth={1.2} />

                            <div style={{
                                width: 72, height: 72, borderRadius: '50%',
                                background: 'rgba(74,124,89,0.1)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                margin: '20px auto', fontSize: 32,
                            }}>✓</div>

                            <h2 style={{
                                fontFamily: 'var(--font-display)',
                                fontSize: 'var(--text-2xl, 28px)',
                                color: 'var(--color-stone)', marginBottom: 12, fontWeight: 400,
                            }}>
                                Submitted for Review
                            </h2>

                            <p style={{
                                fontSize: 'var(--text-base)', color: 'rgba(234,229,222,0.4)',
                                lineHeight: 1.7, maxWidth: 380, margin: '0 auto 8px',
                            }}>
                                Your property has been submitted for review. Our team will review your submission and be in touch.
                            </p>

                            {submitResult?.propertyId && (
                                <div style={{
                                    fontSize: 12, color: 'rgba(234,229,222,0.25)',
                                    marginBottom: 24, fontFamily: 'monospace',
                                }}>
                                    Reference: {submitResult.propertyId}
                                </div>
                            )}

                            <div style={{
                                ...card, padding: '16px 20px', textAlign: 'left',
                                maxWidth: 380, margin: '0 auto 24px',
                            }}>
                                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-stone)', marginBottom: 10 }}>
                                    What happens next
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    {[
                                        { icon: '📋', text: 'Our team reviews your submission' },
                                        { icon: '📧', text: 'We\'ll contact you with next steps' },
                                        { icon: '✅', text: 'Once approved, you can start managing your property on Domaniqo' },
                                    ].map((item, i) => (
                                        <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                                            <span style={{ fontSize: 14, flexShrink: 0, marginTop: 1 }}>{item.icon}</span>
                                            <span style={{ fontSize: 13, color: 'rgba(234,229,222,0.5)', lineHeight: 1.5 }}>{item.text}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 300, margin: '0 auto' }}>
                                <Link href="/" style={{ ...primaryBtn, textDecoration: 'none', textAlign: 'center' }}>
                                    Back to Domaniqo
                                </Link>
                            </div>

                            <p style={{
                                fontSize: 'var(--text-xs)', color: 'rgba(234,229,222,0.15)', marginTop: 40,
                            }}>
                                Questions? Contact us at info@domaniqo.com
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
