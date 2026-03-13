'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface Job {
    name: string;
    description: string;
    interval_hours: number;
}

interface HistoryEntry {
    job_id: string;
    job_name: string;
    status: string;
    started_at: string;
    completed_at: string | null;
}

export default function ScheduledJobsPage() {
    const [jobs, setJobs] = useState<Record<string, Job>>({});
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getSchedulerStatus?.() || { jobs: {} };
            setJobs((res.jobs || {}) as Record<string, Job>);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);
    const jobList = Object.entries(jobs);

    return (
        <div style={{ maxWidth: 900 }}>
            <div style={{ marginBottom: 'var(--space-8)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>Background automation</p>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--color-text)' }}>
                    Scheduled <span style={{ color: 'var(--color-primary)' }}>Jobs</span>
                </h1>
            </div>

            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                {!loading && jobList.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No jobs registered.</p>}
                {jobList.map(([name, job]) => (
                    <div key={name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-2)' }}>
                        <div>
                            <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>{name.replace(/_/g, ' ')}</div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{job.description}</div>
                        </div>
                        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, padding: '2px 8px', borderRadius: 'var(--radius-full)', background: 'var(--color-primary)22', color: 'var(--color-primary)', fontFamily: 'var(--font-mono)' }}>
                            every {job.interval_hours >= 1 ? `${job.interval_hours}h` : `${Math.round(job.interval_hours * 60)}m`}
                        </span>
                    </div>
                ))}
            </div>

            <div style={{ paddingTop: 'var(--space-6)', fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', marginTop: 'var(--space-6)' }}>
                iHouse Core — Scheduled Jobs · Phase 523
            </div>
        </div>
    );
}
