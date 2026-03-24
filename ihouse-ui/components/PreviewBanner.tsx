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
                gap: 16,
                padding: '10px 20px',
                background: 'linear-gradient(135deg, rgba(234,179,8,0.15) 0%, rgba(234,179,8,0.08) 100%)',
                borderBottom: '2px solid rgba(234,179,8,0.5)',
                fontFamily: "'Inter', sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: '#EAB308',
                backdropFilter: 'blur(8px)',
                letterSpacing: '0.02em',
            }}
        >
            <span>👁 PREVIEW MODE: Viewing as {roleLabel}</span>
            <span style={{ color: 'rgba(234,179,8,0.5)', fontWeight: 400 }}>|</span>
            <span style={{ fontWeight: 400, opacity: 0.8 }}>Read-only — all actions disabled</span>
            <span style={{ color: 'rgba(234,179,8,0.5)', fontWeight: 400 }}>|</span>
            <span style={{ fontWeight: 400, opacity: 0.6, fontSize: 11 }}>Data: tasks role-filtered · bookings admin-scoped</span>
            <span style={{ color: 'rgba(234,179,8,0.5)', fontWeight: 400 }}>|</span>
            <button
                onClick={() => clearPreview()}
                style={{
                    background: 'rgba(234,179,8,0.2)',
                    border: '1px solid rgba(234,179,8,0.4)',
                    borderRadius: 6,
                    padding: '4px 14px',
                    fontSize: 12,
                    fontWeight: 600,
                    color: '#EAB308',
                    cursor: 'pointer',
                    fontFamily: "'Inter', sans-serif",
                    transition: 'all 0.15s',
                }}
                onMouseEnter={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(234,179,8,0.35)';
                }}
                onMouseLeave={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(234,179,8,0.2)';
                }}
            >
                Close Preview
            </button>
        </div>
    );
}
