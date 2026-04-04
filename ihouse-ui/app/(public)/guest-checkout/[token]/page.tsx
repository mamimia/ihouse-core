'use client';

/**
 * Phase 1065B — Guest Self Checkout Wizard
 * Route: /guest-checkout/[token]
 *
 * Standalone, unauthenticated. Works on mobile.
 * Token is a GUEST_CHECKOUT token embedded in the URL.
 *
 * Flow:
 *   1. Load: GET /guest-checkout/{token}  — fetch portal state
 *   2. Step-by-step wizard:
 *        Step 1 — Ready to leave (confirm departure + framing)
 *        Step 2 — AC, lights, appliances
 *        Step 3 — Doors & windows locked
 *        Step 4 — Keys & access cards returned (with key method)
 *        Step 5 — Proof photo helper (optional, reference check-in photos)
 *        Step 6 — Follow-up contact (phone/email)
 *        Step 7 — Optional feedback
 *   3. Final confirm → POST /guest-checkout/{token}/complete
 *   4. Summary screen: exact timestamp, what was confirmed, pending items
 *
 * Principles:
 *   - Keep it simple. Guest is leaving, not doing admin work.
 *   - Financial honesty: never pretend deposit/meter is final.
 *   - Proof photos: optional helper, not an evidence workflow.
 *   - Contact: required for post-checkout follow-up path.
 *   - OM sees the full closure summary in the stay chat thread.
 */

import { useState, useEffect, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Constants & Styles
// ---------------------------------------------------------------------------

const BG       = 'linear-gradient(160deg,#0f172a 0%,#1e1b4b 50%,#0f172a 100%)';
const CARD_BG  = 'rgba(255,255,255,0.03)';
const BORDER   = 'rgba(255,255,255,0.08)';
const SURFACE  = 'rgba(255,255,255,0.06)';
const ACCENT   = '#6366f1';
const SUCCESS  = '#10b981';
const WARN     = 'rgba(245,158,11,0.1)';
const WARN_BR  = 'rgba(245,158,11,0.4)';
const WARN_TXT = '#f59e0b';
const FAINT    = '#475569';
const TEXT     = '#f1f5f9';
const MUTED    = '#94a3b8';
const RADIUS   = 14;
const BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

const containerStyle: React.CSSProperties = {
    minHeight: '100dvh',
    background: BG,
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    padding: '24px 16px 64px',
    fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
};

const cardStyle: React.CSSProperties = {
    width: '100%',
    maxWidth: 480,
    background: CARD_BG,
    backdropFilter: 'blur(20px)',
    border: `1px solid ${BORDER}`,
    borderRadius: 20,
    padding: 24,
    boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CheckinPhoto { url: string; caption?: string; }

interface PortalBooking {
    booking_id: string;
    guest_name: string;
    check_in: string;
    check_out: string;
    effective_checkout_date: string;
    is_early_checkout: boolean;
}

interface PortalProperty {
    name: string;
    address?: string;
    city?: string;
    checkout_time: string;
    emergency_contact?: string;
}

interface PortalStep {
    key: string;
    label: string;
    instruction: string;
    optional: boolean;
    completed: boolean;
}

interface PortalState {
    booking: PortalBooking;
    property: PortalProperty;
    steps: PortalStep[];
    steps_completed: Record<string, any>;
    required_complete: boolean;
    already_confirmed: boolean;
    confirmed_at?: string;
    checkin_photos: CheckinPhoto[];
    deposit_status: string;
    has_opening_meter: boolean;
    summary?: any;
}

interface CompletionResult {
    status: string;
    confirmed_at: string;
    guest_name: string;
    property_name: string;
    summary: any;
    pending_items: string[];
    pending_notice?: string;
    noop?: boolean;
}

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------

async function gcFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const resp = await fetch(`${BASE_URL}${path}`, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...(init?.headers as Record<string, string>) },
    });
    const json = await resp.json().catch(() => ({}));
    if (!resp.ok) throw { status: resp.status, body: json };
    return json as T;
}

// ---------------------------------------------------------------------------
// Wizard step definition (maps to backend + includes proof-photo step)
// ---------------------------------------------------------------------------

const WIZARD_STEPS = [
    { id: 'ready',         label: 'Ready to leave',         icon: '👋' },
    { id: 'ac_lights',     label: 'AC & lights',            icon: '💡' },
    { id: 'doors_locked',  label: 'Doors & windows',        icon: '🔒' },
    { id: 'key_handover',  label: 'Keys & cards',           icon: '🗝️' },
    { id: 'proof_photos',  label: 'Photo reminder',         icon: '📷' },
    { id: 'contact',       label: 'Your contact details',   icon: '📞' },
    { id: 'feedback',      label: 'Any final notes?',       icon: '💬' },
];
const TOTAL_STEPS = WIZARD_STEPS.length;

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ProgressBar({ current, total }: { current: number; total: number }) {
    const pct = total === 0 ? 0 : Math.round((current / total) * 100);
    return (
        <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: MUTED, marginBottom: 6 }}>
                <span>Step {current} of {total}</span>
                <span>{pct}%</span>
            </div>
            <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                <div style={{
                    height: '100%', width: `${pct}%`,
                    background: pct === 100 ? `linear-gradient(90deg,${SUCCESS},#059669)` : `linear-gradient(90deg,${ACCENT},#8b5cf6)`,
                    borderRadius: 2, transition: 'width 0.4s ease',
                }} />
            </div>
        </div>
    );
}

function StepHeader({ icon, title, subtitle }: { icon: string; title: string; subtitle?: string }) {
    return (
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <div style={{ fontSize: 44, marginBottom: 10 }}>{icon}</div>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: TEXT, margin: '0 0 6px' }}>{title}</h2>
            {subtitle && (
                <p style={{ fontSize: 14, color: MUTED, lineHeight: 1.6, margin: 0 }}>{subtitle}</p>
            )}
        </div>
    );
}

function NavButtons({
    onBack, onNext,
    nextLabel = 'Continue →', nextDisabled = false, submitting = false,
    backLabel = '← Back', hideBack = false,
}: {
    onBack?: () => void;
    onNext?: () => void;
    nextLabel?: string;
    nextDisabled?: boolean;
    submitting?: boolean;
    backLabel?: string;
    hideBack?: boolean;
}) {
    return (
        <div style={{ display: 'flex', gap: 10, marginTop: 28 }}>
            {!hideBack && onBack && (
                <button
                    onClick={onBack}
                    disabled={submitting}
                    style={{
                        flex: '0 0 auto', padding: '12px 18px', borderRadius: 10,
                        background: SURFACE, border: `1px solid ${BORDER}`,
                        color: MUTED, fontSize: 14, fontWeight: 600, cursor: 'pointer',
                    }}
                >{backLabel}</button>
            )}
            <button
                onClick={onNext}
                disabled={nextDisabled || submitting}
                style={{
                    flex: 1, padding: '14px 20px', borderRadius: 10,
                    background: nextDisabled || submitting ? `rgba(99,102,241,0.25)` : `linear-gradient(135deg,${ACCENT},#8b5cf6)`,
                    color: nextDisabled || submitting ? ACCENT : 'white',
                    fontSize: 15, fontWeight: 800, border: 'none', cursor: nextDisabled || submitting ? 'not-allowed' : 'pointer',
                    boxShadow: nextDisabled || submitting ? 'none' : '0 4px 20px rgba(99,102,241,0.35)',
                    transition: 'all 0.2s ease',
                }}
            >
                {submitting ? 'Saving…' : nextLabel}
            </button>
        </div>
    );
}

function CheckCard({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
    return (
        <label style={{
            display: 'flex', alignItems: 'flex-start', gap: 14, cursor: 'pointer',
            background: checked ? 'rgba(16,185,129,0.08)' : SURFACE,
            border: `1px solid ${checked ? 'rgba(16,185,129,0.35)' : BORDER}`,
            borderRadius: 10, padding: '14px 16px',
            transition: 'all 0.2s ease',
        }}>
            <input
                type="checkbox"
                checked={checked}
                onChange={e => onChange(e.target.checked)}
                style={{ width: 20, height: 20, marginTop: 1, accentColor: SUCCESS, flexShrink: 0 }}
            />
            <span style={{ fontSize: 14, color: checked ? '#34d399' : TEXT, lineHeight: 1.55, fontWeight: 500 }}>
                {label}
            </span>
        </label>
    );
}

function KeyMethodSelector({ value, onChange }: { value: string; onChange: (v: string) => void }) {
    const opts = [
        { id: 'lockbox',    label: 'Left in lockbox / key drop',     icon: '🔐' },
        { id: 'reception',  label: 'Handed to reception / front desk', icon: '🏢' },
        { id: 'staff',      label: 'Given to a staff member',         icon: '👤' },
        { id: 'host',       label: 'Returned to host directly',       icon: '🤝' },
        { id: 'confirmed',  label: 'Confirmed returned (as instructed)', icon: '✅' },
    ];
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {opts.map(o => (
                <label key={o.id} style={{
                    display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer',
                    background: value === o.id ? 'rgba(99,102,241,0.12)' : SURFACE,
                    border: `1px solid ${value === o.id ? 'rgba(99,102,241,0.4)' : BORDER}`,
                    borderRadius: 10, padding: '12px 14px', transition: 'all 0.2s ease',
                }}>
                    <input
                        type="radio"
                        name="key_method"
                        checked={value === o.id}
                        onChange={() => onChange(o.id)}
                        style={{ accentColor: ACCENT, width: 16, height: 16, flexShrink: 0 }}
                    />
                    <span style={{ fontSize: 18, flexShrink: 0 }}>{o.icon}</span>
                    <span style={{ fontSize: 14, color: value === o.id ? '#a5b4fc' : TEXT, fontWeight: 500 }}>{o.label}</span>
                </label>
            ))}
        </div>
    );
}

function ProofPhotoHelper({ photos }: { photos: CheckinPhoto[] }) {
    return (
        <div style={{
            background: WARN, border: `1px solid ${WARN_BR}`,
            borderRadius: 12, padding: 16, marginBottom: 16,
        }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ fontSize: 22, flexShrink: 0 }}>📷</span>
                <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: WARN_TXT, marginBottom: 6 }}>
                        Optional: Take general photos for your records
                    </div>
                    <div style={{ fontSize: 13, color: '#fcd34d', lineHeight: 1.6 }}>
                        If you'd like to protect yourself, you can take a few quick photos of the property
                        before you leave — for example, the living area, bedroom, and bathroom.
                        This is entirely optional and for your own peace of mind.
                    </div>
                    {photos.length > 0 && (
                        <div style={{ marginTop: 12 }}>
                            <div style={{ fontSize: 12, color: '#92400e', marginBottom: 8, fontWeight: 600 }}>
                                For reference — how it looked when you arrived:
                            </div>
                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                {photos.map((p, i) => (
                                    <div key={i} style={{ position: 'relative' }}>
                                        <img
                                            src={p.url}
                                            alt={p.caption || `Check-in photo ${i + 1}`}
                                            style={{
                                                width: 100, height: 70, objectFit: 'cover',
                                                borderRadius: 8, border: '1px solid rgba(245,158,11,0.3)',
                                            }}
                                        />
                                        {p.caption && (
                                            <div style={{ fontSize: 10, color: '#92400e', marginTop: 2, maxWidth: 100 }}>
                                                {p.caption}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                    <div style={{ fontSize: 12, color: '#92400e', marginTop: 10, lineHeight: 1.5 }}>
                        Our team will complete their own review after your departure.
                        These photos are for your records only — there's no need to submit them here.
                    </div>
                </div>
            </div>
        </div>
    );
}

function FinancialHonestyCard({ deposit_status, has_meter }: { deposit_status: string; has_meter: boolean }) {
    const hasPending = (deposit_status && !['returned', 'waived', 'na', 'n/a', 'none'].includes(deposit_status)) || has_meter;
    if (!hasPending) return null;
    return (
        <div style={{
            background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
            borderRadius: 10, padding: 14, marginBottom: 16, fontSize: 13, color: '#a5b4fc', lineHeight: 1.65,
        }}>
            <span style={{ fontWeight: 700 }}>ℹ️ Final review still ahead</span>
            <div style={{ marginTop: 6, color: '#c4b5fd' }}>
                Our team will complete a final review after your departure
                {deposit_status && !['returned', 'waived', 'na', 'n/a', 'none', 'unknown'].includes(deposit_status) && ' — including deposit reconciliation'}
                {has_meter && ' and electricity reading'}.
                They'll contact you if anything needs clarifying.
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Individual wizard step views
// ---------------------------------------------------------------------------

// Step 1: Ready to leave
function StepReady({
    booking, property, onNext,
}: {
    booking: PortalBooking;
    property: PortalProperty;
    onNext: () => void;
}) {
    const [confirmed, setConfirmed] = useState(false);
    const fmtDate = (d: string) => { try { return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }); } catch { return d; } };
    return (
        <>
            <StepHeader icon="👋" title="Ready to check out?" subtitle={`Let's wrap up your stay at ${property.name}.`} />
            <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 10, padding: 14, marginBottom: 16, fontSize: 13, color: MUTED, lineHeight: 1.7 }}>
                <div><span style={{ color: TEXT, fontWeight: 600 }}>📅 Checkout date:</span> {fmtDate(booking.effective_checkout_date)}</div>
                {booking.is_early_checkout && <div style={{ color: WARN_TXT, fontSize: 12, marginTop: 4 }}>✓ Early checkout — approved by host</div>}
                {property.checkout_time && <div style={{ marginTop: 6 }}><span style={{ color: TEXT, fontWeight: 600 }}>🕐 Checkout time:</span> {property.checkout_time}</div>}
            </div>
            <div style={{ marginBottom: 16 }}>
                <CheckCard
                    checked={confirmed}
                    onChange={setConfirmed}
                    label="I confirm that I and all guests are ready to leave and have collected all our belongings."
                />
            </div>
            <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 10, padding: 14, fontSize: 13, color: MUTED, lineHeight: 1.6 }}>
                <div style={{ fontWeight: 600, color: TEXT, marginBottom: 6 }}>We'll walk you through a short checklist.</div>
                It takes about 1–2 minutes. No forms to fill out — just a few quick taps.
            </div>
            <NavButtons hideBack onNext={onNext} nextLabel="Let's go →" nextDisabled={!confirmed} />
        </>
    );
}

// Step 2: AC & lights
function StepACLights({ onBack, onNext, submitting }: { onBack: () => void; onNext: (note?: string) => void; submitting: boolean }) {
    const [confirmed, setConfirmed] = useState(false);
    return (
        <>
            <StepHeader icon="💡" title="AC, lights & appliances" subtitle="A small habit that makes a big difference." />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
                <CheckCard checked={confirmed} onChange={setConfirmed} label="I've turned off the air conditioning, all lights, fans, and any other appliances." />
            </div>
            <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 10, padding: 14, fontSize: 12, color: MUTED, lineHeight: 1.6, marginBottom: 4 }}>
                💡 Don't forget: water heater, TV, and kitchen appliances (stove, rice cooker, etc.) if applicable.
            </div>
            <NavButtons onBack={onBack} onNext={() => onNext()} nextDisabled={!confirmed} submitting={submitting} />
        </>
    );
}

// Step 3: Doors & windows
function StepDoorsLocked({ onBack, onNext, submitting }: { onBack: () => void; onNext: () => void; submitting: boolean }) {
    const [confirmed, setConfirmed] = useState(false);
    return (
        <>
            <StepHeader icon="🔒" title="Doors & windows" subtitle="Just a quick check before you go." />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
                <CheckCard checked={confirmed} onChange={setConfirmed} label="I've checked that all doors and windows are closed and locked." />
            </div>
            <NavButtons onBack={onBack} onNext={onNext} nextDisabled={!confirmed} submitting={submitting} />
        </>
    );
}

// Step 4: Keys & cards
function StepKeyHandover({ onBack, onNext, submitting }: { onBack: () => void; onNext: (method: string) => void; submitting: boolean }) {
    const [method, setMethod] = useState('');
    return (
        <>
            <StepHeader icon="🗝️" title="Keys & access cards" subtitle="How are you returning them?" />
            <div style={{ marginBottom: 16 }}>
                <KeyMethodSelector value={method} onChange={setMethod} />
            </div>
            <NavButtons onBack={onBack} onNext={() => onNext(method)} nextDisabled={!method} submitting={submitting} />
        </>
    );
}

// Step 5: Proof photos (frontend-only, no upload, no submission)
function StepProofPhotos({ photos, onBack, onNext }: { photos: CheckinPhoto[]; onBack: () => void; onNext: () => void }) {
    return (
        <>
            <StepHeader icon="📷" title="A quick reminder" subtitle="Optional — entirely up to you." />
            <ProofPhotoHelper photos={photos} />
            <NavButtons onBack={onBack} onNext={onNext} nextLabel="Understood, continue →" />
        </>
    );
}

// Step 6: Contact details
function StepContactConfirm({
    onBack, onNext, submitting,
}: {
    onBack: () => void;
    onNext: (phone: string, email: string) => void;
    submitting: boolean;
}) {
    const [phone, setPhone] = useState('');
    const [email, setEmail] = useState('');
    const canNext = (phone.trim().length > 3 || email.trim().includes('@'));
    return (
        <>
            <StepHeader icon="📞" title="Your follow-up contact" subtitle="So we can reach you after checkout if needed." />
            <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 10, padding: 14, fontSize: 13, color: MUTED, lineHeight: 1.6, marginBottom: 16 }}>
                The team may need to contact you about deposit return, electricity settlement, or any questions after inspection.
                Your portal link expires soon, so please leave a number or email.
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
                <input
                    type="tel"
                    placeholder="Phone number (e.g. +66 81 234 5678)"
                    value={phone}
                    onChange={e => setPhone(e.target.value)}
                    style={{
                        padding: '12px 14px', borderRadius: 10, fontSize: 14,
                        background: SURFACE, border: `1px solid ${BORDER}`,
                        color: TEXT, outline: 'none',
                    }}
                />
                <input
                    type="email"
                    placeholder="Email address (optional)"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    style={{
                        padding: '12px 14px', borderRadius: 10, fontSize: 14,
                        background: SURFACE, border: `1px solid ${BORDER}`,
                        color: TEXT, outline: 'none',
                    }}
                />
            </div>
            <div style={{ fontSize: 12, color: FAINT, marginBottom: 4, lineHeight: 1.5 }}>
                At least one contact method is required. Your details are used only for follow-up on this stay.
            </div>
            <NavButtons onBack={onBack} onNext={() => onNext(phone.trim(), email.trim())} nextDisabled={!canNext} submitting={submitting} />
        </>
    );
}

// Step 7: Feedback (optional)
function StepFeedback({
    onBack, onNext, submitting,
}: {
    onBack: () => void;
    onNext: (rating: number | null, comment: string) => void;
    submitting: boolean;
}) {
    const [rating, setRating] = useState<number | null>(null);
    const [comment, setComment] = useState('');
    return (
        <>
            <StepHeader icon="💬" title="Any final thoughts?" subtitle="This is completely optional — skip if you'd prefer." />
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 16 }}>
                {[1, 2, 3, 4, 5].map(n => (
                    <button
                        key={n}
                        onClick={() => setRating(rating === n ? null : n)}
                        style={{
                            fontSize: 28, background: 'none', border: 'none', cursor: 'pointer',
                            opacity: rating !== null && n > rating ? 0.3 : 1,
                            transform: rating === n ? 'scale(1.2)' : 'scale(1)',
                            transition: 'all 0.15s ease',
                        }}
                    >⭐</button>
                ))}
            </div>
            <textarea
                placeholder="Leave a short note about your stay — your host will appreciate it."
                value={comment}
                onChange={e => setComment(e.target.value.slice(0, 500))}
                rows={4}
                style={{
                    width: '100%', padding: '12px 14px', borderRadius: 10, fontSize: 14,
                    background: SURFACE, border: `1px solid ${BORDER}`,
                    color: TEXT, outline: 'none', resize: 'vertical', lineHeight: 1.6,
                    boxSizing: 'border-box',
                }}
            />
            <div style={{ fontSize: 12, color: FAINT, marginTop: 6, textAlign: 'right' }}>{comment.length}/500</div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
                <button onClick={onBack} style={{
                    flex: '0 0 auto', padding: '12px 18px', borderRadius: 10,
                    background: SURFACE, border: `1px solid ${BORDER}`,
                    color: MUTED, fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}>← Back</button>
                <button
                    onClick={() => onNext(null, '')}
                    style={{
                        flex: '0 0 auto', padding: '12px 16px', borderRadius: 10,
                        background: 'rgba(255,255,255,0.04)', border: `1px solid ${BORDER}`,
                        color: MUTED, fontSize: 14, fontWeight: 500, cursor: 'pointer',
                    }}
                >Skip</button>
                <button
                    onClick={() => onNext(rating, comment)}
                    disabled={submitting}
                    style={{
                        flex: 1, padding: '14px 20px', borderRadius: 10,
                        background: submitting ? `rgba(99,102,241,0.25)` : `linear-gradient(135deg,${ACCENT},#8b5cf6)`,
                        color: 'white', fontSize: 15, fontWeight: 800, border: 'none',
                        cursor: submitting ? 'not-allowed' : 'pointer',
                        boxShadow: submitting ? 'none' : '0 4px 20px rgba(99,102,241,0.35)',
                    }}
                >{submitting ? 'Saving…' : 'Confirm checkout →'}</button>
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Summary screen (post-completion)
// ---------------------------------------------------------------------------

function SummaryScreen({
    result, deposit_status, has_meter,
}: {
    result: CompletionResult;
    deposit_status: string;
    has_meter: boolean;
}) {
    const fmtTimestamp = (iso: string) => {
        try {
            const d = new Date(iso);
            return d.toLocaleString('en-US', {
                weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short',
            });
        } catch { return iso; }
    };

    const steps = result.summary?.steps_confirmed || {};
    const contact = result.summary?.contact_left || {};
    const feedback = result.summary?.feedback;

    const pendingItems = result.pending_items || [];
    const hasReviewItems = pendingItems.some(p => p !== 'property_inspection');

    return (
        <div style={containerStyle}>
            <div style={cardStyle}>
                {/* Hero */}
                <div style={{ textAlign: 'center', marginBottom: 28 }}>
                    <div style={{ fontSize: 56, marginBottom: 10 }}>✅</div>
                    <h1 style={{ fontSize: 22, fontWeight: 900, color: '#34d399', margin: '0 0 6px' }}>
                        Checkout complete
                    </h1>
                    <p style={{ fontSize: 14, color: MUTED, margin: 0 }}>
                        Thank you for your stay at <span style={{ color: TEXT, fontWeight: 600 }}>{result.property_name}</span>
                    </p>
                </div>

                {/* Timestamp */}
                <div style={{
                    background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)',
                    borderRadius: 10, padding: '12px 14px', marginBottom: 16,
                }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#34d399', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>
                        Checkout recorded at
                    </div>
                    <div style={{ fontSize: 13, color: '#a7f3d0', fontFamily: 'monospace', lineHeight: 1.5 }}>
                        {fmtTimestamp(result.confirmed_at)}
                    </div>
                </div>

                {/* Confirmed checklist */}
                <div style={{
                    background: SURFACE, border: `1px solid ${BORDER}`,
                    borderRadius: 10, padding: '14px 16px', marginBottom: 14,
                }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: MUTED, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
                        You confirmed
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {steps.confirmed_departure !== undefined && (
                            <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 13, color: TEXT }}>
                                <span style={{ color: '#34d399', fontSize: 16 }}>✓</span>
                                All guests have vacated and belongings collected
                            </div>
                        )}
                        {steps.ac_lights_off !== undefined && (
                            <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 13, color: TEXT }}>
                                <span style={{ color: '#34d399', fontSize: 16 }}>✓</span>
                                AC, lights and appliances turned off
                            </div>
                        )}
                        {steps.doors_locked !== undefined && (
                            <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 13, color: TEXT }}>
                                <span style={{ color: '#34d399', fontSize: 16 }}>✓</span>
                                Doors and windows locked
                            </div>
                        )}
                        {steps.keys_returned !== undefined && (
                            <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 13, color: TEXT }}>
                                <span style={{ color: '#34d399', fontSize: 16 }}>✓</span>
                                Keys returned
                                {steps.key_method && (
                                    <span style={{ color: MUTED, fontSize: 12 }}>({steps.key_method.replace('_', ' ')})</span>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* Contact left */}
                {(contact.phone || contact.email) && (
                    <div style={{
                        background: SURFACE, border: `1px solid ${BORDER}`,
                        borderRadius: 10, padding: '12px 14px', marginBottom: 14,
                    }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: MUTED, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
                            Follow-up contact
                        </div>
                        {contact.phone && <div style={{ fontSize: 13, color: TEXT }}>📞 {contact.phone}</div>}
                        {contact.email && <div style={{ fontSize: 13, color: TEXT, marginTop: 4 }}>✉️ {contact.email}</div>}
                    </div>
                )}

                {/* Pending notice */}
                {hasReviewItems && result.pending_notice && (
                    <div style={{
                        background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
                        borderRadius: 10, padding: 14, marginBottom: 14,
                        fontSize: 13, color: '#c4b5fd', lineHeight: 1.65,
                    }}>
                        <div style={{ fontWeight: 700, color: '#a5b4fc', marginBottom: 4 }}>ℹ️ What happens next</div>
                        {result.pending_notice}
                    </div>
                )}

                {/* Feedback */}
                {feedback && (feedback.rating || feedback.comment) && (
                    <div style={{
                        background: SURFACE, border: `1px solid ${BORDER}`,
                        borderRadius: 10, padding: '12px 14px', marginBottom: 14,
                    }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: MUTED, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
                            Your feedback
                        </div>
                        {feedback.rating && (
                            <div style={{ fontSize: 16 }}>
                                {'⭐'.repeat(feedback.rating)}{'☆'.repeat(5 - feedback.rating)}
                            </div>
                        )}
                        {feedback.comment && (
                            <div style={{ fontSize: 13, color: MUTED, marginTop: 6, fontStyle: 'italic', lineHeight: 1.6 }}>
                                "{feedback.comment}"
                            </div>
                        )}
                    </div>
                )}

                {/* Farewell */}
                <div style={{ textAlign: 'center', padding: '16px 0 8px', fontSize: 14, color: MUTED, lineHeight: 1.7 }}>
                    We hope you had a wonderful stay. 🌟
                    <br />
                    <span style={{ fontSize: 12, color: FAINT }}>
                        Safe travels — we look forward to welcoming you back.
                    </span>
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function GuestCheckoutPortalPage({ params }: { params: { token: string } }) {
    const token = params.token;

    const [loading, setLoading] = useState(true);
    const [state, setState] = useState<PortalState | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [completed, setCompleted] = useState<CompletionResult | null>(null);
    const [currentStep, setCurrentStep] = useState(0);
    const [submitting, setSubmitting] = useState(false);
    const [stepError, setStepError] = useState<string | null>(null);

    const load = useCallback(async () => {
        try {
            const data = await gcFetch<PortalState>(`/guest-checkout/${token}`);
            setState(data);
            if (data.already_confirmed) {
                // Reconstruct a minimal result for summary from stored state
                setCompleted({
                    status: 'already_confirmed',
                    confirmed_at: data.confirmed_at || new Date().toISOString(),
                    guest_name: data.booking.guest_name,
                    property_name: data.property.name,
                    summary: data.summary,
                    pending_items: data.summary?.pending_items || [],
                    pending_notice: undefined,
                    noop: true,
                });
            }
        } catch (err: any) {
            const detail = err?.body?.detail || 'This checkout link is unavailable. Please check the link or contact your host.';
            setError(detail);
        } finally {
            setLoading(false);
        }
    }, [token]);

    useEffect(() => { load(); }, [load]);

    const submitStep = async (stepKey: string, payload: Record<string, any>) => {
        await gcFetch(`/guest-checkout/${token}/step/${stepKey}`, {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    };

    const handleStepAction = async (stepId: string, data: Record<string, any>, nextStep: number) => {
        setSubmitting(true);
        setStepError(null);
        try {
            if (stepId !== 'ready' && stepId !== 'proof_photos') {
                await submitStep(stepId === 'contact' ? 'contact_confirm' : stepId, data);
            }
            setCurrentStep(nextStep);
        } catch (err: any) {
            const msg = err?.body?.detail || 'Something went wrong. Please try again.';
            setStepError(msg);
        } finally {
            setSubmitting(false);
        }
    };

    const handleComplete = async (rating: number | null, comment: string) => {
        setSubmitting(true);
        setStepError(null);
        try {
            if (rating || comment) {
                await submitStep('feedback', { rating, comment });
            }
            const result = await gcFetch<CompletionResult>(`/guest-checkout/${token}/complete`, { method: 'POST' });
            setCompleted(result);
        } catch (err: any) {
            const msg = err?.body?.detail || 'Could not complete checkout. Please try again or contact your host.';
            setStepError(msg);
        } finally {
            setSubmitting(false);
        }
    };

    // ---------------------------------------------------------------------------
    // Render: loading
    // ---------------------------------------------------------------------------
    if (loading) {
        return (
            <div style={containerStyle}>
                <div style={cardStyle}>
                    <div style={{ textAlign: 'center', padding: 40, color: MUTED }}>
                        <div style={{ fontSize: 40, marginBottom: 16 }}>⏳</div>
                        <p style={{ fontSize: 15 }}>Loading your checkout…</p>
                    </div>
                </div>
            </div>
        );
    }

    // ---------------------------------------------------------------------------
    // Render: error
    // ---------------------------------------------------------------------------
    if (error || !state) {
        return (
            <div style={containerStyle}>
                <div style={cardStyle}>
                    <div style={{ textAlign: 'center', padding: 32 }}>
                        <div style={{ fontSize: 48, marginBottom: 16 }}>🔒</div>
                        <h1 style={{ fontSize: 20, fontWeight: 700, color: TEXT, marginBottom: 8 }}>Link unavailable</h1>
                        <p style={{ fontSize: 14, color: MUTED, lineHeight: 1.7 }}>{error}</p>
                        <p style={{ fontSize: 12, color: FAINT, marginTop: 12 }}>
                            If you need help, contact your host directly.
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    // ---------------------------------------------------------------------------
    // Render: already completed — show summary screen
    // ---------------------------------------------------------------------------
    if (completed) {
        return (
            <SummaryScreen
                result={completed}
                deposit_status={state.deposit_status}
                has_meter={state.has_opening_meter}
            />
        );
    }

    // ---------------------------------------------------------------------------
    // Render: wizard
    // ---------------------------------------------------------------------------
    const step = WIZARD_STEPS[currentStep];

    return (
        <div style={containerStyle}>
            <div style={cardStyle}>
                {/* Header */}
                <div style={{ textAlign: 'center', marginBottom: 20 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: FAINT, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>
                        Self Checkout
                    </div>
                    <div style={{ fontSize: 14, color: MUTED }}>{state.property.name}</div>
                </div>

                <ProgressBar current={currentStep + 1} total={TOTAL_STEPS} />

                {/* Step error */}
                {stepError && (
                    <div style={{
                        background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                        borderRadius: 10, padding: '10px 14px', fontSize: 13, color: '#fca5a5',
                        marginBottom: 16, lineHeight: 1.5,
                    }}>
                        {stepError}
                    </div>
                )}

                {/* Step views */}
                {step.id === 'ready' && (
                    <StepReady
                        booking={state.booking}
                        property={state.property}
                        onNext={() => handleStepAction('ready', { confirmed: true }, 1)}
                    />
                )}
                {step.id === 'ac_lights' && (
                    <StepACLights
                        onBack={() => setCurrentStep(s => s - 1)}
                        onNext={(note) => handleStepAction('ac_lights', { note }, 2)}
                        submitting={submitting}
                    />
                )}
                {step.id === 'doors_locked' && (
                    <StepDoorsLocked
                        onBack={() => setCurrentStep(s => s - 1)}
                        onNext={() => handleStepAction('doors_locked', {}, 3)}
                        submitting={submitting}
                    />
                )}
                {step.id === 'key_handover' && (
                    <StepKeyHandover
                        onBack={() => setCurrentStep(s => s - 1)}
                        onNext={(method) => handleStepAction('key_handover', { method }, 4)}
                        submitting={submitting}
                    />
                )}
                {step.id === 'proof_photos' && (
                    <StepProofPhotos
                        photos={state.checkin_photos || []}
                        onBack={() => setCurrentStep(s => s - 1)}
                        onNext={() => setCurrentStep(s => s + 1)}
                    />
                )}
                {step.id === 'contact' && (
                    <StepContactConfirm
                        onBack={() => setCurrentStep(s => s - 1)}
                        onNext={(phone, email) => handleStepAction('contact', { phone, email }, 6)}
                        submitting={submitting}
                    />
                )}
                {step.id === 'feedback' && (
                    <>
                        <FinancialHonestyCard deposit_status={state.deposit_status} has_meter={state.has_opening_meter} />
                        <StepFeedback
                            onBack={() => setCurrentStep(s => s - 1)}
                            onNext={handleComplete}
                            submitting={submitting}
                        />
                    </>
                )}

                {/* Footer */}
                <p style={{ textAlign: 'center', fontSize: 11, color: FAINT, marginTop: 28, lineHeight: 1.6 }}>
                    This link is private and unique to your booking.
                </p>
            </div>
        </div>
    );
}
