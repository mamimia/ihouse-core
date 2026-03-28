'use client';

/**
 * Admin Settings — /admin/settings
 * Property ID auto-generation configuration.
 */

import { useEffect, useState } from 'react';
import { getToken } from '@/lib/api';

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

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
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
}

// ─── Phase 991: OCR Provider Configuration Section ───────────────

const PROVIDER_META: Record<string, { label: string; icon: string; desc: string; captureTypes: string[] }> = {
    azure_document_intelligence: {
        label: 'Azure Document Intelligence',
        icon: '☁️',
        desc: 'Microsoft Azure AI — identity document recognition (passport, ID, license)',
        captureTypes: ['Identity Documents'],
    },
    local_mrz: {
        label: 'Local MRZ Reader',
        icon: '📟',
        desc: 'On-device MRZ zone extraction from passport machine-readable zones',
        captureTypes: ['Identity Documents (MRZ)'],
    },
    local_meter: {
        label: 'Local Meter Reader',
        icon: '⚡',
        desc: 'On-device meter display digit extraction via pattern matching',
        captureTypes: ['Opening Meter', 'Closing Meter'],
    },
    local_tesseract: {
        label: 'Local Tesseract OCR',
        icon: '🔤',
        desc: 'Generic on-device text recognition — last-resort fallback',
        captureTypes: ['All (fallback)'],
    },
};

interface ProviderConfig {
    id: string;
    provider_name: string;
    enabled: boolean;
    priority: number;
    is_primary: boolean;
    is_fallback: boolean;
    last_test_at: string | null;
    last_test_result: string | null;
    has_endpoint: boolean;
    has_api_key: boolean;
    endpoint_preview: string;
    api_key_preview: string;
}

function OcrConfigSection({ sectionStyle, labelStyle, inputStyle, showNotice }: {
    sectionStyle: React.CSSProperties;
    labelStyle: React.CSSProperties;
    inputStyle: React.CSSProperties;
    showNotice: (msg: string) => void;
}) {
    const [providers, setProviders] = useState<ProviderConfig[]>([]);
    const [ocrLoading, setOcrLoading] = useState(true);
    const [expanded, setExpanded] = useState<string | null>(null);
    const [saving, setSaving] = useState<string | null>(null);
    const [testing, setTesting] = useState<string | null>(null);
    const [testResult, setTestResult] = useState<Record<string, { success: boolean; message: string; ms: number }>>({});
    const [azureEndpoint, setAzureEndpoint] = useState('');
    const [azureApiKey, setAzureApiKey] = useState('');

    useEffect(() => { loadProviders(); }, []);

    async function loadProviders() {
        try {
            const raw = await apiFetch<any>('/admin/ocr/provider-config');
            const list: ProviderConfig[] = Array.isArray(raw) ? raw : (raw?.data || []);
            setProviders(list);
            const az = list.find(p => p.provider_name === 'azure_document_intelligence');
            if (az) {
                setAzureEndpoint(az.endpoint_preview || '');
                setAzureApiKey(az.has_api_key ? az.api_key_preview : '');
            }
        } catch { /* silent */ }
        setOcrLoading(false);
    }

    async function toggleProvider(name: string, enabled: boolean) {
        const p = providers.find(x => x.provider_name === name);
        if (!p) return;
        setSaving(name);
        try {
            await apiFetch(`/admin/ocr/provider-config/${name}`, {
                method: 'PUT',
                body: JSON.stringify({ enabled, priority: p.priority, is_primary: p.is_primary, is_fallback: p.is_fallback }),
            });
            setProviders(prev => prev.map(x => x.provider_name === name ? { ...x, enabled } : x));
            showNotice(`${enabled ? '✓ Enabled' : '✗ Disabled'} ${PROVIDER_META[name]?.label || name}`);
        } catch { showNotice('Failed to update provider'); }
        setSaving(null);
    }

    async function saveAzureConfig() {
        setSaving('azure_document_intelligence');
        try {
            await apiFetch('/admin/ocr/provider-config/azure_document_intelligence', {
                method: 'PUT',
                body: JSON.stringify({
                    enabled: providers.find(p => p.provider_name === 'azure_document_intelligence')?.enabled ?? false,
                    priority: 1, is_primary: true, is_fallback: false,
                    config: { endpoint: azureEndpoint.trim(), api_key: azureApiKey.trim(), timeout: 30 },
                }),
            });
            showNotice('✓ Azure configuration saved');
            await loadProviders();
        } catch { showNotice('Failed to save Azure config'); }
        setSaving(null);
    }

    async function testConnection(name: string) {
        setTesting(name);
        try {
            const res = await apiFetch<any>('/admin/ocr/test-connection', {
                method: 'POST', body: JSON.stringify({ provider_name: name }),
            });
            const d = res?.data || res;
            setTestResult(prev => ({ ...prev, [name]: { success: d.success, message: d.message || '', ms: d.response_time_ms || 0 } }));
            await loadProviders();
            showNotice(d.success ? `✓ ${PROVIDER_META[name]?.label} connected (${d.response_time_ms}ms)` : `✗ ${d.message}`);
        } catch {
            setTestResult(prev => ({ ...prev, [name]: { success: false, message: 'Request failed', ms: 0 } }));
        }
        setTesting(null);
    }

    function fmtTestTime(ts: string | null) {
        if (!ts) return 'Never';
        try {
            const ms = Date.now() - new Date(ts).getTime();
            if (ms < 60_000) return 'Just now';
            if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
            if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
            return new Date(ts).toLocaleDateString();
        } catch { return ts; }
    }

    if (ocrLoading) return <div style={sectionStyle}><div style={{ color: 'var(--color-text-dim)' }}>Loading OCR config…</div></div>;

    return (
        <div style={sectionStyle}>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 'var(--space-2)' }}>
                OCR Configuration
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 'var(--space-5)' }}>
                Configure OCR providers for identity document scanning and meter reading.
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                {providers.map(prov => {
                    const meta = PROVIDER_META[prov.provider_name] || { label: prov.provider_name, icon: '🔧', desc: '', captureTypes: [] };
                    const isAzure = prov.provider_name === 'azure_document_intelligence';
                    const isExp = expanded === prov.provider_name;
                    const statusColor = !prov.last_test_result ? 'var(--color-text-faint)' : prov.last_test_result.startsWith('success') ? '#22c55e' : '#ef4444';
                    const tr = testResult[prov.provider_name];

                    return (
                        <div key={prov.provider_name} style={{
                            border: `1px solid ${prov.enabled ? 'rgba(88,166,255,0.3)' : 'var(--color-border)'}`,
                            borderRadius: 'var(--radius-md)',
                            background: prov.enabled ? 'rgba(88,166,255,0.03)' : 'var(--color-surface-2)',
                            overflow: 'hidden', transition: 'border-color 0.2s',
                        }}>
                            {/* Header */}
                            <div
                                style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', padding: 'var(--space-3) var(--space-4)', cursor: isAzure ? 'pointer' : 'default' }}
                                onClick={() => isAzure && setExpanded(isExp ? null : prov.provider_name)}
                            >
                                <span style={{ fontSize: 22 }}>{meta.icon}</span>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)' }}>{meta.label}</span>
                                        {prov.is_primary && <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: 'rgba(88,166,255,0.15)', color: 'var(--color-sage)' }}>PRIMARY</span>}
                                        {prov.is_fallback && <span style={{ fontSize: 9, fontWeight: 600, padding: '1px 5px', borderRadius: 3, background: 'rgba(160,160,160,0.12)', color: 'var(--color-text-dim)' }}>FALLBACK</span>}
                                        <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'rgba(160,160,160,0.1)', color: 'var(--color-text-faint)' }}>P{prov.priority}</span>
                                    </div>
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 1 }}>{meta.captureTypes.join(' · ')}</div>
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: statusColor, display: 'inline-block' }} />
                                    <span style={{ fontSize: 10, color: 'var(--color-text-faint)' }}>{fmtTestTime(prov.last_test_at)}</span>
                                </div>

                                {/* Toggle */}
                                <button onClick={e => { e.stopPropagation(); toggleProvider(prov.provider_name, !prov.enabled); }} disabled={saving === prov.provider_name}
                                    style={{ width: 40, height: 22, borderRadius: 11, background: prov.enabled ? '#22c55e' : 'var(--color-border)', border: 'none', cursor: 'pointer', position: 'relative', transition: 'background 0.2s', opacity: saving === prov.provider_name ? 0.5 : 1, flexShrink: 0 }}>
                                    <span style={{ position: 'absolute', top: 2, left: prov.enabled ? 20 : 2, width: 18, height: 18, borderRadius: '50%', background: '#fff', transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
                                </button>

                                {/* Test */}
                                <button onClick={e => { e.stopPropagation(); testConnection(prov.provider_name); }} disabled={testing === prov.provider_name}
                                    style={{ fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', cursor: 'pointer', flexShrink: 0 }}>
                                    {testing === prov.provider_name ? '⏳' : '🔌 Test'}
                                </button>

                                {isAzure && <span style={{ fontSize: 11, color: 'var(--color-text-faint)', transform: isExp ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▼</span>}
                            </div>

                            {/* Test result */}
                            {tr && (
                                <div style={{ padding: '0 var(--space-4) var(--space-2)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: tr.success ? '#22c55e' : '#ef4444' }} />
                                    <span style={{ fontSize: 11, color: tr.success ? '#22c55e' : '#ef4444' }}>{tr.message}</span>
                                    {tr.ms > 0 && <span style={{ fontSize: 10, color: 'var(--color-text-faint)' }}>({tr.ms}ms)</span>}
                                </div>
                            )}

                            {/* Azure expanded config */}
                            {isAzure && isExp && (
                                <div style={{ padding: 'var(--space-3) var(--space-4) var(--space-4)', borderTop: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontStyle: 'italic' }}>{meta.desc}</div>
                                    <div>
                                        <label style={labelStyle}>Azure Endpoint URL</label>
                                        <input style={inputStyle} value={azureEndpoint} onChange={e => setAzureEndpoint(e.target.value)} placeholder="https://your-resource.cognitiveservices.azure.com" />
                                        <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginTop: 3 }}>{prov.has_endpoint ? `Current: ${prov.endpoint_preview}` : 'Not configured'}</div>
                                    </div>
                                    <div>
                                        <label style={labelStyle}>Azure API Key</label>
                                        <input type="password" style={inputStyle} value={azureApiKey} onChange={e => setAzureApiKey(e.target.value)} placeholder="Enter API key" />
                                        <div style={{ fontSize: 10, color: 'var(--color-text-faint)', marginTop: 3 }}>{prov.has_api_key ? `Current: ${prov.api_key_preview}` : 'Not configured'}</div>
                                    </div>
                                    <div style={{ background: 'rgba(210,153,34,0.08)', border: '1px solid rgba(210,153,34,0.2)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--color-warn)' }}>
                                        <strong>Security:</strong> API keys are stored securely and never displayed in full. Leaving the key field empty preserves the existing key.
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)' }}>
                                        <button onClick={() => testConnection('azure_document_intelligence')} disabled={testing === 'azure_document_intelligence'}
                                            style={{ padding: '8px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer' }}>
                                            {testing === 'azure_document_intelligence' ? '⏳ Testing…' : '🔌 Test Connection'}
                                        </button>
                                        <button onClick={saveAzureConfig} disabled={saving === 'azure_document_intelligence'}
                                            style={{ padding: '8px 14px', borderRadius: 'var(--radius-sm)', border: 'none', background: saving === 'azure_document_intelligence' ? 'var(--color-border)' : 'var(--color-primary)', color: '#fff', fontSize: 'var(--text-xs)', fontWeight: 700, cursor: 'pointer' }}>
                                            {saving === 'azure_document_intelligence' ? 'Saving…' : 'Save Azure Config'}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Scope notice */}
            <div style={{ marginTop: 'var(--space-4)', background: 'rgba(88,166,255,0.06)', border: '1px solid rgba(88,166,255,0.15)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-3) var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--color-sage)' }}>
                <strong>OCR Scope:</strong> OCR is restricted to check-in identity documents, check-in opening meter readings, and check-out closing meter readings only. It does not apply to any other image workflows.
            </div>
        </div>
    );
}

export default function AdminSettingsPage() {
    const [prefix, setPrefix] = useState('KPG');
    const [startNumber, setStartNumber] = useState(500);
    const [nextId, setNextId] = useState('');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState<string | null>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3500); };

    useEffect(() => {
        apiFetch('/admin/property-id-settings')
            .then(data => {
                setPrefix(data.prefix ?? 'KPG');
                setStartNumber(data.start_number ?? 500);
                setNextId(data.next_id ?? '');
            })
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    // Live preview: update nextId as user types
    useEffect(() => {
        if (prefix.trim()) {
            setNextId(`${prefix.trim().toUpperCase()}-${startNumber} (preview only until saved)`);
        }
    }, [prefix, startNumber]);

    const handleSave = async () => {
        if (!prefix.trim() || prefix.length > 10) {
            showNotice('Prefix must be 1–10 characters.');
            return;
        }
        if (startNumber < 1) {
            showNotice('Starting number must be at least 1.');
            return;
        }
        setSaving(true);
        try {
            const data = await apiFetch('/admin/property-id-settings', {
                method: 'PUT',
                body: JSON.stringify({ prefix: prefix.trim().toUpperCase(), start_number: startNumber }),
            });
            setPrefix(data.prefix);
            setStartNumber(data.start_number);
            setNextId(data.next_id);
            showNotice(`✓ Saved. Next property ID will be ${data.next_id}`);
        } catch {
            showNotice('Save failed. Please try again.');
        }
        setSaving(false);
    };

    const inputStyle: React.CSSProperties = {
        width: '100%', boxSizing: 'border-box',
        background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-sm)', color: 'var(--color-text)',
        fontSize: 'var(--text-sm)', padding: '10px 14px',
    };
    const labelStyle: React.CSSProperties = {
        fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)',
        fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
        marginBottom: 6, display: 'block',
    };
    const sectionStyle: React.CSSProperties = {
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)',
        marginBottom: 'var(--space-5)',
    };

    return (
        <div style={{ maxWidth: 640 }}>
            {/* Notice toast */}
            {notice && (
                <div style={{
                    position: 'fixed', top: 20, right: 20, zIndex: 999,
                    background: 'var(--color-surface)', border: '1px solid var(--color-primary)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)', color: 'var(--color-primary)', boxShadow: 'var(--shadow-md)',
                }}>
                    {notice}
                </div>
            )}

            {/* Page header */}
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                    Admin
                </p>
                <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em', margin: 0 }}>
                    Settings
                </h1>
            </div>

            {loading ? (
                <div style={{ color: 'var(--color-text-dim)' }}>Loading…</div>
            ) : (
                <>
                    {/* Property ID Section */}
                    <div style={sectionStyle}>
                        <div style={{
                            fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)',
                            textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 'var(--space-5)',
                        }}>
                            Property ID Auto-generation
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)', marginBottom: 'var(--space-5)' }}>
                            <div>
                                <label style={labelStyle} htmlFor="id-prefix">Prefix</label>
                                <input
                                    id="id-prefix"
                                    style={inputStyle}
                                    value={prefix}
                                    onChange={e => setPrefix(e.target.value.toUpperCase())}
                                    maxLength={10}
                                    placeholder="e.g. KPG"
                                />
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                                    Max 10 characters
                                </div>
                            </div>
                            <div>
                                <label style={labelStyle} htmlFor="id-start">Starting number</label>
                                <input
                                    id="id-start"
                                    style={inputStyle}
                                    type="number"
                                    min={1}
                                    value={startNumber}
                                    onChange={e => setStartNumber(parseInt(e.target.value) || 1)}
                                />
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>
                                    Only applies if no properties with this prefix exist yet
                                </div>
                            </div>
                        </div>

                        {/* Next ID preview */}
                        {nextId && (
                            <div style={{
                                background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)',
                                marginBottom: 'var(--space-5)', fontSize: 'var(--text-sm)',
                                color: 'var(--color-text)',
                            }}>
                                <span style={{ color: 'var(--color-text-faint)' }}>Next property will be assigned: </span>
                                <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-primary)' }}>
                                    {nextId.includes('preview') ? `${prefix.trim().toUpperCase() || 'KPG'}-??? (save to confirm)` : nextId}
                                </strong>
                            </div>
                        )}

                        {/* Immutability notice */}
                        <div style={{
                            background: 'rgba(181,110,69,0.06)', border: '1px solid rgba(181,110,69,0.2)',
                            borderRadius: 'var(--radius-sm)', padding: 'var(--space-3) var(--space-4)',
                            marginBottom: 'var(--space-5)', fontSize: 'var(--text-xs)', color: 'var(--color-warn)',
                        }}>
                            <strong>Immutability rules:</strong><br />
                            • Property IDs are assigned automatically at creation and <strong>cannot be changed</strong> once set.<br />
                            • IDs are <strong>never reused</strong> — not even after archiving or deletion.<br />
                            • Archived properties retain their original IDs permanently.
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                style={{
                                    background: saving ? 'var(--color-border)' : 'var(--color-primary)',
                                    color: '#fff', border: 'none', borderRadius: 'var(--radius-md)',
                                    padding: '10px 28px', fontSize: 'var(--text-sm)', fontWeight: 700,
                                    cursor: saving ? 'not-allowed' : 'pointer',
                                    boxShadow: saving ? 'none' : 'var(--shadow-sm)',
                                }}
                            >{saving ? 'Saving…' : 'Save Settings'}</button>
                        </div>
                    </div>
                    {/* ─── Phase 991: OCR Configuration ─── */}
                    <OcrConfigSection sectionStyle={sectionStyle} labelStyle={labelStyle} inputStyle={inputStyle} showNotice={showNotice} />
                </>
            )}

            <div style={{ marginTop: 'var(--space-8)', paddingTop: 'var(--space-5)', borderTop: '1px solid var(--color-border)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                Domaniqo · Admin Settings · Phase 991
            </div>
        </div>
    );
}
