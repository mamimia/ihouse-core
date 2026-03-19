'use client';

import { useEffect, useState, useCallback } from 'react';
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
    icon: string;
    configured: boolean;
    active: boolean;
    credentials?: Record<string, string>; // Cached credentials
}

// Map integration IDs to the fields they require for configuration
const INTEGRATION_FIELDS: Record<string, { key: string; label: string; placeholder: string; type?: string }[]> = {
    line: [
        { key: 'channel_access_token', label: 'Channel Access Token', placeholder: 'Enter LINE Messaging API token' }
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
    ]
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
        title: 'How to connect LINE Notify',
        steps: [
            <span key="1">Log into the <strong>LINE Developers Console</strong> and create a Provider.</span>,
            <span key="2">Create a new <strong>Messaging API</strong> channel.</span>,
            <span key="3">Scroll down to issue a long-lived <strong>Channel Access Token</strong>.</span>
        ]
    },
    sms: {
        title: 'How to connect Twilio SMS',
        steps: [
            <span key="1">Create a <strong>Twilio</strong> account and configure billing.</span>,
            <span key="2">Purchase a Twilio Phone Number capable of sending SMS.</span>,
            <span key="3">Copy your <strong>Account SID</strong> and <strong>Auth Token</strong>.</span>
        ]
    }
};

// ---------------------------------------------------------------------------
// Reusable components
// ---------------------------------------------------------------------------

function SectionCard({ title, icon, children }: {
    title: string;
    icon: string;
    children: React.ReactNode;
}) {
    return (
        <div style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            marginBottom: 'var(--space-6)',
            boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
            overflow: 'hidden',
        }}>
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                padding: 'var(--space-4) var(--space-5)',
                borderBottom: '1px solid var(--color-border)',
                background: 'var(--color-surface-2)',
            }}>
                <span style={{ fontSize: '1.2em' }}>{icon}</span>
                <h2 style={{
                    fontSize: '12px',
                    fontWeight: 700,
                    color: 'var(--color-text)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                }}>{title}</h2>
            </div>
            <div style={{ padding: '0 var(--space-2)' }}>
                {children}
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
    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '10px',
            transition: 'border-color 0.2s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--color-border-hover)'}
        onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--color-border)'}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{
                    width: 40, height: 40, borderRadius: '8px', 
                    background: 'var(--color-surface-2)', display: 'flex', 
                    alignItems: 'center', justifyContent: 'center', fontSize: '20px'
                }}>
                    {intg.icon}
                </div>
                <div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-text)', marginBottom: '4px' }}>
                        {intg.name}
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
                
                <ToggleBtn 
                    active={intg.active} 
                    onToggle={() => onToggle(intg.id, !intg.active)} 
                    label={`Toggle ${intg.name}`}
                />
                
                <button
                    onClick={() => onConfigure(intg.id)}
                    style={{
                        padding: '6px 14px',
                        background: 'transparent',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        fontSize: '12px',
                        fontWeight: 600,
                        color: 'var(--color-text)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--color-surface-2)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                    Configure <span style={{ fontSize: '14px', lineHeight: 1 }}>→</span>
                </button>
            </div>
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
    const [integrations, setIntegrations] = useState<Integration[]>([
        { id: 'line', name: 'LINE Notify', description: 'Send task alerts and notifications via LINE', icon: '💬', configured: false, active: false, credentials: {} },
        { id: 'whatsapp', name: 'WhatsApp', description: 'Send alerts via WhatsApp Business (Twilio/Meta)', icon: '📞', configured: false, active: false, credentials: {} },
        { id: 'telegram', name: 'Telegram', description: 'Send alerts via Telegram bot', icon: '✈️', configured: false, active: false, credentials: {} },
        { id: 'sms', name: 'SMS', description: 'Send alerts via standard SMS', icon: '📱', configured: false, active: false, credentials: {} },
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
        setConfigModal({
            isOpen: true,
            integrationId: id,
            credentials: intg.credentials || {}
        });
    };

    const handleSaveConfiguration = async () => {
        const { integrationId, credentials } = configModal;
        if (!integrationId) return;

        const intg = integrations.find(i => i.id === integrationId);
        // Optimistic UI update
        const prevIntegrations = [...integrations];
        const newHasCreds = Object.keys(credentials).some(k => !!credentials[k]);
        
        setIntegrations(prev => prev.map(i => i.id === integrationId ? { ...i, configured: newHasCreds, credentials } : i));
        
        try {
            await api.updateTenantIntegration(integrationId, { 
                is_active: intg?.active ?? false, 
                credentials 
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

            {/* Section 1 — Provider Registry */}
            <SectionCard title="Provider Registry" icon="🔌">
                {providers.length === 0 ? (
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                        {loading ? 'Loading…' : 'No providers registered yet.'}
                    </p>
                ) : (
                    <>
                        {providers.map(p => (
                            <ProviderRow key={p.provider} p={p} onPatch={handlePatchProvider} />
                        ))}
                    </>
                )}
            </SectionCard>

            {/* Section 1.5 — Notification Integrations */}
            <SectionCard title="Notification Integrations" icon="🔔">
                <p style={{ fontSize: '12px', color: 'var(--color-text-dim)', marginBottom: '16px' }}>
                    Integration tokens are encrypted at rest and scoped per organization.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                    {integrations.map(intg => (
                        <IntegrationRow 
                            key={intg.id} 
                            intg={intg} 
                            onToggle={handleToggleIntegration} 
                            onConfigure={handleConfigureIntegration} 
                        />
                    ))}
                </div>
            </SectionCard>

            {/* Section 2 — Permissions */}
            <SectionCard title="User Permissions" icon="🔑">
                {permissions.length === 0 ? (
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                        {loading ? 'Loading…' : 'No permission records found.'}
                    </p>
                ) : (
                    permissions.map(p => <PermissionRow key={p.user_id} perm={p} />)
                )}
            </SectionCard>

            {/* Section 3 — DLQ */}
            <SectionCard title={`Integration Alerts${dlq.length ? ` (${dlq.length})` : ''}`} icon="⚠️">
                {dlq.length === 0 ? (
                    <p style={{ color: 'var(--color-ok)', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        <span>✓</span> DLQ clear — no pending events
                    </p>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
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
            </SectionCard>

            {/* Modal for Configuration */}
            {configModal.isOpen && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(2px)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 10000
                }}>
                    <div style={{
                        background: 'var(--color-surface)', width: '420px',
                        borderRadius: 'var(--radius-lg)', boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
                        display: 'flex', flexDirection: 'column', overflow: 'hidden'
                    }}>
                        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>
                                Configure {integrations.find(i => i.id === configModal.integrationId)?.name}
                            </h2>
                            <button onClick={() => setConfigModal({ isOpen: false, integrationId: null, credentials: {} })} style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '18px', color: 'var(--color-text-dim)' }}>✕</button>
                        </div>
                        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                            {configModal.integrationId && INTEGRATION_FIELDS[configModal.integrationId]?.map(field => (
                                <div key={field.key} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text)' }}>{field.label}</label>
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
                                </div>
                            ))}
                            {configModal.integrationId && INTEGRATION_INSTRUCTIONS[configModal.integrationId] && (
                                <div style={{ 
                                    marginTop: '8px', 
                                    padding: '16px', 
                                    borderRadius: '8px', 
                                    background: 'var(--color-surface-2)', 
                                    border: '1px dashed var(--color-border)',
                                    fontSize: '13px',
                                }}>
                                    <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                        <span style={{color: 'var(--color-primary)'}}>ℹ</span> {INTEGRATION_INSTRUCTIONS[configModal.integrationId].title}
                                    </div>
                                    <ol style={{ margin: 0, paddingLeft: '20px', color: 'var(--color-text-dim)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                        {INTEGRATION_INSTRUCTIONS[configModal.integrationId].steps.map((step, idx) => (
                                            <li key={idx} style={{ paddingLeft: '4px' }}>{step}</li>
                                        ))}
                                    </ol>
                                </div>
                            )}
                        </div>
                        <div style={{ padding: '16px 24px', background: 'var(--color-surface-2)', borderTop: '1px solid var(--color-border)', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
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
                    </div>
                </div>
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
                <span>iHouse Core — Admin Settings · Phase 169</span>
                <span>Permissions: Phase 165–167 · Provider Registry: Phase 136</span>
            </div>
        </div>
    );
}
