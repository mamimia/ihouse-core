'use client';

/**
 * Phase 1016 — Self Check-in Guest Portal
 * Route: /self-checkin/[token]
 *
 * Standalone, unauthenticated page. Works on mobile.
 * Token is embedded in the URL — no login required.
 *
 * Flow:
 *   1. Load: GET /self-checkin/{token} — fetch step status + arrival guide
 *   2. Pre-access steps: Guest completes all Gate 1 requirements
 *   3. Time gate: if check-in time not yet reached, show countdown
 *   4. Complete: POST /self-checkin/{token}/complete — get access code + post-entry list
 *   5. Post-entry: guest submits Gate 2 items at their own pace
 *   6. Portal continuity: deep link to main Guest Portal when complete
 *
 * Invariant: Access code is NEVER shown until all gate-1 steps pass + time gate clears.
 */

import { useState, useEffect, useCallback } from 'react';

// ---------------------------------------------------------------------------
// API helpers (no auth token required for self-checkin portal)
// ---------------------------------------------------------------------------

const BASE_URL =
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

async function scFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const resp = await fetch(`${BASE_URL}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(init?.headers as Record<string, string>),
        },
    });
    const json = await resp.json().catch(() => ({}));
    if (!resp.ok) throw { status: resp.status, body: json };
    return json as T;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Step {
    key: string;
    label: string;
    instruction?: string;
    required: boolean;
    completed: boolean;
    completed_at?: string;
}

interface ArrivalGuide {
    entry_instructions?: string;
    on_arrival_what_to_do?: string;
    electricity_instructions?: string;
    key_locations?: string;
    emergency_contact?: string;
}

interface PortalState {
    booking_id: string;
    property_name: string;
    guest_name: string;
    check_in: string;
    check_out: string;
    self_checkin_status: string;
    time_gate_open: boolean;
    check_in_time: string | null;
    pre_access: { steps: Step[]; all_complete: boolean };
    post_entry: { steps: Step[] };
    arrival_guide: ArrivalGuide | null;
    departure_info: Record<string, any> | null;
    portal_continuity: { guest_portal_available: boolean; guest_portal_url: string | null };
}

interface CompletionResult {
    status: string;
    access_released: boolean;
    access_code: string | null;
    access_instructions: string | null;
    property_address: string | null;
    arrival_guide: ArrivalGuide | null;
    post_entry_steps: Step[];
    guest_portal_url: string | null;
    message: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STEP_LABELS: Record<string, string> = {
    id_photo: 'Upload ID Photo',
    selfie: 'Take a Selfie',
    agreement: 'Accept House Rules',
    deposit: 'Acknowledge Deposit',
    electricity_meter: 'Record Electricity Meter',
    arrival_photos: 'Take Arrival Photos',
};

const STEP_ICONS: Record<string, string> = {
    id_photo: '🪪',
    selfie: '🤳',
    agreement: '📋',
    deposit: '💳',
    electricity_meter: '⚡',
    arrival_photos: '📷',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ProgressBar({ current, total }: { current: number; total: number }) {
    const pct = total === 0 ? 0 : Math.round((current / total) * 100);
    return (
        <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
                <span>{current} of {total} steps complete</span>
                <span>{pct}%</span>
            </div>
            <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
                <div style={{
                    height: '100%', width: `${pct}%`,
                    background: pct === 100 ? 'linear-gradient(90deg,#10b981,#059669)' : 'linear-gradient(90deg,#6366f1,#8b5cf6)',
                    borderRadius: 3, transition: 'width 0.4s ease',
                }} />
            </div>
        </div>
    );
}

function StepCard({ step, onComplete }: { step: Step; onComplete: (key: string, payload: any) => Promise<void> }) {
    const [expanded, setExpanded] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [photoData, setPhotoData] = useState<string | null>(null);
    const [checked, setChecked] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => setPhotoData(reader.result as string);
        reader.readAsDataURL(file);
    };

    const handleSubmit = async () => {
        setSubmitting(true);
        setError(null);
        try {
            const payload: Record<string, any> = { completed: true };
            if (photoData) payload.photo_data = photoData;
            if (checked) payload.accepted = true;
            await onComplete(step.key, payload);
        } catch (err: any) {
            setError(err?.body?.detail || 'Failed to submit step. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    const needsPhoto = ['id_photo', 'selfie', 'electricity_meter', 'arrival_photos'].includes(step.key);
    const needsCheckbox = ['agreement', 'deposit'].includes(step.key);
    const canSubmit = !needsPhoto || photoData ? (!needsCheckbox || checked) : false;

    return (
        <div style={{
            background: step.completed
                ? 'rgba(16,185,129,0.08)'
                : expanded
                ? 'rgba(99,102,241,0.1)'
                : 'rgba(255,255,255,0.04)',
            border: `1px solid ${step.completed ? 'rgba(16,185,129,0.3)' : expanded ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.08)'}`,
            borderRadius: 12,
            padding: 16,
            cursor: step.completed ? 'default' : 'pointer',
            transition: 'all 0.2s ease',
        }}
            onClick={() => !step.completed && setExpanded(!expanded)}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                    width: 36, height: 36, borderRadius: '50%', display: 'flex',
                    alignItems: 'center', justifyContent: 'center', fontSize: 18,
                    background: step.completed ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.06)',
                    border: `1px solid ${step.completed ? 'rgba(16,185,129,0.4)' : 'rgba(255,255,255,0.1)'}`,
                    flexShrink: 0,
                }}>
                    {step.completed ? '✓' : (STEP_ICONS[step.key] ?? '○')}
                </div>
                <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: step.completed ? '#34d399' : '#f1f5f9' }}>
                        {STEP_LABELS[step.key] ?? step.label}
                    </div>
                    {step.instruction && !expanded && !step.completed && (
                        <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
                            {step.instruction.slice(0, 60)}{step.instruction.length > 60 ? '…' : ''}
                        </div>
                    )}
                    {step.completed && step.completed_at && (
                        <div style={{ fontSize: 11, color: '#34d399', marginTop: 2 }}>
                            Completed ✓
                        </div>
                    )}
                </div>
                {!step.completed && (
                    <span style={{ fontSize: 12, color: '#64748b' }}>{expanded ? '▲' : '▼'}</span>
                )}
            </div>

            {expanded && !step.completed && (
                <div style={{ marginTop: 14, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 14 }}
                    onClick={e => e.stopPropagation()}
                >
                    {step.instruction && (
                        <p style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 12, lineHeight: 1.6 }}>
                            {step.instruction}
                        </p>
                    )}

                    {needsPhoto && (
                        <div style={{ marginBottom: 12 }}>
                            <input
                                type="file"
                                accept="image/*"
                                capture="environment"
                                onChange={handleFileChange}
                                style={{ display: 'none' }}
                                id={`file-${step.key}`}
                            />
                            <label htmlFor={`file-${step.key}`} style={{
                                display: 'flex', alignItems: 'center', gap: 8,
                                padding: '10px 16px', borderRadius: 8, cursor: 'pointer',
                                background: 'rgba(99,102,241,0.15)', border: '1px dashed rgba(99,102,241,0.4)',
                                color: '#a5b4fc', fontSize: 13, fontWeight: 500,
                            }}>
                                📷 {photoData ? 'Photo ready ✓' : 'Take / Upload Photo'}
                            </label>
                            {photoData && (
                                <img src={photoData} alt="Preview" style={{
                                    marginTop: 8, width: '100%', maxHeight: 180,
                                    objectFit: 'cover', borderRadius: 8,
                                }} />
                            )}
                        </div>
                    )}

                    {needsCheckbox && (
                        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer', marginBottom: 12 }}>
                            <input
                                type="checkbox"
                                checked={checked}
                                onChange={e => setChecked(e.target.checked)}
                                style={{ width: 18, height: 18, marginTop: 1, accentColor: '#6366f1', flexShrink: 0 }}
                            />
                            <span style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.5 }}>
                                {step.key === 'agreement'
                                    ? 'I have read and agree to the house rules and terms of stay.'
                                    : 'I acknowledge the deposit terms and understand the conditions.'}
                            </span>
                        </label>
                    )}

                    {error && (
                        <div style={{
                            background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                            borderRadius: 8, padding: '8px 12px', fontSize: 12,
                            color: '#fca5a5', marginBottom: 10,
                        }}>
                            {error}
                        </div>
                    )}

                    <button
                        onClick={handleSubmit}
                        disabled={submitting || !canSubmit}
                        style={{
                            width: '100%', padding: '12px', borderRadius: 10, fontSize: 14,
                            fontWeight: 700, border: 'none', cursor: submitting || !canSubmit ? 'not-allowed' : 'pointer',
                            background: submitting || !canSubmit
                                ? 'rgba(99,102,241,0.3)'
                                : 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                            color: 'white', transition: 'opacity 0.2s',
                        }}
                    >
                        {submitting ? 'Submitting…' : 'Mark Complete'}
                    </button>
                </div>
            )}
        </div>
    );
}

function ArrivalGuideBlock({ guide, label = 'Arrival Guide' }: { guide: ArrivalGuide; label?: string }) {
    const sections = [
        { key: 'entry_instructions', title: '🚪 Entry Instructions' },
        { key: 'on_arrival_what_to_do', title: '📋 On Arrival' },
        { key: 'electricity_instructions', title: '⚡ Electricity & Utilities' },
        { key: 'key_locations', title: '🔑 Key Locations' },
        { key: 'emergency_contact', title: '🆘 Emergency Contact' },
    ];

    const filled = sections.filter(s => (guide as any)[s.key]);
    if (filled.length === 0) return null;

    return (
        <div style={{
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 12, padding: 16, marginTop: 16,
        }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 12px' }}>
                {label}
            </h3>
            {filled.map(s => (
                <div key={s.key} style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>{s.title}</div>
                    <div style={{ fontSize: 13, color: '#94a3b8', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                        {(guide as any)[s.key]}
                    </div>
                </div>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function SelfCheckinPortalPage({ params }: { params: { token: string } }) {
    const token = params.token;

    const [loading, setLoading] = useState(true);
    const [state, setState] = useState<PortalState | null>(null);
    const [completion, setCompletion] = useState<CompletionResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [completing, setCompleting] = useState(false);
    const [view, setView] = useState<'steps' | 'access' | 'post-entry'>('steps');

    // Time gate countdown
    const [timeLeft, setTimeLeft] = useState<number | null>(null);

    const load = useCallback(async () => {
        try {
            const data = await scFetch<PortalState>(`/self-checkin/${token}`);
            setState(data);

            // If already access_released, try to load completion
            if (['access_released', 'completed', 'followup_required'].includes(data.self_checkin_status)) {
                setView('access');
            }
        } catch (err: any) {
            const detail = err?.body?.detail || 'Something went wrong. Please check the link and try again.';
            setError(detail);
        } finally {
            setLoading(false);
        }
    }, [token]);

    useEffect(() => { load(); }, [load]);

    // Time gate countdown
    useEffect(() => {
        if (!state?.check_in_time || state.time_gate_open) {
            setTimeLeft(null);
            return;
        }
        const update = () => {
            const ms = new Date(state.check_in_time!).getTime() - Date.now();
            setTimeLeft(ms > 0 ? ms : 0);
        };
        update();
        const t = setInterval(update, 60000);
        return () => clearInterval(t);
    }, [state?.check_in_time, state?.time_gate_open]);

    const handleComplete = async () => {
        if (!state) return;
        setCompleting(true);
        setError(null);
        try {
            const result = await scFetch<CompletionResult>(`/self-checkin/${token}/complete`, { method: 'POST' });
            setCompletion(result);
            setView('access');
        } catch (err: any) {
            const detail = err?.body?.detail || err?.body?.code || 'Could not release access. Please try again or contact support.';
            setError(detail);
        } finally {
            setCompleting(false);
        }
    };

    const handlePostEntry = async (stepKey: string, payload: any) => {
        await scFetch(`/self-checkin/${token}/post-entry/${stepKey}`, {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        // Reload to get updated step state
        await load();
    };

    // ---------------------------------------------------------------------------
    // Render: loading
    // ---------------------------------------------------------------------------
    if (loading) {
        return (
            <div style={containerStyle}>
                <div style={cardStyle}>
                    <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>
                        <div style={{ fontSize: 40, marginBottom: 16, animation: 'spin 1s linear infinite' }}>⏳</div>
                        <p style={{ fontSize: 15 }}>Loading your check-in…</p>
                    </div>
                </div>
            </div>
        );
    }

    // ---------------------------------------------------------------------------
    // Render: error
    // ---------------------------------------------------------------------------
    if (error && !state) {
        return (
            <div style={containerStyle}>
                <div style={cardStyle}>
                    <div style={{ textAlign: 'center', padding: 32 }}>
                        <div style={{ fontSize: 48, marginBottom: 16 }}>🔒</div>
                        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9', marginBottom: 8 }}>
                            Link Unavailable
                        </h1>
                        <p style={{ fontSize: 14, color: '#94a3b8', lineHeight: 1.7, marginBottom: 20 }}>
                            {error}
                        </p>
                        <p style={{ fontSize: 12, color: '#64748b' }}>
                            If you believe this is an error, please contact your property host.
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    if (!state) return null;

    const allPreAccessDone = state.pre_access.all_complete;
    const timeGateOpen = state.time_gate_open;
    const canComplete = allPreAccessDone && timeGateOpen;

    const doneCount = state.pre_access.steps.filter(s => s.completed).length;
    const totalCount = state.pre_access.steps.length;

    const formatTimeLeft = (ms: number) => {
        const h = Math.floor(ms / 3600000);
        const m = Math.floor((ms % 3600000) / 60000);
        if (h > 0) return `${h}h ${m}m`;
        return `${m} minutes`;
    };

    const fmtDate = (d: string) => {
        try {
            return new Date(d).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
        } catch { return d; }
    };

    // ---------------------------------------------------------------------------
    // Render: access released (post-completion view)
    // ---------------------------------------------------------------------------
    if (view === 'access') {
        const guide = completion?.arrival_guide || state.arrival_guide;
        const postSteps = completion?.post_entry_steps || state.post_entry.steps;
        return (
            <div style={containerStyle}>
                <div style={cardStyle}>
                    <div style={{ textAlign: 'center', marginBottom: 24 }}>
                        <div style={{ fontSize: 52, marginBottom: 8 }}>🟢</div>
                        <h1 style={{ fontSize: 22, fontWeight: 800, color: '#34d399', margin: 0 }}>
                            You're checked in!
                        </h1>
                        <p style={{ fontSize: 14, color: '#94a3b8', marginTop: 6 }}>
                            Welcome to {state.property_name}
                        </p>
                    </div>

                    {/* Access code */}
                    {completion?.access_code && (
                        <div style={{
                            background: 'linear-gradient(135deg,rgba(16,185,129,0.15),rgba(5,150,105,0.1))',
                            border: '1px solid rgba(16,185,129,0.4)',
                            borderRadius: 12, padding: 20, marginBottom: 20, textAlign: 'center',
                        }}>
                            <div style={{ fontSize: 11, fontWeight: 700, color: '#34d399', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
                                Entry Code
                            </div>
                            <div style={{ fontSize: 36, fontWeight: 900, color: '#ffffff', fontFamily: 'monospace', letterSpacing: '0.12em' }}>
                                {completion.access_code}
                            </div>
                            {completion.access_instructions && (
                                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 8 }}>
                                    {completion.access_instructions}
                                </div>
                            )}
                        </div>
                    )}

                    {completion?.property_address && (
                        <div style={{
                            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: 10, padding: 12, marginBottom: 16, fontSize: 13, color: '#cbd5e1',
                        }}>
                            📍 {completion.property_address}
                        </div>
                    )}

                    {/* Arrival guide */}
                    {guide && <ArrivalGuideBlock guide={guide} />}

                    {/* Post-entry steps */}
                    {postSteps.length > 0 && (
                        <div style={{ marginTop: 24 }}>
                            <h3 style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
                                After You Arrive
                            </h3>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                                {postSteps.map(step => (
                                    <StepCard key={step.key} step={step} onComplete={handlePostEntry} />
                                ))}
                            </div>
                            <p style={{ fontSize: 12, color: '#64748b', marginTop: 10, textAlign: 'center' }}>
                                These steps don't block your entry — complete them when ready.
                            </p>
                        </div>
                    )}

                    {/* Guest portal continuity */}
                    {(completion?.guest_portal_url || state.portal_continuity.guest_portal_url) && (
                        <div style={{
                            marginTop: 24, padding: 16, background: 'rgba(99,102,241,0.1)',
                            border: '1px solid rgba(99,102,241,0.3)', borderRadius: 12, textAlign: 'center',
                        }}>
                            <p style={{ fontSize: 13, color: '#a5b4fc', marginBottom: 12 }}>
                                Access all your stay details, messages, and requests in the Guest Portal.
                            </p>
                            <a
                                href={completion?.guest_portal_url ?? state.portal_continuity.guest_portal_url!}
                                style={{
                                    display: 'block', padding: '12px 24px', borderRadius: 10,
                                    background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                                    color: 'white', fontWeight: 700, fontSize: 14,
                                    textDecoration: 'none', transition: 'opacity 0.2s',
                                }}
                            >
                                Open Guest Portal →
                            </a>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // ---------------------------------------------------------------------------
    // Render: main pre-access step flow
    // ---------------------------------------------------------------------------

    return (
        <div style={containerStyle}>
            <div style={cardStyle}>
                {/* Header */}
                <div style={{ textAlign: 'center', marginBottom: 28 }}>
                    <div style={{ fontSize: 36, marginBottom: 8 }}>🏡</div>
                    <h1 style={{ fontSize: 20, fontWeight: 800, color: '#f1f5f9', margin: '0 0 4px' }}>
                        Welcome, {state.guest_name}
                    </h1>
                    <p style={{ fontSize: 14, color: '#94a3b8', margin: 0 }}>
                        {state.property_name}
                    </p>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 10, fontSize: 12, color: '#64748b' }}>
                        <span>📅 {fmtDate(state.check_in)}</span>
                        <span>→</span>
                        <span>{fmtDate(state.check_out)}</span>
                    </div>
                </div>

                {/* Progress */}
                {totalCount > 0 && (
                    <ProgressBar current={doneCount} total={totalCount} />
                )}

                {/* Error message */}
                {error && (
                    <div style={{
                        background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                        borderRadius: 10, padding: '10px 14px', fontSize: 13, color: '#fca5a5',
                        marginBottom: 16, lineHeight: 1.5,
                    }}>
                        {error}
                    </div>
                )}

                {/* Time gate warning */}
                {allPreAccessDone && !timeGateOpen && timeLeft !== null && (
                    <div style={{
                        background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)',
                        borderRadius: 10, padding: '14px', fontSize: 13, color: '#fbbf24',
                        marginBottom: 16, textAlign: 'center', lineHeight: 1.6,
                    }}>
                        <div style={{ fontSize: 24, marginBottom: 6 }}>⏰</div>
                        <strong>Almost ready!</strong> Your check-in time is at{' '}
                        {state.check_in_time ? new Date(state.check_in_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : 'the official check-in time'}.
                        {timeLeft > 0 && (
                            <div style={{ marginTop: 4, color: '#f59e0b' }}>
                                Access will be available in approximately {formatTimeLeft(timeLeft)}.
                            </div>
                        )}
                        <div style={{ marginTop: 8, fontSize: 12, color: '#92400e' }}>
                            You've completed all required steps — hang tight!
                        </div>
                    </div>
                )}

                {/* Pre-access steps */}
                {state.pre_access.steps.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
                        {state.pre_access.steps.map(step => (
                            <StepCard
                                key={step.key}
                                step={step}
                                onComplete={async (key, payload) => {
                                    await scFetch(`/self-checkin/${token}/step/${key}`, {
                                        method: 'POST',
                                        body: JSON.stringify(payload),
                                    });
                                    await load();
                                }}
                            />
                        ))}
                    </div>
                )}

                {/* Arrival guide teaser (before access released) */}
                {state.arrival_guide && (
                    <ArrivalGuideBlock guide={state.arrival_guide} label="Property Information" />
                )}

                {/* Check-in button */}
                <div style={{ marginTop: 24 }}>
                    <button
                        id="btn-sc-complete"
                        onClick={handleComplete}
                        disabled={!canComplete || completing}
                        style={{
                            width: '100%', padding: '16px', borderRadius: 12, fontSize: 16,
                            fontWeight: 800, border: 'none',
                            cursor: !canComplete || completing ? 'not-allowed' : 'pointer',
                            background: canComplete && !completing
                                ? 'linear-gradient(135deg,#6366f1,#8b5cf6)'
                                : 'rgba(99,102,241,0.25)',
                            color: canComplete ? 'white' : '#6366f1',
                            boxShadow: canComplete ? '0 4px 20px rgba(99,102,241,0.4)' : 'none',
                            transition: 'all 0.3s ease',
                        }}
                    >
                        {completing ? 'Getting your access…' : canComplete ? '🔓 Get Access Code' : '⏳ Complete Steps Above'}
                    </button>

                    {!allPreAccessDone && (
                        <p style={{ textAlign: 'center', fontSize: 12, color: '#64748b', marginTop: 10 }}>
                            Complete all required steps above to unlock your access code.
                        </p>
                    )}
                </div>

                {/* Guest portal link if already available */}
                {state.portal_continuity.guest_portal_url && (
                    <div style={{ textAlign: 'center', marginTop: 16 }}>
                        <a href={state.portal_continuity.guest_portal_url} style={{ fontSize: 12, color: '#6366f1', textDecoration: 'none' }}>
                            View guest portal →
                        </a>
                    </div>
                )}

                {/* Footer note */}
                <p style={{ textAlign: 'center', fontSize: 11, color: '#475569', marginTop: 24, lineHeight: 1.6 }}>
                    This link is private and unique to your booking.
                    <br />Do not share it. Valid for your check-in period only.
                </p>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const containerStyle: React.CSSProperties = {
    minHeight: '100dvh',
    background: 'linear-gradient(160deg,#0f172a 0%,#1e1b4b 50%,#0f172a 100%)',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    padding: '24px 16px 48px',
    fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
};

const cardStyle: React.CSSProperties = {
    width: '100%',
    maxWidth: 480,
    background: 'rgba(255,255,255,0.03)',
    backdropFilter: 'blur(20px)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 20,
    padding: 24,
    boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
};
