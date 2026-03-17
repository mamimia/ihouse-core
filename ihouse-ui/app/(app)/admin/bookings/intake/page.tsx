'use client';

/**
 * Operational Core — Phase 821: Booking Intake Surface
 * Primary booking entry point for the system.
 *
 * 3 intake paths wired to existing backend:
 *   1. Manual Booking — POST /bookings/manual (manual_booking_router.py)
 *   2. iCal Import  — POST /integrations/ical/connect (bulk_import_router.py)
 *   3. CSV Import   — POST /import/csv (bulk_import_router.py)
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

type IntakePath = 'select' | 'manual' | 'ical' | 'csv';

// ========== Property selector ==========
function PropertySelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
    const [properties, setProperties] = useState<any[]>([]);
    useEffect(() => {
        apiFetch('/properties?limit=100').then(res => {
            setProperties(res.properties || res.data || []);
        }).catch(() => {});
    }, []);
    return (
        <select value={value} onChange={e => onChange(e.target.value)} style={inputStyle}>
            <option value="">— Select Property —</option>
            {properties.map((p: any) => (
                <option key={p.property_id} value={p.property_id}>
                    {p.display_name || p.property_id}
                </option>
            ))}
        </select>
    );
}

const inputStyle: React.CSSProperties = {
    width: '100%', background: 'var(--color-surface)', border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-sm)', padding: '10px 14px', color: 'var(--color-text)',
    fontSize: 'var(--text-sm)', outline: 'none',
};

const cardStyle: React.CSSProperties = {
    background: 'var(--color-surface)', border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
};

// ========== Main Component ==========
export default function BookingIntakePage() {
    const [path, setPath] = useState<IntakePath>('select');
    const [notice, setNotice] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Manual booking form state
    const [mPropertyId, setMPropertyId] = useState('');
    const [mGuestName, setMGuestName] = useState('');
    const [mCheckIn, setMCheckIn] = useState('');
    const [mCheckOut, setMCheckOut] = useState('');
    const [mGuestCount, setMGuestCount] = useState('1');
    const [mSource, setMSource] = useState('direct');
    const [mTotalPrice, setMTotalPrice] = useState('');
    const [mCurrency, setMCurrency] = useState('THB');
    const [mNotes, setMNotes] = useState('');
    const [mSubmitting, setMSubmitting] = useState(false);

    // iCal state
    const [icalPropertyId, setIcalPropertyId] = useState('');
    const [icalUrl, setIcalUrl] = useState('');
    const [icalProvider, setIcalProvider] = useState('airbnb');
    const [icalSubmitting, setIcalSubmitting] = useState(false);
    const [icalResult, setIcalResult] = useState<any>(null);

    // CSV state
    const [csvFile, setCsvFile] = useState<File | null>(null);
    const [csvSubmitting, setCsvSubmitting] = useState(false);
    const [csvResult, setCsvResult] = useState<any>(null);

    // Recent bookings
    const [recentBookings, setRecentBookings] = useState<any[]>([]);

    const showNotice = (msg: string) => { setNotice(msg); setError(null); setTimeout(() => setNotice(null), 3000); };
    const showError = (msg: string) => { setError(msg); setNotice(null); setTimeout(() => setError(null), 5000); };

    const loadRecent = useCallback(async () => {
        try {
            const res = await apiFetch('/bookings?limit=5&sort=created_at:desc');
            setRecentBookings(res.bookings || res.data?.bookings || []);
        } catch { /* graceful */ }
    }, []);

    useEffect(() => { loadRecent(); }, [loadRecent]);

    // ======= Manual booking submit =======
    const submitManual = async () => {
        if (!mPropertyId || !mGuestName || !mCheckIn || !mCheckOut) {
            showError('Please fill required fields');
            return;
        }
        setMSubmitting(true);
        try {
            await apiFetch('/bookings/manual', {
                method: 'POST',
                body: JSON.stringify({
                    property_id: mPropertyId,
                    guest_name: mGuestName.trim(),
                    check_in: mCheckIn,
                    check_out: mCheckOut,
                    guest_count: parseInt(mGuestCount) || 1,
                    source: mSource,
                    total_price: mTotalPrice ? parseFloat(mTotalPrice) : undefined,
                    currency: mCurrency,
                    notes: mNotes || undefined,
                }),
            });
            showNotice('✅ Booking created');
            setMGuestName(''); setMCheckIn(''); setMCheckOut(''); setMTotalPrice(''); setMNotes('');
            loadRecent();
        } catch (e: any) {
            showError(`Failed: ${e.message}`);
        }
        setMSubmitting(false);
    };

    // ======= iCal connect submit =======
    const submitIcal = async () => {
        if (!icalPropertyId || !icalUrl.trim()) {
            showError('Property and iCal URL are required');
            return;
        }
        setIcalSubmitting(true);
        try {
            const res = await apiFetch('/integrations/ical/connect', {
                method: 'POST',
                body: JSON.stringify({
                    property_id: icalPropertyId,
                    ical_url: icalUrl.trim(),
                    provider: icalProvider,
                }),
            });
            setIcalResult(res.data || res);
            showNotice(`✅ iCal connected — ${(res.data || res)?.bookings_imported || 0} bookings imported`);
            setIcalUrl('');
            loadRecent();
        } catch (e: any) {
            showError(`iCal failed: ${e.message}`);
        }
        setIcalSubmitting(false);
    };

    // ======= CSV import submit =======
    const submitCsv = async () => {
        if (!csvFile) {
            showError('Please select a CSV file');
            return;
        }
        setCsvSubmitting(true);
        try {
            const formData = new FormData();
            formData.append('file', csvFile);
            const token = getToken();
            const res = await fetch(`${BASE}/import/csv`, {
                method: 'POST',
                headers: token ? { Authorization: `Bearer ${token}` } : {},
                body: formData,
            });
            if (!res.ok) throw new Error(`${res.status}`);
            const data = await res.json();
            setCsvResult(data.data || data);
            showNotice(`✅ CSV imported — ${(data.data || data)?.imported || 0} records`);
            setCsvFile(null);
            loadRecent();
        } catch (e: any) {
            showError(`CSV import failed: ${e.message}`);
        }
        setCsvSubmitting(false);
    };

    return (
        <div style={{ maxWidth: 700, margin: '0 auto' }}>
            {/* Toast overlays */}
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

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-5)' }}>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Booking Management
                </p>
                <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
                    New Booking
                </h1>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                    Manual entry, iCal import, or CSV upload
                </p>
            </div>

            {/* ========== PATH SELECTOR ========== */}
            {path === 'select' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                    {[
                        { key: 'manual' as IntakePath, icon: '✍️', title: 'Manual Booking', desc: 'Enter guest details manually' },
                        { key: 'ical' as IntakePath, icon: '📡', title: 'iCal Import', desc: 'Connect Airbnb, Booking.com, or custom iCal URL' },
                        { key: 'csv' as IntakePath, icon: '📄', title: 'CSV Upload', desc: 'Bulk import from spreadsheet' },
                    ].map(opt => (
                        <div key={opt.key} onClick={() => setPath(opt.key)} style={{
                            ...cardStyle, cursor: 'pointer', transition: 'border-color 0.2s, transform 0.15s',
                            display: 'flex', alignItems: 'center', gap: 'var(--space-4)',
                        }}
                            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--color-primary)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
                            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.transform = 'none'; }}>
                            <div style={{ fontSize: 'var(--text-2xl)' }}>{opt.icon}</div>
                            <div>
                                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)' }}>{opt.title}</div>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{opt.desc}</div>
                            </div>
                            <span style={{ marginLeft: 'auto', color: 'var(--color-text-faint)', fontSize: 'var(--text-lg)' }}>→</span>
                        </div>
                    ))}

                    {/* Recent bookings section */}
                    {recentBookings.length > 0 && (
                        <div style={{ marginTop: 'var(--space-4)' }}>
                            <h3 style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                                Recent Bookings
                            </h3>
                            {recentBookings.map((b: any, i) => (
                                <div key={b.booking_id || b.id || i} style={{
                                    padding: 'var(--space-2) var(--space-3)', background: 'var(--color-surface-2)',
                                    borderRadius: 'var(--radius-sm)', marginBottom: 4,
                                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                    fontSize: 'var(--text-xs)',
                                }}>
                                    <span style={{ color: 'var(--color-text)' }}>{b.guest_name || 'Guest'}</span>
                                    <span style={{ color: 'var(--color-text-dim)' }}>{b.check_in || '—'} → {b.check_out || '—'}</span>
                                    <span style={{
                                        padding: '1px 8px', borderRadius: 8, fontSize: '10px', fontWeight: 600,
                                        background: b.status === 'confirmed' ? 'rgba(63,185,80,0.1)' : 'rgba(88,166,255,0.1)',
                                        color: b.status === 'confirmed' ? '#3fb950' : '#58a6ff',
                                    }}>{b.status || '—'}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ========== MANUAL BOOKING ========== */}
            {path === 'manual' && (
                <div style={cardStyle}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                        <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>✍️ Manual Booking</h2>
                        <button onClick={() => setPath('select')} style={{
                            background: 'none', border: 'none', color: 'var(--color-text-dim)',
                            cursor: 'pointer', fontSize: 'var(--text-sm)',
                        }}>← Back</button>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Property *</label>
                            <PropertySelect value={mPropertyId} onChange={setMPropertyId} />
                        </div>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Guest Name *</label>
                            <input value={mGuestName} onChange={e => setMGuestName(e.target.value)} placeholder="John Doe" style={inputStyle} />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
                            <div>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Check-in *</label>
                                <input type="date" value={mCheckIn} onChange={e => setMCheckIn(e.target.value)} style={inputStyle} />
                            </div>
                            <div>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Check-out *</label>
                                <input type="date" value={mCheckOut} onChange={e => setMCheckOut(e.target.value)} style={inputStyle} />
                            </div>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-2)' }}>
                            <div>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Guests</label>
                                <input type="number" value={mGuestCount} onChange={e => setMGuestCount(e.target.value)} min="1" style={inputStyle} />
                            </div>
                            <div>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Source</label>
                                <select value={mSource} onChange={e => setMSource(e.target.value)} style={inputStyle}>
                                    <option value="direct">Direct</option>
                                    <option value="airbnb">Airbnb</option>
                                    <option value="booking">Booking.com</option>
                                    <option value="agoda">Agoda</option>
                                    <option value="phone">Phone</option>
                                    <option value="referral">Referral</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                            <div>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Currency</label>
                                <select value={mCurrency} onChange={e => setMCurrency(e.target.value)} style={inputStyle}>
                                    <option value="THB">THB</option>
                                    <option value="USD">USD</option>
                                    <option value="EUR">EUR</option>
                                    <option value="GBP">GBP</option>
                                    <option value="ILS">ILS</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Total Price</label>
                            <input type="number" value={mTotalPrice} onChange={e => setMTotalPrice(e.target.value)} placeholder="0" style={inputStyle} />
                        </div>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Notes</label>
                            <textarea value={mNotes} onChange={e => setMNotes(e.target.value)} placeholder="Special requests, late arrival, etc."
                                rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
                        </div>
                    </div>

                    <button onClick={submitManual} disabled={mSubmitting} style={{
                        width: '100%', padding: '14px', marginTop: 'var(--space-4)',
                        borderRadius: 'var(--radius-md)', background: 'var(--color-primary)', color: '#fff',
                        border: 'none', fontWeight: 700, fontSize: 'var(--text-sm)',
                        cursor: mSubmitting ? 'not-allowed' : 'pointer', opacity: mSubmitting ? 0.5 : 1,
                    }}>{mSubmitting ? 'Creating...' : '✅ Create Booking'}</button>
                </div>
            )}

            {/* ========== ICAL IMPORT ========== */}
            {path === 'ical' && (
                <div style={cardStyle}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                        <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>📡 iCal Import</h2>
                        <button onClick={() => setPath('select')} style={{
                            background: 'none', border: 'none', color: 'var(--color-text-dim)',
                            cursor: 'pointer', fontSize: 'var(--text-sm)',
                        }}>← Back</button>
                    </div>

                    <div style={{
                        padding: 'var(--space-3)', background: 'rgba(88,166,255,0.05)',
                        border: '1px solid rgba(88,166,255,0.2)', borderRadius: 'var(--radius-sm)',
                        fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', lineHeight: 1.5,
                    }}>
                        💡 Paste the iCal export URL from Airbnb, Booking.com, or any other calendar provider. The system will parse and import all future bookings from the feed.
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Property *</label>
                            <PropertySelect value={icalPropertyId} onChange={setIcalPropertyId} />
                        </div>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Provider</label>
                            <select value={icalProvider} onChange={e => setIcalProvider(e.target.value)} style={inputStyle}>
                                <option value="airbnb">Airbnb</option>
                                <option value="booking">Booking.com</option>
                                <option value="vrbo">VRBO</option>
                                <option value="agoda">Agoda</option>
                                <option value="custom">Custom iCal</option>
                            </select>
                        </div>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>iCal URL *</label>
                            <input value={icalUrl} onChange={e => setIcalUrl(e.target.value)}
                                placeholder="https://www.airbnb.com/calendar/ical/..." style={inputStyle} />
                        </div>
                    </div>

                    <button onClick={submitIcal} disabled={icalSubmitting} style={{
                        width: '100%', padding: '14px', marginTop: 'var(--space-4)',
                        borderRadius: 'var(--radius-md)', background: 'var(--color-primary)', color: '#fff',
                        border: 'none', fontWeight: 700, fontSize: 'var(--text-sm)',
                        cursor: icalSubmitting ? 'not-allowed' : 'pointer', opacity: icalSubmitting ? 0.5 : 1,
                    }}>{icalSubmitting ? 'Connecting...' : '📡 Connect & Import'}</button>

                    {icalResult && (
                        <div style={{
                            marginTop: 'var(--space-4)', padding: 'var(--space-4)',
                            background: 'rgba(63,185,80,0.05)', border: '1px solid rgba(63,185,80,0.2)',
                            borderRadius: 'var(--radius-md)',
                        }}>
                            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: '#3fb950', marginBottom: 'var(--space-2)' }}>
                                ✅ iCal Connected
                            </div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                Bookings imported: <strong>{icalResult.bookings_imported || 0}</strong>
                            </div>
                            {icalResult.connection_id && (
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                                    Connection ID: {icalResult.connection_id}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* ========== CSV IMPORT ========== */}
            {path === 'csv' && (
                <div style={cardStyle}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
                        <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>📄 CSV Upload</h2>
                        <button onClick={() => setPath('select')} style={{
                            background: 'none', border: 'none', color: 'var(--color-text-dim)',
                            cursor: 'pointer', fontSize: 'var(--text-sm)',
                        }}>← Back</button>
                    </div>

                    <div style={{
                        padding: 'var(--space-3)', background: 'rgba(210,153,34,0.05)',
                        border: '1px solid rgba(210,153,34,0.2)', borderRadius: 'var(--radius-sm)',
                        fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-4)', lineHeight: 1.5,
                    }}>
                        📋 CSV format: property_id, guest_name, check_in, check_out, guest_count, source, total_price, currency
                    </div>

                    <label style={{
                        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                        padding: 'var(--space-6)', borderRadius: 'var(--radius-md)',
                        border: '2px dashed var(--color-border)', background: 'var(--color-surface-2)',
                        cursor: 'pointer', transition: 'border-color 0.2s',
                    }}
                        onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--color-primary)'; }}
                        onDragLeave={e => { e.currentTarget.style.borderColor = 'var(--color-border)'; }}
                        onDrop={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--color-border)'; if (e.dataTransfer.files[0]) setCsvFile(e.dataTransfer.files[0]); }}>
                        <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>📄</div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                            {csvFile ? csvFile.name : 'Drop CSV here or click to select'}
                        </div>
                        <input type="file" accept=".csv" style={{ display: 'none' }}
                            onChange={e => { if (e.target.files?.[0]) setCsvFile(e.target.files[0]); }} />
                    </label>

                    <button onClick={submitCsv} disabled={csvSubmitting || !csvFile} style={{
                        width: '100%', padding: '14px', marginTop: 'var(--space-4)',
                        borderRadius: 'var(--radius-md)', background: csvFile ? 'var(--color-primary)' : 'var(--color-surface-2)',
                        color: csvFile ? '#fff' : 'var(--color-text-dim)', border: 'none',
                        fontWeight: 700, fontSize: 'var(--text-sm)',
                        cursor: csvSubmitting || !csvFile ? 'not-allowed' : 'pointer',
                        opacity: csvSubmitting || !csvFile ? 0.5 : 1,
                    }}>{csvSubmitting ? 'Uploading...' : '📤 Upload & Import'}</button>

                    {csvResult && (
                        <div style={{
                            marginTop: 'var(--space-4)', padding: 'var(--space-4)',
                            background: 'rgba(63,185,80,0.05)', border: '1px solid rgba(63,185,80,0.2)',
                            borderRadius: 'var(--radius-md)',
                        }}>
                            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: '#3fb950', marginBottom: 'var(--space-2)' }}>
                                ✅ CSV Imported
                            </div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                Properties: {csvResult.imported || 0} · Skipped: {csvResult.skipped || 0}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
