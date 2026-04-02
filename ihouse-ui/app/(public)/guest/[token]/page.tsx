'use client';

/**
 * Phase 64 — Guest Portal: Current Stay V1
 * Route: /guest/[token]
 *
 * Public route, token-authenticated.
 * Structure:
 *   1. Welcome / Stay Header
 *   2. Home Essentials (wifi, check-in/out, emergency, house rules)
 *   3. How This Home Works  (via /{token}/house-info)
 *   4. Need Help            (via /{token}/contact + /{token}/messages)
 *   5. Around You           (via /{token}/extras + /{token}/location)
 *   6. Your Stay            (guests, deposit, checkout guidance)
 */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import DMonogram from '../../../../components/DMonogram';
import CompactLangSwitcher from '../../../../components/CompactLangSwitcher';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GuestPortalData {
    // Section 1 — Welcome / Stay Header
    guest_name?: string;
    check_in?: string;
    check_out?: string;
    booking_status?: string;
    cover_photo_url?: string;      // Phase 1047A — wired from properties.cover_photo_url
    // Section 2 — Home Essentials
    property_name: string;
    property_address?: string;
    wifi_name?: string;
    wifi_password?: string;
    check_in_time?: string;
    check_out_time?: string;
    house_rules?: string[];
    emergency_contact?: string;
    welcome_message?: string;
    // Section 6 — Your Stay
    number_of_guests?: number;
    deposit_status?: string;
    checkout_notes?: string;
    // Phase 1047B — Guest Portal Host Identity (display layer only, not routing truth)
    portal_host_name?: string | null;
    portal_host_photo_url?: string | null;
    portal_host_intro?: string | null;
}

interface HouseInfo {
    ac_instructions?: string;
    hot_water_info?: string;
    stove_instructions?: string;
    parking_info?: string;
    pool_instructions?: string;
    laundry_info?: string;
    tv_info?: string;
    extra_notes?: string;
}

interface ContactInfo {
    name?: string;
    phone?: string;
    email?: string;
    line?: string;
    whatsapp_link?: string;   // Phase 1047A — returned by /contact endpoint
}

interface ExtraItem {
    extra_id: string;
    name: string;
    price?: number;
    currency?: string;
    description?: string;
}

interface LocationInfo {
    lat?: number;
    lng?: number;
    maps_url?: string;
    waze_url?: string;
    nearby?: string[];
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

const cs = (values: Record<string, string>) => Object.entries(values).map(([k, v]) => `${k}:${v}`).join(';');

const SURFACE = '#1a1f2e';
const BORDER  = '#ffffff12';
const TEXT    = '#f9fafb';
const DIM     = '#6b7280';
const FAINT   = '#4b5563';
const PRIMARY = '#3b82f6';
const RADIUS  = '16px';

// ---------------------------------------------------------------------------
// Section header
// ---------------------------------------------------------------------------

function SectionHeader({ emoji, label }: { emoji: string; label: string }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '24px 0 12px' }}>
            <span style={{ fontSize: 18 }}>{emoji}</span>
            <div style={{
                fontSize: 11, fontWeight: 700, letterSpacing: '0.07em',
                textTransform: 'uppercase', color: DIM,
            }}>
                {label}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Info Card — reused from Phase 388
// ---------------------------------------------------------------------------

function InfoCard({ icon, label, value, mono }: {
    icon: string; label: string; value: string; mono?: boolean;
}) {
    return (
        <div style={{
            background: SURFACE, border: `1px solid ${BORDER}`,
            borderRadius: RADIUS, padding: 16,
            display: 'flex', alignItems: 'flex-start', gap: 12,
        }}>
            <span style={{ fontSize: 22, flexShrink: 0 }}>{icon}</span>
            <div>
                <div style={{ fontSize: 11, color: DIM, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                    {label}
                </div>
                <div style={{
                    fontSize: 16, fontWeight: 600, color: TEXT,
                    fontFamily: mono ? 'monospace' : 'inherit',
                    wordBreak: 'break-all',
                }}>
                    {value}
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// House info row
// ---------------------------------------------------------------------------

function HouseInfoItem({ icon, label, value }: { icon: string; label: string; value: string }) {
    return (
        <div style={{
            padding: '12px 16px', borderBottom: `1px solid ${BORDER}`,
            display: 'flex', gap: 12, alignItems: 'flex-start',
        }}>
            <span style={{ fontSize: 20, flexShrink: 0 }}>{icon}</span>
            <div>
                <div style={{ fontSize: 12, color: DIM, marginBottom: 4, fontWeight: 600 }}>{label}</div>
                <div style={{ fontSize: 14, color: TEXT, lineHeight: 1.5 }}>{value}</div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Section 1 — Welcome / Stay Header
// ---------------------------------------------------------------------------

// Phase 1047A-name: unknown status values must also NOT leak through as raw internal strings.
function _stayStatusChip(status?: string | null): string {
    const s = (status || '').toLowerCase().replace(/-/g, '_');
    if (['checked_in', 'checkedin', 'instay', 'active'].includes(s)) return '✅ In Stay';
    if (['confirmed'].includes(s)) return '📅 Upcoming';
    if (['checked_out', 'checkedout', 'completed'].includes(s)) return '✔ Checked Out';
    // Phase 1047A-name: unknown values fall to generic guest-safe label, not the raw status string
    return '🏡 In Stay';
}

function WelcomeHeader({ data }: { data: GuestPortalData }) {
    const fmt = (d?: string) => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';

    return (
        <div style={{
            background: `linear-gradient(135deg, #1e3a5f 0%, #1a2744 100%)`,
            borderRadius: RADIUS, padding: 24, marginBottom: 4,
            border: `1px solid #2a4a7f`,
            overflow: 'hidden',
        }}>
            {/* Phase 1047A: cover photo hero image if set */}
            {data.cover_photo_url && (
                <div style={{
                    margin: '-24px -24px 16px -24px',
                    height: 160,
                    background: `url(${data.cover_photo_url}) center/cover no-repeat`,
                    borderRadius: `${RADIUS} ${RADIUS} 0 0`,
                }} />
            )}
            {/* Phase 1047A: real status — was hardcoded '✅ Checked In' */}
            <div style={{ fontSize: 13, color: '#93c5fd', marginBottom: 8, fontWeight: 600 }}>
                {_stayStatusChip(data.booking_status)}
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, color: TEXT, marginBottom: 4, letterSpacing: '-0.02em' }}>
                {data.guest_name ? `Welcome, ${data.guest_name.split(' ')[0]}` : 'Welcome'}
            </div>
            <div style={{ fontSize: 16, color: '#93c5fd', fontWeight: 600, marginBottom: 16 }}>
                {/* Phase 1047A-name: backend returns null when name missing — never fall through to a code */}
                {data.property_name || 'Your Villa'}
            </div>
            {(data.check_in || data.check_out) && (
                <div style={{ display: 'flex', gap: 12 }}>
                    {data.check_in && (
                        <div style={{
                            flex: 1, background: '#0f1e3a', borderRadius: 10,
                            padding: '10px 12px', border: '1px solid #2a4a7f',
                        }}>
                            <div style={{ fontSize: 10, color: '#60a5fa', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Check-in</div>
                            <div style={{ fontSize: 13, fontWeight: 700, color: TEXT }}>{fmt(data.check_in)}</div>
                        </div>
                    )}
                    {data.check_out && (
                        <div style={{
                            flex: 1, background: '#0f1e3a', borderRadius: 10,
                            padding: '10px 12px', border: '1px solid #2a4a7f',
                        }}>
                            <div style={{ fontSize: 10, color: '#60a5fa', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Check-out</div>
                            <div style={{ fontSize: 13, fontWeight: 700, color: TEXT }}>{fmt(data.check_out)}</div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Phase 1047B — Guest Portal Host Identity Block
// Display layer only. Renders only when portal_host_name is set.
// No name → renders nothing. Photo missing → initials avatar. Intro missing → compact.
// ---------------------------------------------------------------------------

function PortalHostBlock({ data }: { data: GuestPortalData }) {
    if (!data.portal_host_name) return null;

    const name = data.portal_host_name;
    const initial = name.charAt(0).toUpperCase();
    const hasPhoto = !!data.portal_host_photo_url;
    const intro = data.portal_host_intro?.trim() || null;

    return (
        <div style={{
            background: 'rgba(30, 58, 95, 0.6)',
            border: '1px solid rgba(42, 74, 127, 0.7)',
            borderRadius: RADIUS,
            padding: '16px 20px',
            marginBottom: 4,
            display: 'flex',
            alignItems: intro ? 'flex-start' : 'center',
            gap: 16,
        }}>
            {/* Avatar: photo or initials */}
            {hasPhoto ? (
                <img
                    src={data.portal_host_photo_url!}
                    alt={name}
                    style={{
                        width: 48, height: 48, borderRadius: '50%',
                        objectFit: 'cover', flexShrink: 0,
                        border: '2px solid rgba(99, 102, 241, 0.5)',
                    }}
                    onError={e => {
                        // fallback to initials-style div on photo error
                        const el = e.currentTarget;
                        el.style.display = 'none';
                        el.parentElement!.querySelector<HTMLDivElement>('[data-initials]')!.style.display = 'flex';
                    }}
                />
            ) : null}
            {/* Initials avatar — shown when no photo, or as fallback */}
            <div
                data-initials=""
                style={{
                    width: 48, height: 48, borderRadius: '50%',
                    background: 'rgba(99, 102, 241, 0.25)',
                    border: '2px solid rgba(99, 102, 241, 0.4)',
                    color: '#a5b4fc',
                    fontSize: 18, fontWeight: 700,
                    flexShrink: 0,
                    display: hasPhoto ? 'none' : 'flex',
                    alignItems: 'center', justifyContent: 'center',
                }}
            >
                {initial}
            </div>
            {/* Text */}
            <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, color: '#93c5fd', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                    Your Host
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, color: TEXT, marginBottom: intro ? 6 : 0 }}>
                    {name}
                </div>
                {intro && (
                    <div style={{ fontSize: 13, color: '#9ca3af', lineHeight: 1.55 }}>
                        {intro}
                    </div>
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Section 3 — How This Home Works
// ---------------------------------------------------------------------------

function HowThisHomeWorks({ token, apiBase }: { token: string; apiBase: string }) {
    const [info, setInfo] = useState<HouseInfo | null>(null);

    useEffect(() => {
        fetch(`${apiBase}/guest/${encodeURIComponent(token)}/house-info`)
            .then(r => r.ok ? r.json() : null)
            // Phase 1047A: backend wraps in { info: {...} } — unwrap before setting state
            .then(d => d && setInfo(d.info ?? d))
            .catch(() => {});
    }, [token, apiBase]);

    const items: Array<{ icon: string; key: keyof HouseInfo; label: string }> = [
        { icon: '❄️', key: 'ac_instructions', label: 'Air Conditioning' },
        { icon: '🚿', key: 'hot_water_info', label: 'Hot Water' },
        { icon: '🍳', key: 'stove_instructions', label: 'Stove / Kitchen' },
        { icon: '🚗', key: 'parking_info', label: 'Parking' },
        { icon: '🏊', key: 'pool_instructions', label: 'Pool' },
        { icon: '👕', key: 'laundry_info', label: 'Laundry' },
        { icon: '📺', key: 'tv_info', label: 'TV / Entertainment' },
        { icon: '📝', key: 'extra_notes', label: 'Extra Notes' },
    ];

    const available = info ? items.filter(i => info[i.key]) : [];
    if (!info || available.length === 0) return null;

    return (
        <>
            <SectionHeader emoji="🏠" label="How This Home Works" />
            <div style={{ background: SURFACE, borderRadius: RADIUS, border: `1px solid ${BORDER}`, overflow: 'hidden' }}>
                {available.map(({ icon, key, label }) => (
                    <HouseInfoItem key={key} icon={icon} label={label} value={info[key] as string} />
                ))}
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Section 4 — Need Help
// ---------------------------------------------------------------------------

function NeedHelp({ token, apiBase }: { token: string; apiBase: string }) {
    const [contact, setContact] = useState<ContactInfo | null>(null);
    const [msgSent, setMsgSent] = useState(false);
    const [msgText, setMsgText] = useState('');
    const [sending, setSending] = useState(false);
    // Phase 1047A: surface real send errors instead of silently swallowing them
    const [msgError, setMsgError] = useState<string | null>(null);

    useEffect(() => {
        fetch(`${apiBase}/guest/${encodeURIComponent(token)}/contact`)
            .then(r => r.ok ? r.json() : null)
            .then(d => d && setContact(d))
            .catch(() => {});
    }, [token, apiBase]);

    const sendMessage = async () => {
        if (!msgText.trim()) return;
        setSending(true);
        setMsgError(null);
        try {
            // Phase 1047A: body key was 'message' — backend expects 'content'
            const resp = await fetch(`${apiBase}/guest/${encodeURIComponent(token)}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: msgText }),
            });
            // Phase 1047A: check real response status before showing success
            if (!resp.ok) {
                const body = await resp.json().catch(() => ({}));
                setMsgError(body?.detail || 'Something went wrong. Please try again.');
                return;
            }
            setMsgSent(true);
            setMsgText('');
        } catch {
            setMsgError('Unable to send. Please check your connection and try again.');
        } finally {
            setSending(false);
        }
    };

    return (
        <>
            <SectionHeader emoji="💬" label="Need Help?" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Phase 1047A: contact.phone is correct. contact.whatsapp_link now available. */}
                {/* contact.line was never returned by the /contact endpoint — removed. */}
                {contact?.phone && (
                    <InfoCard icon="📞" label="Call / WhatsApp" value={contact.phone} />
                )}
                {contact?.whatsapp_link && (
                    <a
                        href={contact.whatsapp_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                            display: 'flex', alignItems: 'center', gap: 12,
                            background: SURFACE, border: `1px solid ${BORDER}`,
                            borderRadius: RADIUS, padding: 16, textDecoration: 'none',
                        }}
                    >
                        <span style={{ fontSize: 22, flexShrink: 0 }}>💬</span>
                        <div>
                            <div style={{ fontSize: 11, color: DIM, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>WhatsApp</div>
                            <div style={{ fontSize: 15, fontWeight: 600, color: '#25d366' }}>Open WhatsApp</div>
                        </div>
                    </a>
                )}
                <div style={{
                    background: SURFACE, border: `1px solid ${BORDER}`,
                    borderRadius: RADIUS, padding: 16,
                }}>
                    <div style={{ fontSize: 12, color: DIM, marginBottom: 10, fontWeight: 600 }}>
                        Send a message to your host
                    </div>
                    {msgSent ? (
                        <div style={{ fontSize: 14, color: '#34d399', fontWeight: 600 }}>
                            ✅ Your message was sent. We&apos;ll get back to you shortly.
                        </div>
                    ) : (
                        <>
                            <textarea
                                value={msgText}
                                onChange={e => { setMsgText(e.target.value); setMsgError(null); }}
                                placeholder="Type your message…"
                                rows={3}
                                style={{
                                    width: '100%', background: '#0f1421', border: `1px solid ${BORDER}`,
                                    borderRadius: 10, padding: '10px 12px', color: TEXT,
                                    fontSize: 14, resize: 'vertical', boxSizing: 'border-box',
                                    fontFamily: 'inherit',
                                }}
                            />
                            {/* Phase 1047A: show real error when send fails */}
                            {msgError && (
                                <div style={{ fontSize: 13, color: '#f87171', marginTop: 8 }}>
                                    ⚠ {msgError}
                                </div>
                            )}
                            <button
                                onClick={sendMessage}
                                disabled={sending || !msgText.trim()}
                                style={{
                                    marginTop: 10, width: '100%', padding: '10px 0',
                                    background: PRIMARY, border: 'none', borderRadius: 10,
                                    color: '#fff', fontWeight: 700, fontSize: 14,
                                    cursor: sending || !msgText.trim() ? 'not-allowed' : 'pointer',
                                    opacity: !msgText.trim() ? 0.5 : 1,
                                }}
                            >
                                {sending ? 'Sending…' : 'Send Message'}
                            </button>
                        </>
                    )}
                </div>
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Section 5 — Around You
// ---------------------------------------------------------------------------

function AroundYou({ token, apiBase }: { token: string; apiBase: string }) {
    const [location, setLocation] = useState<LocationInfo | null>(null);
    const [extras, setExtras] = useState<ExtraItem[]>([]);

    useEffect(() => {
        Promise.all([
            fetch(`${apiBase}/guest/${encodeURIComponent(token)}/location`).then(r => r.ok ? r.json() : null).catch(() => null),
            fetch(`${apiBase}/guest/${encodeURIComponent(token)}/extras`).then(r => r.ok ? r.json() : null).catch(() => null),
        ]).then(([loc, ext]) => {
            if (loc) setLocation(loc);
            if (ext?.items) setExtras(ext.items);
        });
    }, [token, apiBase]);

    if (!location && extras.length === 0) return null;

    return (
        <>
            <SectionHeader emoji="📍" label="Around You" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {location && (
                    <div style={{
                        background: SURFACE, border: `1px solid ${BORDER}`,
                        borderRadius: RADIUS, padding: 16,
                        display: 'flex', gap: 12,
                    }}>
                        {location.maps_url && (
                            <a href={location.maps_url} target="_blank" rel="noopener noreferrer" style={{
                                flex: 1, padding: '10px 0', background: '#1e3a5f', borderRadius: 10,
                                color: '#93c5fd', fontWeight: 700, fontSize: 14, textAlign: 'center',
                                textDecoration: 'none',
                            }}>
                                🗺️ Google Maps
                            </a>
                        )}
                        {location.waze_url && (
                            <a href={location.waze_url} target="_blank" rel="noopener noreferrer" style={{
                                flex: 1, padding: '10px 0', background: '#1e3a5f', borderRadius: 10,
                                color: '#93c5fd', fontWeight: 700, fontSize: 14, textAlign: 'center',
                                textDecoration: 'none',
                            }}>
                                🔷 Waze
                            </a>
                        )}
                    </div>
                )}
                {location?.nearby && location.nearby.length > 0 && (
                    <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: RADIUS, padding: 16 }}>
                        <div style={{ fontSize: 12, color: DIM, marginBottom: 10, fontWeight: 600, textTransform: 'uppercase' }}>Nearby</div>
                        {location.nearby.map((place, i) => (
                            <div key={i} style={{ fontSize: 14, color: TEXT, marginBottom: 4, display: 'flex', gap: 8 }}>
                                <span style={{ color: DIM }}>•</span><span>{place}</span>
                            </div>
                        ))}
                    </div>
                )}
                {extras.length > 0 && (
                    <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: RADIUS, overflow: 'hidden' }}>
                        <div style={{ padding: '12px 16px', borderBottom: `1px solid ${BORDER}` }}>
                            <div style={{ fontSize: 12, color: DIM, fontWeight: 700, textTransform: 'uppercase' }}>Extras & Services</div>
                        </div>
                        {extras.map(e => (
                            <div key={e.extra_id} style={{ padding: '12px 16px', borderBottom: `1px solid ${BORDER}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div style={{ fontSize: 14, fontWeight: 600, color: TEXT }}>{e.name}</div>
                                    {e.description && <div style={{ fontSize: 12, color: DIM, marginTop: 2 }}>{e.description}</div>}
                                </div>
                                {e.price && (
                                    <div style={{ fontSize: 14, fontWeight: 700, color: '#34d399', marginLeft: 16, flexShrink: 0 }}>
                                        {e.currency ?? ''}{e.price}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Section 6 — Your Stay
// ---------------------------------------------------------------------------

function YourStay({ data }: { data: GuestPortalData }) {
    const hasAnything = data.number_of_guests || data.deposit_status || data.checkout_notes;
    if (!hasAnything) return null;

    const depositLabel: Record<string, string> = {
        collected: '✅ Collected',
        pending: '⏳ Pending',
        returned: '↩️ Returned',
        waived: '–– Waived',
    };

    return (
        <>
            <SectionHeader emoji="📋" label="Your Stay" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {data.number_of_guests && (
                    <InfoCard icon="👥" label="Guests" value={`${data.number_of_guests} guest${data.number_of_guests !== 1 ? 's' : ''}`} />
                )}
                {data.deposit_status && (
                    <InfoCard icon="💰" label="Deposit Status" value={depositLabel[data.deposit_status] ?? data.deposit_status} />
                )}
                {data.checkout_notes && (
                    <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: RADIUS, padding: 16 }}>
                        <div style={{ fontSize: 12, color: DIM, marginBottom: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                            🛏️ Checkout Notes
                        </div>
                        <div style={{ fontSize: 14, color: TEXT, lineHeight: 1.6 }}>{data.checkout_notes}</div>
                    </div>
                )}
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function GuestPortalPage() {
    const params = useParams();
    const token = params?.token as string;
    const [data, setData] = useState<GuestPortalData | null>(null);
    const [error, setError] = useState(false);
    const [loading, setLoading] = useState(true);

    const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

    useEffect(() => {
        if (!token) { setError(true); setLoading(false); return; }
        fetch(`${API_BASE}/guest/portal/${encodeURIComponent(token)}`)
            .then(r => { if (!r.ok) throw new Error('Invalid'); return r.json(); })
            .then(d => setData(d))
            .catch(() => setError(true))
            .finally(() => setLoading(false));
    }, [token]);

    if (error) {
        return (
            <div style={{
                minHeight: '100vh', display: 'flex', alignItems: 'center',
                justifyContent: 'center', flexDirection: 'column', gap: 16,
                padding: 24, textAlign: 'center',
            }}>
                <DMonogram size={48} />
                <h1 style={{ fontSize: 22, fontWeight: 800, color: TEXT, margin: 0 }}>Link Expired or Invalid</h1>
                <p style={{ fontSize: 14, color: DIM, maxWidth: 340 }}>
                    This guest access link is no longer valid. Please contact your host for a new link.
                </p>
                <div style={{ fontSize: 11, color: FAINT, marginTop: 16 }}>info@domaniqo.com</div>
            </div>
        );
    }

    if (loading) {
        return (
            <div style={{
                minHeight: '100vh', display: 'flex', alignItems: 'center',
                justifyContent: 'center', flexDirection: 'column', gap: 12,
            }}>
                <DMonogram size={40} />
                <div style={{ fontSize: 14, color: DIM, animation: 'pulse 1.5s infinite' }}>
                    Loading your stay information…
                </div>
                <style>{`@keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }`}</style>
            </div>
        );
    }

    if (!data) return null;

    return (
        <>
            <style>{`
                @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
            `}</style>

            <div style={{
                maxWidth: 480, margin: '0 auto',
                padding: '20px 16px 40px',
                minHeight: '100vh',
                animation: 'fadeIn 400ms ease',
            }}>
                {/* Language switcher */}
                <div style={{ position: 'fixed', top: 12, right: 14, zIndex: 200 }}>
                    <CompactLangSwitcher theme="auto" position="inline" />
                </div>

                {/* Top logo */}
                <div style={{ textAlign: 'center', paddingTop: 32, marginBottom: 20 }}>
                    <DMonogram size={32} />
                </div>

                {/* Section 1 — Welcome / Stay Header */}
                <WelcomeHeader data={data} />

                {/* Phase 1047B — Host Identity Block (renders only when portal_host_name is set) */}
                <PortalHostBlock data={data} />

                {/* Section 2 — Home Essentials */}
                <SectionHeader emoji="🏡" label="Home Essentials" />

                {/* Welcome message */}
                {data.welcome_message && (
                    <div style={{
                        background: SURFACE, border: `1px solid ${BORDER}`,
                        borderRadius: RADIUS, padding: 16, marginBottom: 12,
                        fontSize: 15, color: '#e5e7eb', lineHeight: 1.6,
                    }}>
                        {data.welcome_message}
                    </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {data.wifi_name && <InfoCard icon="📶" label="Wi-Fi Network" value={data.wifi_name} mono />}
                    {data.wifi_password && <InfoCard icon="🔑" label="Wi-Fi Password" value={data.wifi_password} mono />}
                    {data.check_in_time && <InfoCard icon="🛬" label="Check-in Time" value={data.check_in_time} />}
                    {data.check_out_time && <InfoCard icon="🛫" label="Check-out Time" value={data.check_out_time} />}
                    {data.emergency_contact && <InfoCard icon="🆘" label="Emergency Contact" value={data.emergency_contact} />}
                </div>

                {/* House rules */}
                {data.house_rules && data.house_rules.length > 0 && (
                    <div style={{
                        marginTop: 12, background: SURFACE,
                        border: `1px solid ${BORDER}`, borderRadius: RADIUS, padding: 16,
                    }}>
                        <div style={{ fontSize: 11, color: DIM, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
                            📋 House Rules
                        </div>
                        {data.house_rules.map((rule, i) => (
                            <div key={i} style={{
                                display: 'flex', alignItems: 'flex-start', gap: 8,
                                marginBottom: 8, fontSize: 14, color: '#d1d5db', lineHeight: 1.5,
                            }}>
                                <span style={{ color: DIM, flexShrink: 0 }}>•</span>
                                <span>{rule}</span>
                            </div>
                        ))}
                    </div>
                )}

                {/* Section 3 — How This Home Works */}
                <HowThisHomeWorks token={token} apiBase={API_BASE} />

                {/* Section 4 — Need Help */}
                <NeedHelp token={token} apiBase={API_BASE} />

                {/* Section 5 — Around You */}
                <AroundYou token={token} apiBase={API_BASE} />

                {/* Section 6 — Your Stay */}
                <YourStay data={data} />

                {/* Footer */}
                <div style={{ textAlign: 'center', marginTop: 32, padding: 16 }}>
                    <DMonogram size={20} />
                    <div style={{ fontSize: 11, color: FAINT, marginTop: 8 }}>
                        Powered by Domaniqo · info@domaniqo.com
                    </div>
                </div>
            </div>
        </>
    );
}
