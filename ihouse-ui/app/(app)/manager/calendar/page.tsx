'use client';

/**
 * Phase 1033 — /manager/calendar
 * Temporal coordination calendar for Operational Manager.
 *
 * Shows booking blocks + task markers per day.
 * Click a date → task list for that day.
 * Click a booking → coordination detail (not an editor).
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../../../../lib/api';
import Link from 'next/link';
import DraftGuard from '../../../../components/DraftGuard';

type Booking = {
  id: string;
  reservation_ref?: string;
  property_id?: string;
  check_in?: string;
  check_out?: string;
  status?: string;
  guest_first_name?: string;
};

type Task = {
  id: string;
  task_kind: string;
  status: string;
  property_id?: string;
  due_date?: string | null;
  title?: string | null;
};

function toDateStr(d: Date) {
  return d.toISOString().slice(0, 10);
}

function datesInMonth(year: number, month: number): Date[] {
  const dates: Date[] = [];
  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  for (let d = 1; d <= last.getDate(); d++) {
    dates.push(new Date(year, month, d));
  }
  return dates;
}

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const TASK_LANE_COLOR: Record<string, string> = {
  CLEANING: '#10b981',
  CHECKIN_PREP: '#3b82f6',
  GUEST_WELCOME: '#8b5cf6',
  CHECKOUT_VERIFY: '#f97316',
  MAINTENANCE: '#ef4444',
  GENERAL: '#6b7280',
};

export default function ManagerCalendarPage() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [bRes, tRes] = await Promise.all([
        api.get<{ bookings?: Booking[]; data?: Booking[] }>('/bookings').catch(() => ({ bookings: [] as Booking[], data: [] as Booking[] })),
        api.get<{ groups: Record<string, Task[]> }>('/manager/tasks').catch(() => ({ groups: {} as Record<string, Task[]> })),
      ]);
      setBookings(bRes.bookings || bRes.data || []);
      const groups = tRes.groups || {};
      setTasks([
        ...(groups.pending || []),
        ...(groups.acknowledged || []),
        ...(groups.in_progress || []),
        ...(groups.manager_executing || []),
      ]);
    } catch {
      // graceful — calendar degrades to booking-only
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const prevMonth = () => {
    if (month === 0) { setYear(y => y - 1); setMonth(11); }
    else setMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setYear(y => y + 1); setMonth(0); }
    else setMonth(m => m + 1);
  };

  const dates = datesInMonth(year, month);
  const firstDayOfWeek = new Date(year, month, 1).getDay(); // 0=Sun

  // Index: dateStr → bookings that span that date
  const bookingsByDate: Record<string, Booking[]> = {};
  for (const b of bookings) {
    if (!b.check_in || !b.check_out) continue;
    const ci = new Date(b.check_in);
    const co = new Date(b.check_out);
    let cur = new Date(ci);
    while (cur <= co) {
      const ds = toDateStr(cur);
      if (!bookingsByDate[ds]) bookingsByDate[ds] = [];
      bookingsByDate[ds].push(b);
      cur.setDate(cur.getDate() + 1);
    }
  }

  // Index: dateStr → tasks due that date
  const tasksByDate: Record<string, Task[]> = {};
  for (const t of tasks) {
    if (!t.due_date) continue;
    const ds = t.due_date.slice(0, 10);
    if (!tasksByDate[ds]) tasksByDate[ds] = [];
    tasksByDate[ds].push(t);
  }

  const selectedBookings = selectedDate ? bookingsByDate[selectedDate] || [] : [];
  const selectedTasks = selectedDate ? tasksByDate[selectedDate] || [] : [];

  return (
    <DraftGuard>
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '24px 20px' }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 800, color: 'var(--color-text)', fontFamily: "'Manrope', sans-serif" }}>
          Calendar
        </h1>
        <p style={{ margin: '4px 0 0', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>
          Coordination view — booking windows + operational tasks
        </p>
      </div>

      {/* Month nav */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <button onClick={prevMonth} style={navBtn}>←</button>
        <span style={{ fontWeight: 700, fontSize: 'var(--text-base)', color: 'var(--color-text)', minWidth: 120, textAlign: 'center' }}>
          {MONTH_NAMES[month]} {year}
        </span>
        <button onClick={nextMonth} style={navBtn}>→</button>
        <button onClick={() => { setYear(today.getFullYear()); setMonth(today.getMonth()); }} style={{ ...navBtn, marginLeft: 8, fontSize: 11 }}>Today</button>
      </div>

      {loading && <div style={{ textAlign: 'center', padding: 20, color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</div>}

      {/* Calendar grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
        {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => (
          <div key={d} style={{
            padding: '6px 4px', textAlign: 'center', fontSize: 10, fontWeight: 700,
            color: 'var(--color-text-dim)', letterSpacing: '0.05em',
          }}>{d}</div>
        ))}

        {/* Padding cells for first day */}
        {Array.from({ length: firstDayOfWeek }).map((_, i) => (
          <div key={`pad-${i}`} />
        ))}

        {dates.map(date => {
          const ds = toDateStr(date);
          const dayBookings = bookingsByDate[ds] || [];
          const dayTasks = tasksByDate[ds] || [];
          const isToday = ds === toDateStr(today);
          const isSelected = ds === selectedDate;

          return (
            <button
              key={ds}
              onClick={() => setSelectedDate(prev => prev === ds ? null : ds)}
              style={{
                padding: '6px 4px', minHeight: 72, borderRadius: 8,
                border: isSelected ? '2px solid var(--color-primary)' : '1px solid var(--color-border)',
                background: isSelected ? 'rgba(59,130,246,0.05)' : isToday ? 'rgba(59,130,246,0.03)' : 'var(--color-bg)',
                cursor: 'pointer', textAlign: 'left', transition: 'all 0.12s',
                position: 'relative', verticalAlign: 'top',
              }}
            >
              {/* Day number */}
              <div style={{
                fontWeight: isToday ? 800 : 500,
                fontSize: isToday ? 13 : 12,
                color: isToday ? 'var(--color-primary)' : 'var(--color-text)',
                marginBottom: 4,
              }}>
                {date.getDate()}
              </div>

              {/* Booking presence indicator */}
              {dayBookings.length > 0 && (
                <div style={{ fontSize: 9, color: '#8b5cf6', fontWeight: 600, marginBottom: 2 }}>
                  {dayBookings.length} stay{dayBookings.length > 1 ? 's' : ''}
                </div>
              )}

              {/* Task dots */}
              {dayTasks.slice(0, 4).map(t => (
                <div key={t.id} style={{
                  width: 6, height: 6, borderRadius: '50%', display: 'inline-block', margin: '1px',
                  background: TASK_LANE_COLOR[t.task_kind] || '#6b7280',
                }} />
              ))}
              {dayTasks.length > 4 && (
                <span style={{ fontSize: 8, color: 'var(--color-text-dim)', display: 'block' }}>+{dayTasks.length - 4}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Selected date detail */}
      {selectedDate && (
        <div style={{
          marginTop: 20, padding: 20, borderRadius: 12,
          border: '1px solid var(--color-border)', background: 'var(--color-surface)',
        }}>
          <h3 style={{ margin: '0 0 14px', fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--color-text)' }}>
            {new Date(selectedDate).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </h3>

          {selectedBookings.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-dim)', marginBottom: 8, letterSpacing: '0.05em' }}>
                STAYS ({selectedBookings.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {selectedBookings.map(b => (
                  <Link key={b.id} href="/manager/bookings" style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 12px', borderRadius: 8, background: 'var(--color-bg)',
                    border: '1px solid var(--color-border)', textDecoration: 'none',
                  }}>
                    <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                      {b.reservation_ref || b.id.slice(0, 8)}
                    </span>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{b.property_id}</span>
                    {b.guest_first_name && (
                      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{b.guest_first_name}</span>
                    )}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {selectedTasks.length > 0 && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-text-dim)', marginBottom: 8, letterSpacing: '0.05em' }}>
                TASKS ({selectedTasks.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {selectedTasks.map(t => (
                  <Link key={t.id} href="/manager/tasks" style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 12px', borderRadius: 8, background: 'var(--color-bg)',
                    border: '1px solid var(--color-border)', textDecoration: 'none',
                  }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: TASK_LANE_COLOR[t.task_kind] || '#6b7280', flexShrink: 0 }} />
                    <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
                      {t.title || t.task_kind}
                    </span>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{t.property_id}</span>
                    <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3, background: '#6b728018', color: '#6b7280' }}>
                      {t.status}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {selectedBookings.length === 0 && selectedTasks.length === 0 && (
            <p style={{ color: 'var(--color-text-faint)', fontSize: 'var(--text-sm)', margin: 0 }}>No bookings or tasks this day.</p>
          )}
        </div>
      )}
    </div>
    </DraftGuard>
  );
}

const navBtn: React.CSSProperties = {
  padding: '6px 14px', borderRadius: 8,
  border: '1px solid var(--color-border)', background: 'var(--color-bg)',
  cursor: 'pointer', color: 'var(--color-text)', fontSize: 'var(--text-sm)',
  transition: 'background 0.12s',
};
