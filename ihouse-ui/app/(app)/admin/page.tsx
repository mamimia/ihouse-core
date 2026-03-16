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
            padding: 'var(--space-6)',
            marginBottom: 'var(--space-6)',
        }}>
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                marginBottom: 'var(--space-5)',
                paddingBottom: 'var(--space-4)',
                borderBottom: '1px solid var(--color-border)',
            }}>
                <span style={{ fontSize: '1.1em' }}>{icon}</span>
                <h2 style={{
                    fontSize: 'var(--text-sm)',
                    fontWeight: 600,
                    color: 'var(--color-text-dim)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                }}>{title}</h2>
            </div>
            {children}
        </div>
    );
}

function Chip({ label, color }: { label: string; color: string }) {
    return (
        <span style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: 'var(--radius-full)',
            background: `${color}22`,
            color,
            border: `1px solid ${color}44`,
            fontFamily: 'var(--font-mono)',
        }}>{label}</span>
    );
}

function ToggleBtn({ active, onToggle, label }: { active: boolean; onToggle: () => void; label: string }) {
    return (
        <button
            onClick={onToggle}
            title={label}
            style={{
                width: 36,
                height: 20,
                borderRadius: 10,
                border: 'none',
                background: active ? 'var(--color-primary)' : 'var(--color-surface-3)',
                position: 'relative',
                cursor: 'pointer',
                transition: 'background var(--transition-fast)',
                flexShrink: 0,
            }}
        >
            <span style={{
                position: 'absolute',
                top: 2,
                left: active ? 18 : 2,
                width: 16,
                height: 16,
                borderRadius: '50%',
                background: '#fff',
                transition: 'left var(--transition-fast)',
                boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
            }} />
        </button>
    );
}

// ---------------------------------------------------------------------------
// Provider Registry section
// ---------------------------------------------------------------------------

function ProviderRow({ p, onPatch }: {
    p: Provider;
    onPatch: (provider: string, updates: Record<string, unknown>) => Promise<void>;
}) {
    const tierColors: Record<string, string> = {
        A: 'var(--color-primary)',
        B: 'var(--color-accent)',
        C: 'var(--color-warn)',
        D: 'var(--color-text-dim)',
    };

    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-5)',
            padding: 'var(--space-3) var(--space-4)',
            background: 'var(--color-surface-2)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 'var(--space-2)',
            flexWrap: 'wrap',
        }}>
            <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)', minWidth: 110 }}>
                {p.provider}
            </span>
            <Chip label={`T${p.tier}`} color={tierColors[p.tier] || 'var(--color-text-dim)'} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <ToggleBtn
                    active={p.supports_api_write}
                    label="Toggle API write"
                    onToggle={() => onPatch(p.provider, { supports_api_write: !p.supports_api_write })}
                />
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>API</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <ToggleBtn
                    active={p.supports_ical_push}
                    label="Toggle iCal push"
                    onToggle={() => onPatch(p.provider, { supports_ical_push: !p.supports_ical_push })}
                />
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>iCal</span>
            </div>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', marginLeft: 'auto' }}>
                {p.rate_limit_per_min}/min
            </span>
            <Chip
                label={p.auth_method.toUpperCase()}
                color="var(--color-text-faint)"
            />
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
