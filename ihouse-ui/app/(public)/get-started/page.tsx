'use client';

/**
 * Phase 858 — Progressive Get Started Wizard (Two-Mode)
 * Route: /get-started
 *
 * Two distinct modes served by one engine:
 *
 * PUBLIC MODE (unauthenticated, 7 steps):
 *   1. Portfolio size
 *   2. Platform selection
 *   3. Import mode
 *   4. Paste listing URLs
 *   5. Property details (first value moment)
 *   6. AUTH GATE (email verification or Google OAuth)
 *   7. Account completion (profile + set password)
 *   → Draft saved → redirect to /my-properties
 *
 * SIGNED-IN MODE (authenticated, 5 steps):
 *   1. Portfolio size
 *   2. Platform selection
 *   3. Import mode
 *   4. Paste listing URLs
 *   5. Property details → Save → /my-properties
 *   No auth gate. No account completion. No auth copy.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import DMonogram from '@/components/DMonogram';
import { supabase, isSupabaseConfigured } from '@/lib/supabaseClient';

/* ─────────── Constants ─────────── */

const STORAGE_KEY = 'domaniqo_get_started_state';

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

type Step = 1 | 2 | 3 | 4 | 5 | 6 | 7;
type ImportMode = 'link' | 'manual' | 'connect';

/* Top country codes — text only, no flags */
const COUNTRY_CODES = [
    { code: '+66', country: 'TH' }, { code: '+1', country: 'US' },
    { code: '+44', country: 'UK' }, { code: '+61', country: 'AU' },
    { code: '+81', country: 'JP' }, { code: '+82', country: 'KR' },
    { code: '+49', country: 'DE' }, { code: '+33', country: 'FR' },
    { code: '+39', country: 'IT' }, { code: '+34', country: 'ES' },
    { code: '+7', country: 'RU' }, { code: '+86', country: 'CN' },
    { code: '+91', country: 'IN' }, { code: '+65', country: 'SG' },
    { code: '+60', country: 'MY' }, { code: '+62', country: 'ID' },
    { code: '+63', country: 'PH' }, { code: '+84', country: 'VN' },
    { code: '+852', country: 'HK' }, { code: '+971', country: 'AE' },
    { code: '+55', country: 'BR' }, { code: '+52', country: 'MX' },
    { code: '+27', country: 'ZA' }, { code: '+64', country: 'NZ' },
    { code: '+46', country: 'SE' }, { code: '+47', country: 'NO' },
    { code: '+45', country: 'DK' }, { code: '+31', country: 'NL' },
    { code: '+41', country: 'CH' }, { code: '+48', country: 'PL' },
    { code: '+90', country: 'TR' }, { code: '+20', country: 'EG' },
];

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
    source_url: string;
    source_platform: string;
    photos: string[];
}

const EMPTY_DRAFT: PropertyDraft = {
    name: '', type: '', city: '', country: '',
    guests: '', bedrooms: '', beds: '', bathrooms: '',
    description: '', address: '',
    source_url: '', source_platform: '',
    photos: [],
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

const stepTitle: React.CSSProperties = {
    fontSize: 'var(--text-lg, 18px)', fontWeight: 600,
    color: 'var(--color-stone, #EAE5DE)', margin: '0 0 4px',
    fontFamily: 'var(--font-brand, inherit)',
};

const stepSubtitle: React.CSSProperties = {
    fontSize: 'var(--text-sm, 14px)', color: 'rgba(234,229,222,0.4)',
    margin: '0 0 16px', lineHeight: 1.5,
};

/* ─────────── Page ─────────── */

export default function GetStartedWizard() {
    const router = useRouter();

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

    // Auth state
    const [authEmail, setAuthEmail] = useState('');
    const [authOtpSent, setAuthOtpSent] = useState(false);
    const [authOtp, setAuthOtp] = useState('');
    const [authLoading, setAuthLoading] = useState(false);
    const [authError, setAuthError] = useState('');
    const [authedUser, setAuthedUser] = useState<{ id: string; email: string } | null>(null);
    const [authProvider, setAuthProvider] = useState<'email' | 'google'>('email');
    // Phase 872: Tracks whether user was already authenticated BEFORE entering Get Started.
    // Pre-existing auth users skip password fields — they already have credentials.
    const [preExistingAuth, setPreExistingAuth] = useState(false);

    // Profile state
    const [profile, setProfile] = useState({ firstName: '', lastName: '', phone: '', countryCode: '+66', userType: '' });
    const [profileSaving, setProfileSaving] = useState(false);

    // Draft save state
    const [draftSaving, setDraftSaving] = useState(false);

    // Password state (OTP path only — Google users skip password)
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [passwordError, setPasswordError] = useState('');
    const [passwordFocused, setPasswordFocused] = useState(false);

    // Photo lightbox
    const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

    // Whether the current auth is via Google OR user was pre-authenticated (skip password section)
    // Phase 872: pre-existing auth users already have credentials — don't ask them to set a password again
    const isGoogleAuth = authProvider === 'google';
    const skipPasswordSection = isGoogleAuth || preExistingAuth;

    const otpInputRef = useRef<HTMLInputElement>(null);

    // Restore state from sessionStorage
    useEffect(() => {
        const saved = sessionStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                setState(prev => ({ ...prev, ...parsed, extracting: false }));
            } catch { /* ignore corrupt state */ }
        }

        // Detect auth from ihouse_token cookie (canonical credential)
        const ihouseToken = document.cookie
            .split('; ')
            .find(c => c.startsWith('ihouse_token='))
            ?.split('=')[1];

        if (ihouseToken) {
            // User is signed in via ihouse_token — mark as authenticated
            // Decode minimal info from JWT for display (without verification)
            try {
                const payload = JSON.parse(atob(ihouseToken.split('.')[1]));
                setAuthedUser({ id: payload.sub || '', email: payload.email || '' });
                setPreExistingAuth(true);
                // Auto-advance past auth gate if stale sessionStorage
                setState(prev => (prev.step === 6 || prev.step === 7) ? { ...prev, step: 5 as Step } : prev);
            } catch { /* corrupt token — fall through */ }
        }

        // Also check Supabase session (for Google OAuth users)
        if (supabase) {
            supabase.auth.getSession().then(({ data }) => {
                if (data.session?.user) {
                    setAuthedUser({ id: data.session.user.id, email: data.session.user.email || '' });
                    setPreExistingAuth(true);
                    const provider = data.session.user.app_metadata?.provider;
                    if (provider === 'google') setAuthProvider('google');
                    const meta = data.session.user.user_metadata;
                    if (meta?.full_name) {
                        const parts = (meta.full_name as string).split(' ');
                        setProfile(p => ({
                            ...p,
                            firstName: p.firstName || parts[0] || '',
                            lastName: p.lastName || parts.slice(1).join(' ') || '',
                        }));
                    }
                    setState(prev => (prev.step === 6 || prev.step === 7) ? { ...prev, step: 5 as Step } : prev);
                }
            });
        }
    }, []);

    // Listen for auth state changes (for Google OAuth return)
    useEffect(() => {
        if (!supabase) return;
        const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
            if (event === 'SIGNED_IN' && session?.user) {
                setAuthedUser({ id: session.user.id, email: session.user.email || '' });
                const provider = session.user.app_metadata?.provider;
                if (provider === 'google') {
                    setAuthProvider('google');
                    // Pre-fill name from Google profile if available
                    const meta = session.user.user_metadata;
                    if (meta?.full_name) {
                        const parts = (meta.full_name as string).split(' ');
                        setProfile(p => ({
                            ...p,
                            firstName: p.firstName || parts[0] || '',
                            lastName: p.lastName || parts.slice(1).join(' ') || '',
                        }));
                    }
                }
                // If returning from OAuth, advance past auth step
                const saved = sessionStorage.getItem(STORAGE_KEY);
                if (saved) {
                    try {
                        const parsed = JSON.parse(saved);
                        if (parsed.step === 6) {
                            setState(prev => ({ ...prev, ...parsed, step: 7, extracting: false }));
                        }
                    } catch { /* ignore */ }
                }
            }
        });
        return () => subscription.unsubscribe();
    }, []);

    // Persist wizard state
    useEffect(() => {
        if (state.step <= 7) {
            const toSave = { ...state, extracting: false, property: { ...state.property, photos: state.property.photos.slice(0, 10) } };
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
                        photos: Array.isArray(ext.photos) ? ext.photos : prev.property.photos,
                    },
                }));
            } else {
                setState(prev => ({ ...prev, extracting: false, extractedCount: 0, property: { ...prev.property, source_url: firstUrl } }));
            }
        } catch {
            setState(prev => ({ ...prev, extracting: false, extractedCount: 0, property: { ...prev.property, source_url: Object.values(prev.urls).find(u => u.trim()) || '' } }));
        }
    }, [state.urls]);

    /* ─── Auth: Email OTP ─── */
    const handleSendOtp = async () => {
        if (!supabase || !authEmail.trim()) return;
        setAuthLoading(true);
        setAuthError('');
        try {
            const { error } = await supabase.auth.signInWithOtp({ email: authEmail.trim() });
            if (error) {
                setAuthError(error.message);
            } else {
                setAuthOtpSent(true);
                setTimeout(() => otpInputRef.current?.focus(), 100);
            }
        } catch (e: unknown) {
            setAuthError(e instanceof Error ? e.message : 'Failed to send verification code');
        } finally {
            setAuthLoading(false);
        }
    };

    const handleVerifyOtp = async () => {
        if (!supabase || !authOtp.trim()) return;
        setAuthLoading(true);
        setAuthError('');
        try {
            // signInWithOtp creates new users via 'signup' flow, existing users via 'email' flow.
            // We don't know which one was triggered, so try 'signup' first (most common
            // for Get Started wizard), then fall back to 'email' for returning users.
            let result = await supabase.auth.verifyOtp({
                email: authEmail.trim(),
                token: authOtp.trim(),
                type: 'signup',
            });
            if (result.error) {
                // Try 'email' type (for existing confirmed users doing magic-link login)
                result = await supabase.auth.verifyOtp({
                    email: authEmail.trim(),
                    token: authOtp.trim(),
                    type: 'email',
                });
            }
            if (result.error) {
                setAuthError(result.error.message);
            } else if (result.data.user) {
                setAuthedUser({ id: result.data.user.id, email: result.data.user.email || authEmail });
                setAuthProvider('email');
                setStep(7);
            }
        } catch (e: unknown) {
            setAuthError(e instanceof Error ? e.message : 'Verification failed');
        } finally {
            setAuthLoading(false);
        }
    };

    /* ─── Auth: Google OAuth ─── */
    const handleGoogleAuth = async () => {
        if (!supabase) return;
        setAuthLoading(true);
        setAuthError('');
        try {
            const { error } = await supabase.auth.signInWithOAuth({
                provider: 'google',
                options: {
                    redirectTo: `${window.location.origin}/get-started?step=7`, // account completion
                },
            });
            if (error) setAuthError(error.message);
        } catch (e: unknown) {
            setAuthError(e instanceof Error ? e.message : 'Google sign-in failed');
            setAuthLoading(false);
        }
    };

    /* ─── Password validation helpers ─── */
    const pwRules = [
        { key: 'length', label: '8+ characters', pass: newPassword.length >= 8 },
        { key: 'upper', label: '1 uppercase letter', pass: /[A-Z]/.test(newPassword) },
        { key: 'number', label: '1 number', pass: /[0-9]/.test(newPassword) },
        { key: 'special', label: '1 special character', pass: /[^A-Za-z0-9]/.test(newPassword) },
    ];
    const allPwRulesPass = pwRules.every(r => r.pass);

    /* ─── Save property draft (shared between both paths) ─── */
    const saveDraft = async () => {
        if (!authedUser) return false;
        const token = document.cookie
            .split('; ')
            .find(c => c.startsWith('ihouse_token='))
            ?.split('=')[1];
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const res = await fetch('/api/onboard', {
            method: 'POST',
            headers,
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
                submitterUserId: authedUser.id,
                submitterEmail: authedUser.email,
                firstName: profile.firstName,
                lastName: profile.lastName,
                phone: profile.countryCode + ' ' + profile.phone,
                userType: profile.userType,
                channels: state.selectedPlatforms
                    .filter(id => state.urls[id]?.trim())
                    .map(id => ({ provider: id, url: state.urls[id] })),
            }),
        });
        const data = await res.json();
        if (data.success || data.property_id) {
            sessionStorage.removeItem(STORAGE_KEY);
            router.push('/my-properties');
            return true;
        }
        return false;
    };

    /* ─── Set Password + Save (OTP path) ─── */
    const handleSetPassword = async () => {
        if (!supabase || !authedUser) return;
        setPasswordError('');
        if (!allPwRulesPass) {
            setPasswordError('Password does not meet all requirements');
            return;
        }
        if (newPassword !== confirmPassword) {
            setPasswordError('Passwords do not match');
            return;
        }
        setDraftSaving(true);
        try {
            const { error: pwError } = await supabase.auth.updateUser({ password: newPassword });
            if (pwError) {
                setPasswordError(pwError.message);
                setDraftSaving(false);
                return;
            }
            const ok = await saveDraft();
            if (!ok) setPasswordError('Failed to save property. Please try again.');
        } catch {
            setPasswordError('Network error. Please try again.');
        } finally {
            setDraftSaving(false);
        }
    };

    /* ─── Save without password (Google path) ─── */
    const handleGoogleSave = async () => {
        if (!authedUser) return;
        setPasswordError('');
        setDraftSaving(true);
        try {
            const ok = await saveDraft();
            if (!ok) setPasswordError('Failed to save property. Please try again.');
        } catch {
            setPasswordError('Network error. Please try again.');
        } finally {
            setDraftSaving(false);
        }
    };

    /* ─── Progress ─── */
    // Signed-in users see 5 steps (property-only). Public users see 7 (including auth).
    const isSignedIn = !!preExistingAuth;
    const totalVisibleSteps = isSignedIn ? 5 : 7;
    const displayStep = Math.min(state.step, totalVisibleSteps);

    /* ─── Step 5: proceed to auth or skip ─── */
    const handleStep5Continue = async () => {
        // If already authenticated (signed-in user), save draft directly and go to /my-properties.
        // Do NOT show step 6 (auth gate) or step 7 (profile completion).
        if (authedUser) {
            setDraftSaving(true);
            try {
                const ok = await saveDraft();
                if (!ok) {
                    setPasswordError('Failed to save property. Please try again.');
                }
            } catch {
                setPasswordError('Network error. Please try again.');
            } finally {
                setDraftSaving(false);
            }
            return;
        }
        // Not authenticated — show auth gate
        setStep(6);
    };

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
                .gs-divider { display:flex; align-items:center; gap:12px; color:rgba(234,229,222,0.2); font-size:12px; }
                .gs-divider::before,.gs-divider::after { content:''; flex:1; height:1px; background:rgba(234,229,222,0.08); }
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
                    {state.step <= 7 && (
                        <div className="gs-fade" style={{ textAlign: 'center', marginBottom: 'var(--space-6, 24px)' }}>
                            <DMonogram size={36} color="var(--color-stone, #EAE5DE)" strokeWidth={1.2} />
                            <h1 style={{
                                fontFamily: 'var(--font-display, serif)',
                                fontSize: 'var(--text-2xl, 28px)',
                                color: 'var(--color-stone, #EAE5DE)',
                                margin: '16px 0 6px', fontWeight: 400,
                            }}>
                                {isSignedIn
                                    ? 'Add Property'
                                    : state.step <= 5 ? 'Get Started' : state.step === 6 ? 'Save Your Property' : 'Complete Your Account'
                                }
                            </h1>

                            {/* Progress bar */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center', margin: '12px 0 8px' }}>
                                <span style={{ fontSize: 12, color: 'rgba(234,229,222,0.3)' }}>
                                    Step {displayStep} of {totalVisibleSteps}
                                </span>
                            </div>
                            <div style={{
                                height: 3, background: 'rgba(234,229,222,0.06)',
                                borderRadius: 99, overflow: 'hidden',
                            }}>
                                <div style={{
                                    height: '100%', width: `${(displayStep / totalVisibleSteps) * 100}%`,
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

                            {!authedUser && (
                                <div style={{ textAlign: 'center', marginTop: 12 }}>
                                    <Link href="/login" style={{ fontSize: 'var(--text-sm, 14px)', color: 'rgba(234,229,222,0.4)', textDecoration: 'none' }}>
                                        Already a user? <span style={{ textDecoration: 'underline' }}>Log in</span>
                                    </Link>
                                </div>
                            )}
                        </div>
                    )}

                    {/* ═══════ Step 2: Platform Selection ═══════ */}
                    {state.step === 2 && (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                            <p style={{ fontSize: 'var(--text-base, 16px)', color: 'var(--color-stone)', fontWeight: 600, margin: '0 0 4px', textAlign: 'center' }}>
                                Where are your properties currently listed?
                            </p>

                            {PLATFORMS.map(p => {
                                const isActive = state.selectedPlatforms.includes(p.id);
                                return (
                                    <div key={p.id} className={`gs-option ${isActive ? 'active' : ''}`} onClick={() => togglePlatform(p.id)}
                                        style={{ ...card, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14 }}>
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
                                                {p.status === 'beta' && <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-copper)', marginLeft: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Beta</span>}
                                                {p.status === 'coming_soon' && <span style={{ fontSize: 10, fontWeight: 700, color: 'rgba(234,229,222,0.25)', marginLeft: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Coming soon</span>}
                                            </div>
                                            {p.subtitle && <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.25)', marginTop: 2 }}>{p.subtitle}</div>}
                                        </div>
                                    </div>
                                );
                            })}

                            <div className={`gs-option ${state.notListed ? 'active' : ''}`} onClick={handleNotListed}
                                style={{ ...card, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14, marginTop: 4 }}>
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
                                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-stone)' }}>Not listed anywhere yet</div>
                            </div>

                            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
                                <button onClick={() => setStep(1)} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
                                <button
                                    onClick={() => {
                                        if (state.notListed) { setState(prev => ({ ...prev, importMode: 'manual' })); setStep(5); }
                                        else setStep(3);
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
                            <p style={{ fontSize: 'var(--text-base, 16px)', color: 'var(--color-stone)', fontWeight: 600, margin: '0 0 4px', textAlign: 'center' }}>
                                How would you like to add your property?
                            </p>

                            {/* Paste listing link */}
                            <div className={`gs-option ${state.importMode === 'link' ? 'active' : ''}`}
                                onClick={() => setState(prev => ({ ...prev, importMode: 'link' }))}
                                style={{ ...card, padding: '16px 18px', cursor: 'pointer' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <span style={{ fontSize: 20 }}>🔗</span>
                                    <div>
                                        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-stone)' }}>Import from existing listing</div>
                                        <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.35)', marginTop: 2 }}>We'll pull details from your existing listing</div>
                                    </div>
                                </div>
                            </div>

                            {/* Manual entry */}
                            <div className={`gs-option ${state.importMode === 'manual' ? 'active' : ''}`}
                                onClick={() => setState(prev => ({ ...prev, importMode: 'manual' }))}
                                style={{ ...card, padding: '16px 18px', cursor: 'pointer' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <span style={{ fontSize: 20 }}>✏️</span>
                                    <div>
                                        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-stone)' }}>Set up manually</div>
                                        <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.35)', marginTop: 2 }}>Enter your property details yourself</div>
                                    </div>
                                </div>
                            </div>

                            {/* Connect account — Coming soon */}
                            <div className="gs-option" style={{ ...card, padding: '16px 18px', cursor: 'pointer', opacity: 0.5 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <span style={{ fontSize: 20 }}>🔌</span>
                                    <div>
                                        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-stone)' }}>
                                            Connect account
                                            <span style={{ fontSize: 10, fontWeight: 700, color: 'rgba(234,229,222,0.3)', marginLeft: 8, textTransform: 'uppercase', letterSpacing: '0.06em', background: 'rgba(234,229,222,0.06)', padding: '2px 6px', borderRadius: 4 }}>Coming soon</span>
                                        </div>
                                        <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.25)', marginTop: 2 }}>Direct account connections are coming soon.</div>
                                    </div>
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
                                <button onClick={() => setStep(2)} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
                                <button onClick={() => { if (state.importMode === 'link') setStep(4); else if (state.importMode === 'manual') setStep(5); }}
                                    disabled={!state.importMode || state.importMode === 'connect'}
                                    style={{ ...primaryBtn, flex: 2, ...disabledStyle(!state.importMode || state.importMode === 'connect') }}>
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
                                    fontSize: 12, color: 'rgba(234,229,222,0.35)', marginBottom: 16, lineHeight: 1.6, padding: '10px 14px',
                                    background: 'rgba(181,110,69,0.06)', borderRadius: 'var(--radius-md, 12px)', border: '1px solid rgba(181,110,69,0.1)',
                                }}>
                                    <strong style={{ color: 'var(--color-copper)' }}>How it works:</strong> Paste the URL of your existing listing. We'll pull publicly available details to speed up your setup.
                                </div>
                                {state.selectedPlatforms.map(platformId => {
                                    const platform = PLATFORMS.find(p => p.id === platformId);
                                    if (!platform) return null;
                                    return (
                                        <div key={platformId} style={{ marginBottom: 20 }}>
                                            <label style={label}>{platform.icon} {platform.name} Listing URL</label>
                                            <input className="gs-input" type="url" value={state.urls[platformId] || ''} onChange={e => updateUrl(platformId, e.target.value)}
                                                placeholder={platform.urlExample || 'Paste listing URL'} style={inputStyle} />
                                            {platform.urlExample && <div style={{ fontSize: 11, color: 'rgba(234,229,222,0.2)', marginTop: 4 }}>Example: {platform.urlExample}</div>}
                                        </div>
                                    );
                                })}
                            </div>
                            <div style={{ display: 'flex', gap: 10 }}>
                                <button onClick={() => setStep(3)} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
                                <button
                                    onClick={async () => {
                                        const hasUrl = Object.values(state.urls).some(u => u.trim());
                                        if (hasUrl) await runImport();
                                        setStep(5);
                                    }}
                                    disabled={state.extracting}
                                    style={{ ...primaryBtn, flex: 2, opacity: state.extracting ? 0.7 : 1 }}>
                                    {state.extracting ? '⏳ Importing property details...' : Object.values(state.urls).some(u => u.trim()) ? 'Import & Review →' : 'Skip — Set Up Manually →'}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 5: Property Preview / Review (FIRST VALUE MOMENT) ═══════ */}
                    {state.step === 5 && (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            {state.extractedCount > 0 && (
                                <div style={{ ...card, padding: '14px 18px', background: 'rgba(74,124,89,0.06)', border: '1px solid rgba(74,124,89,0.15)' }}>
                                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ok, #4A7C59)' }}>✅ {state.extractedCount} details imported from your listing</div>
                                    <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.35)', marginTop: 4 }}>Review and edit anything below before continuing.</div>
                                </div>
                            )}

                            <div style={card}>
                                <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-stone)', margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span style={{ fontSize: 16 }}>🏠</span> Property Details
                                </h3>

                                {/* ── Photo Strip ── */}
                                <div style={{ display: 'flex', gap: 8, marginBottom: 18, overflowX: 'auto' }}>
                                    {state.property.photos.length > 0 ? (
                                        <>
                                            {state.property.photos.slice(0, 4).map((url, i) => (
                                                <div key={i} onClick={() => setLightboxIndex(i)} style={{
                                                    width: 80, height: 56, borderRadius: 8, overflow: 'hidden',
                                                    cursor: 'pointer', flexShrink: 0, position: 'relative',
                                                    border: '1px solid rgba(234,229,222,0.08)',
                                                }}>
                                                    <img src={url} alt={`Photo ${i + 1}`} style={{
                                                        width: '100%', height: '100%', objectFit: 'cover',
                                                    }} />
                                                </div>
                                            ))}
                                            {state.property.photos.length > 4 && (
                                                <div onClick={() => setLightboxIndex(4)} style={{
                                                    width: 80, height: 56, borderRadius: 8, flexShrink: 0,
                                                    background: 'rgba(234,229,222,0.04)', border: '1px solid rgba(234,229,222,0.08)',
                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                    cursor: 'pointer', fontSize: 14, fontWeight: 600,
                                                    color: 'rgba(234,229,222,0.4)',
                                                }}>
                                                    +{state.property.photos.length - 4}
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        /* Empty photo state */
                                        <div style={{ display: 'flex', gap: 8, width: '100%' }}>
                                            {[0, 1, 2, 3, 4].map(i => (
                                                <div key={i} style={{
                                                    width: 80, height: 56, borderRadius: 8, flexShrink: 0,
                                                    border: '1px dashed rgba(234,229,222,0.1)',
                                                    background: 'rgba(234,229,222,0.015)',
                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                }}>
                                                    {i === 2 && <span style={{ fontSize: 11, color: 'rgba(234,229,222,0.15)' }}>📷</span>}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                {state.property.photos.length === 0 && (
                                    <div style={{ fontSize: 11, color: 'rgba(234,229,222,0.2)', marginBottom: 14, marginTop: -10 }}>
                                        No photos yet — you can add them later
                                    </div>
                                )}
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
                                        <div><label style={label}>Bedrooms</label><input className="gs-input" type="number" value={state.property.bedrooms} onChange={e => updateProperty('bedrooms', e.target.value)} placeholder="3" style={inputStyle} /></div>
                                        <div><label style={label}>Beds</label><input className="gs-input" type="number" value={state.property.beds} onChange={e => updateProperty('beds', e.target.value)} placeholder="4" style={inputStyle} /></div>
                                        <div><label style={label}>Baths</label><input className="gs-input" type="number" value={state.property.bathrooms} onChange={e => updateProperty('bathrooms', e.target.value)} placeholder="2" style={inputStyle} /></div>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div><label style={label}>City</label><input className="gs-input" value={state.property.city} onChange={e => updateProperty('city', e.target.value)} placeholder="e.g. Phuket" style={inputStyle} /></div>
                                        <div><label style={label}>Country</label><input className="gs-input" value={state.property.country} onChange={e => updateProperty('country', e.target.value)} placeholder="e.g. Thailand" style={inputStyle} /></div>
                                    </div>
                                    <div><label style={label}>Full Address</label><input className="gs-input" value={state.property.address} onChange={e => updateProperty('address', e.target.value)} placeholder="Street address" style={inputStyle} /></div>
                                    <div><label style={label}>Description</label><textarea className="gs-input" value={state.property.description} onChange={e => updateProperty('description', e.target.value)} rows={3} placeholder="Brief property description..." style={{ ...inputStyle, resize: 'none' as const }} /></div>
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 10 }}>
                                <button onClick={() => { if (state.importMode === 'link') setStep(4); else if (state.notListed) setStep(2); else setStep(3); }} style={{ ...ghostBtn, flex: 1 }}>← Back</button>
                                <button onClick={handleStep5Continue} disabled={!state.property.name.trim() || draftSaving} style={{ ...primaryBtn, flex: 2, ...disabledStyle(!state.property.name.trim() || draftSaving) }}>
                                    {draftSaving ? 'Saving…' : isSignedIn ? 'Save Property →' : 'Save & Continue →'}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ═══════ Step 6: AUTH GATE (public mode only) ═══════ */}
                    {!isSignedIn && state.step === 6 && (() => {
                        // Guard: if user is already authenticated, never show the auth gate.
                        // Bypass immediately to step 7. This handles the case where
                        // sessionStorage restored step=6 before the Supabase session
                        // check could correct it.
                        if (authedUser) {
                            // Schedule state update outside render
                            setTimeout(() => setStep(7 as Step), 0);
                            return null;
                        }
                        return (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            <div style={card}>
                                <p style={{ fontSize: 14, color: 'rgba(234,229,222,0.4)', margin: '0 0 20px', lineHeight: 1.6 }}>
                                    Create an account to save your property and track its review status.
                                </p>

                                {!authOtpSent ? (
                                    <>
                                        <div style={{ marginBottom: 14 }}>
                                            <label style={label}>Email Address</label>
                                            <input
                                                className="gs-input" type="email"
                                                value={authEmail} onChange={e => setAuthEmail(e.target.value)}
                                                onKeyDown={e => e.key === 'Enter' && handleSendOtp()}
                                                placeholder="you@example.com" style={inputStyle} autoFocus
                                            />
                                        </div>
                                        <button onClick={handleSendOtp} disabled={authLoading || !authEmail.trim()}
                                            style={{ ...primaryBtn, ...disabledStyle(authLoading || !authEmail.trim()) }}>
                                            {authLoading ? 'Sending…' : 'Continue with Email →'}
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <div style={{
                                            fontSize: 13, color: 'rgba(234,229,222,0.4)', marginBottom: 14, lineHeight: 1.6,
                                            padding: '10px 14px', background: 'rgba(74,124,89,0.06)', borderRadius: 'var(--radius-md, 12px)', border: '1px solid rgba(74,124,89,0.1)',
                                        }}>
                                            ✉️ We sent a verification code to <strong style={{ color: 'var(--color-stone)' }}>{authEmail}</strong>
                                        </div>
                                        <div style={{ marginBottom: 14 }}>
                                            <label style={label}>8-Digit Verification Code</label>
                                            <input
                                                ref={otpInputRef} className="gs-input"
                                                value={authOtp} onChange={e => setAuthOtp(e.target.value.replace(/\D/g, '').slice(0, 8))}
                                                onKeyDown={e => e.key === 'Enter' && authOtp.length === 8 && handleVerifyOtp()}
                                                placeholder="· · · · · · · ·" style={{ ...inputStyle, textAlign: 'center', fontSize: 22, letterSpacing: '0.3em', fontWeight: 300, color: 'var(--color-stone)' }}
                                                maxLength={8} inputMode="numeric" autoComplete="one-time-code"
                                            />
                                            <div style={{ fontSize: 11, color: 'rgba(234,229,222,0.2)', marginTop: 6, textAlign: 'center' }}>
                                                Enter the 8-digit code from your email
                                            </div>
                                        </div>
                                        <button onClick={handleVerifyOtp} disabled={authLoading || authOtp.length !== 8}
                                            style={{ ...primaryBtn, ...disabledStyle(authLoading || authOtp.length !== 8) }}>
                                            {authLoading ? 'Verifying…' : 'Verify & Continue →'}
                                        </button>
                                        <button onClick={() => { setAuthOtp(''); setAuthOtpSent(false); setAuthError(''); }}
                                            style={{ ...ghostBtn, marginTop: 8, fontSize: 13, color: 'rgba(234,229,222,0.3)' }}>
                                            Use a different email
                                        </button>
                                    </>
                                )}

                                {authError && (
                                    <div style={{ fontSize: 13, color: '#D64545', marginTop: 12, padding: '8px 12px', background: 'rgba(214,69,69,0.08)', borderRadius: 8 }}>
                                        {authError}
                                    </div>
                                )}

                                {!authOtpSent && isSupabaseConfigured() && (
                                    <>
                                        <div className="gs-divider" style={{ margin: '16px 0' }}>or</div>
                                        <button onClick={handleGoogleAuth} disabled={authLoading}
                                            style={{
                                                ...ghostBtn, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                                                borderColor: 'rgba(234,229,222,0.15)', ...disabledStyle(authLoading),
                                            }}>
                                            <svg width="18" height="18" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
                                            Continue with Google
                                        </button>
                                    </>
                                )}
                            </div>

                            <div style={{ textAlign: 'center' }}>
                                <Link href="/login" style={{ fontSize: 13, color: 'rgba(234,229,222,0.3)', textDecoration: 'none' }}>
                                    Already have an account? <span style={{ textDecoration: 'underline' }}>Log in</span>
                                </Link>
                            </div>

                            <button onClick={() => setStep(5)} style={{ ...ghostBtn, fontSize: 13 }}>← Back to property details</button>
                        </div>
                        );
                    })()}

                    {/* ═══════ Step 7: Account Completion (public mode only) ═══════ */}
                    {!isSignedIn && state.step === 7 && authedUser && (
                        <div className="gs-fade" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            <div style={card}>
                                <div style={{
                                    fontSize: 13, color: 'rgba(234,229,222,0.4)', marginBottom: 16, lineHeight: 1.6,
                                    padding: '10px 14px', background: 'rgba(74,124,89,0.06)', borderRadius: 'var(--radius-md, 12px)', border: '1px solid rgba(74,124,89,0.1)',
                                }}>
                                    ✅ Signed in as <strong style={{ color: 'var(--color-stone)' }}>{authedUser.email}</strong>
                                </div>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                                    {/* Name */}
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                        <div>
                                            <label style={label}>First Name *</label>
                                            <input className="gs-input" value={profile.firstName} onChange={e => setProfile(p => ({ ...p, firstName: e.target.value }))} placeholder="David" style={inputStyle} autoFocus />
                                        </div>
                                        <div>
                                            <label style={label}>Last Name *</label>
                                            <input className="gs-input" value={profile.lastName} onChange={e => setProfile(p => ({ ...p, lastName: e.target.value }))} placeholder="Chen" style={inputStyle} />
                                        </div>
                                    </div>

                                    {/* Phone with inline country code */}
                                    <div>
                                        <label style={label}>Phone</label>
                                        <div style={{
                                            display: 'flex', alignItems: 'center',
                                            background: 'var(--color-midnight, #171A1F)',
                                            border: '1px solid rgba(234,229,222,0.1)',
                                            borderRadius: 'var(--radius-md, 12px)',
                                            transition: 'border-color 0.2s',
                                        }}>
                                            {/* Country code: invisible <select> overlaying visible code text */}
                                            <div style={{ position: 'relative', flexShrink: 0, display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                                                <span style={{
                                                    padding: '12px 2px 12px 14px',
                                                    fontSize: 'var(--text-sm, 14px)',
                                                    color: 'rgba(234,229,222,0.5)',
                                                    pointerEvents: 'none', whiteSpace: 'nowrap',
                                                }}>
                                                    {profile.countryCode}
                                                </span>
                                                <span style={{ color: 'rgba(234,229,222,0.15)', fontSize: 10, pointerEvents: 'none', marginRight: 2 }}>▾</span>
                                                <select
                                                    value={profile.countryCode}
                                                    onChange={e => setProfile(p => ({ ...p, countryCode: e.target.value }))}
                                                    style={{
                                                        position: 'absolute', inset: 0,
                                                        opacity: 0, cursor: 'pointer',
                                                        width: '100%', height: '100%',
                                                    }}
                                                >
                                                    {COUNTRY_CODES.map(cc => (
                                                        <option key={cc.code} value={cc.code}>{cc.code} {cc.country}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <input
                                                className="gs-input" type="tel"
                                                value={profile.phone}
                                                onChange={e => setProfile(p => ({ ...p, phone: e.target.value }))}
                                                placeholder="81 xxx xxxx"
                                                style={{
                                                    ...inputStyle,
                                                    border: 'none', borderRadius: 0,
                                                    background: 'transparent',
                                                    flex: 1, minWidth: 0,
                                                    paddingLeft: 6,
                                                }}
                                            />
                                        </div>
                                    </div>

                                    {/* Role selection */}
                                    <div>
                                        <label style={label}>I am a *</label>
                                        <div style={{ display: 'flex', gap: 10 }}>
                                            {[
                                                { id: 'owner', label: 'Property Owner', icon: '🏠' },
                                                { id: 'manager', label: 'Property Manager', icon: '📋' },
                                            ].map(opt => (
                                                <div key={opt.id}
                                                    className={`gs-option ${profile.userType === opt.id ? 'active' : ''}`}
                                                    onClick={() => setProfile(p => ({ ...p, userType: opt.id }))}
                                                    style={{ ...card, flex: 1, padding: '12px 14px', textAlign: 'center', cursor: 'pointer' }}>
                                                    <div style={{ fontSize: 24, marginBottom: 4 }}>{opt.icon}</div>
                                                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-stone)' }}>{opt.label}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {/* ── Password section (OTP path only — skip for Google auth AND pre-existing auth) ── */}
                                    {!skipPasswordSection && (
                                        <>
                                            <div className="gs-divider" style={{ margin: '6px 0' }}>Secure your account</div>
                                            <div>
                                                <label style={label}>Password *</label>
                                                <input className="gs-input" type="password" value={newPassword}
                                                    onChange={e => { setNewPassword(e.target.value); setPasswordError(''); }}
                                                    onFocus={() => setPasswordFocused(true)}
                                                    onBlur={() => setPasswordFocused(false)}
                                                    placeholder="Create a password" style={inputStyle}
                                                    autoComplete="new-password" />
                                            </div>
                                            {/* Live password rules checklist */}
                                            {(passwordFocused || newPassword.length > 0) && (
                                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', fontSize: 11, lineHeight: 1.8 }}>
                                                    {pwRules.map(r => (
                                                        <span key={r.key} style={{
                                                            color: newPassword.length === 0
                                                                ? 'rgba(234,229,222,0.25)'
                                                                : r.pass ? '#4A7C59' : 'rgba(234,229,222,0.3)',
                                                            transition: 'color 0.2s',
                                                        }}>
                                                            {newPassword.length > 0 && r.pass ? '✓' : '○'} {r.label}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                            <div>
                                                <label style={label}>Confirm Password *</label>
                                                <input className="gs-input" type="password" value={confirmPassword}
                                                    onChange={e => { setConfirmPassword(e.target.value); setPasswordError(''); }}
                                                    onKeyDown={e => e.key === 'Enter' && allPwRulesPass && confirmPassword === newPassword && profile.firstName.trim() && profile.lastName.trim() && profile.userType && handleSetPassword()}
                                                    placeholder="Re-enter your password" style={inputStyle}
                                                    autoComplete="new-password" />
                                            </div>
                                            {confirmPassword.length > 0 && newPassword !== confirmPassword && (
                                                <div style={{ fontSize: 12, color: '#D64545' }}>✗ Passwords do not match</div>
                                            )}
                                            {confirmPassword.length > 0 && newPassword === confirmPassword && allPwRulesPass && (
                                                <div style={{ fontSize: 12, color: '#4A7C59' }}>✓ Passwords match</div>
                                            )}
                                        </>
                                    )}
                                </div>

                                {passwordError && (
                                    <div style={{ fontSize: 13, color: '#D64545', marginTop: 12, padding: '8px 12px', background: 'rgba(214,69,69,0.08)', borderRadius: 8 }}>
                                        {passwordError}
                                    </div>
                                )}
                            </div>

                            {/* Phase 872: Use no-password save for Google auth AND pre-existing auth */}
                            {skipPasswordSection ? (
                                <button
                                    onClick={handleGoogleSave}
                                    disabled={draftSaving || !profile.firstName.trim() || !profile.lastName.trim() || !profile.userType}
                                    style={{ ...primaryBtn, ...disabledStyle(draftSaving || !profile.firstName.trim() || !profile.lastName.trim() || !profile.userType) }}>
                                    {draftSaving ? 'Saving…' : 'Save Property →'}
                                </button>
                            ) : (
                                <button
                                    onClick={handleSetPassword}
                                    disabled={draftSaving || !profile.firstName.trim() || !profile.lastName.trim() || !profile.userType || !allPwRulesPass || newPassword !== confirmPassword}
                                    style={{ ...primaryBtn, ...disabledStyle(draftSaving || !profile.firstName.trim() || !profile.lastName.trim() || !profile.userType || !allPwRulesPass || newPassword !== confirmPassword) }}>
                                    {draftSaving ? 'Creating your account…' : 'Create Account & Save Property →'}
                                </button>
                            )}
                        </div>
                    )}

                    {/* ── Photo Lightbox ── */}
                    {lightboxIndex !== null && state.property.photos.length > 0 && (
                        <div onClick={() => setLightboxIndex(null)} style={{
                            position: 'fixed', inset: 0, zIndex: 9999,
                            background: 'rgba(0,0,0,0.85)', display: 'flex',
                            alignItems: 'center', justifyContent: 'center',
                            cursor: 'pointer',
                        }}>
                            <img
                                src={state.property.photos[lightboxIndex]}
                                alt={`Photo ${lightboxIndex + 1}`}
                                style={{ maxWidth: '90vw', maxHeight: '80vh', borderRadius: 12, objectFit: 'contain' }}
                            />
                            {/* Nav arrows */}
                            {lightboxIndex > 0 && (
                                <button onClick={e => { e.stopPropagation(); setLightboxIndex(lightboxIndex - 1); }} style={{
                                    position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)',
                                    background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: 99,
                                    width: 40, height: 40, color: '#fff', fontSize: 20, cursor: 'pointer',
                                }}>‹</button>
                            )}
                            {lightboxIndex < state.property.photos.length - 1 && (
                                <button onClick={e => { e.stopPropagation(); setLightboxIndex(lightboxIndex + 1); }} style={{
                                    position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)',
                                    background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: 99,
                                    width: 40, height: 40, color: '#fff', fontSize: 20, cursor: 'pointer',
                                }}>›</button>
                            )}
                            <div style={{
                                position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
                                fontSize: 13, color: 'rgba(255,255,255,0.5)',
                            }}>
                                {lightboxIndex + 1} / {state.property.photos.length}
                            </div>
                        </div>
                    )}

                    {/* Step 7 without auth — safety redirect */}
                    {state.step === 7 && !authedUser && (
                        <div className="gs-fade" style={{ textAlign: 'center', padding: 'var(--space-8) 0' }}>
                            <p style={{ color: 'rgba(234,229,222,0.5)', marginBottom: 16 }}>Please sign in to continue.</p>
                            <button onClick={() => setStep(6)} style={primaryBtn}>← Back to Sign In</button>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
