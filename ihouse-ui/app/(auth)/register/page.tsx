'use client';

/**
 * Registration Step 1 — Portfolio Size
 * Route: /register
 *
 * "What is the size of your listings portfolio?"
 * Three selectable cards: 1–4 / 5–20 / 20+
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import AuthCard from '../../../components/auth/AuthCard';
import ProgressBar from '../../../components/auth/ProgressBar';

const SIZES = [
    { id: '1-5', label: '1–5 Listings', desc: 'Getting started' },
    { id: '5-20', label: '5–20 Listings', desc: 'Growing portfolio' },
    { id: '20+', label: '20+ Listings', desc: 'Established manager' },
];

export default function RegisterStep1Page() {
    const router = useRouter();
    const [selected, setSelected] = useState<string | null>(null);

    const handleContinue = () => {
        if (!selected) return;
        router.push(`/register/email?portfolio=${selected}`);
    };

    return (
        <AuthCard title="Create your account" subtitle="Let's start by understanding your portfolio">
            <ProgressBar current={1} total={3} />

            <p style={{
                fontSize: 'var(--text-base, 16px)',
                color: 'var(--color-stone, #EAE5DE)',
                fontWeight: 600,
                margin: '0 0 var(--space-4, 16px)',
            }}>
                What is the size of your listings portfolio?
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 'var(--space-5, 20px)' }}>
                {SIZES.map(s => (
                    <button
                        key={s.id}
                        type="button"
                        onClick={() => setSelected(s.id)}
                        style={{
                            padding: '16px 18px',
                            background: selected === s.id
                                ? 'rgba(181,110,69,0.08)'
                                : 'var(--color-midnight, #171A1F)',
                            border: `2px solid ${selected === s.id
                                ? 'var(--color-copper, #B56E45)'
                                : 'rgba(234,229,222,0.08)'}`,
                            borderRadius: 'var(--radius-md, 12px)',
                            cursor: 'pointer',
                            textAlign: 'left',
                            transition: 'all 0.2s',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 14,
                        }}
                    >
                        <div style={{
                            width: 22, height: 22, borderRadius: 11,
                            border: `2px solid ${selected === s.id ? 'var(--color-copper, #B56E45)' : 'rgba(234,229,222,0.15)'}`,
                            background: selected === s.id ? 'var(--color-copper, #B56E45)' : 'transparent',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 11, color: '#fff', fontWeight: 700, flexShrink: 0,
                        }}>
                            {selected === s.id && '✓'}
                        </div>
                        <div>
                            <div style={{
                                fontSize: 'var(--text-base, 15px)',
                                fontWeight: 600,
                                color: 'var(--color-stone, #EAE5DE)',
                            }}>
                                {s.label}
                            </div>
                            <div style={{
                                fontSize: 'var(--text-xs, 12px)',
                                color: 'rgba(234,229,222,0.3)',
                                marginTop: 2,
                            }}>
                                {s.desc}
                            </div>
                        </div>
                    </button>
                ))}
            </div>

            <button
                type="button"
                className="auth-btn"
                onClick={handleContinue}
                disabled={!selected}
                style={{
                    width: '100%',
                    padding: '14px', background: 'var(--color-moss, #334036)',
                    border: 'none', borderRadius: 'var(--radius-md, 12px)',
                    color: 'var(--color-white, #F8F6F2)', fontSize: 'var(--text-base, 16px)',
                    fontWeight: 600, fontFamily: 'var(--font-brand, "Inter", sans-serif)',
                    cursor: !selected ? 'not-allowed' : 'pointer',
                    opacity: !selected ? 0.4 : 1,
                    transition: 'all 0.2s', minHeight: 48,
                }}
            >
                Continue
            </button>

            <div style={{ marginTop: 'var(--space-6, 24px)', textAlign: 'center' }}>
                <a href="/login" className="auth-link" style={{ fontSize: 'var(--text-sm, 14px)' }}>
                    Already a Domaniqo user? <span style={{ textDecoration: 'underline' }}>Login here</span>
                </a>
            </div>
        </AuthCard>
    );
}
