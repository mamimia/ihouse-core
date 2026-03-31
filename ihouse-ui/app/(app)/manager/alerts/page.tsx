'use client';

/**
 * Phase 1033 — /manager/alerts
 * Operational Manager alert surface.
 *
 * SCAFFOLD STUB — Step 1 only.
 * Full alert list, drill-down, and intervention flow will be built in Step 3.
 *
 * Protected by DraftGuard: admin only until baseline surface is approved and
 * explicitly wired into the live manager navigation.
 */

import DraftGuard from '../../../../components/DraftGuard';

export default function ManagerAlertsPage() {
  return (
    <DraftGuard>
      <div style={{
        maxWidth: 900, margin: '0 auto', padding: '40px 20px',
        textAlign: 'center', color: 'var(--color-text-dim)',
      }}>
        <div style={{ fontSize: 36, marginBottom: 16 }}>🚨</div>
        <h1 style={{
          margin: '0 0 8px', fontSize: 'var(--text-xl)',
          fontWeight: 800, color: 'var(--color-text)',
          fontFamily: "'Manrope', sans-serif",
        }}>
          Alerts
        </h1>
        <p style={{ margin: 0, fontSize: 'var(--text-sm)' }}>
          Phase 1033 scaffold — Alert surface builds in Step 3.
        </p>
      </div>
    </DraftGuard>
  );
}
