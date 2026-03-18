'use client';

/**
 * OTA Settings Tab — per-property iCal + API channel management.
 *
 * Reuses existing backend surfaces:
 *   - GET  /properties/{pid}/ical-connections    (new — list iCal feeds)
 *   - POST /integrations/ical/connect            (existing — connect iCal)
 *   - DELETE /integrations/ical/{id}             (new — disconnect iCal)
 *   - GET  /admin/properties/{pid}/channels      (existing — list API channels)
 *   - POST /admin/properties/{pid}/channels      (existing — add API channel)
 *   - DELETE /admin/properties/{pid}/channels/{provider} (existing — remove)
 *   - PATCH /admin/properties/{pid}/channels/{provider}  (existing — update)
 *   - GET  /admin/registry/providers              (existing — global provider list)
 */

import { useEffect, useState, useCallback } from 'react';
import { getToken } from '@/lib/api';

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

async function apiFetch<T = any>(path: string, init?: RequestInit): Promise<T> {
    const token = getToken();
    const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(init?.headers || {}),
        },
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.error || `${res.status}`);
    }
    return res.json();
}

// ── Types ──

interface ProviderCapability {
    provider: string;
    tier: string;
    supports_api_write: boolean;
    supports_ical_push: boolean;
    supports_ical_pull: boolean;
}

interface IcalConnection {
    id: string;
    property_id: string;
    ical_url: string;
    provider: string;
    status: string;
    last_sync_at: string | null;
    created_at: string;
}

interface ApiChannel {
    provider: string;
    external_id: string;
    sync_mode: string;
    enabled: boolean;
    inventory_type?: string;
    created_at?: string;
    updated_at?: string;
}

type SubTab = 'ical' | 'api';

// ── Provider display names + ordering ──

const PROVIDER_DISPLAY: Record<string, string> = {
    airbnb: 'Airbnb',
    bookingcom: 'Booking.com',
    'booking.com': 'Booking.com',
    booking: 'Booking.com',
    expedia: 'Expedia',
    agoda: 'Agoda',
    vrbo: 'VRBO',
    tripadvisor: 'TripAdvisor',
    trip: 'Trip.com',
    hostaway: 'Hostaway',
    guesty: 'Guesty',
    hotelbeds: 'Hotelbeds',
    despegar: 'Despegar',
    houfy: 'Houfy',
    misterb_b: 'Mister B&B',
    homeawayde: 'HomeAway DE',
    golightly: 'Golightly',
    line_channel: 'LINE Channel',
    direct: 'Direct',
};

const PROVIDER_ORDER = [
    'airbnb', 'bookingcom', 'booking.com', 'booking', 'expedia', 'agoda', 'vrbo',
    'tripadvisor', 'trip', 'hostaway', 'guesty', 'hotelbeds', 'despegar',
    'houfy', 'misterb_b', 'homeawayde', 'golightly',
];

function providerSortKey(p: string): number {
    const idx = PROVIDER_ORDER.indexOf(p.toLowerCase());
    return idx >= 0 ? idx : 999;
}

function displayName(p: string): string {
    return PROVIDER_DISPLAY[p.toLowerCase()] || p.charAt(0).toUpperCase() + p.slice(1);
}

// ── Styles ──

const cardStyle: React.CSSProperties = {
    background: 'var(--color-surface)', border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)',
};

const inputStyle: React.CSSProperties = {
    width: '100%', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-sm)', padding: '8px 12px', color: 'var(--color-text)',
    fontSize: 'var(--text-xs)', outline: 'none',
};

const btnPrimary: React.CSSProperties = {
    padding: '6px 16px', borderRadius: 'var(--radius-md)',
    background: 'var(--color-primary)', color: '#fff', border: 'none',
    fontWeight: 600, fontSize: 'var(--text-xs)', cursor: 'pointer',
};

const btnDanger: React.CSSProperties = {
    padding: '4px 12px', borderRadius: 'var(--radius-sm)',
    background: 'none', border: '1px solid rgba(248,81,73,0.3)',
    color: '#f85149', fontWeight: 600, fontSize: 10, cursor: 'pointer',
};

const btnSecondary: React.CSSProperties = {
    padding: '6px 16px', borderRadius: 'var(--radius-md)',
    background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
    color: 'var(--color-text)', fontWeight: 600, fontSize: 'var(--text-xs)', cursor: 'pointer',
};

// ── Main Component ──

export default function OtaSettingsTab({ propertyId }: { propertyId: string }) {
    const [subTab, setSubTab] = useState<SubTab>('ical');
    const [providers, setProviders] = useState<ProviderCapability[]>([]);
    const [icalConnections, setIcalConnections] = useState<IcalConnection[]>([]);
    const [apiChannels, setApiChannels] = useState<ApiChannel[]>([]);
    const [loading, setLoading] = useState(true);
    const [notice, setNotice] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // iCal connect form state
    const [icalProvider, setIcalProvider] = useState('');
    const [icalUrl, setIcalUrl] = useState('');
    const [icalConnecting, setIcalConnecting] = useState(false);

    // API connect form state
    const [apiProvider, setApiProvider] = useState('');
    const [apiExternalId, setApiExternalId] = useState('');
    const [apiSyncMode, setApiSyncMode] = useState('api_first');
    const [apiConnecting, setApiConnecting] = useState(false);

    const showNotice = (msg: string) => { setNotice(msg); setError(null); setTimeout(() => setNotice(null), 3000); };
    const showError = (msg: string) => { setError(msg); setNotice(null); setTimeout(() => setError(null), 5000); };

    // ── Data loading ──

    const loadAll = useCallback(async () => {
        setLoading(true);
        try {
            const [provRes, icalRes, apiRes] = await Promise.allSettled([
                apiFetch<{ providers: ProviderCapability[] }>('/admin/registry/providers'),
                apiFetch<{ connections: IcalConnection[] }>(`/properties/${propertyId}/ical-connections`),
                apiFetch<{ channels?: ApiChannel[]; data?: ApiChannel[] }>(`/admin/properties/${propertyId}/channels`),
            ]);
            if (provRes.status === 'fulfilled') setProviders(provRes.value.providers || []);
            if (icalRes.status === 'fulfilled') setIcalConnections(icalRes.value.connections || []);
            if (apiRes.status === 'fulfilled') {
                const ch = apiRes.value.channels || apiRes.value.data || [];
                setApiChannels(Array.isArray(ch) ? ch : []);
            }
        } catch { /* graceful */ }
        setLoading(false);
    }, [propertyId]);

    useEffect(() => { loadAll(); }, [loadAll]);

    // ── Derived lists ──

    const icalProviders = providers
        .filter(p => p.supports_ical_pull || p.supports_ical_push)
        .sort((a, b) => providerSortKey(a.provider) - providerSortKey(b.provider));

    const apiProviders = providers
        .filter(p => p.tier === 'A' || p.tier === 'B' || p.supports_api_write)
        .sort((a, b) => providerSortKey(a.provider) - providerSortKey(b.provider));

    const connectedIcalProviders = new Set(icalConnections.map(c => c.provider?.toLowerCase()));
    const connectedApiProviders = new Set(apiChannels.map(c => c.provider?.toLowerCase()));

    // ── Actions ──

    const connectIcal = async (provider: string, url: string) => {
        if (!url.trim()) { showError('iCal URL is required'); return; }
        setIcalConnecting(true);
        try {
            await apiFetch('/integrations/ical/connect', {
                method: 'POST',
                body: JSON.stringify({ property_id: propertyId, ical_url: url.trim(), provider }),
            });
            showNotice(`✅ ${displayName(provider)} iCal connected`);
            setIcalUrl(''); setIcalProvider('');
            loadAll();
        } catch (e: any) { showError(`Failed: ${e.message}`); }
        setIcalConnecting(false);
    };

    const disconnectIcal = async (connectionId: string, provider: string) => {
        try {
            await apiFetch(`/integrations/ical/${connectionId}`, { method: 'DELETE' });
            showNotice(`${displayName(provider)} iCal disconnected`);
            loadAll();
        } catch (e: any) { showError(`Failed: ${e.message}`); }
    };

    const connectApi = async (provider: string, externalId: string, syncMode: string) => {
        if (!externalId.trim()) { showError('External ID is required'); return; }
        setApiConnecting(true);
        try {
            await apiFetch(`/admin/properties/${propertyId}/channels`, {
                method: 'POST',
                body: JSON.stringify({ provider, external_id: externalId.trim(), sync_mode: syncMode }),
            });
            showNotice(`✅ ${displayName(provider)} API channel connected`);
            setApiExternalId(''); setApiProvider('');
            loadAll();
        } catch (e: any) { showError(`Failed: ${e.message}`); }
        setApiConnecting(false);
    };

    const disconnectApi = async (provider: string) => {
        try {
            await apiFetch(`/admin/properties/${propertyId}/channels/${provider}`, { method: 'DELETE' });
            showNotice(`${displayName(provider)} disconnected`);
            loadAll();
        } catch (e: any) { showError(`Failed: ${e.message}`); }
    };

    const toggleApiEnabled = async (provider: string, enabled: boolean) => {
        try {
            await apiFetch(`/admin/properties/${propertyId}/channels/${provider}`, {
                method: 'PATCH',
                body: JSON.stringify({ enabled: !enabled }),
            });
            showNotice(`${displayName(provider)} ${!enabled ? 'enabled' : 'disabled'}`);
            loadAll();
        } catch (e: any) { showError(`Failed: ${e.message}`); }
    };

    // ── Render ──

    if (loading) return <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading OTA settings…</p>;

    return (
        <div>
            {/* Toasts */}
            {notice && (
                <div style={{
                    position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 999,
                    background: 'var(--color-surface)', border: '1px solid #3fb950',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)', color: '#3fb950', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                }}>{notice}</div>
            )}
            {error && (
                <div style={{
                    position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 999,
                    background: 'var(--color-surface)', border: '1px solid #f85149',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)', color: '#f85149', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                }}>{error}</div>
            )}

            {/* Sub-tab selector */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 'var(--space-5)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', padding: 3 }}>
                {(['ical', 'api'] as SubTab[]).map(st => (
                    <button key={st} onClick={() => setSubTab(st)} style={{
                        flex: 1, padding: '8px 16px', borderRadius: 'var(--radius-sm)',
                        background: subTab === st ? 'var(--color-surface)' : 'transparent',
                        border: subTab === st ? '1px solid var(--color-border)' : '1px solid transparent',
                        color: subTab === st ? 'var(--color-text)' : 'var(--color-text-dim)',
                        fontWeight: subTab === st ? 700 : 500, fontSize: 'var(--text-sm)',
                        cursor: 'pointer', transition: 'all 0.15s',
                        boxShadow: subTab === st ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                    }}>
                        {st === 'ical' ? '📡 iCal Feeds' : '🔗 API Channels'}
                    </button>
                ))}
            </div>

            {/* ========== iCal Sub-tab ========== */}
            {subTab === 'ical' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>

                    {/* Connected iCal feeds */}
                    {icalConnections.length > 0 && (
                        <div style={{ marginBottom: 'var(--space-2)' }}>
                            <h3 style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                                Connected Feeds ({icalConnections.length})
                            </h3>
                            {icalConnections.map(conn => (
                                <div key={conn.id} style={{
                                    ...cardStyle, marginBottom: 'var(--space-2)',
                                    display: 'flex', alignItems: 'center', gap: 'var(--space-4)',
                                }}>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 4 }}>
                                            <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                                                {displayName(conn.provider || 'unknown')}
                                            </span>
                                            <span style={{
                                                padding: '1px 8px', borderRadius: 'var(--radius-full)',
                                                fontSize: 10, fontWeight: 600,
                                                background: conn.status === 'active' ? 'rgba(63,185,80,0.1)' : 'rgba(248,81,73,0.1)',
                                                color: conn.status === 'active' ? '#3fb950' : '#f85149',
                                            }}>
                                                {conn.status === 'active' ? 'CONNECTED' : conn.status?.toUpperCase()}
                                            </span>
                                        </div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
                                            {conn.ical_url}
                                        </div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                                            {conn.last_sync_at
                                                ? `Last sync: ${new Date(conn.last_sync_at).toLocaleString()}`
                                                : 'Never synced'}
                                            {' · '}
                                            Connected {new Date(conn.created_at).toLocaleDateString()}
                                        </div>
                                    </div>
                                    <button onClick={() => disconnectIcal(conn.id, conn.provider)} style={btnDanger}>
                                        Disconnect
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Available providers */}
                    <div>
                        <h3 style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                            {icalConnections.length > 0 ? 'Add Another iCal Feed' : 'Connect iCal Feed'}
                        </h3>

                        <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            <div style={{
                                padding: 'var(--space-2) var(--space-3)', background: 'rgba(88,166,255,0.05)',
                                border: '1px solid rgba(88,166,255,0.15)', borderRadius: 'var(--radius-sm)',
                                fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', lineHeight: 1.5,
                            }}>
                                💡 Paste the iCal export URL from your OTA provider. The system will fetch and import all future bookings from the calendar feed.
                            </div>

                            <div>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Provider</label>
                                <select value={icalProvider} onChange={e => setIcalProvider(e.target.value)} style={inputStyle}>
                                    <option value="">— Select Provider —</option>
                                    {icalProviders.map(p => (
                                        <option key={p.provider} value={p.provider}>
                                            {displayName(p.provider)}
                                            {connectedIcalProviders.has(p.provider) ? ' (already connected)' : ''}
                                        </option>
                                    ))}
                                    <option value="custom">Custom iCal</option>
                                </select>
                            </div>

                            <div>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>iCal URL</label>
                                <input
                                    value={icalUrl}
                                    onChange={e => setIcalUrl(e.target.value)}
                                    placeholder="https://www.airbnb.com/calendar/ical/..."
                                    style={inputStyle}
                                />
                            </div>

                            <button
                                onClick={() => connectIcal(icalProvider || 'custom', icalUrl)}
                                disabled={icalConnecting || !icalUrl.trim()}
                                style={{
                                    ...btnPrimary,
                                    opacity: icalConnecting || !icalUrl.trim() ? 0.5 : 1,
                                    cursor: icalConnecting || !icalUrl.trim() ? 'not-allowed' : 'pointer',
                                }}
                            >
                                {icalConnecting ? 'Connecting…' : '📡 Connect & Import'}
                            </button>
                        </div>
                    </div>

                    {/* Provider reference */}
                    {icalProviders.length > 0 && (
                        <div style={{ marginTop: 'var(--space-2)' }}>
                            <h3 style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-2)' }}>
                                Supported iCal Providers
                            </h3>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                {icalProviders.map(p => (
                                    <span key={p.provider} style={{
                                        padding: '3px 10px', borderRadius: 'var(--radius-full)',
                                        fontSize: 10, fontWeight: 500,
                                        background: connectedIcalProviders.has(p.provider) ? 'rgba(63,185,80,0.1)' : 'var(--color-surface-2)',
                                        color: connectedIcalProviders.has(p.provider) ? '#3fb950' : 'var(--color-text-dim)',
                                        border: `1px solid ${connectedIcalProviders.has(p.provider) ? 'rgba(63,185,80,0.2)' : 'var(--color-border)'}`,
                                    }}>
                                        {connectedIcalProviders.has(p.provider) ? '✓ ' : ''}{displayName(p.provider)}
                                        <span style={{ opacity: 0.5, marginLeft: 4 }}>Tier {p.tier}</span>
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ========== API Sub-tab ========== */}
            {subTab === 'api' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>

                    {/* Connected API channels */}
                    {apiChannels.length > 0 && (
                        <div style={{ marginBottom: 'var(--space-2)' }}>
                            <h3 style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                                Connected Channels ({apiChannels.length})
                            </h3>
                            {apiChannels.map(ch => (
                                <div key={ch.provider} style={{
                                    ...cardStyle, marginBottom: 'var(--space-2)',
                                    display: 'flex', alignItems: 'center', gap: 'var(--space-4)',
                                }}>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 4 }}>
                                            <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                                                {displayName(ch.provider)}
                                            </span>
                                            <span style={{
                                                padding: '1px 8px', borderRadius: 'var(--radius-full)',
                                                fontSize: 10, fontWeight: 600,
                                                background: ch.enabled ? 'rgba(63,185,80,0.1)' : 'rgba(139,148,158,0.1)',
                                                color: ch.enabled ? '#3fb950' : '#8b949e',
                                            }}>
                                                {ch.enabled ? 'ENABLED' : 'DISABLED'}
                                            </span>
                                        </div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
                                            <span>External ID: <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text)' }}>{ch.external_id}</strong></span>
                                            <span>Sync: <strong style={{ color: 'var(--color-text)' }}>{ch.sync_mode?.replace('_', ' ')}</strong></span>
                                            {ch.inventory_type && <span>Type: {ch.inventory_type}</span>}
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
                                        <button onClick={() => toggleApiEnabled(ch.provider, ch.enabled)} style={btnSecondary}>
                                            {ch.enabled ? 'Disable' : 'Enable'}
                                        </button>
                                        <button onClick={() => disconnectApi(ch.provider)} style={btnDanger}>
                                            Remove
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Add new API channel */}
                    <div>
                        <h3 style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                            {apiChannels.length > 0 ? 'Add Another Channel' : 'Connect API Channel'}
                        </h3>

                        <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            <div style={{
                                padding: 'var(--space-2) var(--space-3)', background: 'rgba(88,166,255,0.05)',
                                border: '1px solid rgba(88,166,255,0.15)', borderRadius: 'var(--radius-sm)',
                                fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', lineHeight: 1.5,
                            }}>
                                🔗 Register an API channel mapping to connect this property to an OTA listing. The external ID is the property/listing identifier on the OTA platform.
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
                                <div>
                                    <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Provider</label>
                                    <select value={apiProvider} onChange={e => setApiProvider(e.target.value)} style={inputStyle}>
                                        <option value="">— Select Provider —</option>
                                        {apiProviders
                                            .filter(p => !connectedApiProviders.has(p.provider))
                                            .map(p => (
                                                <option key={p.provider} value={p.provider}>
                                                    {displayName(p.provider)} (Tier {p.tier})
                                                </option>
                                            ))}
                                    </select>
                                </div>
                                <div>
                                    <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Sync Mode</label>
                                    <select value={apiSyncMode} onChange={e => setApiSyncMode(e.target.value)} style={inputStyle}>
                                        <option value="api_first">API First</option>
                                        <option value="ical_fallback">iCal Fallback</option>
                                        <option value="disabled">Disabled</option>
                                    </select>
                                </div>
                            </div>

                            <div>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>External Listing ID</label>
                                <input
                                    value={apiExternalId}
                                    onChange={e => setApiExternalId(e.target.value)}
                                    placeholder="e.g. AIRBNB-123456 or BDC-789"
                                    style={inputStyle}
                                />
                            </div>

                            <button
                                onClick={() => connectApi(apiProvider, apiExternalId, apiSyncMode)}
                                disabled={apiConnecting || !apiProvider || !apiExternalId.trim()}
                                style={{
                                    ...btnPrimary,
                                    opacity: apiConnecting || !apiProvider || !apiExternalId.trim() ? 0.5 : 1,
                                    cursor: apiConnecting || !apiProvider || !apiExternalId.trim() ? 'not-allowed' : 'pointer',
                                }}
                            >
                                {apiConnecting ? 'Connecting…' : '🔗 Connect Channel'}
                            </button>
                        </div>
                    </div>

                    {/* Provider reference */}
                    {apiProviders.length > 0 && (
                        <div style={{ marginTop: 'var(--space-2)' }}>
                            <h3 style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-2)' }}>
                                Available API Providers
                            </h3>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                {apiProviders.map(p => (
                                    <span key={p.provider} style={{
                                        padding: '3px 10px', borderRadius: 'var(--radius-full)',
                                        fontSize: 10, fontWeight: 500,
                                        background: connectedApiProviders.has(p.provider) ? 'rgba(63,185,80,0.1)' : 'var(--color-surface-2)',
                                        color: connectedApiProviders.has(p.provider) ? '#3fb950' : 'var(--color-text-dim)',
                                        border: `1px solid ${connectedApiProviders.has(p.provider) ? 'rgba(63,185,80,0.2)' : 'var(--color-border)'}`,
                                    }}>
                                        {connectedApiProviders.has(p.provider) ? '✓ ' : ''}{displayName(p.provider)}
                                        <span style={{ opacity: 0.5, marginLeft: 4 }}>Tier {p.tier}</span>
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
