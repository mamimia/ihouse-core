'use client';

/**
 * Phase 1033 — /manager/team
 * Operational team overview: workers, coverage gaps, task load.
 * Calls GET /manager/team (new Phase 1033 endpoint).
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../../../../lib/api';
import DraftGuard from '../../../../components/DraftGuard';

type Worker = {
  user_id: string;
  display_name: string;
  role: string;
  is_active: boolean;
  lane: string;
  priority: number;
  designation: string;
  open_tasks_on_property: number;
  contact: { line: string; phone: string; email: string };
};

type LaneCoverage = {
  has_primary: boolean;
  primary_user_id?: string | null;
  backup_user_id?: string | null;
};

type PropertyTeam = {
  property_id: string;
  workers: Worker[];
  lane_coverage: Record<string, LaneCoverage>;
  coverage_gaps: string[];
};

const LANES = ['CLEANING', 'MAINTENANCE', 'CHECKIN_CHECKOUT'];
const LANE_LABELS: Record<string, string> = {
  CLEANING: 'Cleaning',
  MAINTENANCE: 'Maintenance',
  CHECKIN_CHECKOUT: 'Check-in/out',
};

export default function ManagerTeamPage() {
  const [properties, setProperties] = useState<PropertyTeam[]>([]);
  const [totalWorkers, setTotalWorkers] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedProp, setExpandedProp] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ properties: PropertyTeam[]; total_workers: number }>('/manager/team');
      setProperties(res.properties || []);
      setTotalWorkers(res.total_workers || 0);
      if (res.properties?.length === 1) {
        setExpandedProp(res.properties[0].property_id);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load team');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const totalGaps = properties.reduce((acc, p) => acc + p.coverage_gaps.length, 0);

  if (loading) return <DraftGuard><div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-dim)' }}>Loading team…</div></DraftGuard>;

  return (
    <DraftGuard>
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 20px' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 800, color: 'var(--color-text)', fontFamily: "'Manrope', sans-serif" }}>
          Team
        </h1>
        <div style={{ display: 'flex', gap: 20, marginTop: 8, flexWrap: 'wrap' }}>
          <Stat label="Properties" value={properties.length} />
          <Stat label="Workers" value={totalWorkers} />
          <Stat label="Coverage gaps" value={totalGaps} color={totalGaps > 0 ? '#ef4444' : '#10b981'} />
        </div>
      </div>

      {error && (
        <div style={{ padding: 16, borderRadius: 8, background: '#ef444414', color: '#ef4444', marginBottom: 16, fontSize: 'var(--text-sm)' }}>
          {error}
        </div>
      )}

      {properties.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-faint)' }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>👥</div>
          <div>No assigned properties found</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {properties.map(prop => (
            <PropertyCard
              key={prop.property_id}
              prop={prop}
              expanded={expandedProp === prop.property_id}
              onToggle={() => setExpandedProp(prev => prev === prop.property_id ? null : prop.property_id)}
            />
          ))}
        </div>
      )}
    </div>
    </DraftGuard>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 22, fontWeight: 800, color: color || 'var(--color-text)', fontFamily: "'Manrope', sans-serif", lineHeight: 1 }}>
        {value}
      </span>
      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{label}</span>
    </div>
  );
}

function PropertyCard({ prop, expanded, onToggle }: { prop: PropertyTeam; expanded: boolean; onToggle: () => void }) {
  const hasGaps = prop.coverage_gaps.length > 0;

  return (
    <div style={{
      borderRadius: 12, border: `1px solid ${hasGaps ? '#ef444440' : 'var(--color-border)'}`,
      background: 'var(--color-surface)', overflow: 'hidden',
    }}>
      {/* Property header */}
      <button onClick={onToggle} style={{
        width: '100%', padding: '14px 18px', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', background: 'transparent', border: 'none',
        cursor: 'pointer', textAlign: 'left', gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {hasGaps && (
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
              background: '#ef444420', color: '#ef4444',
            }}>
              {prop.coverage_gaps.length} GAP{prop.coverage_gaps.length > 1 ? 'S' : ''}
            </span>
          )}
          <span style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--color-text)', fontFamily: "'Manrope', sans-serif" }}>
            {prop.property_id}
          </span>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
            {prop.workers.length} worker{prop.workers.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Lane coverage pills */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {LANES.map(lane => {
            const cov = prop.lane_coverage[lane];
            return (
              <span key={lane} style={{
                fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                background: cov?.has_primary ? '#10b98120' : '#f9731620',
                color: cov?.has_primary ? '#10b981' : '#f97316',
              }}>
                {LANE_LABELS[lane]} {cov?.has_primary ? '✓' : '!'}
              </span>
            );
          })}
        </div>

        <span style={{ color: 'var(--color-text-faint)', fontSize: '0.85em', flexShrink: 0 }}>
          {expanded ? '▲' : '▼'}
        </span>
      </button>

      {/* Expanded worker list */}
      {expanded && (
        <div style={{ borderTop: '1px solid var(--color-border)', padding: '12px 18px' }}>
          {prop.workers.length === 0 ? (
            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', margin: 0 }}>No workers assigned</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {prop.workers.map(w => (
                <WorkerRow key={`${w.user_id}-${w.lane}`} worker={w} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function WorkerRow({ worker: w }: { worker: Worker }) {
  const isPrimary = w.priority === 1;
  const isBackup = w.priority === 2;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px',
      borderRadius: 8, background: 'var(--color-bg)', border: '1px solid var(--color-border)',
      flexWrap: 'wrap',
    }}>
      {/* Designation badge */}
      <span style={{
        fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
        background: isPrimary ? '#10b98118' : isBackup ? '#3b82f618' : '#6b72801a',
        color: isPrimary ? '#10b981' : isBackup ? '#3b82f6' : '#6b7280',
        flexShrink: 0,
      }}>
        {w.designation}
      </span>

      {/* Name + lane */}
      <div style={{ flex: 1, minWidth: 120 }}>
        <div style={{
          fontWeight: 600, fontSize: 'var(--text-sm)', color: w.is_active ? 'var(--color-text)' : 'var(--color-text-faint)',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          {w.display_name}
          {!w.is_active && <span style={{ fontSize: 10, color: '#ef4444', fontWeight: 700 }}>INACTIVE</span>}
        </div>
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
          {LANE_LABELS[w.lane] || w.lane}
        </div>
      </div>

      {/* Open tasks */}
      {w.open_tasks_on_property > 0 && (
        <span style={{
          fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
          background: '#f59e0b18', color: '#f59e0b',
        }}>
          {w.open_tasks_on_property} task{w.open_tasks_on_property !== 1 ? 's' : ''}
        </span>
      )}

      {/* Contact */}
      <div style={{ display: 'flex', gap: 6 }}>
        {w.contact.phone && (
          <a href={`tel:${w.contact.phone}`} style={contactLink}>📞</a>
        )}
        {w.contact.line && (
          <a href={`https://line.me/ti/p/${w.contact.line}`} target="_blank" rel="noreferrer" style={contactLink}>
            💬
          </a>
        )}
        {w.contact.email && (
          <a href={`mailto:${w.contact.email}`} style={contactLink}>✉️</a>
        )}
      </div>
    </div>
  );
}

const contactLink: React.CSSProperties = {
  width: 30, height: 30, borderRadius: 8, border: '1px solid var(--color-border)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  textDecoration: 'none', fontSize: '0.85em', background: 'var(--color-surface)',
  transition: 'background 0.15s',
};
