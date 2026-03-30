'use client';

/**
 * Phase 858 — My Properties (Draft Management)
 *
 * Authenticated user area showing their properties with status badges.
 * Entry point after completing the Get Started wizard.
 *
 * Status model:
 *   draft          → saved, not yet submitted
 *   pending_review → submitted, awaiting admin review
 *   approved       → admin approved
 *   active         → live in system
 *   rejected       → admin rejected, needs updates
 *   expired        → draft older than 90 days
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import DMonogram from '@/components/DMonogram';
import { supabase } from '@/lib/supabaseClient';
import { performClientLogout } from '@/lib/api';
import SignedInShell, { SHELL_TOP_PADDING } from '@/components/SignedInShell';

interface Property {
    id: string;
    name: string;
    property_type: string;
    city: string;
    country: string;
    status: string;
    created_at: string;
    max_guests?: number;
    bedrooms?: number;
    cover_photo_url?: string;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');

/* ─── Status journey config ─── */
type JourneyStep = {
    key: string[];          // statuses that map to this step
    label: string;
    shortLabel: string;
};

const JOURNEY_STEPS: JourneyStep[] = [
    { key: ['draft', 'pending_review', 'pending', 'approved', 'active', 'rejected'], label: 'Submitted', shortLabel: 'Sub.' },
    { key: ['pending_review', 'pending', 'approved', 'active', 'rejected'],          label: 'Under Review', shortLabel: 'Review' },
    { key: ['approved', 'active', 'rejected'],                                        label: 'Decision',    shortLabel: 'Decision' },
    { key: ['active'],                                                                label: 'Active',       shortLabel: 'Active' },
];

/* Step index of the CURRENT status (0-based, matches JOURNEY_STEPS) */
function getJourneyIndex(status: string): number {
    if (status === 'draft') return 0;
    if (status === 'pending_review' || status === 'pending') return 1;
    if (status === 'approved' || status === 'rejected') return 2;
    if (status === 'active') return 3;
    return 0;
}

/* Context line shown under the progress bar */
function getStatusContext(status: string): { text: string; color: string } {
    switch (status) {
        case 'draft':
            return { text: 'Your property is saved as a draft. Submit it for review when ready.', color: '#9ca3af' };
        case 'pending_review':
        case 'pending':
            return { text: 'Under Review — We typically respond within 24–48 hours.', color: '#f59e0b' };
        case 'approved':
            return { text: 'Approved — Your property has been approved and is being set up.', color: '#22c55e' };
        case 'active':
            return { text: 'Active — Your property is live in the system.', color: '#22c55e' };
        case 'rejected':
            return { text: 'Not approved — Please contact us for more information.', color: '#ef4444' };
        case 'expired':
            return { text: 'This draft has expired. Submit a new property to get started.', color: '#6b7280' };
        default:
            return { text: '', color: '#9ca3af' };
    }
}

const card: React.CSSProperties = {
    background: 'var(--color-elevated, #1E2127)',
    border: '1px solid rgba(234,229,222,0.06)',
    borderRadius: 'var(--radius-lg, 16px)',
    padding: 'var(--space-6, 24px)',
};

const primaryBtn: React.CSSProperties = {
    padding: '12px 24px',
    background: 'var(--color-moss, #334036)', border: 'none',
    borderRadius: 'var(--radius-md, 12px)',
    color: 'var(--color-white, #F8F6F2)',
    fontSize: 'var(--text-sm, 14px)', fontWeight: 600,
    fontFamily: 'var(--font-brand, inherit)',
    cursor: 'pointer', textDecoration: 'none',
    display: 'inline-flex', alignItems: 'center', gap: 6,
};

/* ─── Delete Confirmation Modal ─── */
function DeleteConfirmModal({
    propertyName,
    onConfirm,
    onCancel,
}: {
    propertyName: string;
    onConfirm: () => void;
    onCancel: () => void;
}) {
    return (
        <>
            {/* Backdrop */}
            <div
                onClick={onCancel}
                style={{
                    position: 'fixed', inset: 0, zIndex: 9000,
                    background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)',
                    animation: 'fadeIn 150ms ease both',
                }}
            />
            {/* Modal */}
            <div style={{
                position: 'fixed', top: '50%', left: '50%',
                transform: 'translate(-50%, -50%)',
                zIndex: 9001,
                background: 'var(--color-elevated, #1E2127)',
                border: '1px solid rgba(239,68,68,0.25)',
                borderRadius: 20,
                padding: '28px 24px 24px',
                width: 'min(92vw, 360px)',
                boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
                animation: 'modalIn 200ms cubic-bezier(0.34,1.56,0.64,1) both',
            }}>
                {/* Icon */}
                <div style={{
                    width: 52, height: 52, borderRadius: 26,
                    background: 'rgba(239,68,68,0.1)',
                    border: '1px solid rgba(239,68,68,0.2)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '0 auto 16px',
                }}>
                    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"
                        fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        <line x1="10" y1="11" x2="10" y2="17" />
                        <line x1="14" y1="11" x2="14" y2="17" />
                    </svg>
                </div>
                <h3 style={{
                    textAlign: 'center', fontSize: 17, fontWeight: 700,
                    color: 'var(--color-stone, #EAE5DE)', margin: '0 0 8px',
                }}>
                    Delete property?
                </h3>
                <p style={{
                    textAlign: 'center', fontSize: 13,
                    color: 'rgba(234,229,222,0.45)', margin: '0 0 24px', lineHeight: 1.6,
                }}>
                    <strong style={{ color: 'rgba(234,229,222,0.75)' }}>{propertyName}</strong> will be permanently removed.
                    This action cannot be undone.
                </p>
                <div style={{ display: 'flex', gap: 10 }}>
                    <button
                        onClick={onCancel}
                        style={{
                            flex: 1, padding: '11px 0',
                            background: 'transparent',
                            border: '1px solid rgba(234,229,222,0.15)',
                            borderRadius: 12, color: 'rgba(234,229,222,0.6)',
                            fontSize: 14, fontWeight: 600, cursor: 'pointer',
                            transition: 'all 0.15s',
                            fontFamily: 'var(--font-brand, inherit)',
                        }}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        style={{
                            flex: 1, padding: '11px 0',
                            background: '#ef4444',
                            border: 'none',
                            borderRadius: 12, color: '#fff',
                            fontSize: 14, fontWeight: 700, cursor: 'pointer',
                            transition: 'all 0.15s',
                            fontFamily: 'var(--font-brand, inherit)',
                        }}
                    >
                        Delete
                    </button>
                </div>
            </div>
        </>
    );
}

export default function MyPropertiesPage() {
    const router = useRouter();
    const [properties, setProperties] = useState<Property[]>([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState<string | null>(null);
    const [deleting, setDeleting] = useState<string | null>(null);
    const [justSubmitted, setJustSubmitted] = useState<string | null>(null);
    const [deleteToast, setDeleteToast] = useState<{ id: string; name: string } | null>(null);
    const [confirmDelete, setConfirmDelete] = useState<{ id: string; name: string } | null>(null);
    const [userName, setUserName] = useState('');
    const [userEmail, setUserEmail] = useState('');

    // Auth check
    useEffect(() => {
        const token = document.cookie
            .split('; ')
            .find(c => c.startsWith('ihouse_token='))
            ?.split('=')[1];
        if (!token) {
            router.replace('/login');
            return;
        }
        if (supabase) {
            supabase.auth.getUser().then(({ data: { user } }) => {
                if (user) {
                    setUserEmail(user.email || '');
                    const meta = user.user_metadata || {};
                    setUserName(meta.first_name || meta.full_name?.split(' ')[0] || '');
                }
            });
        }
    }, [router]);

    const fetchProperties = useCallback(async () => {
        try {
            const token = document.cookie
                .split('; ')
                .find(c => c.startsWith('ihouse_token='))
                ?.split('=')[1];
            if (!token) { setLoading(false); return; }

            const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
            const res = await fetch(`${apiBase}/properties/mine`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                const payload = data.data || data;
                setProperties(payload.items || []);
            }
        } catch { /* ignore */ }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchProperties(); }, [fetchProperties]);

    const handleSubmitForReview = async (propertyId: string) => {
        setSubmitting(propertyId);
        try {
            const token = document.cookie
                .split('; ')
                .find(c => c.startsWith('ihouse_token='))
                ?.split('=')[1];
            const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
            const res = await fetch(`${apiBase}/properties/${propertyId}/submit`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
            });
            if (res.ok) {
                setJustSubmitted(propertyId);
                setProperties(prev => prev.map(p =>
                    p.id === propertyId ? { ...p, status: 'pending_review' } : p
                ));
            }
        } catch { /* ignore */ }
        finally { setSubmitting(null); }
    };

    /* First tap → open modal. Modal confirm → actually delete. */
    const handleDeleteRequest = (propertyId: string, propertyName: string) => {
        setConfirmDelete({ id: propertyId, name: propertyName });
    };

    const handleDeleteConfirmed = async () => {
        if (!confirmDelete) return;
        const { id: propertyId, name: propName } = confirmDelete;
        setConfirmDelete(null);

        setProperties(prev => prev.filter(p => p.id !== propertyId));
        setDeleteToast({ id: propertyId, name: propName });

        setDeleting(propertyId);
        try {
            const token = document.cookie
                .split('; ')
                .find(c => c.startsWith('ihouse_token='))
                ?.split('=')[1];
            const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
            const res = await fetch(`${apiBase}/properties/${propertyId}/draft`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!res.ok) {
                // Backend failed — restore
                fetchProperties();
                setDeleteToast(null);
            } else {
                setTimeout(() => setDeleteToast(null), 3000);
                try {
                    const wizardState = sessionStorage.getItem('domaniqo_get_started_state');
                    if (wizardState) {
                        const parsed = JSON.parse(wizardState);
                        if (parsed?.property?.id === propertyId) {
                            sessionStorage.removeItem('domaniqo_get_started_state');
                        }
                    }
                } catch { /* ignore */ }
            }
        } catch {
            fetchProperties();
            setDeleteToast(null);
        }
        finally { setDeleting(null); }
    };

    const handleSignOut = async () => {
        await supabase?.auth.signOut();
        performClientLogout('/');
    };

    const drafts    = properties.filter(p => p.status === 'draft');
    const submitted = properties.filter(p => ['pending_review', 'pending'].includes(p.status));
    const approved  = properties.filter(p => ['approved', 'active'].includes(p.status));
    const rejected  = properties.filter(p => p.status === 'rejected');
    const expired   = properties.filter(p => p.status === 'expired');

    return (
        <>
            <style>{`
                @keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
                @keyframes fadeSlideIn { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
                @keyframes modalIn { from { opacity:0; transform:translate(-50%,-48%) scale(0.94); } to { opacity:1; transform:translate(-50%,-50%) scale(1); } }
                .mp-fade { animation: fadeSlideIn 400ms ease both; }
                .mp-card { transition: border-color 0.2s; }
                .mp-card:hover { border-color: rgba(234,229,222,0.12) !important; }
                .del-btn:hover { background: rgba(239,68,68,0.12) !important; border-color: rgba(239,68,68,0.4) !important; color: #ef4444 !important; }
            `}</style>

            <SignedInShell back="/welcome" backLabel="← Home" />

            {/* Delete confirmation modal */}
            {confirmDelete && (
                <DeleteConfirmModal
                    propertyName={confirmDelete.name}
                    onConfirm={handleDeleteConfirmed}
                    onCancel={() => setConfirmDelete(null)}
                />
            )}

            {/* Success toast after confirmed delete */}
            {deleteToast && (
                <div style={{
                    position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
                    zIndex: 9999, background: '#1E2127', border: '1px solid rgba(234,229,222,0.15)',
                    borderRadius: 12, padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 10,
                    boxShadow: '0 8px 32px rgba(0,0,0,0.4)', fontSize: 14, color: 'rgba(234,229,222,0.7)',
                    animation: 'fadeSlideIn 300ms ease both', whiteSpace: 'nowrap',
                }}>
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                        fill="none" stroke="#6b7280" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                    {deleteToast.name} deleted
                </div>
            )}

            <div style={{ minHeight: '100vh', background: 'var(--color-midnight, #171A1F)', paddingTop: SHELL_TOP_PADDING }}>
                <div style={{ maxWidth: 480, margin: '0 auto', padding: 'var(--space-6, 24px) var(--space-4, 16px)' }}>

                    {/* Page heading */}
                    <div className="mp-fade" style={{ marginBottom: 'var(--space-6, 24px)' }}>
                        <h1 style={{
                            fontFamily: 'var(--font-display, serif)',
                            fontSize: 'var(--text-xl, 24px)',
                            color: 'var(--color-stone, #EAE5DE)',
                            margin: '0 0 6px', fontWeight: 400,
                        }}>
                            My Properties
                        </h1>
                        <p style={{ fontSize: 14, color: 'rgba(234,229,222,0.35)', margin: 0 }}>
                            {userName ? `Welcome back, ${userName}.` : userEmail ? `Signed in as ${userEmail}` : 'Manage your properties.'}
                        </p>
                    </div>

                    {loading ? (
                        <div style={{ textAlign: 'center', padding: 'var(--space-8) 0', color: 'rgba(234,229,222,0.3)' }}>
                            Loading your properties…
                        </div>
                    ) : properties.length === 0 ? (
                        <div className="mp-fade" style={{ ...card, textAlign: 'center', padding: 'var(--space-8, 32px)' }}>
                            <div style={{ fontSize: 48, marginBottom: 12 }}>🏠</div>
                            <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--color-stone)', margin: '0 0 8px' }}>
                                No properties yet
                            </h2>
                            <p style={{ fontSize: 14, color: 'rgba(234,229,222,0.4)', margin: '0 0 20px', lineHeight: 1.6 }}>
                                Add your first property to get started with Domaniqo.
                            </p>
                            <button style={primaryBtn} onClick={() => { sessionStorage.removeItem('domaniqo_get_started_state'); router.push('/get-started'); }}>
                                + Add Your First Property
                            </button>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

                            {/* Just submitted banner */}
                            {justSubmitted && (
                                <div className="mp-fade" style={{
                                    ...card, padding: '14px 18px',
                                    background: 'rgba(74,124,89,0.06)',
                                    border: '1px solid rgba(74,124,89,0.15)',
                                }}>
                                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ok, #4A7C59)', marginBottom: 4 }}>
                                        ✅ Submitted for Review
                                    </div>
                                    <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.4)', lineHeight: 1.5 }}>
                                        Your property has been submitted. We&apos;ll review it and get back to you soon.
                                    </div>
                                </div>
                            )}

                            {/* Render all sections */}
                            {[
                                { label: 'Submitted', items: submitted, showProgress: true },
                                { label: 'Needs Attention', items: rejected, showProgress: true },
                                { label: 'Drafts', items: drafts, showProgress: true },
                                { label: 'Approved', items: approved, showProgress: true },
                                { label: 'Archived', items: expired, showProgress: false },
                            ].map(({ label, items, showProgress }) => items.length > 0 && (
                                <div key={label}>
                                    <h2 style={{
                                        fontSize: 12, fontWeight: 700, color: 'rgba(234,229,222,0.3)',
                                        textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 10px',
                                    }}>
                                        {label} ({items.length})
                                    </h2>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                        {items.map(prop => (
                                            <PropertyCard
                                                key={prop.id}
                                                property={prop}
                                                showProgress={showProgress}
                                                onSubmit={prop.status === 'draft' ? () => handleSubmitForReview(prop.id) : undefined}
                                                onDeleteRequest={() => handleDeleteRequest(prop.id, prop.name || 'Property')}
                                                canDelete={['draft', 'pending_review', 'pending', 'rejected'].includes(prop.status)}
                                                submitting={submitting === prop.id || deleting === prop.id}
                                            />
                                        ))}
                                    </div>
                                </div>
                            ))}

                            {/* Add another */}
                            <div style={{ textAlign: 'center', paddingTop: 4 }}>
                                <button style={primaryBtn} onClick={() => { sessionStorage.removeItem('domaniqo_get_started_state'); router.push('/get-started'); }}>
                                    + Add Another Property
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}

/* ─── Status Journey Progress Bar ─── */
function StatusJourney({ status }: { status: string }) {
    const currentIdx = getJourneyIndex(status);
    const ctx = getStatusContext(status);
    const isRejected = status === 'rejected';

    return (
        <div style={{ paddingTop: 14 }}>
            {/* Step dots + line */}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 0, marginBottom: 10 }}>
                {JOURNEY_STEPS.map((step, i) => {
                    const isDone = i < currentIdx;
                    const isCurrent = i === currentIdx;
                    const isDecisionRejected = isRejected && i === 2;

                    let dotBg = 'transparent';
                    let dotBorder = 'rgba(234,229,222,0.15)';
                    let dotColor = 'rgba(234,229,222,0.2)';
                    let labelColor = 'rgba(234,229,222,0.25)';

                    if (isDone) {
                        dotBg = '#334036'; dotBorder = '#334036'; dotColor = '#fff'; labelColor = 'rgba(234,229,222,0.5)';
                    }
                    if (isCurrent && !isDecisionRejected) {
                        dotBg = isRejected ? '#ef4444' : '#334036';
                        dotBorder = isRejected ? '#ef4444' : '#334036';
                        dotColor = '#fff'; labelColor = isRejected ? '#ef4444' : '#EAE5DE';
                    }
                    if (isDecisionRejected) {
                        dotBg = '#ef4444'; dotBorder = '#ef4444'; dotColor = '#fff'; labelColor = '#ef4444';
                    }

                    const isLast = i === JOURNEY_STEPS.length - 1;

                    return (
                        <div key={step.label} style={{ display: 'flex', alignItems: 'flex-start', flex: isLast ? 0 : 1 }}>
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 36 }}>
                                {/* Dot */}
                                <div style={{
                                    width: 22, height: 22, borderRadius: 11,
                                    background: dotBg, border: `2px solid ${dotBorder}`,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    transition: 'all 0.3s',
                                    flexShrink: 0,
                                }}>
                                    {(isDone || isDecisionRejected) ? (
                                        isDecisionRejected ? (
                                            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"
                                                fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                                                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                                            </svg>
                                        ) : (
                                            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"
                                                fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="20 6 9 17 4 12" />
                                            </svg>
                                        )
                                    ) : isCurrent ? (
                                        <div style={{ width: 7, height: 7, borderRadius: 4, background: '#fff' }} />
                                    ) : null}
                                </div>
                                {/* Label */}
                                <div style={{
                                    fontSize: 10, fontWeight: isCurrent ? 700 : 500,
                                    color: labelColor, marginTop: 5, textAlign: 'center',
                                    lineHeight: 1.2, whiteSpace: 'nowrap',
                                }}>
                                    {step.shortLabel !== step.label
                                        ? step.label.split(' ').map((w, wi) => <div key={wi}>{w}</div>)
                                        : step.label}
                                </div>
                            </div>
                            {/* Connector line */}
                            {!isLast && (
                                <div style={{
                                    flex: 1, height: 2, marginTop: 10,
                                    background: isDone ? '#334036' : 'rgba(234,229,222,0.1)',
                                    transition: 'background 0.3s',
                                }} />
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Context text */}
            {ctx.text && (
                <div style={{
                    fontSize: 12, color: ctx.color, lineHeight: 1.55,
                    padding: '8px 10px',
                    background: 'rgba(0,0,0,0.15)',
                    borderRadius: 8,
                    borderLeft: `3px solid ${ctx.color}`,
                }}>
                    {ctx.text}
                </div>
            )}
        </div>
    );
}

/* ─── Property Card Component ─── */
function PropertyCard({
    property, onSubmit, onDeleteRequest, canDelete, submitting, showProgress,
}: {
    property: Property;
    onSubmit?: () => void;
    onDeleteRequest?: () => void;
    canDelete?: boolean;
    submitting?: boolean;
    showProgress?: boolean;
}) {
    const router = useRouter();
    const isExpired = property.status === 'expired';

    return (
        <div className="mp-card" style={{
            ...card,
            padding: '16px',
            opacity: (isExpired || submitting) ? 0.55 : 1,
            pointerEvents: submitting ? 'none' : 'auto',
        }}>
            {/* Top row: photo + name + delete */}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                {/* Photo */}
                {property.cover_photo_url ? (
                    <div style={{
                        width: 58, height: 58, borderRadius: 8, overflow: 'hidden', flexShrink: 0,
                        background: 'var(--color-surface, #1E2127)', border: '1px solid rgba(234,229,222,0.1)',
                    }}>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={property.cover_photo_url} alt={property.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    </div>
                ) : (
                    <div style={{
                        width: 58, height: 58, borderRadius: 8, flexShrink: 0,
                        background: 'rgba(234,229,222,0.03)', border: '1px dashed rgba(234,229,222,0.15)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22,
                    }}>
                        🏠
                    </div>
                )}

                {/* Name + location */}
                <div style={{ flex: 1, minWidth: 0 }}>
                    <h3 style={{
                        fontSize: 15, fontWeight: 700,
                        color: 'var(--color-stone, #EAE5DE)',
                        margin: '0 0 3px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
                        {property.name || 'Untitled Property'}
                    </h3>
                    <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.35)' }}>
                        {[property.city, property.country].filter(Boolean).join(', ') || 'Location not set'}
                        {property.property_type && ` · ${property.property_type}`}
                    </div>
                </div>

                {/* Delete button — clearly visible, red-tinted, labelled */}
                {canDelete && onDeleteRequest && (
                    <button
                        className="del-btn"
                        onClick={onDeleteRequest}
                        disabled={submitting}
                        title="Delete this property"
                        style={{
                            flexShrink: 0,
                            display: 'flex', alignItems: 'center', gap: 5,
                            padding: '6px 10px',
                            background: 'rgba(239,68,68,0.07)',
                            border: '1px solid rgba(239,68,68,0.2)',
                            borderRadius: 8,
                            color: 'rgba(239,68,68,0.7)',
                            fontSize: 12, fontWeight: 600,
                            cursor: submitting ? 'not-allowed' : 'pointer',
                            transition: 'all 0.15s',
                            opacity: submitting ? 0.4 : 1,
                        }}
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
                            fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                        Delete
                    </button>
                )}
            </div>

            {/* Status journey progress */}
            {showProgress && !isExpired && (
                <StatusJourney status={property.status} />
            )}

            {/* Draft actions */}
            {property.status === 'draft' && onSubmit && (
                <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                    <button
                        onClick={() => router.push(`/get-started?edit=${property.id}`)}
                        disabled={submitting}
                        style={{
                            flex: 1, padding: '9px 0', fontSize: 13, fontWeight: 600,
                            background: 'transparent', border: '1px solid rgba(234,229,222,0.15)',
                            borderRadius: 10, color: 'var(--color-stone)',
                            cursor: 'pointer', transition: 'all 0.15s',
                            fontFamily: 'var(--font-brand, inherit)',
                        }}
                    >
                        ✏️ Edit
                    </button>
                    <button
                        onClick={onSubmit}
                        disabled={submitting}
                        style={{
                            flex: 1, padding: '9px 0', fontSize: 13, fontWeight: 700,
                            background: 'var(--color-moss, #334036)', border: 'none',
                            borderRadius: 10, color: '#fff',
                            cursor: submitting ? 'not-allowed' : 'pointer',
                            opacity: submitting ? 0.6 : 1, transition: 'all 0.15s',
                            fontFamily: 'var(--font-brand, inherit)',
                        }}
                    >
                        {submitting ? '…' : 'Submit for Review →'}
                    </button>
                </div>
            )}
        </div>
    );
}
