'use client';

/**
 * Phase 389 — DetailSheet shared component
 * Bottom-sheet detail view, generalized from worker page, Domaniqo tokens.
 */

import React, { useState } from 'react';

interface DetailSheetProps {
    open: boolean;
    onClose: () => void;
    title: string;
    subtitle?: string;
    accentColor?: string;
    children: React.ReactNode;
}

export default function DetailSheet({ open, onClose, title, subtitle, accentColor, children }: DetailSheetProps) {
    if (!open) return null;

    return (
        <>
            {/* Backdrop */}
            <div
                onClick={onClose}
                style={{
                    position: 'fixed', inset: 0,
                    background: 'rgba(0,0,0,0.6)',
                    zIndex: 100,
                    backdropFilter: 'blur(4px)',
                }}
            />
            {/* Sheet */}
            <div style={{
                position: 'fixed', bottom: 0, left: 0, right: 0,
                background: 'var(--color-bg, #111827)',
                borderRadius: '24px 24px 0 0',
                zIndex: 101,
                padding: '0 0 env(safe-area-inset-bottom, 24px)',
                maxHeight: '85vh',
                overflowY: 'auto',
                animation: 'sheetSlideUp 240ms cubic-bezier(0.32,0.72,0,1)',
            }}>
                {/* Handle */}
                <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 12, paddingBottom: 4 }}>
                    <div style={{
                        width: 40, height: 4,
                        background: 'var(--color-border, #374151)',
                        borderRadius: 99,
                    }} />
                </div>

                <div style={{ padding: '12px 20px 28px' }}>
                    {/* Title */}
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 'var(--space-2, 8px)',
                        marginBottom: 'var(--space-4, 16px)',
                    }}>
                        {accentColor && (
                            <div style={{
                                width: 6, height: 40,
                                background: accentColor,
                                borderRadius: 99, flexShrink: 0,
                            }} />
                        )}
                        <div>
                            {subtitle && (
                                <div style={{
                                    fontSize: 'var(--text-xs, 11px)',
                                    color: 'var(--color-text-dim, #6b7280)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.06em',
                                }}>
                                    {subtitle}
                                </div>
                            )}
                            <div style={{
                                fontSize: 'var(--text-lg, 20px)', fontWeight: 700,
                                color: 'var(--color-text, #f9fafb)',
                                lineHeight: 1.2,
                            }}>
                                {title}
                            </div>
                        </div>
                    </div>

                    {children}
                </div>
            </div>

            <style>{`
                @keyframes sheetSlideUp {
                    from { opacity: 0; transform: translateY(24px); }
                    to   { opacity: 1; transform: translateY(0); }
                }
            `}</style>
        </>
    );
}
