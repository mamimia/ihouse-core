'use client';

/**
 * Phase 1033 — /manager/streams
 * Operational Manager live stream / activity feed surface.
 *
 * SCAFFOLD STUB — Step 1 only.
 * Full stream view will be built in Step 4.
 *
 * Protected by DraftGuard: admin only until baseline surface is approved and
 * explicitly wired into the live manager navigation.
 */

import DraftGuard from '../../../../components/DraftGuard';

export default function ManagerStreamsPage() {
  return (
    <DraftGuard>
      <div style={{
        maxWidth: 900, margin: '0 auto', padding: '40px 20px',
        textAlign: 'center', color: 'var(--color-text-dim)',
      }}>
        <div style={{ fontSize: 36, marginBottom: 16 }}>📡</div>
        <h1 style={{
          margin: '0 0 8px', fontSize: 'var(--text-xl)',
          fontWeight: 800, color: 'var(--color-text)',
          fontFamily: "'Manrope', sans-serif",
        }}>
          Live Stream
        </h1>
        <p style={{ margin: 0, fontSize: 'var(--text-sm)' }}>
          Phase 1033 scaffold — Stream view builds in Step 4.
        </p>
      </div>
    </DraftGuard>
  );
}
