'use client';

/**
 * Phase 863 — Preview Mode Banner
 * 
 * Non-interactive banner displayed on every page when admin is in Preview Mode.
 * Per admin-preview-and-act-as.md §2 — UI Indicator:
 *   👁 PREVIEW MODE: Viewing as [Role]  |  Read-only  |  [Close Preview]
 */

import { usePreview } from '../lib/PreviewContext';

const ROLE_LABELS: Record<string, string> = {
    manager: 'Ops Manager',
    owner: 'Owner',
    cleaner: 'Cleaner',
    checkin: 'Check-in Staff',
    checkout: 'Check-out Staff',
    checkin_checkout: 'Check-in & Check-out',
    maintenance: 'Maintenance',
};

export default function PreviewBanner() {
    const { previewRole, isPreviewActive, clearPreview } = usePreview();

    if (!isPreviewActive || !previewRole) return null;

    const roleLabel = ROLE_LABELS[previewRole] || previewRole;

    // Person name stored by preview/page.tsx when person-specific preview started
    const personName = typeof window !== 'undefined'
        ? (sessionStorage.getItem('ihouse_preview_display_name') || '')
        : '';

    // Full identity label: "Ops Manager · Nana G" or just "Ops Manager"
    const identityLabel = personName ? `${roleLabel} · ${personName}` : roleLabel;

    return (
        <div
            id="preview-mode-banner"
            style={{
                position: 'sticky',
                top: 0,
                zIndex: 9999,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 12,
                padding: '4px 16px',
                background: 'rgba(234,179,8,0.12)',
                borderBottom: '1px solid rgba(234,179,8,0.4)',
                fontFamily: "'Inter', sans-serif",
                fontSize: 11,
                fontWeight: 600,
                color: '#EAB308',
                backdropFilter: 'blur(6px)',
                letterSpacing: '0.02em',
                minHeight: 28,
                overflow: 'hidden',
            }}
        >
            <span>👁 PREVIEW: <strong>{identityLabel}</strong></span>
            <span style={{ color: 'rgba(234,179,8,0.4)', fontWeight: 300 }}>·</span>
            <span style={{ fontWeight: 400, opacity: 0.75 }}>Read-only</span>
            <span style={{ color: 'rgba(234,179,8,0.4)', fontWeight: 300 }}>·</span>
            <button
                onClick={() => clearPreview()}
                style={{
                    background: 'rgba(234,179,8,0.16)',
                    border: '1px solid rgba(234,179,8,0.35)',
                    borderRadius: 4,
                    padding: '2px 10px',
                    fontSize: 10,
                    fontWeight: 700,
                    color: '#EAB308',
                    cursor: 'pointer',
                    fontFamily: "'Inter', sans-serif",
                    transition: 'all 0.15s',
                    textTransform: 'uppercase',
                    letterSpacing: '0.03em',
                    flexShrink: 0,
                }}
                onMouseEnter={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(234,179,8,0.3)';
                }}
                onMouseLeave={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(234,179,8,0.16)';
                }}
            >
                Close
            </button>
        </div>
    );
}
