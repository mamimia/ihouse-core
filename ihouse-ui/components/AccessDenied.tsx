'use client';

/**
 * Phase 862 P46 — AccessDenied component
 *
 * Displays a polished "access denied" message when a user lacks a delegated
 * capability. Used in page-level error boundaries to avoid blank screens
 * when CAPABILITY_DENIED is returned from the API.
 */

import React from 'react';

interface AccessDeniedProps {
  /** Human-readable capability name (e.g. "Financial", "Bookings") */
  capability?: string;
  /** Optional message override */
  message?: string;
  /** Optional action button */
  onBack?: () => void;
}

export default function AccessDenied({ capability, message, onBack }: AccessDeniedProps) {
  const displayMessage =
    message ||
    (capability
      ? `You do not have the "${capability}" capability. Contact your administrator to request access.`
      : 'You do not have permission to access this page. Contact your administrator.');

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '60vh',
      padding: '2rem',
      textAlign: 'center',
    }}>
      <div style={{
        width: 64,
        height: 64,
        borderRadius: '50%',
        background: 'rgba(239, 68, 68, 0.1)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: '1.5rem',
        fontSize: '1.75rem',
      }}>
        🔒
      </div>

      <h2 style={{
        fontSize: '1.25rem',
        fontWeight: 600,
        color: 'var(--text-primary, #f1f5f9)',
        marginBottom: '0.75rem',
      }}>
        Access Denied
      </h2>

      <p style={{
        fontSize: '0.95rem',
        color: 'var(--text-secondary, #94a3b8)',
        maxWidth: 420,
        lineHeight: 1.6,
        marginBottom: '1.5rem',
      }}>
        {displayMessage}
      </p>

      {onBack && (
        <button
          onClick={onBack}
          style={{
            padding: '0.6rem 1.5rem',
            borderRadius: '0.5rem',
            border: '1px solid rgba(148, 163, 184, 0.3)',
            background: 'rgba(148, 163, 184, 0.08)',
            color: 'var(--text-primary, #f1f5f9)',
            cursor: 'pointer',
            fontSize: '0.9rem',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={e => {
            (e.target as HTMLButtonElement).style.background = 'rgba(148, 163, 184, 0.15)';
          }}
          onMouseLeave={e => {
            (e.target as HTMLButtonElement).style.background = 'rgba(148, 163, 184, 0.08)';
          }}
        >
          ← Go Back
        </button>
      )}
    </div>
  );
}
