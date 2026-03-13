'use client';

/**
 * Listing QuickStart — Onboarding Connection Wizard
 * Route: /onboard/connect
 *
 * Multi-step wizard that lets new users:
 *   1. Select which OTA platforms their property is listed on
 *   2. Paste their listing URL for each selected platform
 *   3. Review imported data with confidence indicators
 *   4. Complete missing fields and submit
 *
 * V1: Creates real property in Supabase via /api/onboard.
 * Formspree kept as notification fallback.
 * Backend scraper integration comes separately.
 */

import { useState, useCallback } from 'react';
import Link from 'next/link';
import DMonogram from '@/components/DMonogram';

/* ─────────── Constants ─────────── */

const FORMSPREE_URL = 'https://formspree.io/f/xldrgdzr';
const ONBOARD_API_URL = '/api/onboard';

interface Platform {
    id: string;
    name: string;
    subtitle?: string;
    supported: 'supported' | 'experimental' | 'coming_soon';
    urlPattern: string;
    urlExample: string;
    icon: string;
}

const PLATFORMS: Platform[] = [
    {
        id: 'airbnb', name: 'Airbnb', supported: 'supported',
        urlPattern: 'airbnb.com/rooms/', urlExample: 'https://www.airbnb.com/rooms/12345678',
        icon: '🏠',
    },
    {
        id: 'booking', name: 'Booking.com', supported: 'supported',
        urlPattern: 'booking.com/hotel/', urlExample: 'https://www.booking.com/hotel/th/your-hotel.html',
        icon: '🔵',
    },
    {
        id: 'vrbo', name: 'Vrbo',
        subtitle: 'Vrbo.com, Abritel.fr, FeWo-Direkt.de, Stayz.com.au',
        supported: 'experimental',
        urlPattern: 'vrbo.com/', urlExample: 'https://www.vrbo.com/12345',
        icon: '🌊',
    },
    {
        id: 'expedia', name: 'Expedia',
        subtitle: 'Hotels.com, Orbitz, Trivago, Wotif',
        supported: 'coming_soon',
        urlPattern: 'expedia.com/', urlExample: '',
        icon: '✈️',
    },
    {
        id: 'agoda', name: 'Agoda', supported: 'coming_soon',
        urlPattern: 'agoda.com/', urlExample: '',
        icon: '🔴',
    },
    {
        id: 'tripadvisor', name: 'TripAdvisor', supported: 'coming_soon',
        urlPattern: 'tripadvisor.com/', urlExample: '',
        icon: '🦉',
    },
];

type Step = 'select' | 'urls' | 'review' | 'complete' | 'manual';

interface ImportedField {
    key: string;
    label: string;
    value: string;
    confidence: 'imported' | 'estimated' | 'manual';
}

/* ─────────── Page ─────────── */

export default function OnboardConnectPage() {
    const [step, setStep] = useState<Step>('select');
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [urls, setUrls] = useState<Record<string, string>>({});
    const [submitting, setSubmitting] = useState(false);
    const [notListed, setNotListed] = useState(false);
    const [createdPropertyId, setCreatedPropertyId] = useState<string | null>(null);
    const [dbPersisted, setDbPersisted] = useState(false);
    const [extracting, setExtracting] = useState(false);
    const [extractError, setExtractError] = useState<string | null>(null);
    const [conflictProperty, setConflictProperty] = useState<{ property_id: string; display_name: string; status: string; created_at: string } | null>(null);

    // Property form state (for review/complete step)
    const [property, setProperty] = useState({
        name: '', type: '', city: '', region: '', country: '',
        guests: '', bedrooms: '', beds: '', bathrooms: '',
        description: '', address: '', wifi_name: '', wifi_password: '',
        house_rules: '', check_in: '', check_out: '',
    });
    const [importedFields, setImportedFields] = useState<ImportedField[]>([]);

    const togglePlatform = (id: string) => {
        setSelected(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            setNotListed(false);
            return next;
        });
    };

    const handleNotListed = () => {
        setSelected(new Set());
        setNotListed(true);
    };

    const updateUrl = (platformId: string, url: string) => {
        setUrls(prev => ({ ...prev, [platformId]: url }));
    };

    const updateField = (key: string, value: string) => {
        setProperty(prev => ({ ...prev, [key]: value }));
    };

    // Import fields from parser backend or fall back to manual entry
    const runImport = useCallback(async () => {
        const firstUrl = Object.values(urls).find(u => u.trim());
        if (!firstUrl) return;

        setExtracting(true);
        setExtractError(null);

        try {
            const res = await fetch('/api/listing/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: firstUrl }),
            });
            const data = await res.json();

            if (data.success && data.extracted) {
                // Pre-fill property form from extracted data
                const ext = data.extracted;
                const conf = data.confidence || {};
                setProperty(prev => ({
                    ...prev,
                    name: ext.display_name || prev.name,
                    type: ext.property_type || prev.type,
                    city: ext.city || prev.city,
                    country: ext.country || prev.country,
                    guests: ext.max_guests ? String(ext.max_guests) : prev.guests,
                    bedrooms: ext.bedrooms !== undefined ? String(ext.bedrooms) : prev.bedrooms,
                    beds: ext.beds ? String(ext.beds) : prev.beds,
                    bathrooms: ext.bathrooms ? String(ext.bathrooms) : prev.bathrooms,
                    description: ext.description || prev.description,
                    address: ext.address || prev.address,
                }));

                // Build imported fields with real confidence
                const fields: ImportedField[] = [
                    { key: 'source_url', label: 'Source URL', value: firstUrl, confidence: 'imported' },
                    { key: 'source_platform', label: 'Source Platform', value: data.source_platform || 'airbnb', confidence: 'imported' },
                ];

                const fieldMap: Array<{ key: string; label: string; extKey: string }> = [
                    { key: 'name', label: 'Property Name', extKey: 'display_name' },
                    { key: 'type', label: 'Property Type', extKey: 'property_type' },
                    { key: 'city', label: 'City', extKey: 'city' },
                    { key: 'country', label: 'Country', extKey: 'country' },
                    { key: 'guests', label: 'Max Guests', extKey: 'max_guests' },
                    { key: 'bedrooms', label: 'Bedrooms', extKey: 'bedrooms' },
                    { key: 'beds', label: 'Beds', extKey: 'beds' },
                    { key: 'bathrooms', label: 'Bathrooms', extKey: 'bathrooms' },
                    { key: 'address', label: 'Full Address', extKey: 'address' },
                    { key: 'description', label: 'Description', extKey: 'description' },
                ];

                fieldMap.forEach(f => {
                    const value = ext[f.extKey];
                    const confLevel = conf[f.extKey];
                    fields.push({
                        key: f.key,
                        label: f.label,
                        value: value != null ? String(value) : '',
                        confidence: value != null
                            ? (confLevel === 'estimated' ? 'estimated' : 'imported')
                            : 'manual',
                    });
                });

                setImportedFields(fields);
            } else {
                // Parser failed — fall back to manual flow
                setExtractError(data.error || 'Could not extract listing data.');
                fallbackManualImport(firstUrl);
            }
        } catch {
            setExtractError('Network error. Continuing with manual entry.');
            fallbackManualImport(firstUrl);
        } finally {
            setExtracting(false);
        }
    }, [urls]);

    /** Fallback: just save URL and platform, mark everything else manual */
    const fallbackManualImport = (url: string) => {
        let platform = 'unknown';
        if (url.includes('airbnb.com') || url.includes('airbnb.')) platform = 'airbnb';
        else if (url.includes('booking.com')) platform = 'booking';
        else if (url.includes('vrbo.com')) platform = 'vrbo';

        const fields: ImportedField[] = [
            { key: 'source_url', label: 'Source URL', value: url, confidence: 'imported' },
            { key: 'source_platform', label: 'Source Platform', value: platform, confidence: 'imported' },
        ];
        const manualFields = [
            { key: 'name', label: 'Property Name' },
            { key: 'type', label: 'Property Type' },
            { key: 'city', label: 'City' },
            { key: 'country', label: 'Country' },
            { key: 'guests', label: 'Max Guests' },
            { key: 'bedrooms', label: 'Bedrooms' },
            { key: 'beds', label: 'Beds' },
            { key: 'bathrooms', label: 'Bathrooms' },
            { key: 'address', label: 'Full Address' },
            { key: 'description', label: 'Description' },
        ];
        manualFields.forEach(f => {
            fields.push({ key: f.key, label: f.label, value: '', confidence: 'manual' });
        });
        setImportedFields(fields);
    };

    const handleSubmit = async () => {
        setSubmitting(true);
        try {
            // Detect source URL and platform from the first entered URL
            const firstUrl = Object.values(urls).find(u => u.trim()) || '';
            let sourcePlatform = '';
            if (firstUrl.includes('airbnb.com')) sourcePlatform = 'airbnb';
            else if (firstUrl.includes('booking.com')) sourcePlatform = 'booking';
            else if (firstUrl.includes('vrbo.com')) sourcePlatform = 'vrbo';

            // Build channel list from entered URLs
            const channels = Object.entries(urls)
                .filter(([, url]) => url.trim())
                .map(([provider, url]) => ({ provider, url }));

            // Step 1: Call real onboarding API → creates property in Supabase
            const apiPayload = {
                propertyName: property.name,
                propertyType: property.type,
                city: property.city,
                country: property.country,
                maxGuests: property.guests,
                bedrooms: property.bedrooms,
                beds: property.beds,
                bathrooms: property.bathrooms,
                address: property.address,
                description: property.description,
                sourceUrl: firstUrl,
                sourcePlatform,
                channels,
            };

            try {
                const apiRes = await fetch(ONBOARD_API_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(apiPayload),
                });
                const apiData = await apiRes.json();

                if (apiRes.status === 409 && apiData.conflict) {
                    // Duplicate URL detected — show conflict screen
                    setConflictProperty(apiData.existing_property);
                    setSubmitting(false);
                    return; // Don't proceed to complete
                }

                if (apiData.success) {
                    setCreatedPropertyId(apiData.property_id);
                    setDbPersisted(apiData.persisted === true);
                }
            } catch {
                // API unavailable — continue with Formspree fallback
                console.warn('[QuickStart] API route unavailable, using Formspree fallback');
            }

            // Step 2: Also send to Formspree as notification / backup
            try {
                await fetch(FORMSPREE_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                    body: JSON.stringify({
                        _subject: `Domaniqo QuickStart: ${property.name || 'New Property'}`,
                        selected_platforms: Array.from(selected),
                        listing_urls: urls,
                        property,
                        submitted_at: new Date().toISOString(),
                    }),
                });
            } catch {
                // Formspree failure is non-critical
            }

            setStep('complete');
        } catch {
            // Even on unexpected error, show success — data may have been partially captured
            setStep('complete');
        } finally {
            setSubmitting(false);
        }
    };

    const stepNumber = step === 'select' ? 1 : step === 'urls' ? 2 : step === 'review' ? 3 : step === 'manual' ? 3 : 4;
    const totalSteps = notListed ? 3 : 4;

    /* ─────────── Styles ─────────── */

    const cardSurface: React.CSSProperties = {
        background: 'var(--color-elevated, #1E2127)',
        border: '1px solid rgba(234,229,222,0.06)',
        borderRadius: 'var(--radius-lg, 16px)',
        padding: 'var(--space-6, 24px)',
    };

    const inputStyle: React.CSSProperties = {
        width: '100%',
        padding: '12px 14px',
        background: 'var(--color-midnight, #171A1F)',
        border: '1px solid rgba(234,229,222,0.1)',
        borderRadius: 'var(--radius-md, 12px)',
        color: 'var(--color-stone, #EAE5DE)',
        fontSize: 'var(--text-sm, 14px)',
        fontFamily: 'var(--font-sans, inherit)',
        outline: 'none',
        boxSizing: 'border-box' as const,
        transition: 'border-color 0.2s',
    };

    const labelStyle: React.CSSProperties = {
        display: 'block',
        fontSize: 'var(--text-xs, 12px)',
        fontWeight: 600,
        color: 'rgba(234,229,222,0.5)',
        marginBottom: 6,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
    };

    const primaryBtn: React.CSSProperties = {
        width: '100%',
        padding: '14px',
        background: 'var(--color-moss, #334036)',
        border: 'none',
        borderRadius: 'var(--radius-md, 12px)',
        color: 'var(--color-white, #F8F6F2)',
        fontSize: 'var(--text-base, 16px)',
        fontWeight: 600,
        fontFamily: 'var(--font-brand, inherit)',
        cursor: 'pointer',
        transition: 'all 0.2s',
        minHeight: 48,
    };

    const ghostBtn: React.CSSProperties = {
        ...primaryBtn,
        background: 'transparent',
        border: '1px solid rgba(234,229,222,0.12)',
        color: 'rgba(234,229,222,0.5)',
    };

    /* ─────────── Render ─────────── */

    return (
        <>
            <style>{`
                @keyframes fadeSlideIn { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
                .qs-fade { animation: fadeSlideIn 400ms ease both; }
                .qs-platform { cursor:pointer; transition: all 0.2s; }
                .qs-platform:hover { border-color: rgba(234,229,222,0.2) !important; }
                .qs-platform.active { border-color: var(--color-copper, #B56E45) !important; background: rgba(181,110,69,0.06) !important; }
                .qs-platform.disabled { opacity: 0.4; cursor: not-allowed; }
                .qs-input:focus { border-color: var(--color-copper, #B56E45) !important; }
                .qs-confidence-imported { color: var(--color-ok, #4A7C59); }
                .qs-confidence-estimated { color: var(--color-warn, #B56E45); }
                .qs-confidence-manual { color: rgba(234,229,222,0.3); }
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
                    maxWidth: 560,
                    margin: '0 auto',
                    padding: 'var(--space-8, 32px) var(--space-4, 16px)',
                }}>
                    {/* Header */}
                    <div className="qs-fade" style={{ textAlign: 'center', marginBottom: 'var(--space-6, 24px)' }}>
                        <DMonogram size={36} color="var(--color-stone, #EAE5DE)" strokeWidth={1.2} />
                        <h1 style={{
                            fontFamily: 'var(--font-display, serif)',
                            fontSize: 'var(--text-2xl, 28px)',
                            color: 'var(--color-stone, #EAE5DE)',
                            margin: '16px 0 6px',
                            fontWeight: 400,
                        }}>
                            {step === 'complete' ? 'You\u0027re all set' : 'Listing QuickStart'}
                        </h1>
                        {step !== 'complete' && (
                            <p style={{
                                fontSize: 'var(--text-sm, 14px)',
                                color: 'rgba(234,229,222,0.35)',
                                margin: '0 0 20px',
                                lineHeight: 1.6,
                            }}>
                                {step === 'select' && 'Where are your properties listed today?'}
                                {step === 'urls' && 'Paste your listing links. We\'ll import what we can.'}
                                {step === 'review' && 'Review and confirm your property details.'}
                                {step === 'manual' && 'Set up your property details.'}
                            </p>
                        )}

                        {/* Progress */}
                        {step !== 'complete' && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center', marginBottom: 8 }}>
                                <span style={{ fontSize: 12, color: 'rgba(234,229,222,0.3)' }}>
                                    Step {stepNumber} of {totalSteps}
                                </span>
                            </div>
                        )}
                        {step !== 'complete' && (
                            <div style={{
                                height: 3,
                                background: 'rgba(234,229,222,0.06)',
                                borderRadius: 99,
                                overflow: 'hidden',
                            }}>
                                <div style={{
                                    height: '100%',
                                    width: `${(stepNumber / totalSteps) * 100}%`,
                                    background: 'var(--color-copper, #B56E45)',
                                    borderRadius: 99,
                                    transition: 'width 0.4s ease',
                                }} />
                            </div>
                        )}
                    </div>

                    {/* ═══════ Step 1: Platform Selection ═══════ */}
                    {step === 'select' && (
                        <div className="qs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                            {PLATFORMS.map(p => {
                                const isDisabled = p.supported === 'coming_soon';
                                const isActive = selected.has(p.id);
                                return (
                                    <div
                                        key={p.id}
                                        className={`qs-platform ${isActive ? 'active' : ''} ${isDisabled ? 'disabled' : ''}`}
                                        onClick={() => !isDisabled && togglePlatform(p.id)}
                                        style={{
                                            ...cardSurface,
                                            padding: '14px 18px',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 14,
                                        }}
                                    >
                                        <div style={{
                                            width: 22, height: 22,
                                            borderRadius: 6,
                                            border: isActive
                                                ? '2px solid var(--color-copper, #B56E45)'
                                                : '2px solid rgba(234,229,222,0.15)',
                                            background: isActive ? 'var(--color-copper, #B56E45)' : 'transparent',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            fontSize: 12, color: '#fff', fontWeight: 700,
                                            flexShrink: 0,
                                            transition: 'all 0.2s',
                                        }}>
                                            {isActive && '✓'}
                                        </div>
                                        <span style={{ fontSize: 18, flexShrink: 0 }}>{p.icon}</span>
                                        <div style={{ flex: 1 }}>
                                            <div style={{
                                                fontSize: 'var(--text-base, 15px)',
                                                color: 'var(--color-stone, #EAE5DE)',
                                                fontWeight: 600,
                                            }}>
                                                {p.name}
                                                {p.supported === 'experimental' && (
                                                    <span style={{
                                                        fontSize: 10, fontWeight: 700,
                                                        color: 'var(--color-warn, #B56E45)',
                                                        marginLeft: 8,
                                                        textTransform: 'uppercase',
                                                        letterSpacing: '0.06em',
                                                    }}>Beta</span>
                                                )}
                                                {p.supported === 'coming_soon' && (
                                                    <span style={{
                                                        fontSize: 10, fontWeight: 700,
                                                        color: 'rgba(234,229,222,0.25)',
                                                        marginLeft: 8,
                                                        textTransform: 'uppercase',
                                                        letterSpacing: '0.06em',
                                                    }}>Coming soon</span>
                                                )}
                                            </div>
                                            {p.subtitle && (
                                                <div style={{
                                                    fontSize: 12,
                                                    color: 'rgba(234,229,222,0.25)',
                                                    marginTop: 2,
                                                }}>
                                                    {p.subtitle}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}

                            {/* Not listed option */}
                            <div
                                className={`qs-platform ${notListed ? 'active' : ''}`}
                                onClick={handleNotListed}
                                style={{
                                    ...cardSurface,
                                    padding: '14px 18px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 14,
                                    marginTop: 4,
                                }}
                            >
                                <div style={{
                                    width: 22, height: 22,
                                    borderRadius: 6,
                                    border: notListed
                                        ? '2px solid var(--color-copper, #B56E45)'
                                        : '2px solid rgba(234,229,222,0.15)',
                                    background: notListed ? 'var(--color-copper, #B56E45)' : 'transparent',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: 12, color: '#fff', fontWeight: 700,
                                    flexShrink: 0,
                                    transition: 'all 0.2s',
                                }}>
                                    {notListed && '✓'}
                                </div>
                                <span style={{ fontSize: 18, flexShrink: 0 }}>📋</span>
                                <div style={{
                                    fontSize: 'var(--text-base, 15px)',
                                    color: 'var(--color-stone, #EAE5DE)',
                                    fontWeight: 600,
                                }}>
                                    My property is not listed yet
                                </div>
                            </div>

                            <button
                                onClick={() => {
                                    if (notListed) setStep('manual');
                                    else if (selected.size > 0) setStep('urls');
                                }}
                                disabled={selected.size === 0 && !notListed}
                                style={{
                                    ...primaryBtn,
                                    marginTop: 12,
                                    opacity: (selected.size === 0 && !notListed) ? 0.3 : 1,
                                    cursor: (selected.size === 0 && !notListed) ? 'not-allowed' : 'pointer',
                                }}
                            >
                                Continue →
                            </button>
                        </div>
                    )}

                    {/* ═══════ Step 2: Paste URLs ═══════ */}
                    {step === 'urls' && (
                        <div className="qs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            <div style={cardSurface}>
                                <div style={{
                                    fontSize: 12,
                                    color: 'rgba(234,229,222,0.3)',
                                    marginBottom: 16,
                                    lineHeight: 1.6,
                                    padding: '10px 14px',
                                    background: 'rgba(181,110,69,0.06)',
                                    borderRadius: 'var(--radius-md, 12px)',
                                    border: '1px solid rgba(181,110,69,0.1)',
                                }}>
                                    <strong style={{ color: 'var(--color-copper, #B56E45)' }}>How it works:</strong> Paste the full URL of your listing page. We'll pull publicly available data (name, location, capacity, photos) to speed up your setup. You'll review everything before it's saved.
                                </div>

                                {Array.from(selected).map(platformId => {
                                    const platform = PLATFORMS.find(p => p.id === platformId)!;
                                    return (
                                        <div key={platformId} style={{ marginBottom: 20 }}>
                                            <label style={labelStyle}>
                                                {platform.icon} {platform.name} Listing URL
                                                {platform.supported === 'experimental' && (
                                                    <span style={{ color: 'var(--color-warn)', marginLeft: 6 }}>BETA</span>
                                                )}
                                            </label>
                                            <input
                                                className="qs-input"
                                                type="url"
                                                value={urls[platformId] || ''}
                                                onChange={e => updateUrl(platformId, e.target.value)}
                                                placeholder={platform.urlExample || 'Paste listing URL'}
                                                style={inputStyle}
                                            />
                                            {platform.urlExample && (
                                                <div style={{
                                                    fontSize: 11,
                                                    color: 'rgba(234,229,222,0.2)',
                                                    marginTop: 4,
                                                }}>
                                                    Example: {platform.urlExample}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>

                            <div style={{ display: 'flex', gap: 10 }}>
                                <button onClick={() => setStep('select')} style={{ ...ghostBtn, flex: 1 }}>
                                    ← Back
                                </button>
                                <button
                                    onClick={async () => {
                                        const hasAnyUrl = Object.values(urls).some(u => u.trim());
                                        if (hasAnyUrl) {
                                            await runImport();
                                            setStep('review');
                                        } else {
                                            setStep('manual');
                                        }
                                    }}
                                    disabled={extracting}
                                    style={{ ...primaryBtn, flex: 2, opacity: extracting ? 0.7 : 1 }}
                                >
                                    {extracting
                                        ? '⏳ Extracting listing data...'
                                        : Object.values(urls).some(u => u.trim()) ? 'Import & Review →' : 'Skip — Set Up Manually →'
                                    }
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 3: Review (after import) ═══════ */}
                    {step === 'review' && (
                        <div className="qs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            {/* Status banner */}
                            {(() => {
                                const extractedCount = importedFields.filter(f => f.confidence === 'imported' && f.key !== 'source_url' && f.key !== 'source_platform').length;
                                const estimatedCount = importedFields.filter(f => f.confidence === 'estimated').length;
                                const hasRealImport = extractedCount > 0 || estimatedCount > 0;
                                return (
                                    <div style={{
                                        ...cardSurface,
                                        padding: '16px 18px',
                                        background: hasRealImport ? 'rgba(74,124,89,0.06)' : (extractError ? 'rgba(180,120,60,0.06)' : 'rgba(74,124,89,0.06)'),
                                        border: `1px solid ${hasRealImport ? 'rgba(74,124,89,0.15)' : (extractError ? 'rgba(180,120,60,0.15)' : 'rgba(74,124,89,0.15)')}`,
                                    }}>
                                        <div style={{
                                            fontSize: 14,
                                            fontWeight: 600,
                                            color: hasRealImport ? 'var(--color-ok, #4A7C59)' : (extractError ? '#B4783C' : 'var(--color-ok, #4A7C59)'),
                                            marginBottom: 4,
                                        }}>
                                            {hasRealImport
                                                ? `✅ ${extractedCount + estimatedCount} fields extracted from listing`
                                                : (extractError
                                                    ? '⚠️ Could not extract listing data'
                                                    : '✅ Listing URL saved'
                                                )
                                            }
                                        </div>
                                        <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.35)', lineHeight: 1.6 }}>
                                            {hasRealImport
                                                ? 'Fields marked with ✅ were extracted from your listing. Fields marked with ⚠️ are estimated. You can edit everything before submitting.'
                                                : (extractError
                                                    ? `${extractError} Please fill in the fields below manually.`
                                                    : 'Your listing URL has been saved. Please complete the fields below to get started.'
                                                )
                                            }
                                        </div>
                                    </div>
                                );
                            })()}

                            {/* Saved URLs */}
                            {importedFields
                                .filter(f => f.confidence === 'imported')
                                .map(f => (
                                    <div key={f.key} style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 10,
                                        padding: '10px 14px',
                                        background: 'rgba(74,124,89,0.04)',
                                        borderRadius: 'var(--radius-md, 12px)',
                                        border: '1px solid rgba(74,124,89,0.08)',
                                    }}>
                                        <span style={{ fontSize: 14 }}>✅</span>
                                        <span style={{ fontSize: 12, color: 'rgba(234,229,222,0.4)', minWidth: 100 }}>
                                            {f.label}
                                        </span>
                                        <span style={{
                                            fontSize: 13,
                                            color: 'var(--color-stone, #EAE5DE)',
                                            flex: 1,
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            whiteSpace: 'nowrap',
                                        }}>
                                            {f.value}
                                        </span>
                                    </div>
                                ))}

                            {/* Manual fields */}
                            <div style={cardSurface}>
                                <h3 style={{
                                    fontSize: 14, fontWeight: 700,
                                    color: 'var(--color-stone)',
                                    margin: '0 0 16px',
                                    display: 'flex', alignItems: 'center', gap: 8,
                                }}>
                                    <span style={{ fontSize: 16 }}>✏️</span>
                                    Complete Your Property Details
                                </h3>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                                    <div>
                                        <label style={labelStyle}>Property Name *</label>
                                        <input className="qs-input" value={property.name} onChange={e => updateField('name', e.target.value)} placeholder="e.g. Sunrise Villa Phuket" style={inputStyle} />
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={labelStyle}>Property Type</label>
                                            <select value={property.type} onChange={e => updateField('type', e.target.value)} style={inputStyle}>
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
                                            <label style={labelStyle}>Max Guests</label>
                                            <input className="qs-input" type="number" value={property.guests} onChange={e => updateField('guests', e.target.value)} placeholder="e.g. 6" style={inputStyle} />
                                        </div>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={labelStyle}>Bedrooms</label>
                                            <input className="qs-input" type="number" value={property.bedrooms} onChange={e => updateField('bedrooms', e.target.value)} placeholder="3" style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={labelStyle}>Beds</label>
                                            <input className="qs-input" type="number" value={property.beds} onChange={e => updateField('beds', e.target.value)} placeholder="4" style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={labelStyle}>Bathrooms</label>
                                            <input className="qs-input" type="number" value={property.bathrooms} onChange={e => updateField('bathrooms', e.target.value)} placeholder="2" style={inputStyle} />
                                        </div>
                                    </div>
                                    <div>
                                        <label style={labelStyle}>City</label>
                                        <input className="qs-input" value={property.city} onChange={e => updateField('city', e.target.value)} placeholder="e.g. Phuket" style={inputStyle} />
                                    </div>
                                    <div>
                                        <label style={labelStyle}>Country</label>
                                        <input className="qs-input" value={property.country} onChange={e => updateField('country', e.target.value)} placeholder="e.g. Thailand" style={inputStyle} />
                                    </div>
                                    <div>
                                        <label style={labelStyle}>Full Address</label>
                                        <input className="qs-input" value={property.address} onChange={e => updateField('address', e.target.value)} placeholder="Street address" style={inputStyle} />
                                    </div>
                                    <div>
                                        <label style={labelStyle}>Description</label>
                                        <textarea className="qs-input" value={property.description} onChange={e => updateField('description', e.target.value)} rows={3} placeholder="Brief property description..." style={{ ...inputStyle, resize: 'none' as const }} />
                                    </div>
                                </div>
                            </div>


                            {/* Conflict banner */}
                            {conflictProperty && (
                                <div style={{
                                    ...cardSurface,
                                    padding: '18px',
                                    background: 'rgba(180,120,60,0.08)',
                                    border: '1px solid rgba(180,120,60,0.25)',
                                }}>
                                    <div style={{ fontSize: 14, fontWeight: 700, color: '#B4783C', marginBottom: 8 }}>
                                        {conflictProperty.status === 'archived'
                                            ? '📦 This listing was previously archived'
                                            : conflictProperty.status === 'pending'
                                            ? '⏳ This listing is already submitted'
                                            : conflictProperty.status === 'rejected'
                                            ? '❌ This listing was previously submitted'
                                            : '⚠️ This listing is already connected'}
                                    </div>
                                    <div style={{ fontSize: 13, color: 'rgba(234,229,222,0.6)', marginBottom: 4 }}>
                                        <strong>{conflictProperty.display_name}</strong>
                                    </div>
                                    <div style={{ fontSize: 11, color: 'rgba(234,229,222,0.3)', marginBottom: 4, fontFamily: 'monospace' }}>
                                        ID: {conflictProperty.property_id}
                                    </div>
                                    <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.45)', marginBottom: 12 }}>
                                        {conflictProperty.status === 'archived'
                                            ? 'Contact us to restore this property.'
                                            : conflictProperty.status === 'pending'
                                            ? 'This property is pending admin review.'
                                            : conflictProperty.status === 'rejected'
                                            ? 'Contact us for more information.'
                                            : 'This property is already active in the system.'}
                                    </div>
                                    <div style={{ display: 'flex', gap: 8 }}>
                                        <button
                                            onClick={() => {
                                                setConflictProperty(null);
                                                setStep('select');
                                            }}
                                            style={{ ...ghostBtn, flex: 1, fontSize: 12, padding: '8px 12px' }}
                                        >
                                            ← Start Over
                                        </button>
                                        <a
                                            href={`mailto:info@domaniqo.com?subject=${encodeURIComponent(`Listing already exists: ${conflictProperty.property_id}`)}`}
                                            style={{ ...primaryBtn, flex: 1, fontSize: 12, padding: '8px 12px', textAlign: 'center' as const, textDecoration: 'none' }}
                                        >
                                            Contact Us
                                        </a>
                                    </div>
                                </div>
                            )}

                            <div style={{ display: 'flex', gap: 10 }}>
                                <button onClick={() => setStep('urls')} style={{ ...ghostBtn, flex: 1 }}>
                                    ← Back
                                </button>
                                <button
                                    onClick={handleSubmit}
                                    disabled={submitting || !property.name.trim()}
                                    style={{
                                        ...primaryBtn,
                                        flex: 2,
                                        opacity: (submitting || !property.name.trim()) ? 0.4 : 1,
                                        cursor: (submitting || !property.name.trim()) ? 'not-allowed' : 'pointer',
                                    }}
                                >
                                    {submitting ? 'Submitting…' : 'Submit Property →'}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 3b: Manual setup (not listed) ═══════ */}
                    {step === 'manual' && (
                        <div className="qs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            <div style={cardSurface}>
                                <h3 style={{
                                    fontSize: 14, fontWeight: 700,
                                    color: 'var(--color-stone)',
                                    margin: '0 0 16px',
                                    display: 'flex', alignItems: 'center', gap: 8,
                                }}>
                                    <span style={{ fontSize: 16 }}>🏠</span>
                                    Property Details
                                </h3>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                                    <div>
                                        <label style={labelStyle}>Property Name *</label>
                                        <input className="qs-input" value={property.name} onChange={e => updateField('name', e.target.value)} placeholder="e.g. Sunrise Villa Phuket" style={inputStyle} />
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={labelStyle}>Property Type</label>
                                            <select value={property.type} onChange={e => updateField('type', e.target.value)} style={inputStyle}>
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
                                            <label style={labelStyle}>Max Guests</label>
                                            <input className="qs-input" type="number" value={property.guests} onChange={e => updateField('guests', e.target.value)} placeholder="e.g. 6" style={inputStyle} />
                                        </div>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={labelStyle}>Bedrooms</label>
                                            <input className="qs-input" type="number" value={property.bedrooms} onChange={e => updateField('bedrooms', e.target.value)} placeholder="3" style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={labelStyle}>Beds</label>
                                            <input className="qs-input" type="number" value={property.beds} onChange={e => updateField('beds', e.target.value)} placeholder="4" style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={labelStyle}>Bathrooms</label>
                                            <input className="qs-input" type="number" value={property.bathrooms} onChange={e => updateField('bathrooms', e.target.value)} placeholder="2" style={inputStyle} />
                                        </div>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={labelStyle}>City</label>
                                            <input className="qs-input" value={property.city} onChange={e => updateField('city', e.target.value)} placeholder="Phuket" style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={labelStyle}>Country</label>
                                            <input className="qs-input" value={property.country} onChange={e => updateField('country', e.target.value)} placeholder="Thailand" style={inputStyle} />
                                        </div>
                                    </div>
                                    <div>
                                        <label style={labelStyle}>Full Address</label>
                                        <input className="qs-input" value={property.address} onChange={e => updateField('address', e.target.value)} placeholder="Full property address" style={inputStyle} />
                                    </div>
                                    <div>
                                        <label style={labelStyle}>Description</label>
                                        <textarea className="qs-input" value={property.description} onChange={e => updateField('description', e.target.value)} rows={3} placeholder="Brief property description..." style={{ ...inputStyle, resize: 'none' as const }} />
                                    </div>
                                </div>
                            </div>

                            {/* Operational details */}
                            <div style={cardSurface}>
                                <h3 style={{
                                    fontSize: 14, fontWeight: 700,
                                    color: 'var(--color-stone)',
                                    margin: '0 0 16px',
                                    display: 'flex', alignItems: 'center', gap: 8,
                                }}>
                                    <span style={{ fontSize: 16 }}>📋</span>
                                    Operational Details
                                    <span style={{ fontWeight: 400, fontSize: 11, color: 'rgba(234,229,222,0.25)' }}>(optional)</span>
                                </h3>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={labelStyle}>WiFi Name</label>
                                            <input className="qs-input" value={property.wifi_name} onChange={e => updateField('wifi_name', e.target.value)} style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={labelStyle}>WiFi Password</label>
                                            <input className="qs-input" value={property.wifi_password} onChange={e => updateField('wifi_password', e.target.value)} style={inputStyle} />
                                        </div>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={labelStyle}>Check-in Time</label>
                                            <input className="qs-input" type="time" value={property.check_in} onChange={e => updateField('check_in', e.target.value)} style={inputStyle} />
                                        </div>
                                        <div>
                                            <label style={labelStyle}>Check-out Time</label>
                                            <input className="qs-input" type="time" value={property.check_out} onChange={e => updateField('check_out', e.target.value)} style={inputStyle} />
                                        </div>
                                    </div>
                                    <div>
                                        <label style={labelStyle}>House Rules</label>
                                        <textarea className="qs-input" value={property.house_rules} onChange={e => updateField('house_rules', e.target.value)} rows={3} placeholder="One rule per line" style={{ ...inputStyle, resize: 'none' as const }} />
                                    </div>
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 10 }}>
                                <button onClick={() => notListed ? setStep('select') : setStep('urls')} style={{ ...ghostBtn, flex: 1 }}>
                                    ← Back
                                </button>
                                <button
                                    onClick={handleSubmit}
                                    disabled={submitting || !property.name.trim()}
                                    style={{
                                        ...primaryBtn,
                                        flex: 2,
                                        opacity: (submitting || !property.name.trim()) ? 0.4 : 1,
                                        cursor: (submitting || !property.name.trim()) ? 'not-allowed' : 'pointer',
                                    }}
                                >
                                    {submitting ? 'Submitting…' : 'Submit Property →'}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 4: Complete ═══════ */}
                    {step === 'complete' && (
                        <div className="qs-fade" style={{ textAlign: 'center', padding: 'var(--space-8, 32px) 0' }}>
                            <div style={{
                                width: 72, height: 72,
                                borderRadius: '50%',
                                background: 'rgba(74,124,89,0.1)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                margin: '0 auto 20px',
                                fontSize: 32,
                            }}>
                                ✓
                            </div>
                            <h2 style={{
                                fontFamily: 'var(--font-display)',
                                fontSize: 'var(--text-2xl, 28px)',
                                color: 'var(--color-stone)',
                                marginBottom: 12,
                                fontWeight: 400,
                            }}>
                                Property submitted
                            </h2>
                            <p style={{
                                fontSize: 'var(--text-base)',
                                color: 'rgba(234,229,222,0.4)',
                                lineHeight: 1.7,
                                maxWidth: 380,
                                margin: '0 auto 16px',
                            }}>
                                {dbPersisted
                                    ? `Your property${property.name ? ` "${property.name}"` : ''} has been created in our system.`
                                    : `We've received your property details${property.name ? ` for "${property.name}"` : ''}. Our team will review your submission.`
                                }
                            </p>
                            {createdPropertyId && (
                                <div style={{
                                    fontSize: 12,
                                    color: 'rgba(234,229,222,0.25)',
                                    marginBottom: 24,
                                    fontFamily: 'monospace',
                                }}>
                                    Property ID: {createdPropertyId}
                                </div>
                            )}

                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 300, margin: '0 auto' }}>
                                <Link href="/" style={{ ...primaryBtn, textDecoration: 'none', textAlign: 'center' }}>
                                    Back to Domaniqo
                                </Link>
                                <button
                                    onClick={() => {
                                        setStep('select');
                                        setSelected(new Set());
                                        setUrls({});
                                        setNotListed(false);
                                        setProperty({
                                            name: '', type: '', city: '', region: '', country: '',
                                            guests: '', bedrooms: '', beds: '', bathrooms: '',
                                            description: '', address: '', wifi_name: '', wifi_password: '',
                                            house_rules: '', check_in: '', check_out: '',
                                        });
                                        setImportedFields([]);
                                        setCreatedPropertyId(null);
                                        setDbPersisted(false);
                                    }}
                                    style={ghostBtn}
                                >
                                    Add Another Property
                                </button>
                            </div>

                            <p style={{
                                fontSize: 'var(--text-xs)',
                                color: 'rgba(234,229,222,0.15)',
                                marginTop: 40,
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
