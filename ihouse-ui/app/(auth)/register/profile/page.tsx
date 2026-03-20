'use client';

/**
 * Registration Step 3 — Profile
 * Route: /register/profile
 *
 * Smart form with:
 * - Country auto-detected from timezone
 * - Phone prefix auto-filled from country
 * - Currency auto-selected from country for Avg Nightly Rate
 *
 * Collects: First Name, Last Name, Country, Phone, Listings Count, Avg Nightly Rate
 * Then calls backend to save profile + create tenant_permissions, redirects to dashboard.
 */

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import AuthCard from '../../../../components/auth/AuthCard';
import ProgressBar from '../../../../components/auth/ProgressBar';
import CountrySelect from '../../../../components/auth/CountrySelect';
import { type Country } from '@/lib/countryData';

function RegisterProfileForm() {
    const searchParams = useSearchParams();
    const email = searchParams.get('email') || '';
    const portfolio = searchParams.get('portfolio') || '';
    const fromGoogle = searchParams.get('google') === '1';

    const [form, setForm] = useState({
        firstName: '',
        lastName: '',
        countryCode: '',   // ISO code, auto-detected
        phone: '',         // auto-prefixed from country
        listings: portfolio || '',
        avgRate: '',
    });
    const [selectedCountry, setSelectedCountry] = useState<Country | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [pending, setPending] = useState(false);

    const update = (key: string, value: string) => setForm(prev => ({ ...prev, [key]: value }));

    // When country changes, auto-fill phone prefix and track currency
    const handleCountryChange = (country: Country) => {
        setSelectedCountry(country);
        setForm(prev => ({
            ...prev,
            countryCode: country.code,
            // Only auto-fill phone prefix if phone is empty or was previously auto-filled
            phone: !prev.phone || prev.phone.startsWith('+')
                ? country.phonePrefix + ' '
                : prev.phone,
        }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!form.firstName.trim() || !form.lastName.trim()) {
            setError('Please enter your name');
            return;
        }
        setError(null);
        setLoading(true);
        try {
            const BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';
            const resp = await fetch(`${BASE_URL}/auth/register/profile`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email,
                    first_name: form.firstName.trim(),
                    last_name: form.lastName.trim(),
                    country: selectedCountry?.name || form.countryCode,
                    country_code: form.countryCode,
                    phone: form.phone.trim(),
                    listings_count: form.listings,
                    avg_nightly_rate: form.avgRate,
                    currency: selectedCountry?.currency || 'USD',
                    from_google: fromGoogle,
                }),
            });
            const body = await resp.json();
            const result = body?.data || body;

            if (resp.ok && result.token) {
                // Got JWT — store and redirect (existing invited/approved users)
                localStorage.setItem('ihouse_token', result.token);
                document.cookie = `ihouse_token=${result.token}; path=/; max-age=${result.expires_in || 86400}; SameSite=Lax`;
                window.location.href = '/dashboard';
            } else if (resp.status === 403 && result?.error === 'REGISTRATION_PENDING') {
                // Phase 856A: Profile saved, but no auto-provisioning.
                // Show friendly "pending review" message.
                setError(null);
                setPending(true);
            } else if (resp.ok) {
                // Profile saved but no token yet — redirect to login
                window.location.href = '/login';
            } else {
                setError(result?.message || result?.error || 'Registration failed. Please try again.');
            }
        } catch {
            setError('Network error. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const inputStyle: React.CSSProperties = {
        width: '100%',
        padding: '12px 14px',
        background: 'var(--color-midnight, #171A1F)',
        border: '1px solid rgba(234,229,222,0.1)',
        borderRadius: 'var(--radius-md, 12px)',
        color: 'var(--color-stone, #EAE5DE)',
        fontSize: 'var(--text-sm, 14px)',
        transition: 'border-color 0.2s, box-shadow 0.2s',
        fontFamily: 'var(--font-sans, inherit)',
        boxSizing: 'border-box',
    };

    const labelStyle: React.CSSProperties = {
        display: 'block', fontSize: 'var(--text-xs, 12px)', fontWeight: 600,
        color: 'rgba(234,229,222,0.5)', marginBottom: 'var(--space-2, 8px)',
        textTransform: 'uppercase', letterSpacing: '0.06em',
    };

    // Currency display for the avg rate field
    const currencyLabel = selectedCountry
        ? `${selectedCountry.currencySymbol} ${selectedCountry.currency}`
        : 'USD';

    // Phase 856A: Show "pending review" screen after successful profile submission
    if (pending) {
        return (
            <AuthCard title="Profile Saved" subtitle="Your request is being reviewed">
                <div style={{
                    textAlign: 'center',
                    padding: 'var(--space-6, 24px) 0',
                }}>
                    <div style={{ fontSize: 48, marginBottom: 'var(--space-4, 16px)' }}>✅</div>
                    <p style={{
                        fontSize: 'var(--text-base, 16px)',
                        color: 'var(--color-stone, #EAE5DE)',
                        lineHeight: 1.6,
                        marginBottom: 'var(--space-4, 16px)',
                    }}>
                        Thank you! Your profile has been saved.
                    </p>
                    <p style={{
                        fontSize: 'var(--text-sm, 14px)',
                        color: 'rgba(234,229,222,0.5)',
                        lineHeight: 1.6,
                        marginBottom: 'var(--space-6, 24px)',
                    }}>
                        An administrator will review your request and grant access.
                        You will be notified when your account is activated.
                    </p>
                    <a
                        href="/"
                        style={{
                            display: 'inline-block',
                            padding: '12px 24px',
                            background: 'var(--color-moss, #334036)',
                            borderRadius: 'var(--radius-md, 12px)',
                            color: 'var(--color-white, #F8F6F2)',
                            fontSize: 'var(--text-sm, 14px)',
                            fontWeight: 600,
                            textDecoration: 'none',
                        }}
                    >
                        Back to Domaniqo
                    </a>
                </div>
            </AuthCard>
        );
    }

    return (
        <AuthCard title="Complete your profile" subtitle="Tell us a bit about yourself and your properties">
            <ProgressBar current={3} total={3} />

            {/* Email confirmation */}
            {email && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '8px 14px',
                    background: 'rgba(74,124,89,0.06)', border: '1px solid rgba(74,124,89,0.1)',
                    borderRadius: 'var(--radius-md, 12px)', marginBottom: 'var(--space-4, 16px)',
                }}>
                    <span style={{ fontSize: 14 }}>✅</span>
                    <span style={{ fontSize: 'var(--text-sm, 14px)', color: 'var(--color-stone, #EAE5DE)' }}>{email}</span>
                </div>
            )}

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
                {/* Name row */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div>
                        <label style={labelStyle}>First Name *</label>
                        <input className="auth-input" value={form.firstName} onChange={e => update('firstName', e.target.value)} placeholder="First" disabled={loading} style={inputStyle} />
                    </div>
                    <div>
                        <label style={labelStyle}>Last Name *</label>
                        <input className="auth-input" value={form.lastName} onChange={e => update('lastName', e.target.value)} placeholder="Last" disabled={loading} style={inputStyle} />
                    </div>
                </div>

                {/* Country — smart searchable select with auto-detect */}
                <div>
                    <label style={labelStyle}>Country</label>
                    <CountrySelect
                        value={form.countryCode}
                        onChange={handleCountryChange}
                        disabled={loading}
                        autoDetect={true}
                    />
                </div>

                {/* Phone — auto-prefixed from country */}
                <div>
                    <label style={labelStyle}>Phone Number</label>
                    <input
                        className="auth-input"
                        type="tel"
                        value={form.phone}
                        onChange={e => update('phone', e.target.value)}
                        placeholder={selectedCountry ? `${selectedCountry.phonePrefix} xxx xxx xxxx` : '+xx xxx xxx xxxx'}
                        disabled={loading}
                        style={inputStyle}
                    />
                </div>

                {/* Business details */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div>
                        <label style={labelStyle}>How Many Listings</label>
                        <select value={form.listings} onChange={e => update('listings', e.target.value)} disabled={loading} style={inputStyle}>
                            <option value="">Select</option>
                            <option value="1-5">1–5</option>
                            <option value="5-20">5–20</option>
                            <option value="20+">20+</option>
                        </select>
                    </div>
                    <div>
                        <label style={labelStyle}>Avg Nightly Rate ({currencyLabel})</label>
                        <div style={{ position: 'relative' }}>
                            <input
                                className="auth-input"
                                type="number"
                                min="0"
                                value={form.avgRate}
                                onChange={e => update('avgRate', e.target.value)}
                                placeholder={selectedCountry ? `e.g. ${selectedCountry.currency === 'THB' ? '3000' : selectedCountry.currency === 'ILS' ? '500' : '150'}` : 'e.g. 150'}
                                disabled={loading}
                                style={{ ...inputStyle, paddingLeft: selectedCountry ? '42px' : '14px' }}
                            />
                            {selectedCountry && (
                                <span style={{
                                    position: 'absolute',
                                    left: 14,
                                    top: '50%',
                                    transform: 'translateY(-50%)',
                                    color: 'rgba(234,229,222,0.4)',
                                    fontSize: 'var(--text-sm, 14px)',
                                    pointerEvents: 'none',
                                }}>
                                    {selectedCountry.currencySymbol}
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                {error && (
                    <div style={{
                        background: 'rgba(155,58,58,0.1)', border: '1px solid rgba(155,58,58,0.25)',
                        borderRadius: 'var(--radius-md, 12px)', padding: '10px 14px',
                        fontSize: 'var(--text-sm, 14px)', color: '#EF4444',
                    }}>
                        ⚠ {error}
                    </div>
                )}

                <button
                    type="submit"
                    className="auth-btn"
                    disabled={loading || !form.firstName.trim() || !form.lastName.trim()}
                    style={{
                        width: '100%', padding: '14px',
                        background: 'var(--color-moss, #334036)', border: 'none',
                        borderRadius: 'var(--radius-md, 12px)', color: 'var(--color-white, #F8F6F2)',
                        fontSize: 'var(--text-base, 16px)', fontWeight: 600,
                        fontFamily: 'var(--font-brand, "Inter", sans-serif)',
                        cursor: loading || !form.firstName.trim() || !form.lastName.trim() ? 'not-allowed' : 'pointer',
                        opacity: loading || !form.firstName.trim() || !form.lastName.trim() ? 0.4 : 1,
                        transition: 'all 0.2s', minHeight: 48,
                    }}
                >
                    {loading ? 'Setting up…' : 'Continue'}
                </button>
            </form>
        </AuthCard>
    );
}

export default function RegisterProfilePage() {
    return (
        <Suspense fallback={null}>
            <RegisterProfileForm />
        </Suspense>
    );
}
