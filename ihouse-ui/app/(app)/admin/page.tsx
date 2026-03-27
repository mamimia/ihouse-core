'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Provider {
    provider: string;
    tier: string;
    supports_api_write: boolean;
    supports_ical_push: boolean;
    supports_ical_pull: boolean;
    rate_limit_per_min: number;
    auth_method: string;
    notes: string | null;
    updated_at: string | null;
}

interface Permission {
    user_id: string;
    role: string;
    permissions: Record<string, unknown>;
    created_at?: string;
}

interface DlqEntry {
    id: number;
    provider: string;
    event_type: string;
    rejection_code: string;
    status: string;
    received_at: string;
}

interface Integration {
    id: string;
    name: string;
    description: string;
    icon: React.ReactNode;
    configured: boolean;
    active: boolean;
    credentials?: Record<string, string>; // Cached credentials
    group: 'messaging' | 'email'; // Phase 951a: channel grouping
    purpose?: string; // Phase 951a: what this channel is used for
    comingSoon?: boolean; // Phase 951a: not yet actionable
}

// Map integration IDs to the fields they require for configuration
const INTEGRATION_FIELDS: Record<string, { key: string; label: string; placeholder: string; type?: string; readOnly?: boolean; copyable?: boolean }[]> = {
    line: [
        { key: 'channel_secret', label: 'Channel Secret', placeholder: 'Webhook verification secret from LINE Basic Settings' },
        { key: 'channel_access_token', label: 'Channel Access Token (long-lived)', placeholder: 'Issue from LINE Developers Console → Messaging API' },
        { key: 'webhook_url', label: 'Your Webhook URL', placeholder: '', type: 'text', readOnly: true, copyable: true },
    ],
    whatsapp: [
        { key: 'access_token', label: 'Access Token', placeholder: 'Enter Meta Cloud API bearer token' },
        { key: 'phone_number_id', label: 'Phone Number ID', placeholder: 'WhatsApp Business Number ID' },
        { key: 'app_secret', label: 'App Secret', placeholder: 'HMAC-SHA256 signature secret' },
        { key: 'verify_token', label: 'Verify Token', placeholder: 'Webhook challenge verification token' }
    ],
    telegram: [
        { key: 'bot_token', label: 'Bot Token', placeholder: 'Enter Telegram Bot Token (e.g. 123456:ABC-DEF1234ghIkl-zyx5cM)' }
    ],
    sms: [
        { key: 'twilio_sid', label: 'Twilio Account SID', placeholder: 'AC...' },
        { key: 'twilio_token', label: 'Twilio Auth Token', placeholder: 'Enter token' },
        { key: 'twilio_from', label: 'Twilio Number', placeholder: '+1234567890' }
    ],
    // Phase 951a — Email sender identities
    email_general: [
        { key: 'from_name', label: 'From Name', placeholder: 'e.g. Domaniqo' },
        { key: 'from_email', label: 'From Email', placeholder: 'e.g. noreply@domaniqo.com' },
        { key: 'reply_to', label: 'Reply-To Email', placeholder: 'e.g. support@domaniqo.com' },
    ],
    email_onboarding: [
        { key: 'from_name', label: 'From Name', placeholder: 'e.g. Domaniqo Team' },
        { key: 'from_email', label: 'From Email', placeholder: 'e.g. onboarding@domaniqo.com' },
    ],
    email_password: [
        { key: 'from_name', label: 'From Name', placeholder: 'e.g. Domaniqo Security' },
        { key: 'from_email', label: 'From Email', placeholder: 'e.g. security@domaniqo.com' },
    ],
    email_guest: [
        { key: 'from_name', label: 'From Name', placeholder: 'e.g. Domaniqo Concierge' },
        { key: 'from_email', label: 'From Email', placeholder: 'e.g. guest@domaniqo.com' },
        { key: 'reply_to', label: 'Reply-To Email', placeholder: 'e.g. concierge@domaniqo.com' },
    ],
    email_owner: [
        { key: 'from_name', label: 'From Name', placeholder: 'e.g. Domaniqo Reports' },
        { key: 'from_email', label: 'From Email', placeholder: 'e.g. reports@domaniqo.com' },
    ],
};

const INTEGRATION_INSTRUCTIONS: Record<string, { title: string; steps: React.ReactNode[] }> = {
    telegram: {
        title: 'How to connect Telegram',
        steps: [
            <span key="1">Search for <strong>@BotFather</strong> in Telegram and send <code>/newbot</code>.</span>,
            <span key="2">Choose a name and username for your agent.</span>,
            <span key="3">Copy the HTTP API Token he replies with and paste it above.</span>
        ]
    },
    whatsapp: {
        title: 'How to connect WhatsApp API',
        steps: [
            <span key="1">Log into <strong>Meta for Developers</strong> and create a Business App.</span>,
            <span key="2">Add the WhatsApp product to your app.</span>,
            <span key="3">Copy the <strong>Access Token</strong> and <strong>Phone Number ID</strong>.</span>,
            <span key="4">Create your own Verify Token and copy the App Secret.</span>
        ]
    },
    line: {
        title: 'Connect LINE Messaging API',
        steps: [
            <span key="1"><strong>1. Open your LINE Official Account</strong><br/>Go to <strong>LINE Official Account Manager</strong>. Create a LINE Official Account if you do not have one, or open an existing account.</span>,
            <span key="2"><strong>2. Enable Messaging API</strong><br/>In LINE Official Account Manager go to <em>Settings → Messaging API → Enable Messaging API</em>. If prompted to choose a provider, select your existing one — do not create a second provider.</span>,
            <span key="3"><strong>3. Open LINE Developers Console</strong><br/>After enabling, open <em>LINE Developers Console → Provider → Your channel → Messaging API</em>.</span>,
            <span key="4"><strong>4. Copy required values</strong><br/>Collect: <strong>Channel Secret</strong> (Basic settings) and <strong>Channel Access Token (long-lived)</strong> (Messaging API tab → Issue).</span>,
            <span key="5"><strong>5. Set your webhook URL</strong><br/>In LINE Official Account Manager → Settings → Messaging API, paste your Domaniqo webhook URL:<br/><code style={{fontFamily:'monospace', fontSize:'11px', background:'var(--color-surface-3)', padding:'1px 4px', borderRadius:3}}>/line/webhook</code><br/>LINE requires a public HTTPS URL — localhost and plain HTTP will not work. Enable webhook usage after saving.</span>,
            <span key="6"><strong>6. Paste values here</strong><br/><em>Channel Secret</em> → webhook verification secret field above.<br/><em>Channel Access Token</em> → outbound messaging token field above.</span>,
            <span key="7"><strong>7. Configure worker delivery</strong><br/>Each worker who should receive LINE messages must have a valid LINE recipient ID linked in their staff profile. Without this, the integration connects but notifications do not reach workers.</span>,
            <span key="8"><strong>8. Test the connection</strong><br/>After saving, verify webhook is enabled and publicly reachable, then send a test notification and confirm a real LINE message is delivered.</span>,
            <span key="warn" style={{display:'block', marginTop:'8px', padding:'10px 12px', background:'#f59e0b0f', border:'1px solid #f59e0b33', borderRadius:'6px', color:'var(--color-text)', fontSize:'12px'}}>
                <strong>⚠ Important</strong><br/>
                Channel Secret and Channel Access Token are <em>different values</em> — do not paste the wrong one into the wrong field.<br/>
                LINE requires a public HTTPS webhook URL. Localhost and plain HTTP will not work.<br/>
                Worker routing must be configured separately for delivery to succeed.
            </span>
        ]
    },
    sms: {
        title: 'How to connect Twilio SMS',
        steps: [
            <span key="1">Create a <strong>Twilio</strong> account and configure billing.</span>,
            <span key="2">Purchase a Twilio Phone Number capable of sending SMS.</span>,
            <span key="3">Copy your <strong>Account SID</strong> and <strong>Auth Token</strong>.</span>
        ]
    },
    // Phase 951a — Email sender instructions
    email_general: {
        title: 'System Email Sender',
        steps: [
            <span key="1">This is the <strong>default sender identity</strong> for all system-generated emails.</span>,
            <span key="2">Configure this first — other senders inherit from this if not configured separately.</span>,
            <span key="3">The <strong>Reply-To</strong> address determines where recipients' replies go.</span>,
        ]
    },
    email_onboarding: {
        title: 'Staff Onboarding Sender',
        steps: [
            <span key="1">Emails from this sender include <strong>invite links</strong>, <strong>access setup</strong>, and <strong>welcome messages</strong> for new staff.</span>,
            <span key="2">If not configured, the system general sender will be used instead.</span>,
        ]
    },
    email_password: {
        title: 'Password & Account Sender',
        steps: [
            <span key="1">Used for <strong>password reset</strong>, <strong>account recovery</strong>, and <strong>security alert</strong> emails.</span>,
            <span key="2">If not configured, the system general sender will be used instead.</span>,
            <span key="3" style={{display:'block', marginTop:'8px', padding:'10px 12px', background:'#f59e0b0f', border:'1px solid #f59e0b33', borderRadius:'6px', color:'var(--color-text)', fontSize:'12px'}}>
                <strong>Note:</strong> Password reset emails are currently handled by Supabase Auth. This sender identity will be used when custom email templates are enabled.
            </span>
        ]
    },
    email_guest: {
        title: 'Guest Communication Sender',
        steps: [
            <span key="1">Used for <strong>guest portal links</strong>, <strong>check-in instructions</strong>, and <strong>stay information</strong> emails.</span>,
            <span key="2">The <strong>Reply-To</strong> address should go to a monitored inbox for guest inquiries.</span>,
        ]
    },
    email_owner: {
        title: 'Owner Reports Sender',
        steps: [
            <span key="1">Used for <strong>financial statements</strong>, <strong>property reports</strong>, and <strong>owner notifications</strong>.</span>,
            <span key="2">If not configured, the system general sender will be used instead.</span>,
        ]
    },
};

// ---------------------------------------------------------------------------
// Reusable components
// ---------------------------------------------------------------------------

function CollapsibleSection({ title, subtitle, icon, badge, badgeColor, defaultOpen = false, children }: {
    title: string;
    subtitle?: string;
    icon: React.ReactNode;
    badge?: string;
    badgeColor?: string;
    defaultOpen?: boolean;
    children: React.ReactNode;
}) {
    const [open, setOpen] = useState(defaultOpen);
    const contentRef = useCallback((node: HTMLDivElement | null) => {
        if (node) {
            // Set max-height for animation
            if (open) {
                node.style.maxHeight = node.scrollHeight + 'px';
                // After transition, set to 'none' so content can grow dynamically
                const handler = () => { node.style.maxHeight = 'none'; };
                node.addEventListener('transitionend', handler, { once: true });
            } else {
                // Collapse: first set explicit height, then on next frame set to 0
                if (node.style.maxHeight === 'none') {
                    node.style.maxHeight = node.scrollHeight + 'px';
                }
                requestAnimationFrame(() => {
                    node.style.maxHeight = '0px';
                });
            }
        }
    }, [open]);

    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg, 12px)',
            marginBottom: 'var(--space-5, 20px)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
            overflow: 'hidden',
            transition: 'box-shadow 200ms ease',
        }}>
            {/* Clickable header */}
            <button
                onClick={() => setOpen(prev => !prev)}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    width: '100%',
                    padding: '16px 20px',
                    background: open ? 'var(--color-surface-2, #fafaf8)' : 'transparent',
                    border: 'none',
                    borderBottom: open ? '1px solid var(--color-border)' : '1px solid transparent',
                    cursor: 'pointer',
                    gap: '14px',
                    transition: 'background 200ms ease, border-color 200ms ease',
                    textAlign: 'left',
                }}
            >
                {/* Icon */}
                <div style={{
                    width: 36,
                    height: 36,
                    borderRadius: '8px',
                    background: 'var(--color-surface-2, #f5f3ef)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '16px',
                    flexShrink: 0,
                }}>
                    {icon}
                </div>

                {/* Title + subtitle */}
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                        fontSize: '13px',
                        fontWeight: 700,
                        color: 'var(--color-text)',
                        letterSpacing: '0.01em',
                        lineHeight: 1.3,
                    }}>
                        {title}
                    </div>
                    {subtitle && (
                        <div style={{
                            fontSize: '11px',
                            color: 'var(--color-text-faint)',
                            marginTop: '2px',
                            lineHeight: 1.3,
                        }}>
                            {subtitle}
                        </div>
                    )}
                </div>

                {/* Badge (right side summary) */}
                {badge && (
                    <span style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        padding: '3px 10px',
                        borderRadius: 'var(--radius-full, 999px)',
                        background: `${badgeColor || 'var(--color-text-dim)'}14`,
                        color: badgeColor || 'var(--color-text-dim)',
                        border: `1px solid ${badgeColor || 'var(--color-text-dim)'}33`,
                        whiteSpace: 'nowrap',
                        flexShrink: 0,
                    }}>
                        {badge}
                    </span>
                )}

                {/* Chevron indicator */}
                <span style={{
                    fontSize: '14px',
                    color: 'var(--color-text-faint)',
                    transition: 'transform 250ms ease',
                    transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
                    flexShrink: 0,
                    lineHeight: 1,
                }}>
                    ▾
                </span>
            </button>

            {/* Collapsible content */}
            <div
                ref={contentRef}
                style={{
                    maxHeight: defaultOpen ? undefined : '0px',
                    overflow: 'hidden',
                    transition: 'max-height 300ms cubic-bezier(0.4, 0, 0.2, 1)',
                }}
            >
                <div style={{ padding: '0 var(--space-2, 8px)' }}>
                    {children}
                </div>
            </div>
        </div>
    );
}

function Chip({ label, color, title }: { label: string; color: string; title?: string }) {
    return (
        <span 
            title={title}
            style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                background: `${color}22`,
                color,
                border: `1px solid ${color}44`,
                fontFamily: 'var(--font-mono)',
                cursor: title ? 'help' : 'inherit'
            }}
        >{label}</span>
    );
}

function ToggleBtn({ active, onToggle, label }: { active: boolean; onToggle: () => void; label: string }) {
    return (
        <div
            onClick={onToggle}
            title={label}
            style={{
                width: '28px',
                height: '16px',
                borderRadius: '8px',
                background: active ? 'var(--color-primary)' : 'var(--color-border)',
                position: 'relative',
                cursor: 'pointer',
                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                flexShrink: 0,
            }}
        >
            <div style={{
                position: 'absolute',
                top: '2px',
                left: active ? '14px' : '2px',
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: '#fff',
                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
            }} />
        </div>
    );
}

// ---------------------------------------------------------------------------
// Draggable floating config panel
// ---------------------------------------------------------------------------

function DraggableConfigPanel({ title, onClose, children }: {
    title: string;
    onClose: () => void;
    children: React.ReactNode;
}) {
    const [pos, setPos] = useState(() => ({
        x: Math.max(0, (window.innerWidth - 480) / 2),
        y: Math.max(0, (window.innerHeight - 580) / 2),
    }));
    const [size, setSize] = useState({ w: 480, h: 580 });
    const dragging = useRef(false);
    const dragOffset = useRef({ x: 0, y: 0 });
    const resizing = useRef(false);
    const resizeStart = useRef({ x: 0, y: 0, w: 0, h: 0 });

    // Drag
    const onDragStart = (e: React.MouseEvent) => {
        dragging.current = true;
        dragOffset.current = { x: e.clientX - pos.x, y: e.clientY - pos.y };
        e.preventDefault();
    };
    useEffect(() => {
        const onMove = (e: MouseEvent) => {
            if (dragging.current) {
                setPos({
                    x: Math.max(0, Math.min(window.innerWidth - size.w, e.clientX - dragOffset.current.x)),
                    y: Math.max(0, Math.min(window.innerHeight - 60, e.clientY - dragOffset.current.y)),
                });
            }
            if (resizing.current) {
                const dw = e.clientX - resizeStart.current.x;
                const dh = e.clientY - resizeStart.current.y;
                setSize({
                    w: Math.max(360, resizeStart.current.w + dw),
                    h: Math.max(300, resizeStart.current.h + dh),
                });
            }
        };
        const onUp = () => { dragging.current = false; resizing.current = false; };
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
        return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
    }, [size.w]);

    // Resize
    const onResizeStart = (e: React.MouseEvent) => {
        resizing.current = true;
        resizeStart.current = { x: e.clientX, y: e.clientY, w: size.w, h: size.h };
        e.preventDefault();
        e.stopPropagation();
    };

    return (
        <div style={{
            position: 'fixed',
            left: pos.x,
            top: pos.y,
            width: size.w,
            height: size.h,
            zIndex: 10000,
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--color-surface)',
            borderRadius: 'var(--radius-lg, 12px)',
            boxShadow: '0 16px 48px rgba(0,0,0,0.25), 0 2px 8px rgba(0,0,0,0.12)',
            border: '1px solid var(--color-border)',
            overflow: 'hidden',
            minWidth: 360,
            minHeight: 300,
        }}>
            {/* Drag handle header */}
            <div
                onMouseDown={onDragStart}
                style={{
                    padding: '16px 20px',
                    borderBottom: '1px solid var(--color-border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    cursor: 'grab',
                    background: 'var(--color-surface-2, #fafaf8)',
                    userSelect: 'none',
                    flexShrink: 0,
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 13, color: 'var(--color-text-faint)', letterSpacing: '0.06em' }}>⋮⋮</span>
                    <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: 'var(--color-text)' }}>
                        {title}
                    </h2>
                </div>
                <button
                    onMouseDown={e => e.stopPropagation()}
                    onClick={onClose}
                    style={{
                        background: 'transparent', border: 'none', cursor: 'pointer',
                        fontSize: '18px', color: 'var(--color-text-dim)', lineHeight: 1,
                        padding: '2px 4px', borderRadius: 4,
                    }}
                >✕</button>
            </div>

            {/* Scrollable content */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {children}
            </div>

            {/* Resize grip */}
            <div
                onMouseDown={onResizeStart}
                style={{
                    position: 'absolute',
                    bottom: 0,
                    right: 0,
                    width: 20,
                    height: 20,
                    cursor: 'nwse-resize',
                    display: 'flex',
                    alignItems: 'flex-end',
                    justifyContent: 'flex-end',
                    padding: '3px',
                    opacity: 0.4,
                    userSelect: 'none',
                }}
            >
                <svg width="10" height="10" viewBox="0 0 10 10">
                    <path d="M9 1L1 9M5 1L1 5M9 5L5 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Provider Registry section
// ---------------------------------------------------------------------------

function ProviderRow({ p, onPatch }: {
    p: Provider;
    onPatch: (provider: string, updates: Record<string, unknown>) => Promise<void>;
}) {
    const tierLabels: Record<string, string> = {
        A: 'F-API',
        B: 'P-API',
        C: 'iCAL',
        D: 'MANUAL',
    };
    const tierTitles: Record<string, string> = {
        A: 'Full API',
        B: 'Partial API',
        C: 'iCal Only',
        D: 'Manual',
    };
    const tierColors: Record<string, string> = {
        A: 'var(--color-primary)',
        B: 'var(--color-accent)',
        C: 'var(--color-warn)',
        D: 'var(--color-text-dim)',
    };

    return (
        <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(110px, 1fr) 70px 75px 75px 75px 75px',
            alignItems: 'center',
            gap: '12px',
            padding: '8px 12px',
            borderBottom: '1px solid var(--color-border)',
            transition: 'background 0.15s ease',
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = 'var(--color-surface-hover)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        >
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text)', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                {p.provider}
            </span>
            
            <div>
                <Chip 
                    label={tierLabels[p.tier] ?? `T${p.tier}`} 
                    color={tierColors[p.tier] || 'var(--color-text-dim)'} 
                    title={tierTitles[p.tier] ?? ''} 
                />
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-dim)', letterSpacing: '0.02em', minWidth: '16px' }}>API</span>
                <ToggleBtn
                    active={p.supports_api_write}
                    label="Toggle API write"
                    onToggle={() => onPatch(p.provider, { supports_api_write: !p.supports_api_write })}
                />
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-dim)', letterSpacing: '0.02em', minWidth: '18px' }}>iCal</span>
                <ToggleBtn
                    active={p.supports_ical_push}
                    label="Toggle iCal push"
                    onToggle={() => onPatch(p.provider, { supports_ical_push: !p.supports_ical_push })}
                />
            </div>
            
            <span style={{ fontSize: '11px', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
                {p.rate_limit_per_min}/m
            </span>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Chip label={p.auth_method.toUpperCase()} color="var(--color-text-faint)" />
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Integrations section
// ---------------------------------------------------------------------------

function IntegrationRow({ intg, onToggle, onConfigure }: {
    intg: Integration;
    onToggle: (id: string, active: boolean) => void;
    onConfigure: (id: string) => void;
}) {
    const router = useRouter();
    const isComingSoon = intg.comingSoon === true;
    // Phase 952a: Navigate to dedicated setup page instead of floating panel
    const handleConfigure = () => {
        if (isComingSoon) return;
        router.push(`/admin/setup/${intg.id}`);
    };
    return (
        <div style={{
            padding: '16px',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '10px',
            transition: 'border-color 0.2s',
            opacity: isComingSoon ? 0.6 : 1,
        }}
        onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--color-border-hover)'}
        onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--color-border)'}
        >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{
                        width: 40, height: 40, borderRadius: '8px', 
                        background: 'var(--color-surface-2)', display: 'flex', 
                        alignItems: 'center', justifyContent: 'center', fontSize: '20px'
                    }}>
                        {intg.icon}
                    </div>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                            <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text)' }}>
                                {intg.name}
                            </span>
                            {isComingSoon && (
                                <Chip label="Coming soon" color="var(--color-accent)" />
                            )}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--color-text-dim)' }}>
                            {intg.description}
                        </div>
                    </div>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                    <div style={{ width: '130px', display: 'flex', justifyContent: 'flex-end' }}>
                        <Chip 
                            label={intg.configured ? '✓ Configured' : '⊗ Not configured'} 
                            color={intg.configured ? 'var(--color-ok)' : 'var(--color-text-dim)'} 
                        />
                    </div>
                    
                    {!isComingSoon && (
                        <ToggleBtn 
                            active={intg.active} 
                            onToggle={() => onToggle(intg.id, !intg.active)} 
                            label={`Toggle ${intg.name}`}
                        />
                    )}
                    
                    <button
                        onClick={handleConfigure}
                        disabled={isComingSoon}
                        style={{
                            padding: '6px 14px',
                            background: 'transparent',
                            border: '1px solid var(--color-border)',
                            borderRadius: 'var(--radius-md)',
                            fontSize: '12px',
                            fontWeight: 600,
                            color: isComingSoon ? 'var(--color-text-faint)' : 'var(--color-text)',
                            cursor: isComingSoon ? 'not-allowed' : 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            transition: 'all 0.15s ease'
                        }}
                        onMouseEnter={e => !isComingSoon && (e.currentTarget.style.background = 'var(--color-surface-2)')}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                        Configure <span style={{ fontSize: '14px', lineHeight: 1 }}>→</span>
                    </button>
                </div>
            </div>
            {/* Phase 951a: Purpose text — shows what this channel is used for in the system */}
            {intg.purpose && (
                <div style={{
                    marginTop: '10px',
                    marginLeft: '56px',
                    fontSize: '11px',
                    lineHeight: 1.5,
                    color: 'var(--color-text-faint)',
                    fontStyle: 'italic',
                }}>
                    {intg.purpose}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Permissions section
// ---------------------------------------------------------------------------

function PermissionRow({ perm }: { perm: Permission }) {
    const roleColors: Record<string, string> = {
        admin: 'var(--color-danger)',
        manager: 'var(--color-primary)',
        worker: 'var(--color-accent)',
        owner: 'var(--color-warn)',
    };
    const caps = Object.keys(perm.permissions || {}).filter(k => perm.permissions[k]);

    return (
        <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            padding: 'var(--space-3) var(--space-4)',
            background: 'var(--color-surface-2)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 'var(--space-2)',
            gap: 'var(--space-4)',
        }}>
            <div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>
                    {perm.user_id}
                </div>
                {caps.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {caps.map(c => (
                            <span key={c} style={{
                                fontSize: 'var(--text-xs)',
                                padding: '1px 6px',
                                borderRadius: 'var(--radius-full)',
                                background: 'var(--color-surface-3)',
                                color: 'var(--color-text-dim)',
                                border: '1px solid var(--color-border)',
                            }}>{c.replace('can_', '')}</span>
                        ))}
                    </div>
                )}
            </div>
            <Chip label={perm.role.toUpperCase()} color={roleColors[perm.role] || 'var(--color-text-dim)'} />
        </div>
    );
}

// ---------------------------------------------------------------------------
// Admin Settings page
// ---------------------------------------------------------------------------

export default function AdminPage() {
    const [providers, setProviders] = useState<Provider[]>([]);
    const [permissions, setPermissions] = useState<Permission[]>([]);
    const [dlq, setDlq] = useState<DlqEntry[]>([]);
    // Phase 951a: System Delivery Configuration — messaging + email senders
    const emailIcon = <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>;
    const [integrations, setIntegrations] = useState<Integration[]>([
        // ── Messaging Channels ──
        { id: 'line', name: 'LINE Messaging API', description: 'Task alerts, SLA escalations, worker notifications', purpose: 'Primary real-time channel for operational staff. Delivers task assignments, acknowledgement prompts, and escalation alerts.', icon: <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>, configured: false, active: false, credentials: {}, group: 'messaging' },
        { id: 'whatsapp', name: 'WhatsApp Business', description: 'Guest communication, booking confirmations', purpose: 'Guest-facing messaging via WhatsApp Business API (Meta Cloud). Used for check-in instructions and stay-related communication.', icon: <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>, configured: false, active: false, credentials: {}, group: 'messaging' },
        { id: 'telegram', name: 'Telegram Bot', description: 'Task alerts for workers who prefer Telegram', purpose: 'Alternative messaging channel for task alerts and escalations. Workers link their Telegram account via bot.', icon: <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>, configured: false, active: false, credentials: {}, group: 'messaging' },
        { id: 'sms', name: 'SMS (Twilio)', description: 'Fallback delivery when primary channels unreachable', purpose: 'Last-resort delivery channel via Twilio. Used when LINE/WhatsApp/Telegram are unavailable or undelivered.', icon: <svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/></svg>, configured: false, active: false, credentials: {}, group: 'messaging' },
        // ── Email Senders ──
        { id: 'email_general', name: 'System / General', description: 'Default sender for all system emails', purpose: 'Fallback sender identity when no specific sender is configured. All other email senders inherit from this.', icon: emailIcon, configured: false, active: false, credentials: {}, group: 'email' },
        { id: 'email_onboarding', name: 'Staff Onboarding', description: 'Invite emails, access links, password setup', purpose: 'Sent to new workers during the onboarding process. Includes invite links, setup instructions, and welcome messages.', icon: emailIcon, configured: false, active: false, credentials: {}, group: 'email', comingSoon: true },
        { id: 'email_password', name: 'Password & Account', description: 'Password reset, recovery, security alerts', purpose: 'Account security emails including password reset links and recovery. Currently handled by Supabase Auth.', icon: emailIcon, configured: false, active: false, credentials: {}, group: 'email', comingSoon: true },
        { id: 'email_guest', name: 'Guest Communication', description: 'Portal links, check-in instructions, stay info', purpose: 'Guest-facing emails with portal access links, check-in details, and stay-related information.', icon: emailIcon, configured: false, active: false, credentials: {}, group: 'email', comingSoon: true },
        { id: 'email_owner', name: 'Owner Reports', description: 'Financial statements, property reports', purpose: 'Owner-facing emails with financial statements, property reports, and periodic notifications.', icon: emailIcon, configured: false, active: false, credentials: {}, group: 'email', comingSoon: true },
    ]);
    const [loading, setLoading] = useState(true);
    const [notice, setNotice] = useState<string | null>(null);

    // Modal state for configuration
    const [configModal, setConfigModal] = useState<{ isOpen: boolean; integrationId: string | null; credentials: Record<string, string> }>({
        isOpen: false,
        integrationId: null,
        credentials: {}
    });

    const showNotice = (msg: string) => {
        setNotice(msg);
        setTimeout(() => setNotice(null), 3000);
    };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [provRes, permRes, dlqRes, intgRes] = await Promise.allSettled([
                api.getProviders(),
                api.getPermissions(),
                api.getDlq({ status: 'pending', limit: 20 }),
                api.getTenantIntegrations(),
            ]);

            if (provRes.status === 'fulfilled') setProviders(provRes.value.providers || []);
            if (permRes.status === 'fulfilled') setPermissions(permRes.value.permissions || []);
            if (dlqRes.status === 'fulfilled') setDlq(dlqRes.value.entries || []);
            if (intgRes.status === 'fulfilled' && intgRes.value.integrations) {
                setIntegrations(prev => prev.map(base => {
                    const row = intgRes.value.integrations.find((r: any) => r.provider === base.id);
                    if (row) {
                        const hasCreds = row.credentials && Object.keys(row.credentials).length > 0;
                        return { ...base, active: row.is_active, configured: hasCreds, credentials: row.credentials || {} };
                    }
                    return base;
                }));
            }
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const handlePatchProvider = async (provider: string, updates: Record<string, unknown>) => {
        try {
            await api.patchProvider(provider, updates);
            showNotice(`✓ ${provider} updated`);
            await load();
        } catch {
            showNotice(`✗ Failed to update ${provider}`);
        }
    };

    const handleToggleIntegration = async (id: string, active: boolean) => {
        // Optimistic UI update
        const prevIntegrations = [...integrations];
        setIntegrations(prev => prev.map(i => i.id === id ? { ...i, active } : i));
        
        try {
            await api.updateTenantIntegration(id, { is_active: active });
            showNotice(`✓ Integration ${active ? 'enabled' : 'disabled'}`);
            await load(); // Reload to sync exact state just in case
        } catch (err) {
            console.error('Toggle integration failed:', err);
            setIntegrations(prevIntegrations); // Revert
            showNotice(`✗ Failed to update integration`);
        }
    };

    const handleConfigureIntegration = (id: string) => {
        const intg = integrations.find(i => i.id === id);
        if (!intg) return;
        // Phase 951a: auto-populate webhook_url for LINE
        const creds = { ...(intg.credentials || {}) };
        if (id === 'line' && !creds.webhook_url) {
            const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
            creds.webhook_url = `${apiUrl}/line/webhook`;
        }
        setConfigModal({
            isOpen: true,
            integrationId: id,
            credentials: creds
        });
    };

    const handleSaveConfiguration = async () => {
        const { integrationId, credentials } = configModal;
        if (!integrationId) return;

        // Phase 951a: strip read-only fields (e.g. webhook_url) — they are derived, not persisted
        const fieldDefs = INTEGRATION_FIELDS[integrationId] || [];
        const readOnlyKeys = new Set(fieldDefs.filter(f => f.readOnly).map(f => f.key));
        const saveCreds = Object.fromEntries(
            Object.entries(credentials).filter(([k]) => !readOnlyKeys.has(k))
        );

        const intg = integrations.find(i => i.id === integrationId);
        // Optimistic UI update
        const prevIntegrations = [...integrations];
        const newHasCreds = Object.keys(saveCreds).some(k => !!saveCreds[k]);
        
        setIntegrations(prev => prev.map(i => i.id === integrationId ? { ...i, configured: newHasCreds, credentials: saveCreds } : i));
        
        try {
            await api.updateTenantIntegration(integrationId, { 
                is_active: intg?.active ?? false, 
                credentials: saveCreds 
            });
            showNotice(`✓ Integration configuration saved`);
            setConfigModal({ isOpen: false, integrationId: null, credentials: {} });
            await load(); // Reload to sync exact state just in case
        } catch (err) {
            console.error('Save configuration failed:', err);
            setIntegrations(prevIntegrations); // Revert
            showNotice(`✗ Failed to save configuration`);
        }
    };

    return (
        <div style={{ maxWidth: 1000 }}>

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-1)' }}>
                    System configuration
                </p>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <h1 style={{
                        fontSize: 'var(--text-3xl)',
                        fontWeight: 700,
                        letterSpacing: '-0.03em',
                        color: 'var(--color-text)',
                    }}>
                        Admin <span style={{ color: 'var(--color-primary)' }}>Settings</span>
                    </h1>
                    <button
                        onClick={load}
                        disabled={loading}
                        style={{
                            background: loading ? 'var(--color-surface-3)' : 'var(--color-primary)',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-2) var(--space-5)',
                            fontSize: 'var(--text-sm)',
                            fontWeight: 600,
                            opacity: loading ? 0.7 : 1,
                            cursor: loading ? 'not-allowed' : 'pointer',
                            transition: 'all var(--transition-fast)',
                        }}
                    >
                        {loading ? '⟳  Refreshing…' : '↺  Refresh'}
                    </button>
                </div>
            </div>

            {/* Toast notice */}
            {notice && (
                <div style={{
                    position: 'fixed',
                    bottom: 'var(--space-6)',
                    right: 'var(--space-6)',
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)',
                    color: 'var(--color-text)',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
                    zIndex: 100,
                }}>{notice}</div>
            )}

            {/* Section 1 — Provider Registry (open by default — primary admin surface) */}
            <CollapsibleSection
                title="Provider Registry"
                subtitle="OTA channel connections and sync capabilities"
                icon={<svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/></svg>}
                badge={providers.length > 0 ? `${providers.length} providers` : undefined}
                badgeColor="var(--color-primary)"
            >
                {providers.length === 0 ? (
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', padding: '12px 8px' }}>
                        {loading ? 'Loading…' : 'No providers registered yet.'}
                    </p>
                ) : (
                    <>
                        {providers.map(p => (
                            <ProviderRow key={p.provider} p={p} onPatch={handlePatchProvider} />
                        ))}
                    </>
                )}
            </CollapsibleSection>

            {/* Section 2 — System Delivery Configuration (Phase 951a — evolved from Notification Integrations) */}
            <CollapsibleSection
                title="System Delivery Configuration"
                subtitle="Messaging channels and email senders for all outbound system communication"
                icon={<svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>}
                badge={(() => {
                    const active = integrations.filter(i => i.active && !i.comingSoon).length;
                    const configured = integrations.filter(i => i.configured && !i.comingSoon).length;
                    return configured > 0 ? `${configured} configured · ${active} active` : 'none configured';
                })()}
                badgeColor={integrations.some(i => i.active && !i.comingSoon) ? 'var(--color-ok)' : 'var(--color-text-faint)'}
            >
                <p style={{ fontSize: '12px', color: 'var(--color-text-dim)', padding: '12px 8px 4px', margin: 0 }}>
                    Integration tokens are encrypted at rest and scoped per organization.
                </p>

                {/* ── Messaging Channels ── */}
                <div style={{ padding: '12px 8px 4px' }}>
                    <div style={{
                        fontSize: '11px', fontWeight: 700, color: 'var(--color-text-faint)',
                        textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '8px',
                        paddingBottom: '6px', borderBottom: '1px solid var(--color-border)',
                    }}>
                        Messaging Channels
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        {integrations.filter(i => i.group === 'messaging').map(intg => (
                            <IntegrationRow 
                                key={intg.id} 
                                intg={intg} 
                                onToggle={handleToggleIntegration} 
                                onConfigure={handleConfigureIntegration} 
                            />
                        ))}
                    </div>
                </div>

                {/* ── Email Senders ── */}
                <div style={{ padding: '12px 8px 4px' }}>
                    <div style={{
                        fontSize: '11px', fontWeight: 700, color: 'var(--color-text-faint)',
                        textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '8px',
                        paddingBottom: '6px', borderBottom: '1px solid var(--color-border)',
                    }}>
                        Email Senders
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        {integrations.filter(i => i.group === 'email').map(intg => (
                            <IntegrationRow 
                                key={intg.id} 
                                intg={intg} 
                                onToggle={handleToggleIntegration} 
                                onConfigure={handleConfigureIntegration} 
                            />
                        ))}
                    </div>
                </div>
            </CollapsibleSection>

            {/* Section 3 — User Permissions (collapsed — stable, reference-only) */}
            <CollapsibleSection
                title="User Permissions"
                subtitle="Role assignments and capability grants"
                icon={<svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/><path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/></svg>}
                badge={permissions.length > 0 ? `${permissions.length} users` : undefined}
                badgeColor="var(--color-primary)"
            >
                {permissions.length === 0 ? (
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', padding: '12px 8px' }}>
                        {loading ? 'Loading…' : 'No permission records found.'}
                    </p>
                ) : (
                    <div style={{ padding: '8px 0' }}>
                        {permissions.map(p => <PermissionRow key={p.user_id} perm={p} />)}
                    </div>
                )}
            </CollapsibleSection>

            {/* Section 4 — Integration Alerts (open if alerts exist, collapsed if clear) */}
            <CollapsibleSection
                title="Integration Alerts"
                subtitle="Dead letter queue — failed or rejected inbound events"
                icon={<svg width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>}
                badge={dlq.length > 0 ? `${dlq.length} pending` : '✓ clear'}
                badgeColor={dlq.length > 0 ? 'var(--color-warn)' : 'var(--color-ok)'}
                defaultOpen={dlq.length > 0}
            >
                {dlq.length === 0 ? (
                    <p style={{ color: 'var(--color-ok)', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)', padding: '12px 8px' }}>
                        <span>✓</span> DLQ clear — no pending events
                    </p>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', padding: '8px 0' }}>
                        {dlq.map(e => (
                            <div key={e.id} style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                padding: 'var(--space-3) var(--space-4)',
                                background: '#f59e0b08',
                                border: '1px solid #f59e0b22',
                                borderRadius: 'var(--radius-md)',
                                fontSize: 'var(--text-sm)',
                            }}>
                                <div>
                                    <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>
                                        {e.provider}
                                    </span>
                                    <span style={{ color: 'var(--color-text-dim)', margin: '0 var(--space-2)' }}>·</span>
                                    <span style={{ color: 'var(--color-text-dim)' }}>{e.event_type}</span>
                                </div>
                                <Chip label={e.rejection_code} color="var(--color-warn)" />
                            </div>
                        ))}
                    </div>
                )}
            </CollapsibleSection>

            {/* Floating draggable config panel */}
            {configModal.isOpen && (
                <DraggableConfigPanel
                    title={`Configure ${integrations.find(i => i.id === configModal.integrationId)?.name ?? ''}`}
                    onClose={() => setConfigModal({ isOpen: false, integrationId: null, credentials: {} })}
                >
                    {configModal.integrationId && INTEGRATION_FIELDS[configModal.integrationId]?.map(field => (
                        <div key={field.key} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text)' }}>{field.label}</label>
                            {field.readOnly ? (
                                <div style={{ display: 'flex', gap: '6px' }}>
                                    <input
                                        type="text"
                                        value={configModal.credentials[field.key] || ''}
                                        readOnly
                                        style={{
                                            flex: 1, padding: '8px 12px', fontSize: '12px', borderRadius: 'var(--radius-sm)',
                                            border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
                                            color: 'var(--color-text-dim)', outline: 'none', fontFamily: 'var(--font-mono)',
                                        }}
                                    />
                                    {field.copyable && (
                                        <button
                                            onClick={() => {
                                                navigator.clipboard.writeText(configModal.credentials[field.key] || '');
                                                showNotice('✓ Copied to clipboard');
                                            }}
                                            style={{
                                                padding: '8px 12px', fontSize: '12px', fontWeight: 600,
                                                background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                                borderRadius: 'var(--radius-sm)', cursor: 'pointer', color: 'var(--color-text)',
                                                whiteSpace: 'nowrap',
                                            }}
                                        >
                                            Copy
                                        </button>
                                    )}
                                </div>
                            ) : (
                                <input
                                    type={field.type || 'text'}
                                    placeholder={field.placeholder}
                                    value={configModal.credentials[field.key] || ''}
                                    onChange={(e) => setConfigModal(prev => ({
                                        ...prev,
                                        credentials: { ...prev.credentials, [field.key]: e.target.value }
                                    }))}
                                    style={{
                                        padding: '8px 12px', fontSize: '13px', borderRadius: 'var(--radius-sm)',
                                        border: '1px solid var(--color-border)', background: 'var(--color-background)',
                                        color: 'var(--color-text)', outline: 'none'
                                    }}
                                    onFocus={(e) => e.target.style.borderColor = 'var(--color-brand)'}
                                    onBlur={(e) => e.target.style.borderColor = 'var(--color-border)'}
                                />
                            )}
                        </div>
                    ))}
                    {configModal.integrationId && INTEGRATION_INSTRUCTIONS[configModal.integrationId] && (
                        <div style={{
                            padding: '16px',
                            borderRadius: '8px',
                            background: 'var(--color-surface-2)',
                            border: '1px dashed var(--color-border)',
                            fontSize: '13px',
                        }}>
                            <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{color: 'var(--color-primary)'}}>ℹ</span>
                                {INTEGRATION_INSTRUCTIONS[configModal.integrationId].title}
                            </div>
                            <ol style={{ margin: 0, paddingLeft: '20px', color: 'var(--color-text-dim)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                                {INTEGRATION_INSTRUCTIONS[configModal.integrationId].steps.map((step, idx) => (
                                    <li key={idx} style={{ paddingLeft: '4px', lineHeight: 1.55 }}>{step}</li>
                                ))}
                            </ol>
                        </div>
                    )}
                    {/* Save / Cancel footer — inside scroll area at bottom */}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '8px', borderTop: '1px solid var(--color-border)', marginTop: 'auto' }}>
                        <button
                            onClick={() => setConfigModal({ isOpen: false, integrationId: null, credentials: {} })}
                            style={{ padding: '8px 16px', fontSize: '13px', fontWeight: 600, background: 'transparent', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', cursor: 'pointer', color: 'var(--color-text)' }}
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSaveConfiguration}
                            style={{ padding: '8px 16px', fontSize: '13px', fontWeight: 600, background: 'var(--color-text)', border: 'none', borderRadius: 'var(--radius-md)', cursor: 'pointer', color: 'var(--color-background)' }}
                        >
                            Save Credentials
                        </button>
                    </div>
                </DraggableConfigPanel>
            )}

            {/* Footer */}
            <div style={{
                paddingTop: 'var(--space-6)',
                borderTop: '1px solid var(--color-border)',
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-faint)',
                display: 'flex',
                justifyContent: 'space-between',
            }}>
                <span>Domaniqo — Admin Settings · Phase 951</span>
                <span>Delivery Config: Phase 951 · Provider Registry: Phase 136</span>
            </div>
        </div>
    );
}
