'use client';

/**
 * Phase 582 — Accessibility Utilities
 *
 * Reusable accessibility helpers for interactive elements:
 *   - Keyboard navigation (Enter/Space as click)
 *   - Focus trap for modals
 *   - Screen reader announcements
 *   - ARIA live regions
 */

import { useEffect, useRef, useCallback, KeyboardEvent } from 'react';

// ---------------------------------------------------------------------------
// Keyboard Handlers
// ---------------------------------------------------------------------------

/**
 * Make a div behave like a button for keyboard users.
 * Returns onKeyDown handler for Enter/Space to trigger onClick.
 */
export function onKeyboardClick(handler: () => void) {
    return (e: KeyboardEvent) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handler();
        }
    };
}

/**
 * Returns props to make a div keyboard-accessible as a button.
 */
export function accessibleButton(onClick: () => void, label: string) {
    return {
        role: 'button' as const,
        tabIndex: 0,
        'aria-label': label,
        onClick,
        onKeyDown: onKeyboardClick(onClick),
        style: { cursor: 'pointer' },
    };
}

// ---------------------------------------------------------------------------
// Focus Trap (for modals/dialogs)
// ---------------------------------------------------------------------------

/**
 * Hook to trap focus within a container element.
 * Used for modals to prevent Tab from leaving the dialog.
 */
export function useFocusTrap(active: boolean) {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!active || !containerRef.current) return;

        const container = containerRef.current;
        const focusable = container.querySelectorAll<HTMLElement>(
            'a[href], button, textarea, input, select, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        // Focus first element
        first.focus();

        const handleKeyDown = (e: globalThis.KeyboardEvent) => {
            if (e.key !== 'Tab') return;

            if (e.shiftKey) {
                if (document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        };

        container.addEventListener('keydown', handleKeyDown);
        return () => container.removeEventListener('keydown', handleKeyDown);
    }, [active]);

    return containerRef;
}

// ---------------------------------------------------------------------------
// Screen Reader Announcements
// ---------------------------------------------------------------------------

let _announcer: HTMLElement | null = null;

function getAnnouncer(): HTMLElement {
    if (_announcer) return _announcer;
    _announcer = document.createElement('div');
    _announcer.setAttribute('aria-live', 'polite');
    _announcer.setAttribute('aria-atomic', 'true');
    _announcer.setAttribute('role', 'status');
    Object.assign(_announcer.style, {
        position: 'absolute',
        width: '1px',
        height: '1px',
        padding: '0',
        margin: '-1px',
        overflow: 'hidden',
        clip: 'rect(0, 0, 0, 0)',
        border: '0',
    });
    document.body.appendChild(_announcer);
    return _announcer;
}

/**
 * Announce a message to screen readers.
 */
export function announce(message: string, priority: 'polite' | 'assertive' = 'polite'): void {
    if (typeof document === 'undefined') return;
    const el = getAnnouncer();
    el.setAttribute('aria-live', priority);
    el.textContent = '';
    // Use setTimeout to ensure the DOM change is noticed
    setTimeout(() => {
        el.textContent = message;
    }, 100);
}

// ---------------------------------------------------------------------------
// Skip Link (Phase 582)
// ---------------------------------------------------------------------------

/**
 * SkipLink component for keyboard users to skip navigation.
 */
export function SkipLink({ targetId = 'main-content' }: { targetId?: string }) {
    return (
        <a
            href={`#${targetId}`}
            style={{
                position: 'absolute',
                top: '-40px',
                left: 0,
                zIndex: 10000,
                background: 'var(--color-primary)',
                color: '#fff',
                padding: 'var(--space-2) var(--space-4)',
                fontSize: 'var(--text-sm)',
                fontWeight: 600,
                textDecoration: 'none',
                borderRadius: '0 0 var(--radius-md) 0',
                transition: 'top 0.2s ease',
            }}
            onFocus={(e) => { (e.target as HTMLElement).style.top = '0'; }}
            onBlur={(e) => { (e.target as HTMLElement).style.top = '-40px'; }}
        >
            Skip to main content
        </a>
    );
}
