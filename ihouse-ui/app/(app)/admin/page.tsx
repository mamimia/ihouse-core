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
}

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
        { id: 'line', name: 'LINE Notify', description: 'Send task alerts and notifications via LINE', icon: '💬', configured: false, active: true },
        { id: 'whatsapp', name: 'WhatsApp', description: 'Send alerts via WhatsApp Business (Twilio)', icon: '📞', configured: false, active: false },
        { id: 'telegram', name: 'Telegram', description: 'Send alerts via Telegram bot', icon: '✈️', configured: false, active: false },
        { id: 'sms', name: 'SMS', description: 'Send alerts via standard SMS (Twilio)', icon: '📱', configured: false, active: false },
    ]);
    const [loading, setLoading] = useState(true);
    const [notice, setNotice] = useState<string | null>(null);

    const showNotice = (msg: string) => {
        setNotice(msg);
        setTimeout(() => setNotice(null), 3000);
    };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [provRes, permRes, dlqRes] = await Promise.allSettled([
                api.getProviders(),
                api.getPermissions(),
                api.getDlq({ status: 'pending', limit: 20 }),
            ]);

            if (provRes.status === 'fulfilled') setProviders(provRes.value.providers || []);
            if (permRes.status === 'fulfilled') setPermissions(permRes.value.permissions || []);
            if (dlqRes.status === 'fulfilled') setDlq(dlqRes.value.entries || []);
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

    const handleToggleIntegration = (id: string, active: boolean) => {
        setIntegrations(prev => prev.map(i => i.id === id ? { ...i, active } : i));
        showNotice(`✓ Integration ${active ? 'enabled' : 'disabled'}`);
    };

    const handleConfigureIntegration = (id: string) => {
        showNotice(`Configuration modal for ${id} not yet implemented.`);
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
