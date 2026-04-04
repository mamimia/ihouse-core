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

import { useEffect, useState, useCallback } from 'react';
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
    // Phase 1064: track load completion to distinguish "not loaded yet" from "loaded with no content"
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
        fetch(`${apiBase}/guest/${encodeURIComponent(token)}/house-info`)
            .then(r => r.ok ? r.json() : null)
            // Phase 1047A: backend wraps in { info: {...} } — unwrap before setting state
            .then(d => { if (d) setInfo(d.info ?? d); })
            .catch(() => {})
            .finally(() => setLoaded(true));
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
    // Phase 1064: hide until loaded; if loaded and nothing configured, hide entirely (not broken-looking)
    if (!loaded || available.length === 0) return null;

    return (
        <>
            <SectionHeader emoji="🏠" label="How This Home Works" />
            <div style={{ background: SURFACE, borderRadius: RADIUS, border: `1px solid ${BORDER}`, overflow: 'hidden' }}>
                {available.map(({ icon, key, label }) => (
                    <HouseInfoItem key={key} icon={icon} label={label} value={info![key] as string} />
                ))}
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Phase 1053 — Guest Conversation Thread
// Fetches GET /{token}/messages — shows history above the note form.
// Polls every 30s. Host labeled as portal_host_name or "Your Host".
// ---------------------------------------------------------------------------

interface PortalMessage {
    id: string;
    sender_type: string;   // 'guest' | 'host'
    message: string;
    created_at: string | null;
}

function fmtMsgTime(iso: string | null): string {
    if (!iso) return '';
    try {
        const d = new Date(iso);
        const diffMs = Date.now() - d.getTime();
        const diffMin = Math.floor(diffMs / 60000);
        if (diffMin < 1) return 'just now';
        if (diffMin < 60) return `${diffMin}m ago`;
        const h = Math.floor(diffMin / 60);
        if (h < 24) return `${h}h ago`;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return ''; }
}

function ConversationThread({ token, apiBase, newMsgSignal }: {
    token: string;
    apiBase: string;
    newMsgSignal: number;   // increments when guest sends a new note → triggers immediate re-fetch
}) {
    const [messages, setMessages] = useState<PortalMessage[]>([]);
    const [hostLabel, setHostLabel] = useState('Your Host');
    const [loaded, setLoaded] = useState(false);

    const fetchMessages = useCallback(async () => {
        try {
            const resp = await fetch(`${apiBase}/guest/${encodeURIComponent(token)}/messages`);
            if (!resp.ok) return;
            const data = await resp.json();
            setMessages(data.messages ?? []);
            if (data.portal_host_name) setHostLabel(data.portal_host_name);
            setLoaded(true);
        } catch { /* non-blocking */ }
    }, [token, apiBase]);

    // Mount fetch + 30s poll
    useEffect(() => {
        fetchMessages();
        const interval = setInterval(fetchMessages, 30000);
        return () => clearInterval(interval);
    }, [fetchMessages]);

    // Immediate re-fetch when guest sends a new message
    useEffect(() => {
        if (newMsgSignal > 0) {
            setTimeout(fetchMessages, 800); // small delay for backend write to settle
        }
    }, [newMsgSignal, fetchMessages]);

    // Null path — no messages yet
    if (!loaded || messages.length === 0) return null;

    return (
        <div style={{ marginBottom: 16 }}>
            <div style={{
                fontSize: 11, color: DIM, fontWeight: 700,
                textTransform: 'uppercase', letterSpacing: '0.06em',
                marginBottom: 10,
            }}>
                Conversation
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {messages.map(msg => {
                    const isGuest = msg.sender_type === 'guest';
                    return (
                        <div
                            key={msg.id}
                            style={{
                                display: 'flex', flexDirection: 'column',
                                alignItems: isGuest ? 'flex-end' : 'flex-start',
                            }}
                        >
                            {/* Sender label */}
                            <div style={{
                                fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                                textTransform: 'uppercase',
                                color: isGuest ? '#60a5fa' : '#93c5fd',
                                marginBottom: 3,
                            }}>
                                {isGuest ? 'You' : hostLabel}
                            </div>
                            {/* Bubble */}
                            <div style={{
                                maxWidth: '82%',
                                padding: '9px 13px',
                                borderRadius: isGuest
                                    ? '16px 4px 16px 16px'
                                    : '4px 16px 16px 16px',
                                background: isGuest
                                    ? 'rgba(59,130,246,0.18)'
                                    : 'rgba(255,255,255,0.06)',
                                border: isGuest
                                    ? '1px solid rgba(59,130,246,0.3)'
                                    : `1px solid ${BORDER}`,
                                fontSize: 14, color: TEXT,
                                lineHeight: 1.55, wordBreak: 'break-word',
                            }}>
                                {msg.message}
                            </div>
                            {/* Timestamp */}
                            {msg.created_at && (
                                <div style={{ fontSize: 10, color: FAINT, marginTop: 3 }}>
                                    {fmtMsgTime(msg.created_at)}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
            <div style={{
                height: 1, background: BORDER, margin: '14px 0 4px',
            }} />
        </div>
    );
}

// ---------------------------------------------------------------------------
// Section 4 — Need Help (updated Phase 1053: thread above form)
// ---------------------------------------------------------------------------

function NeedHelp({ token, apiBase }: { token: string; apiBase: string }) {
    const [contact, setContact] = useState<ContactInfo | null>(null);
    const [msgSent, setMsgSent] = useState(false);
    const [msgText, setMsgText] = useState('');
    const [sending, setSending] = useState(false);
    // Phase 1047A: surface real send errors instead of silently swallowing them
    const [msgError, setMsgError] = useState<string | null>(null);
    // Phase 1053: signal to ConversationThread to re-fetch after guest sends
    const [sentSignal, setSentSignal] = useState(0);

    // Phase 1047-polish: auto-dismiss success banner after 4s
    useEffect(() => {
        if (!msgSent) return;
        const t = setTimeout(() => setMsgSent(false), 4000);
        return () => clearTimeout(t);
    }, [msgSent]);

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
            // Phase 1053: trigger thread re-fetch to show the sent message
            setSentSignal(prev => prev + 1);
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

                {/* Phase 1064: no direct contact configured — reassure the guest to use the message box */}
                {contact !== null && !contact?.phone && !contact?.whatsapp_link && (
                    <div style={{
                        background: SURFACE, border: `1px solid ${BORDER}`,
                        borderRadius: RADIUS, padding: 16,
                        display: 'flex', alignItems: 'center', gap: 12,
                    }}>
                        <span style={{ fontSize: 22, flexShrink: 0 }}>✉️</span>
                        <div>
                            <div style={{ fontSize: 12, color: DIM, marginBottom: 4, fontWeight: 600 }}>Contact your host</div>
                            <div style={{ fontSize: 14, color: '#9ca3af', lineHeight: 1.5 }}>
                                Use the message box below to reach your host directly.
                            </div>
                        </div>
                    </div>
                )}
                <div style={{
                    background: SURFACE, border: `1px solid ${BORDER}`,
                    borderRadius: RADIUS, padding: 16,
                }}>
                    {/* Phase 1053: Conversation thread above the note form */}
                    <ConversationThread token={token} apiBase={apiBase} newMsgSignal={sentSignal} />

                    {/* Phase 1047C: honest copy — no false response promise */}
                    <div style={{ fontSize: 12, color: DIM, marginBottom: 10, fontWeight: 600 }}>
                        Leave us a note
                    </div>

                    {/* Phase 1047-polish: success banner — stays above form, auto-clears */}
                    {msgSent && (
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 8,
                            background: 'rgba(52,211,153,0.1)', border: '1px solid rgba(52,211,153,0.25)',
                            borderRadius: 8, padding: '8px 12px', marginBottom: 10,
                            fontSize: 13, color: '#34d399', fontWeight: 600,
                        }}>
                            <span>✅</span>
                            <span>We got your note — thank you.</span>
                        </div>
                    )}

                    {/* Input area always visible — conversation stays open */}
                    <textarea
                        value={msgText}
                        onChange={e => { setMsgText(e.target.value); setMsgError(null); }}
                        placeholder="Any questions or special requests…"
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
                        {sending ? 'Sending…' : 'Send Note'}
                    </button>
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
// Phase 1065 — Guest Checkout Actions
// Flow A: Request Early Check-Out (during stay, before checkout window)
// Flow B: Self Check-Out (within 24h of effective checkout)
// ---------------------------------------------------------------------------

interface CheckoutStatus {
    booking_id: string;
    original_checkout_date: string;
    effective_checkout_date: string;
    is_early_checkout_approved: boolean;
    early_checkout_status: string;   // none | requested | approved | completed
    already_requested_early_checkout: boolean;
    self_checkout_eligible: boolean;
    valid_early_request_dates: string[];
    guest_checkout_confirmed: boolean;
    // Phase 1065B: correct wizard URL with GUEST_CHECKOUT token (auto-generated by backend)
    checkout_portal_url?: string | null;
}

function fmtDate(iso: string): string {
    try {
        const d = new Date(iso + 'T12:00:00Z');
        return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    } catch { return iso; }
}

function GuestCheckoutActions({ token, apiBase }: { token: string; apiBase: string }) {
    const [status, setStatus] = useState<CheckoutStatus | null>(null);
    const [loadError, setLoadError] = useState(false);

    // Flow A: request state
    const [showRequestForm, setShowRequestForm] = useState(false);
    const [selectedDate, setSelectedDate] = useState<string>('');
    const [reason, setReason] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [submitted, setSubmitted] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);

    useEffect(() => {
        fetch(`${apiBase}/guest/${encodeURIComponent(token)}/checkout-status`)
            .then(r => r.ok ? r.json() : null)
            .then(d => { if (d) setStatus(d); else setLoadError(true); })
            .catch(() => setLoadError(true));
    }, [token, apiBase]);

    // Don't render while loading, or if we couldn't load
    if (!status || loadError) return null;

    // Don't show anything if checkout is already fully confirmed by guest
    if (status.guest_checkout_confirmed) return null;

    // Determine what to show
    const showSelfCheckout = status.self_checkout_eligible && !status.guest_checkout_confirmed;
    const isEarlyApproved = status.is_early_checkout_approved;
    const alreadyRequested = status.already_requested_early_checkout;
    const hasValidDates = status.valid_early_request_dates.length > 0;
    // Only show "Request Early Check-Out" if booking is in-stay and dates exist
    // and no request is already pending/approved
    const showRequestCTA = !alreadyRequested && hasValidDates && !showSelfCheckout;

    // Nothing to show — guest is mid-stay, no special window
    if (!showSelfCheckout && !showRequestCTA && !alreadyRequested && !isEarlyApproved) return null;

    const handleSubmitRequest = async () => {
        if (!selectedDate) {
            setSubmitError('Please select a date.');
            return;
        }
        setSubmitting(true);
        setSubmitError(null);
        try {
            const resp = await fetch(`${apiBase}/guest/${encodeURIComponent(token)}/request-early-checkout`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ requested_date: selectedDate, reason: reason.trim() || undefined }),
            });
            const data = await resp.json();
            if (!resp.ok) {
                setSubmitError(data.detail || 'Request failed. Please try again.');
            } else {
                setSubmitted(true);
                setShowRequestForm(false);
                // Optimistically update local status so the UI transitions immediately
                setStatus(prev => prev ? { ...prev, already_requested_early_checkout: true, early_checkout_status: 'requested' } : prev);
            }
        } catch {
            setSubmitError('Network error. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <>
            <SectionHeader emoji="🚪" label="Checkout" />

            {/* === Self Check-Out CTA (Flow B) ===
                 Only shown when within 24h of effective checkout.
                 Links to the existing /guest-checkout/{token} portal. */}
            {showSelfCheckout && (
                <div style={{
                    background: 'linear-gradient(135deg, rgba(59,130,246,0.12) 0%, rgba(30,58,95,0.8) 100%)',
                    border: '1px solid rgba(59,130,246,0.35)',
                    borderRadius: RADIUS, padding: '20px 16px', marginBottom: 12,
                }}>
                    <div style={{ fontSize: 18, fontWeight: 800, color: TEXT, marginBottom: 6 }}>
                        Ready to check out?
                    </div>
                    <div style={{ fontSize: 13, color: '#9ca3af', lineHeight: 1.55, marginBottom: 16 }}>
                        {isEarlyApproved
                            ? `Your early checkout has been approved. Effective: ${fmtDate(status.effective_checkout_date)}.`
                            : `Your checkout is ${fmtDate(status.effective_checkout_date)}.`
                        }
                        {' '}Use the button below to complete your self checkout.
                    </div>

                    {/* Financial honesty — don't pretend everything is final */}
                    <div style={{
                        background: 'rgba(251,191,36,0.07)', border: '1px solid rgba(251,191,36,0.2)',
                        borderRadius: 10, padding: '10px 12px', marginBottom: 16,
                        fontSize: 12, color: '#fbbf24', lineHeight: 1.55,
                    }}>
                        ℹ️ After checkout, our team will complete a final review — including any deposit return or electricity settlement. We'll contact you if anything needs to be clarified.
                    </div>

                    {/* Contact continuity reminder */}
                    <div style={{
                        background: SURFACE, border: `1px solid ${BORDER}`,
                        borderRadius: 10, padding: '10px 12px', marginBottom: 16,
                        fontSize: 12, color: DIM, lineHeight: 1.55,
                    }}>
                        📞 Make sure your host has your correct phone or email in case they need to reach you after checkout.
                    </div>

                    <a
                        href={status.checkout_portal_url || `/guest-checkout/${token}`}
                        style={{
                            display: 'block', background: PRIMARY, border: 'none',
                            borderRadius: 12, padding: '13px 0', textAlign: 'center',
                            color: '#fff', fontWeight: 700, fontSize: 15,
                            textDecoration: 'none', letterSpacing: '-0.01em',
                        }}
                    >
                        Start Self Check-Out →
                    </a>
                </div>
            )}

            {/* === Early Checkout — approved state ===
                 Pending self-checkout window: show approved confirmation. */}
            {isEarlyApproved && !showSelfCheckout && (
                <div style={{
                    background: 'rgba(52,211,153,0.07)', border: '1px solid rgba(52,211,153,0.2)',
                    borderRadius: RADIUS, padding: '16px',
                    display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 12,
                }}>
                    <span style={{ fontSize: 22, flexShrink: 0 }}>✅</span>
                    <div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#34d399', marginBottom: 4 }}>
                            Early checkout approved
                        </div>
                        <div style={{ fontSize: 13, color: '#9ca3af', lineHeight: 1.55 }}>
                            Your early checkout has been confirmed for{' '}
                            <strong style={{ color: TEXT }}>{fmtDate(status.effective_checkout_date)}</strong>.
                            {' '}The self-checkout option will appear once you&apos;re in the checkout window.
                        </div>
                    </div>
                </div>
            )}

            {/* === Early Checkout — requested (pending OM review) === */}
            {(alreadyRequested || submitted) && !isEarlyApproved && (
                <div style={{
                    background: 'rgba(251,191,36,0.07)', border: '1px solid rgba(251,191,36,0.2)',
                    borderRadius: RADIUS, padding: '16px',
                    display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 12,
                }}>
                    <span style={{ fontSize: 22, flexShrink: 0 }}>⏳</span>
                    <div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#fbbf24', marginBottom: 4 }}>
                            Early checkout request received
                        </div>
                        <div style={{ fontSize: 13, color: '#9ca3af', lineHeight: 1.55 }}>
                            We've received your request.
                            {selectedDate && ` Requested date: ${fmtDate(selectedDate)}.`}
                            {' '}The team will review and confirm shortly.
                        </div>
                    </div>
                </div>
            )}

            {/* === Request Early Check-Out CTA (Flow A) ===
                 Shown during stay, when dates are available and no request exists yet. */}
            {showRequestCTA && (
                <div style={{
                    background: SURFACE, border: `1px solid ${BORDER}`,
                    borderRadius: RADIUS, overflow: 'hidden', marginBottom: 12,
                }}>
                    {/* Header row */}
                    <div style={{
                        padding: '14px 16px',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        cursor: 'pointer',
                    }}
                        onClick={() => setShowRequestForm(prev => !prev)}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{ fontSize: 20 }}>📅</span>
                            <div>
                                <div style={{ fontSize: 14, fontWeight: 700, color: TEXT }}>Request Early Check-Out</div>
                                <div style={{ fontSize: 12, color: DIM, marginTop: 2 }}>
                                    Scheduled: {fmtDate(status.original_checkout_date)}
                                </div>
                            </div>
                        </div>
                        <span style={{ fontSize: 18, color: DIM, transform: showRequestForm ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
                            ⌄
                        </span>
                    </div>

                    {/* Collapsible form */}
                    {showRequestForm && (
                        <div style={{ borderTop: `1px solid ${BORDER}`, padding: '16px' }}>
                            <div style={{ fontSize: 13, color: DIM, marginBottom: 14, lineHeight: 1.5 }}>
                                Select the date you'd like to check out. Your request will be reviewed by the team.
                            </div>

                            {/* Date options — radio buttons, not a free calendar */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
                                {status.valid_early_request_dates.map(d => (
                                    <label key={d} style={{
                                        display: 'flex', alignItems: 'center', gap: 10,
                                        background: selectedDate === d ? 'rgba(59,130,246,0.12)' : '#0f1421',
                                        border: `1px solid ${selectedDate === d ? 'rgba(59,130,246,0.4)' : BORDER}`,
                                        borderRadius: 10, padding: '10px 14px', cursor: 'pointer',
                                        transition: 'background 0.15s, border-color 0.15s',
                                    }}>
                                        <input
                                            type="radio"
                                            name="early_checkout_date"
                                            value={d}
                                            checked={selectedDate === d}
                                            onChange={() => setSelectedDate(d)}
                                            style={{ accentColor: PRIMARY, width: 16, height: 16, flexShrink: 0 }}
                                        />
                                        <span style={{ fontSize: 14, fontWeight: selectedDate === d ? 700 : 400, color: TEXT }}>
                                            {fmtDate(d)}
                                        </span>
                                    </label>
                                ))}
                            </div>

                            {/* Optional reason */}
                            <textarea
                                value={reason}
                                onChange={e => setReason(e.target.value)}
                                placeholder="Reason (optional) — e.g. flight change, family emergency…"
                                rows={2}
                                maxLength={200}
                                style={{
                                    width: '100%', background: '#0f1421', border: `1px solid ${BORDER}`,
                                    borderRadius: 10, padding: '10px 12px', color: TEXT,
                                    fontSize: 13, resize: 'none', boxSizing: 'border-box',
                                    fontFamily: 'inherit', marginBottom: 12,
                                }}
                            />

                            {submitError && (
                                <div style={{ fontSize: 13, color: '#f87171', marginBottom: 10 }}>
                                    ⚠ {submitError}
                                </div>
                            )}

                            <div style={{ display: 'flex', gap: 10 }}>
                                <button
                                    onClick={() => setShowRequestForm(false)}
                                    style={{
                                        flex: 1, padding: '10px 0', borderRadius: 10,
                                        background: 'transparent', border: `1px solid ${BORDER}`,
                                        color: DIM, fontSize: 14, cursor: 'pointer',
                                    }}
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleSubmitRequest}
                                    disabled={submitting || !selectedDate}
                                    style={{
                                        flex: 2, padding: '10px 0', borderRadius: 10,
                                        background: !selectedDate ? FAINT : PRIMARY,
                                        border: 'none', color: '#fff',
                                        fontWeight: 700, fontSize: 14,
                                        cursor: submitting || !selectedDate ? 'not-allowed' : 'pointer',
                                        opacity: !selectedDate ? 0.6 : 1,
                                    }}
                                >
                                    {submitting ? 'Sending…' : 'Send Request'}
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </>
    );
}


// ---------------------------------------------------------------------------
// Section 6 — Your Stay
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

                {/* Section 2 — Home Essentials
                     Phase 1064: Guard — compute whether ANY essential content is present
                     before rendering the section. If zero items configured, show a calm
                     placeholder instead of a floating section header with nothing below it. */}
                {(() => {
                    const hasEssentials = !!(
                        data.welcome_message ||
                        data.wifi_name || data.wifi_password ||
                        data.check_in_time || data.check_out_time ||
                        data.emergency_contact ||
                        (data.house_rules && data.house_rules.length > 0)
                    );
                    return (
                        <>
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

                            {/* Phase 1064: empty state — shown only when zero essentials configured */}
                            {!hasEssentials && (
                                <div style={{
                                    background: SURFACE, border: `1px solid ${BORDER}`,
                                    borderRadius: RADIUS, padding: '20px 16px',
                                    display: 'flex', alignItems: 'flex-start', gap: 12,
                                }}>
                                    <span style={{ fontSize: 20, flexShrink: 0, opacity: 0.5 }}>🏡</span>
                                    <div>
                                        <div style={{ fontSize: 14, color: '#9ca3af', lineHeight: 1.6 }}>
                                            Home information will be available here once your host has set it up.
                                        </div>
                                        <div style={{ fontSize: 12, color: FAINT, marginTop: 6, lineHeight: 1.5 }}>
                                            If you need anything right away, use the message box below.
                                        </div>
                                    </div>
                                </div>
                            )}
                        </>
                    );
                })()}

                {/* Section 3 — How This Home Works */}
                <HowThisHomeWorks token={token} apiBase={API_BASE} />

                {/* Section 4 — Need Help */}
                <NeedHelp token={token} apiBase={API_BASE} />

                {/* Section 5 — Around You
                     Phase 1064: AroundYou returns null when neither location nor extras are
                     configured — intentional hide, not a broken empty state. */}
                <AroundYou token={token} apiBase={API_BASE} />

                {/* Section 6 — Your Stay
                     Phase 1064: YourStay returns null when nothing is set — intentional hide. */}
                <YourStay data={data} />

                {/* Phase 1065 — Guest Checkout Actions
                     Flow A: Request Early Check-Out (during stay, before window)
                     Flow B: Self Check-Out (within 24h of effective checkout)
                     Component fetches /guest/{token}/checkout-status and self-manages visibility.
                     Returns null while loading, if endpoint fails, or if no relevant actions apply. */}
                <GuestCheckoutActions token={token} apiBase={API_BASE} />

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
