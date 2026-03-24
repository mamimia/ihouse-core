'use client';

/**
 * Phase 863 — MutationGuard
 *
 * Wraps page content and blocks all interactive mutations when Preview Mode is active.
 * Applies a CSS overlay + pointer-events:none on all buttons, forms, and inputs.
 *
 * Usage:
 *   <MutationGuard>
 *     <YourPageContent />
 *   </MutationGuard>
 *
 * Or use the hook directly:
 *   const { isMutationDisabled } = useMutationGuard();
 *   <button disabled={isMutationDisabled}>Save</button>
 */

import { usePreview } from '../lib/PreviewContext';

export function useMutationGuard() {
    const { isPreviewActive, previewRole } = usePreview();
    return {
        /** True when all mutations should be blocked */
        isMutationDisabled: isPreviewActive,
        previewRole,
    };
}

export default function MutationGuard({ children }: { children: React.ReactNode }) {
    const { isPreviewActive } = usePreview();

    if (!isPreviewActive) {
        return <>{children}</>;
    }

    return (
        <>
            {/* Global style injection to disable all interactive controls in preview mode */}
            <style>{`
                .preview-guard button:not(#preview-mode-banner button),
                .preview-guard input[type="submit"],
                .preview-guard [role="button"],
                .preview-guard form {
                    pointer-events: none !important;
                    opacity: 0.5 !important;
                    cursor: not-allowed !important;
                }
                .preview-guard a[href*="/edit"],
                .preview-guard a[href*="/new"],
                .preview-guard a[href*="/create"] {
                    pointer-events: none !important;
                    opacity: 0.5 !important;
                }
            `}</style>
            <div className="preview-guard">
                {children}
            </div>
        </>
    );
}
