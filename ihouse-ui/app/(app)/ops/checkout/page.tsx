'use client';

/**
 * Operational Core — Phase D-7: Mobile Check-out Flow
 * Architecture: 4-step checkout wired to existing backend APIs:
 *   - deposit_settlement_router.py (421 lines) — deposits, deductions, settlement
 *   - booking_checkin_router.py (317 lines) — checkout state transition + audit
 *   - problem_report_router.py (382 lines) — issue flagging
 *
 * Steps: Inspection → Issue Flagging → Deposit Resolution → Complete
 */

import { useEffect, useState, useCallback } from 'react';
import { getToken } from '@/lib/api';
import BottomNav from '@/components/BottomNav';
import MobileStaffShell from '@/components/MobileStaffShell';

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

type Booking = {
    booking_id?: string; booking_ref?: string; id?: string;
    property_id: string; guest_name?: string; check_in?: string; check_out?: string;
    status?: string; guest_count?: number; nights?: number;
    deposit_amount?: number; deposit_currency?: string;
};

function getBookingId(b: Booking): string {
    return b.booking_id || b.booking_ref || b.id || 'unknown';
}

type CheckoutStep = 'list' | 'inspection' | 'issues' | 'deposit' | 'complete' | 'success';

// ========== Components ==========

function StepHeader({ step, total, title, onBack }: { step: number; total: number; title: string; onBack: () => void }) {
    return (
        <div style={{ marginBottom: 'var(--space-4)' }}>
            <button onClick={onBack} style={{
                background: 'none', border: 'none', color: 'var(--color-text-dim)',
                cursor: 'pointer', fontSize: 'var(--text-sm)', padding: 0, marginBottom: 'var(--space-2)',
            }}>← Back</button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <span style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: 28, height: 28, borderRadius: '50%', background: 'var(--color-primary)',
                    color: '#fff', fontSize: 'var(--text-xs)', fontWeight: 700,
                }}>{step}</span>
                <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>{title}</h2>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginLeft: 'auto' }}>
                    Step {step} of {total}
                </span>
            </div>
            <div style={{ height: 3, background: 'var(--color-border)', borderRadius: 2, marginTop: 'var(--space-2)' }}>
                <div style={{ height: '100%', width: `${(step / total) * 100}%`, background: 'var(--color-primary)', borderRadius: 2, transition: 'width 0.3s' }} />
            </div>
        </div>
    );
}

function InfoRow({ label, value }: { label: string; value: string | number | undefined }) {
    return (
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-border)', fontSize: 'var(--text-sm)' }}>
            <span style={{ color: 'var(--color-text-dim)' }}>{label}</span>
            <span style={{ color: 'var(--color-text)', fontWeight: 500 }}>{value ?? '—'}</span>
        </div>
    );
}

function ActionButton({ label, onClick, variant = 'primary', disabled = false }: {
    label: string; onClick: () => void; variant?: 'primary' | 'danger' | 'outline'; disabled?: boolean;
}) {
    const styles = {
        primary: { bg: 'var(--color-primary)', color: '#fff', border: 'none' },
        danger: { bg: 'rgba(248,81,73,0.1)', color: 'var(--color-alert)', border: '1px solid rgba(248,81,73,0.3)' },
        outline: { bg: 'transparent', color: 'var(--color-text-dim)', border: '1px solid var(--color-border)' },
    };
    const s = styles[variant];
    return (
        <button onClick={onClick} disabled={disabled} style={{
            width: '100%', padding: '14px', borderRadius: 'var(--radius-md)',
            background: s.bg, color: s.color, border: s.border,
            fontWeight: 700, fontSize: 'var(--text-sm)', cursor: disabled ? 'not-allowed' : 'pointer',
            opacity: disabled ? 0.5 : 1, transition: 'opacity 0.2s',
        }}>{label}</button>
    );
}

// ========== Main Page ==========
export default function MobileCheckoutPage() {
    const [bookings, setBookings] = useState<Booking[]>([]);
    const [loading, setLoading] = useState(true);
    const [step, setStep] = useState<CheckoutStep>('list');
    const [selected, setSelected] = useState<Booking | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    // Step state
    const [inspectionNotes, setInspectionNotes] = useState('');
    const [inspectionOk, setInspectionOk] = useState(true);
    const [issueDescription, setIssueDescription] = useState('');
    const [issueCategory, setIssueCategory] = useState('damage');
    const [issueSeverity, setIssueSeverity] = useState('MEDIUM');
    const [issues, setIssues] = useState<any[]>([]);
    const [depositAction, setDepositAction] = useState<'full_return' | 'deduct'>('full_return');
    const [deductionAmount, setDeductionAmount] = useState('');
    const [deductionReason, setDeductionReason] = useState('');
    const [settlement, setSettlement] = useState<any>(null);

    const showNotice = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 3000); };

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch<any>('/bookings?status=checked_in&limit=50');
            const list = res.bookings || res.data?.bookings || res.data || [];
            setBookings(Array.isArray(list) ? list : []);
        } catch { setBookings([]); }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const startCheckout = (b: Booking) => {
        setSelected(b);
        setStep('inspection');
        setInspectionNotes('');
        setInspectionOk(true);
        setIssues([]);
        setIssueDescription('');
        setDepositAction('full_return');
        setDeductionAmount('');
        setDeductionReason('');
        setSettlement(null);
    };

    const goBack = () => {
        const flow: CheckoutStep[] = ['list', 'inspection', 'issues', 'deposit', 'complete'];
        const idx = flow.indexOf(step);
        if (idx <= 1) { setStep('list'); setSelected(null); }
        else setStep(flow[idx - 1]);
    };

    // Step 2: Submit an issue via existing problem_report_router
    const submitIssue = async () => {
        if (!selected || !issueDescription.trim()) return;
        try {
            const res = await apiFetch<any>('/problem-reports', {
                method: 'POST',
                body: JSON.stringify({
                    property_id: selected.property_id,
                    booking_id: getBookingId(selected),
                    description: issueDescription.trim(),
                    category: issueCategory,
                    severity: issueSeverity,
                    reported_by: 'checkout_flow',
                }),
            });
            setIssues(prev => [...prev, res.data || res]);
            setIssueDescription('');
            showNotice('🚨 Issue reported');
        } catch {
            showNotice('Issue report failed — recorded locally');
            setIssues(prev => [...prev, { description: issueDescription, category: issueCategory, severity: issueSeverity, local: true }]);
            setIssueDescription('');
        }
    };

    // Step 3: Handle deposit — deduction or full return
    // Correct flow: GET /deposits?booking_id= → get deposit_id → POST /deposits/{deposit_id}/deductions
    const handleDeposit = async () => {
        if (!selected) return;
        const bookingId = getBookingId(selected);
        try {
            // Step 1: Find the deposit record for this booking
            let depositId: string | null = null;
            try {
                const depositLookup = await apiFetch<any>(`/deposits?booking_id=${bookingId}`);
                const deposits = depositLookup.deposits || [];
                if (deposits.length > 0) {
                    depositId = deposits[0].id;
                }
            } catch { /* no deposit found — skip deductions */ }

            // Step 2: If deducting and we have a deposit_id, add the deduction
            if (depositAction === 'deduct' && deductionAmount && depositId) {
                await apiFetch(`/deposits/${depositId}/deductions`, {
                    method: 'POST',
                    body: JSON.stringify({
                        description: deductionReason || 'Damage/cleaning deduction',
                        amount: parseFloat(deductionAmount),
                        category: 'damage',
                    }),
                });
                showNotice('💰 Deduction recorded');
            } else if (depositAction === 'deduct' && deductionAmount && !depositId) {
                showNotice('⚠️ No deposit on file — deduction skipped');
            }

            // Step 3: Get settlement breakdown (if deposit exists)
            if (depositId) {
                try {
                    const s = await apiFetch<any>(`/deposits/${depositId}/settlement`);
                    setSettlement(s.data || s);
                } catch { /* settlement unavailable */ }
            }
            setStep('complete');
        } catch {
            showNotice('Deposit action failed — proceeding');
            setStep('complete');
        }
    };

    // Step 4: Complete checkout via POST /bookings/{id}/checkout
    const completeCheckout = async () => {
        if (!selected) return;
        const bookingId = getBookingId(selected);
        try {
            await apiFetch<any>(`/bookings/${bookingId}/checkout`, {
                method: 'POST',
            });
            showNotice('✅ Check-out completed');
            setStep('success');
        } catch {
            showNotice('⚠️ Checkout failed — please verify manually');
        }
    };

    const returnToList = () => {
        setStep('list');
        setSelected(null);
        load();
    };

    const navigateToProperty = async (propertyId: string) => {
        try {
            const res = await apiFetch<any>(`/properties/${propertyId}/location`);
            const lat = res.latitude;
            const lng = res.longitude;
            if (lat != null && lng != null) {
                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                const wazeUrl = `https://waze.com/ul?ll=${lat},${lng}&navigate=yes`;
                const googleUrl = `https://maps.google.com/maps?daddr=${lat},${lng}`;
                window.open(isMobile ? wazeUrl : googleUrl, '_blank');
            } else {
                showNotice('📍 No GPS coordinates set for this property');
            }
        } catch {
            showNotice('⚠️ Navigation unavailable — GPS not configured');
        }
    };

    const today = new Date();
    const dateStr = today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

    const card = {
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)',
    };
    const inputStyle = {
        width: '100%', background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-sm)', padding: '10px 14px', color: 'var(--color-text)',
        fontSize: 'var(--text-sm)', outline: 'none',
    };

    return (
        <MobileStaffShell hideHeader>
        <div style={{ maxWidth: 600, margin: '0 auto', paddingBottom: 80 }}>
            {/* Notice toast */}
            {notice && (
                <div style={{
                    position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 999,
                    background: 'var(--color-surface)', border: '1px solid var(--color-primary)',
                    borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-5)',
                    fontSize: 'var(--text-sm)', color: 'var(--color-primary)', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                }}>{notice}</div>
            )}

            {/* ========== LIST: Active stays ========== */}
            {step === 'list' && (
                <>
                    <div style={{ marginBottom: 'var(--space-5)' }}>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            {dateStr}
                        </p>
                        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.03em' }}>
                            Check-out
                        </h1>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                            Active stays ready for checkout
                        </p>
                    </div>

                    {loading && <div style={{ ...card, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading…</div>}

                    {!loading && bookings.length === 0 && (
                        <div style={{ ...card, textAlign: 'center' }}>
                            <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>🏠</div>
                            <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No active stays to check out</div>
                        </div>
                    )}

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        {bookings.map(b => (
                            <div key={getBookingId(b)} style={{ ...card, cursor: 'pointer', transition: 'border-color 0.2s' }}
                                onClick={() => startCheckout(b)}
                                onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                                onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
                                    <div>
                                        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)' }}>
                                            {b.guest_name || 'Guest'}
                                        </div>
                                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                                            {b.property_id}
                                        </div>
                                    </div>
                                    <span style={{
                                        padding: '2px 10px', borderRadius: 12, fontSize: 'var(--text-xs)', fontWeight: 600,
                                        background: 'rgba(130,80,223,0.12)', color: 'var(--color-accent)',
                                    }}>In Stay</span>
                                </div>
                                <div style={{ display: 'flex', gap: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
                                    <span>📅 CO: {b.check_out || '—'}</span>
                                    <span>👥 {b.guest_count || '—'} guests</span>
                                    {b.deposit_amount && <span>💰 {b.deposit_currency || 'THB'} {b.deposit_amount}</span>}
                                </div>
                                <div style={{ marginTop: 'var(--space-3)' }}>
                                    <button style={{
                                        width: '100%', padding: '8px', background: 'rgba(248,81,73,0.08)', color: 'var(--color-alert)',
                                        border: '1px solid rgba(248,81,73,0.2)', borderRadius: 'var(--radius-sm)',
                                        fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer',
                                    }}>Start Check-out →</button>
                                </div>
                            </div>
                        ))}
                    </div>
                </>
            )}

            {/* ========== STEP 1: Inspection ========== */}
            {step === 'inspection' && selected && (
                <div style={card}>
                    <StepHeader step={1} total={4} title="Property Inspection" onBack={goBack} />
                    <InfoRow label="Guest" value={selected.guest_name} />
                    <InfoRow label="Property" value={selected.property_id} />
                    <InfoRow label="Check-out" value={selected.check_out} />

                    <div style={{ marginTop: 'var(--space-4)' }}>
                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                            Inspection Notes
                        </label>
                        <textarea value={inspectionNotes} onChange={e => setInspectionNotes(e.target.value)}
                            placeholder="Any damage, missing items, or notes..."
                            rows={3} style={{ ...inputStyle, resize: 'vertical' }} />
                    </div>

                    <div style={{ marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-2)' }}>
                        {[{ label: '✅ All Good', ok: true }, { label: '⚠️ Issues Found', ok: false }].map(opt => (
                            <button key={String(opt.ok)} onClick={() => setInspectionOk(opt.ok)} style={{
                                flex: 1, padding: '10px', borderRadius: 'var(--radius-sm)',
                                background: inspectionOk === opt.ok ? (opt.ok ? 'rgba(63,185,80,0.1)' : 'rgba(248,81,73,0.1)') : 'var(--color-surface-2)',
                                border: `1px solid ${inspectionOk === opt.ok ? (opt.ok ? 'rgba(63,185,80,0.3)' : 'rgba(248,81,73,0.3)') : 'var(--color-border)'}`,
                                color: inspectionOk === opt.ok ? (opt.ok ? 'var(--color-ok)' : 'var(--color-alert)') : 'var(--color-text-dim)',
                                fontSize: 'var(--text-sm)', fontWeight: 600, cursor: 'pointer',
                            }}>{opt.label}</button>
                        ))}
                    </div>

                    <div style={{ marginTop: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                        <ActionButton label={inspectionOk ? 'Continue → Deposit' : 'Continue → Report Issues'} onClick={() => {
                            setStep(inspectionOk ? 'deposit' : 'issues');
                        }} />
                        <ActionButton label="📍 Navigate to Property" onClick={() => navigateToProperty(selected.property_id)} variant="outline" />
                    </div>
                </div>
            )}

            {/* ========== STEP 2: Issue Flagging ========== */}
            {step === 'issues' && selected && (
                <div style={card}>
                    <StepHeader step={2} total={4} title="Report Issues" onBack={goBack} />

                    {issues.length > 0 && (
                        <div style={{ marginBottom: 'var(--space-4)' }}>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase', marginBottom: 'var(--space-2)' }}>
                                Reported ({issues.length})
                            </div>
                            {issues.map((issue, i) => (
                                <div key={i} style={{
                                    padding: 'var(--space-2) var(--space-3)', background: 'rgba(248,81,73,0.05)',
                                    border: '1px solid rgba(248,81,73,0.15)', borderRadius: 'var(--radius-sm)',
                                    fontSize: 'var(--text-xs)', color: 'var(--color-text)', marginBottom: 4,
                                }}>
                                    🚨 {issue.description} ({issue.category} · {issue.severity})
                                </div>
                            ))}
                        </div>
                    )}

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        <div>
                            <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                                Issue Description *
                            </label>
                            <textarea value={issueDescription} onChange={e => setIssueDescription(e.target.value)}
                                placeholder="Describe the issue..." rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
                        </div>
                        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                            <div style={{ flex: 1 }}>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Category</label>
                                <select value={issueCategory} onChange={e => setIssueCategory(e.target.value)} style={inputStyle}>
                                    <option value="damage">Damage</option>
                                    <option value="cleanliness">Cleanliness</option>
                                    <option value="missing_items">Missing Items</option>
                                    <option value="appliance">Appliance</option>
                                    <option value="plumbing">Plumbing</option>
                                    <option value="electrical">Electrical</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                            <div style={{ flex: 1 }}>
                                <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>Severity</label>
                                <select value={issueSeverity} onChange={e => setIssueSeverity(e.target.value)} style={inputStyle}>
                                    <option value="LOW">Low</option>
                                    <option value="MEDIUM">Medium</option>
                                    <option value="HIGH">High</option>
                                    <option value="CRITICAL">Critical</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <div style={{ marginTop: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                        <ActionButton label="🚨 Report Issue" onClick={submitIssue} variant="danger" disabled={!issueDescription.trim()} />
                        <ActionButton label="Continue → Deposit Resolution" onClick={() => setStep('deposit')} variant="outline" />
                    </div>
                </div>
            )}

            {/* ========== STEP 3: Deposit Resolution ========== */}
            {step === 'deposit' && selected && (
                <div style={card}>
                    <StepHeader step={3} total={4} title="Deposit Resolution" onBack={goBack} />

                    {selected.deposit_amount ? (
                        <>
                            <div style={{
                                padding: 'var(--space-4)', background: 'rgba(210,153,34,0.1)',
                                border: '1px solid rgba(210,153,34,0.3)', borderRadius: 'var(--radius-md)',
                                marginBottom: 'var(--space-4)',
                            }}>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', textTransform: 'uppercase' }}>Deposit Held</div>
                                <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-warn)', marginTop: 4 }}>
                                    {selected.deposit_currency || 'THB'} {selected.deposit_amount}
                                </div>
                            </div>

                            {issues.length > 0 && (
                                <div style={{
                                    padding: 'var(--space-3)', background: 'rgba(248,81,73,0.05)',
                                    border: '1px solid rgba(248,81,73,0.15)', borderRadius: 'var(--radius-sm)',
                                    fontSize: 'var(--text-xs)', color: 'var(--color-alert)', marginBottom: 'var(--space-4)',
                                }}>
                                    ⚠ {issues.length} issue(s) reported — consider deduction
                                </div>
                            )}

                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
                                {[
                                    { action: 'full_return' as const, label: '💵 Full Return', desc: 'Return entire deposit' },
                                    { action: 'deduct' as const, label: '📉 Deduct from Deposit', desc: 'Deduct for damages/cleaning' },
                                ].map(opt => (
                                    <label key={opt.action} onClick={() => setDepositAction(opt.action)} style={{
                                        display: 'flex', alignItems: 'center', gap: 8, padding: '12px 14px',
                                        background: depositAction === opt.action ? 'rgba(63,185,80,0.08)' : 'var(--color-surface-2)',
                                        border: `1px solid ${depositAction === opt.action ? 'rgba(63,185,80,0.3)' : 'var(--color-border)'}`,
                                        borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                                    }}>
                                        <input type="radio" name="deposit_action" checked={depositAction === opt.action} readOnly />
                                        <div>
                                            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>{opt.label}</div>
                                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{opt.desc}</div>
                                        </div>
                                    </label>
                                ))}
                            </div>

                            {depositAction === 'deduct' && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
                                    <div>
                                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                                            Deduction Amount ({selected.deposit_currency || 'THB'})
                                        </label>
                                        <input type="number" value={deductionAmount} onChange={e => setDeductionAmount(e.target.value)}
                                            placeholder="0" style={inputStyle} max={selected.deposit_amount} />
                                    </div>
                                    <div>
                                        <label style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', display: 'block', marginBottom: 4 }}>
                                            Reason
                                        </label>
                                        <input value={deductionReason} onChange={e => setDeductionReason(e.target.value)}
                                            placeholder="Damage to bathroom mirror..." style={inputStyle} />
                                    </div>
                                </div>
                            )}
                        </>
                    ) : (
                        <div style={{ padding: 'var(--space-4)', textAlign: 'center', color: 'var(--color-ok)', fontSize: 'var(--text-sm)' }}>
                            ✓ No deposit on file — skip to completion
                        </div>
                    )}

                    <div style={{ marginTop: 'var(--space-4)' }}>
                        <ActionButton label="Confirm & Continue →" onClick={handleDeposit} />
                    </div>
                </div>
            )}

            {/* ========== STEP 4: Complete ========== */}
            {step === 'complete' && selected && (
                <div style={card}>
                    <StepHeader step={4} total={4} title="Complete Check-out" onBack={goBack} />

                    <div style={{
                        padding: 'var(--space-6)', textAlign: 'center',
                        background: 'rgba(248,81,73,0.03)', borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(248,81,73,0.15)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-2)' }}>🚪</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-text)' }}>
                            Ready to complete check-out
                        </div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                            This will mark the booking as <strong>Completed</strong> and create a <strong>CLEANING</strong> task.
                        </div>
                    </div>

                    <InfoRow label="Guest" value={selected.guest_name} />
                    <InfoRow label="Property" value={selected.property_id} />
                    <InfoRow label="Issues Reported" value={issues.length > 0 ? `${issues.length} issue(s)` : 'None'} />
                    {settlement && (
                        <>
                            <InfoRow label="Deposit Held" value={`${selected.deposit_currency || 'THB'} ${settlement.total_deposit || selected.deposit_amount || 0}`} />
                            <InfoRow label="Deductions" value={`${selected.deposit_currency || 'THB'} ${settlement.total_deductions || 0}`} />
                            <InfoRow label="Return Amount" value={`${selected.deposit_currency || 'THB'} ${settlement.return_amount || settlement.total_deposit || 0}`} />
                        </>
                    )}

                    <div style={{ marginTop: 'var(--space-5)' }}>
                        <ActionButton label="✅ Complete Check-out" onClick={completeCheckout} variant="danger" />
                    </div>
                </div>
            )}

            {/* ========== SUCCESS ========== */}
            {step === 'success' && selected && (
                <div style={card}>
                    <div style={{
                        padding: 'var(--space-6)', textAlign: 'center',
                        background: 'rgba(63,185,80,0.05)', borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(63,185,80,0.2)', marginBottom: 'var(--space-4)',
                    }}>
                        <div style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-2)' }}>✅</div>
                        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--color-ok)' }}>
                            Check-out Complete
                        </div>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginTop: 'var(--space-2)' }}>
                            {selected.guest_name || 'Guest'} checked out from <strong>{selected.property_id}</strong>
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-3)' }}>
                            A CLEANING task has been automatically created for this property.
                        </div>
                    </div>
                    <ActionButton label="Done — Return to List" onClick={returnToList} />
                </div>
            )}

            <BottomNav items={[
                { href: '/dashboard', label: 'Home', icon: '🏠' },
                { href: '/ops/checkin', label: 'Check-in', icon: '📋' },
                { href: '/ops/checkout', label: 'Check-out', icon: '🚪' },
                { href: '/ops/cleaner', label: 'Cleaning', icon: '🧹' },
                { href: '/ops/maintenance', label: 'Maint.', icon: '🔧' },
            ]} />
        </div>
        </MobileStaffShell>
    );
}
