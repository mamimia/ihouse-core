'use client';
/**
 * Phase 844 — Property Full-Page Create
 * /admin/properties/new
 *
 * Replaces AddPropertyModal on the list page.
 * Collects all base fields in one page with 2 sections:
 *   Section A: Core identity (ID, name, type, timezone, currency)
 *   Section B: Location & capacity (city, country, address, GPS, bedrooms, beds, bathrooms, max guests)
 *   Section C: Operation (checkin time, checkout time, description, listing URL)
 *
 * Layout: back=top-left, "Create Property"=sticky bottom-right footer
 */

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
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
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

// ── Styles ──────────────────────────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  width: '100%', background: 'var(--color-surface-2)',
  border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)',
  padding: '9px 12px', color: 'var(--color-text)',
  fontSize: 'var(--text-sm)', outline: 'none', boxSizing: 'border-box',
};
const labelStyle: React.CSSProperties = {
  fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)',
  display: 'block', marginBottom: 6, fontWeight: 500,
  textTransform: 'uppercase', letterSpacing: '0.04em',
};
const sectionHead: React.CSSProperties = {
  fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-faint)',
  textTransform: 'uppercase', letterSpacing: '0.07em',
  marginTop: 'var(--space-6)', marginBottom: 'var(--space-3)',
  paddingBottom: 'var(--space-2)', borderBottom: '1px solid var(--color-border)',
};

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <label style={labelStyle}>{label}</label>
      {children}
      {hint && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 4 }}>{hint}</span>}
    </div>
  );
}

const TIMEZONES = [
  'Asia/Bangkok', 'Asia/Singapore', 'Asia/Tokyo', 'Asia/Kolkata',
  'Asia/Dubai', 'Europe/London', 'Europe/Paris', 'America/New_York', 'America/Los_Angeles', 'UTC',
];
const CURRENCIES = ['THB', 'USD', 'EUR', 'GBP', 'SGD', 'AUD', 'HKD', 'JPY'];
const PROPERTY_TYPES = ['apartment', 'villa', 'house', 'condo', 'studio', 'resort', 'hostel', 'hotel', 'other'];

export default function NewPropertyPage() {
  const router = useRouter();

  // Section A — Core identity
  const [propertyId, setPropertyId] = useState('');
  const [idLoading, setIdLoading] = useState(true);
  const [displayName, setDisplayName] = useState('');
  const [propertyType, setPropertyType] = useState('');
  const [timezone, setTimezone] = useState('Asia/Bangkok');
  const [currency, setCurrency] = useState('THB');

  // Auto-fetch next property ID on mount
  useEffect(() => {
    (async () => {
      try {
        const data = await apiFetch<{ next_id: string }>('/properties/next-id');
        setPropertyId(data.next_id);
      } catch {
        setPropertyId('KPG-500');
      } finally {
        setIdLoading(false);
      }
    })();
  }, []);

  // Section B — Location & capacity
  const [city, setCity] = useState('');
  const [country, setCountry] = useState('TH');
  const [address, setAddress] = useState('');
  const [lat, setLat] = useState('');
  const [lng, setLng] = useState('');
  const [bedrooms, setBedrooms] = useState('');
  const [beds, setBeds] = useState('');
  const [bathrooms, setBathrooms] = useState('');
  const [maxGuests, setMaxGuests] = useState('');

  // Section C — Operation
  const [checkinTime, setCheckinTime] = useState('15:00');
  const [checkoutTime, setCheckoutTime] = useState('11:00');
  const [description, setDescription] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  // Deposit (Phase 844)
  const [depositRequired, setDepositRequired] = useState(false);
  const [depositAmount, setDepositAmount] = useState('');
  const [depositCurrency, setDepositCurrency] = useState('THB');
  // Geolocation (Phase 844)
  const [geoStatus, setGeoStatus] = useState<'idle'|'loading'|'ok'|'err'>('idle');

  // UI
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Listing URL fetch (Phase 844)
  const [fetchStatus, setFetchStatus] = useState<'idle'|'loading'|'done'|'err'>('idle');
  const [pullResult, setPullResult] = useState<any>(null);
  const [fetchedPhotos, setFetchedPhotos] = useState<string[]>([]);

  const handlePull = async () => {
    if (!sourceUrl.trim() || !sourceUrl.startsWith('http')) { setError('Enter a valid listing URL first.'); return; }
    setFetchStatus('loading');
    setPullResult(null);
    setFetchedPhotos([]);
    try {
      const data = await apiFetch<any>('/properties/_draft/fetch-listing', {
        method: 'POST',
        body: JSON.stringify({ listing_url: sourceUrl.trim() }),
      });
      setPullResult(data);
      setFetchStatus('done');
      // Auto-fill fields — always overwrite on fresh fetch
      const imp = data?.imported || {};
      if (imp.name) setDisplayName(imp.name);
      if (imp.description) setDescription(imp.description);
      if (imp.city) setCity(imp.city);
      if (imp.country) setCountry(imp.country);
      if (imp.address) setAddress(imp.address);
      if (imp.latitude) setLat(String(imp.latitude));
      if (imp.longitude) setLng(String(imp.longitude));
      if (imp.bedrooms) setBedrooms(String(imp.bedrooms));
      if (imp.beds) setBeds(String(imp.beds));
      if (imp.bathrooms) setBathrooms(String(imp.bathrooms));
      if (imp.max_guests) setMaxGuests(String(imp.max_guests));
      // Store photos for preview
      if (imp.photos && Array.isArray(imp.photos) && imp.photos.length > 0) {
        setFetchedPhotos(imp.photos);
      }
    } catch (e: any) {
      setFetchStatus('err');
      setPullResult({ error: e.message });
    }
  };

  const handleCreate = async () => {
    setError(null);
    setSaving(true);
    try {
      const body: Record<string, any> = {
        property_id: propertyId,  // auto-generated KPG-XXX
        timezone,
        base_currency: currency,
      };
      if (displayName.trim())   body.display_name  = displayName.trim();
      if (propertyType)         body.property_type  = propertyType;
      if (city.trim())          body.city           = city.trim();
      if (country.trim())       body.country        = country.trim();
      if (address.trim())       body.address        = address.trim();
      if (lat.trim())           body.latitude       = parseFloat(lat);
      if (lng.trim())           body.longitude      = parseFloat(lng);
      if (bedrooms.trim())      body.bedrooms       = parseInt(bedrooms);
      if (beds.trim())          body.beds           = parseInt(beds);
      if (bathrooms.trim())     body.bathrooms      = parseFloat(bathrooms);
      if (maxGuests.trim())     body.max_guests     = parseInt(maxGuests);
      if (checkinTime)          body.checkin_time   = checkinTime;
      if (checkoutTime)         body.checkout_time  = checkoutTime;
      if (description.trim())   body.description    = description.trim();
      if (sourceUrl.trim())     body.source_url     = sourceUrl.trim();
      // Deposit (Phase 844)
      body.deposit_required = depositRequired;
      if (depositRequired && depositAmount) body.deposit_amount = parseFloat(depositAmount);
      if (depositRequired) body.deposit_currency = depositCurrency;

      const result = await apiFetch<any>('/properties', { method: 'POST', body: JSON.stringify(body) });
      const createdId = result?.property_id || propertyId;

      // Save fetched photos to gallery
      if (fetchedPhotos.length > 0) {
        for (let i = 0; i < fetchedPhotos.length; i++) {
          try {
            await apiFetch(`/properties/${createdId}/marketing-photos`, {
              method: 'POST',
              body: JSON.stringify({
                photo_url: fetchedPhotos[i],
                caption: `Photo ${i + 1}`,
                display_order: i,
                source: 'listing_import',
              }),
            });
          } catch {
            console.warn(`Failed to save photo ${i + 1}`);
          }
        }
      }

      router.push(`/admin/properties/${createdId}?created=1`);
    } catch (e: any) {
      const msg = String(e?.message || '');
      setError(msg.includes('409') ? 'Property ID already exists.' : 'Failed to create property. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>

      {/* ── Page header ─────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 'var(--space-4)',
        padding: 'var(--space-4) var(--space-5)', borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
      }}>
        <button onClick={() => router.back()} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)',
          padding: '6px 10px', borderRadius: 'var(--radius-sm)',
        }}>
          ← Back
        </button>
        <div>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Properties</p>
          <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-text)', margin: 0 }}>Add Property</h1>
        </div>
      </div>

      {/* ── Error banner ─────────────────────────────────────────────────── */}
      {error && (
        <div style={{ background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.3)', color: '#f85149', padding: '10px 20px', fontSize: 'var(--text-sm)' }}>
          {error}
        </div>
      )}

      {/* ── Content ─────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflow: 'auto', padding: 'var(--space-6) var(--space-5)', maxWidth: 720 }}>

        {/* Section A — Core Identity */}
        <div style={sectionHead}>Core Identity</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <Field label="Property ID" hint="Auto-generated — cannot be changed">
            <input
              style={{ ...inputStyle, fontWeight: 700, color: 'var(--color-text)', background: 'var(--color-surface-3)', cursor: 'not-allowed' }}
              value={idLoading ? 'Loading…' : propertyId}
              readOnly
            />
          </Field>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
            <Field label="Display Name">
              <input style={inputStyle} value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="Villa Sunset 3BR" />
            </Field>
            <Field label="Property Type">
              <select style={{ ...inputStyle, cursor: 'pointer' }} value={propertyType} onChange={e => setPropertyType(e.target.value)}>
                <option value="">— Select type —</option>
                {PROPERTY_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
              </select>
            </Field>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
            <Field label="Timezone">
              <select style={{ ...inputStyle, cursor: 'pointer' }} value={timezone} onChange={e => setTimezone(e.target.value)}>
                {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
              </select>
            </Field>
            <Field label="Base Currency">
              <select style={{ ...inputStyle, cursor: 'pointer' }} value={currency} onChange={e => setCurrency(e.target.value)}>
                {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </Field>
          </div>
        </div>

        {/* Section B — Location & Capacity */}
        <div style={sectionHead}>Location &amp; Capacity</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
            <Field label="City">
              <input style={inputStyle} value={city} onChange={e => setCity(e.target.value)} placeholder="Koh Samui" />
            </Field>
            <Field label="Country">
              <input style={inputStyle} value={country} onChange={e => setCountry(e.target.value)} placeholder="TH" />
            </Field>
          </div>

          <Field label="Address">
            <textarea style={{ ...inputStyle, resize: 'vertical', minHeight: 64 }} value={address} onChange={e => setAddress(e.target.value)} placeholder="Full address" />
          </Field>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 'var(--space-3)', alignItems: 'end' }}>
            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 4 }}>Latitude</div>
              <input style={inputStyle} value={lat} onChange={e => setLat(e.target.value)} placeholder="9.527476" type="number" step="any" />
            </div>
            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginBottom: 4 }}>Longitude</div>
              <input style={inputStyle} value={lng} onChange={e => setLng(e.target.value)} placeholder="100.062256" type="number" step="any" />
            </div>
            <button
              onClick={() => {
                if (!navigator.geolocation) { setGeoStatus('err'); return; }
                setGeoStatus('loading');
                navigator.geolocation.getCurrentPosition(
                  pos => {
                    setLat(String(pos.coords.latitude));
                    setLng(String(pos.coords.longitude));
                    setGeoStatus('ok');
                    setTimeout(() => setGeoStatus('idle'), 4000);
                  },
                  () => { setGeoStatus('err'); setTimeout(() => setGeoStatus('idle'), 4000); },
                  { enableHighAccuracy: true, timeout: 10000 }
                );
              }}
              disabled={geoStatus === 'loading'}
              style={{
                padding: '9px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)',
                background: geoStatus === 'ok' ? 'rgba(34,197,94,0.15)' : geoStatus === 'err' ? 'rgba(248,81,73,0.1)' : 'var(--color-surface-2)',
                color: geoStatus === 'ok' ? '#22c55e' : geoStatus === 'err' ? '#f85149' : 'var(--color-text-dim)',
                fontSize: 'var(--text-xs)', fontWeight: 600, cursor: geoStatus === 'loading' ? 'wait' : 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {geoStatus === 'loading' ? '⏳ Locating…' : geoStatus === 'ok' ? '✓ Location saved' : geoStatus === 'err' ? '✕ Access denied' : '📍 Use Current Location'}
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-3)' }}>
            <Field label="Bedrooms">
              <input style={inputStyle} value={bedrooms} onChange={e => setBedrooms(e.target.value)} placeholder="3" type="number" min="0" step="1" />
            </Field>
            <Field label="Beds">
              <input style={inputStyle} value={beds} onChange={e => setBeds(e.target.value)} placeholder="4" type="number" min="0" step="1" />
            </Field>
            <Field label="Bathrooms">
              <input style={inputStyle} value={bathrooms} onChange={e => setBathrooms(e.target.value)} placeholder="2" type="number" min="0" step="1" />
            </Field>
            <Field label="Max Guests">
              <input style={inputStyle} value={maxGuests} onChange={e => setMaxGuests(e.target.value)} placeholder="8" type="number" min="1" step="1" />
            </Field>
          </div>
        </div>

        {/* Section C — Operation */}
        <div style={sectionHead}>Operation</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
            <Field label="Check-in Time">
              <input style={inputStyle} value={checkinTime} onChange={e => setCheckinTime(e.target.value)} type="time" />
            </Field>
            <Field label="Check-out Time">
              <input style={inputStyle} value={checkoutTime} onChange={e => setCheckoutTime(e.target.value)} type="time" />
            </Field>
          </div>

          <Field label="Description">
            <textarea style={{ ...inputStyle, resize: 'vertical', minHeight: 88 }} value={description} onChange={e => setDescription(e.target.value)} placeholder="Short description visible to guests and staff" />
          </Field>

          <Field label="Listing URL" hint="Airbnb / VRBO / Booking.com URL — click Fetch to auto-fill fields">
            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
              <input style={{ ...inputStyle, flex: 1 }} value={sourceUrl} onChange={e => setSourceUrl(e.target.value)} placeholder="https://airbnb.com/rooms/..." />
              <button
                onClick={handlePull}
                disabled={fetchStatus === 'loading' || !sourceUrl.trim()}
                style={{
                  padding: '9px 18px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)',
                  background: fetchStatus === 'done' ? 'rgba(34,197,94,0.15)' : 'var(--color-surface-2)',
                  color: fetchStatus === 'done' ? '#22c55e' : 'var(--color-text)',
                  fontSize: 'var(--text-sm)', fontWeight: 700, cursor: fetchStatus === 'loading' ? 'wait' : 'pointer',
                  whiteSpace: 'nowrap', flexShrink: 0,
                }}
              >
                {fetchStatus === 'loading' ? '⏳ Fetching…' : fetchStatus === 'done' ? '✓ Fetched' : '↓ Fetch'}
              </button>
            </div>
          </Field>
          {pullResult && (
            <div style={{
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)', padding: 'var(--space-3)', fontSize: 'var(--text-xs)',
              color: 'var(--color-text-dim)', marginTop: 'var(--space-2)',
            }}>
              {pullResult.warning && <div style={{ color: 'var(--color-warn)', marginBottom: 6 }}>⚠ {pullResult.warning}</div>}
              {pullResult.imported && Object.keys(pullResult.imported).length > 0 && (
                <div style={{ marginBottom: 4 }}>✅ Imported: {Object.keys(pullResult.imported).join(', ')}</div>
              )}
              {pullResult.could_not_import && pullResult.could_not_import.length > 0 && (
                <div>⬚ Could not import: {pullResult.could_not_import.join(', ')}</div>
              )}
              {pullResult.error && <div style={{ color: 'var(--color-danger)' }}>❌ {pullResult.error}</div>}
            </div>
          )}
        </div>

        {/* Section D — Fetched Photos (Phase 844) */}
        {fetchedPhotos.length > 0 && (
          <>
            <div style={sectionHead}>📷 Fetched Photos ({fetchedPhotos.length})</div>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
              gap: 'var(--space-2)',
            }}>
              {fetchedPhotos.map((url, i) => (
                <div key={i} style={{
                  position: 'relative', borderRadius: 'var(--radius-sm)', overflow: 'hidden',
                  border: '1px solid var(--color-border)', aspectRatio: '4/3',
                }}>
                  <img
                    src={url}
                    alt={`Photo ${i + 1}`}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                  <span style={{
                    position: 'absolute', bottom: 4, right: 6,
                    fontSize: 'var(--text-xs)', color: '#fff', background: 'rgba(0,0,0,0.5)',
                    padding: '1px 6px', borderRadius: 'var(--radius-sm)',
                  }}>{i + 1}</span>
                </div>
              ))}
            </div>
            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-1)' }}>
              These photos will be saved as gallery photos after you create the property.
            </p>
          </>
        )}

        {/* Section E — Deposit (Phase 844) */}
        <div style={sectionHead}>Deposit</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <button
              onClick={() => setDepositRequired(v => !v)}
              style={{
                position: 'relative', width: 44, height: 24, borderRadius: 12,
                background: depositRequired ? 'var(--color-primary)' : 'var(--color-border)',
                border: 'none', cursor: 'pointer', transition: 'background 0.2s', flexShrink: 0,
              }}
            >
              <span style={{
                position: 'absolute', top: 3, left: depositRequired ? 22 : 3,
                width: 18, height: 18, borderRadius: '50%', background: '#fff',
                transition: 'left 0.2s', display: 'block',
              }} />
            </button>
            <div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>
                {depositRequired ? 'Deposit Required' : 'Deposit Not Required'}
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)' }}>
                Workers will be prompted to collect a deposit during check-in when enabled
              </div>
            </div>
          </div>
          {depositRequired && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--space-3)' }}>
              <Field label="Deposit Amount">
                <input style={inputStyle} value={depositAmount} onChange={e => setDepositAmount(e.target.value)} type="number" min="0" step="1" placeholder="e.g. 5000" />
              </Field>
              <Field label="Currency">
                <select style={{ ...inputStyle, cursor: 'pointer', minWidth: 90 }} value={depositCurrency} onChange={e => setDepositCurrency(e.target.value)}>
                  {['THB','USD','EUR','GBP','SGD','AUD','HKD','JPY','AED'].map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
            </div>
          )}
        </div>
      </div>

      {/* ── Sticky footer ───────────────────────────────────────────────── */}
      <div style={{
        position: 'sticky', bottom: 0,
        background: 'var(--color-surface)', borderTop: '1px solid var(--color-border)',
        padding: 'var(--space-3) var(--space-5)',
        display: 'flex', justifyContent: 'flex-end', alignItems: 'center',
      }}>
        <button
          onClick={handleCreate}
          disabled={saving || idLoading}
          style={{
            padding: '10px 28px', borderRadius: 'var(--radius-md)',
            background: saving || idLoading ? 'var(--color-border)' : 'var(--color-primary)',
            color: '#fff', border: 'none',
            cursor: saving || idLoading ? 'not-allowed' : 'pointer',
            fontWeight: 700, fontSize: 'var(--text-sm)',
            boxShadow: saving || idLoading ? 'none' : '0 2px 12px rgba(99,102,241,0.4)',
            transition: 'all 0.15s',
          }}
        >
          {saving ? 'Creating…' : '+ Create Property'}
        </button>
      </div>
    </div>
  );
}
