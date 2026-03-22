'use client';

/**
 * Phase 858 — My Properties (Draft Management)
 *
 * Authenticated user area showing their properties with status badges.
 * Entry point after completing the Get Started wizard.
 * Also accessible from the main navigation for returning users.
 *
 * Status model:
 *   draft          → saved, not yet submitted
 *   pending_review → submitted, awaiting admin review
 *   approved       → admin approved, live in system
 *   expired        → draft older than 90 days (archived)
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
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

const STATUS_CONFIG: Record<string, { label: string; icon: string; color: string; bg: string }> = {
    draft: { label: 'Draft', icon: '📝', color: '#6b7280', bg: 'rgba(107, 114, 128, 0.1)' },
    pending_review: { label: 'Pending Review', icon: '⏳', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.1)' },
    pending: { label: 'Pending Review', icon: '⏳', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.1)' },
    active: { label: 'Active', icon: '✅', color: '#22c55e', bg: 'rgba(34, 197, 94, 0.1)' },
    approved: { label: 'Approved', icon: '✅', color: '#22c55e', bg: 'rgba(34, 197, 94, 0.1)' },
    rejected: { label: 'Needs Updates', icon: '⛔', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)' },
    expired:        { label: 'Expired',         color: 'rgba(234,229,222,0.25)', bg: 'rgba(234,229,222,0.03)', icon: '📦' },
};

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

export default function MyPropertiesPage() {
    const router = useRouter();
    const [properties, setProperties] = useState<Property[]>([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState<string | null>(null);
    const [deleting, setDeleting] = useState<string | null>(null);
    const [justSubmitted, setJustSubmitted] = useState<string | null>(null);
    const [userName, setUserName] = useState('');
    const [userEmail, setUserEmail] = useState('');

    // Auth check — ihouse_token is the canonical credential
    useEffect(() => {
        const token = document.cookie
            .split('; ')
            .find(c => c.startsWith('ihouse_token='))
            ?.split('=')[1];
        if (!token) {
            router.replace('/login');
            return;
        }
        // Try Supabase session for display name (optional — not required for auth)
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
            // Phase 862 P24: use ihouse_token cookie for auth
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

    const handleDelete = async (propertyId: string) => {
        if (!confirm('Are you sure you want to permanently delete this property? This cannot be undone.')) return;
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
            if (res.ok) {
                setProperties(prev => prev.filter(p => p.id !== propertyId));
            } else {
                alert('Failed to delete property.');
            }
        } catch { 
            alert('Failed to delete property due to network error.');
        }
        finally { setDeleting(null); }
    };

    const handleSignOut = async () => {
        await supabase?.auth.signOut();
        performClientLogout('/');
    };

    const drafts = properties.filter(p => p.status === 'draft');
    const submitted = properties.filter(p => ['pending_review', 'pending'].includes(p.status));
    const approved = properties.filter(p => ['approved', 'active'].includes(p.status));
    const expired = properties.filter(p => p.status === 'expired');

    return (
        <>
            <style>{`
                @keyframes fadeSlideIn { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
                .mp-fade { animation: fadeSlideIn 400ms ease both; }
                .mp-card { transition: border-color 0.2s; }
                .mp-card:hover { border-color: rgba(234,229,222,0.12) !important; }
            `}</style>

            <SignedInShell back="/welcome" backLabel="← Home" />

            <div style={{
                minHeight: '100vh',
                background: 'var(--color-midnight, #171A1F)',
                paddingTop: SHELL_TOP_PADDING,
            }}>
                <div style={{
                    maxWidth: 480, margin: '0 auto',
                    padding: 'var(--space-6, 24px) var(--space-4, 16px)',
                }}>
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
                        /* Empty state */
                        <div className="mp-fade" style={{ ...card, textAlign: 'center', padding: 'var(--space-8, 32px)' }}>
                            <div style={{ fontSize: 48, marginBottom: 12 }}>🏠</div>
                            <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--color-stone)', margin: '0 0 8px' }}>
                                No properties yet
                            </h2>
                            <p style={{ fontSize: 14, color: 'rgba(234,229,222,0.4)', margin: '0 0 20px', lineHeight: 1.6 }}>
                                Add your first property to get started with Domaniqo.
                            </p>
                            <Link href="/get-started" style={primaryBtn}>
                                + Add Your First Property
                            </Link>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                            {/* Just submitted banner */}
                            {justSubmitted && (
                                <div className="mp-fade" style={{
                                    ...card,
                                    padding: '14px 18px',
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

                            {/* Drafts section */}
                            {drafts.length > 0 && (
                                <div>
                                    <h2 style={{
                                        fontSize: 12, fontWeight: 700, color: 'rgba(234,229,222,0.3)',
                                        textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 10px',
                                    }}>
                                        Drafts ({drafts.length})
                                    </h2>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                        {drafts.map(prop => (
                                            <PropertyCard key={prop.id} property={prop}
                                                onSubmit={() => handleSubmitForReview(prop.id)}
                                                onDelete={() => handleDelete(prop.id)}
                                                submitting={submitting === prop.id || deleting === prop.id} />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Submitted section */}
                            {submitted.length > 0 && (
                                <div>
                                    <h2 style={{
                                        fontSize: 12, fontWeight: 700, color: 'rgba(234,229,222,0.3)',
                                        textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 10px',
                                    }}>
                                        Submitted ({submitted.length})
                                    </h2>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                        {submitted.map(prop => (
                                            <PropertyCard key={prop.id} property={prop}
                                                onDelete={['draft', 'pending_review', 'rejected'].includes(prop.status) ? () => handleDelete(prop.id) : undefined}
                                                submitting={deleting === prop.id} />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Approved section */}
                            {approved.length > 0 && (
                                <div>
                                    <h2 style={{
                                        fontSize: 12, fontWeight: 700, color: 'rgba(234,229,222,0.3)',
                                        textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 10px',
                                    }}>
                                        Approved ({approved.length})
                                    </h2>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                        {approved.map(prop => (
                                            <PropertyCard key={prop.id} property={prop} />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Expired section */}
                            {expired.length > 0 && (
                                <div>
                                    <h2 style={{
                                        fontSize: 12, fontWeight: 700, color: 'rgba(234,229,222,0.2)',
                                        textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 10px',
                                    }}>
                                        Archived ({expired.length})
                                    </h2>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                        {expired.map(prop => (
                                            <PropertyCard key={prop.id} property={prop} />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Add another */}
                            <div style={{ textAlign: 'center', paddingTop: 4 }}>
                                <Link href="/get-started" style={primaryBtn}>
                                    + Add Another Property
                                </Link>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}

/* ─── Property Card Component ─── */

function PropertyCard({ property, onSubmit, onDelete, submitting }: {
    property: Property;
    onSubmit?: () => void;
    onDelete?: () => void;
    submitting?: boolean;
}) {
    const router = useRouter();
    const statusConf = STATUS_CONFIG[property.status] || STATUS_CONFIG.draft;
    const isExpired = property.status === 'expired';

    return (
        <div className="mp-card" style={{
            ...card,
            padding: '14px 16px',
            opacity: isExpired ? 0.5 : 1,
        }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                {/* Left side: photo + info */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, flex: 1, minWidth: 0 }}>
                    {property.cover_photo_url ? (
                        <div style={{
                            width: 64, height: 64, borderRadius: 8, overflow: 'hidden', flexShrink: 0,
                            background: 'var(--color-surface, #1E2127)', border: '1px solid rgba(234,229,222,0.1)'
                        }}>
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={property.cover_photo_url} alt={property.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        </div>
                    ) : (
                        <div style={{
                            width: 64, height: 64, borderRadius: 8, flexShrink: 0,
                            background: 'rgba(234,229,222,0.03)', border: '1px dashed rgba(234,229,222,0.15)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24
                        }}>
                            🏠
                        </div>
                    )}

                    <div style={{ flex: 1, minWidth: 0 }}>
                        <h3 style={{
                            fontSize: 15, fontWeight: 600,
                            color: 'var(--color-stone, #EAE5DE)',
                            margin: '0 0 3px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        }}>
                            {property.name || 'Untitled Property'}
                        </h3>

                        <div style={{ fontSize: 12, color: 'rgba(234,229,222,0.35)', marginBottom: 6 }}>
                            {[property.city, property.country].filter(Boolean).join(', ') || 'Location not set'}
                            {property.property_type && ` · ${property.property_type}`}
                        </div>

                        {/* Status badge */}
                        <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: 4,
                            fontSize: 10, fontWeight: 700,
                            color: statusConf.color, background: statusConf.bg,
                            padding: '2px 8px', borderRadius: 99,
                            textTransform: 'uppercase', letterSpacing: '0.04em',
                        }}>
                            {statusConf.icon} {statusConf.label}
                        </span>
                    </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'flex-end', minWidth: 100 }}>
                    {property.status === 'draft' && onSubmit && (
                        <>
                            <button
                                onClick={() => router.push(`/get-started?edit=${property.id}`)}
                                disabled={submitting}
                                style={{
                                    ...primaryBtn, padding: '6px 14px', fontSize: 12, flexShrink: 0,
                                    background: 'transparent',
                                    border: '1px solid rgba(234,229,222,0.15)',
                                    color: 'var(--color-stone)',
                                    opacity: submitting ? 0.5 : 1,
                                }}
                            >
                                Edit ✏️
                            </button>
                            <button
                                onClick={onSubmit}
                                disabled={submitting}
                                style={{
                                    ...primaryBtn, padding: '6px 14px', fontSize: 12, flexShrink: 0,
                                    opacity: submitting ? 0.5 : 1,
                                }}
                            >
                                {submitting ? '…' : 'Submit →'}
                            </button>
                        </>
                    )}
                    {(!onSubmit && property.status !== 'draft' && !['approved', 'active'].includes(property.status)) && (
                        <div style={{ width: 1, height: 1 }}>{/* Spacer basically if no edit/submit on submitted view... wait we don't need this */}</div>
                    )}
                    
                    {onDelete && (
                        <button
                            onClick={onDelete}
                            disabled={submitting}
                            style={{
                                background: 'transparent', color: '#ff4444', border: 'none', 
                                cursor: submitting ? 'not-allowed' : 'pointer', fontSize: 12, 
                                fontWeight: 600, padding: '6px 10px', opacity: submitting ? 0.5 : 1,
                                marginLeft: 'auto'
                            }}
                        >
                            {submitting ? '…' : 'Delete 🗑️'}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
