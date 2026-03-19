'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch, performClientLogout } from '@/lib/api';
import AuthCard from '@/components/AuthCard';
import Button from '@/components/Button';
import ErrorDisplay from '@/components/ErrorDisplay';

export default function UpdatePasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await apiFetch<{ message: string }>('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ new_password: password })
      });
      alert('Password updated successfully. Please log in again.');
      performClientLogout('/login');
    } catch (err: any) {
      setError(err.message || 'Failed to update password');
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '12px',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--color-border)',
    background: 'var(--color-surface-2)',
    color: 'var(--color-text)',
    fontSize: 'var(--text-base)',
    outline: 'none',
    boxSizing: 'border-box'
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 'var(--space-4)',
      background: 'var(--color-surface, #fff)',
    }}>
      <AuthCard title="Set Your Password">
        <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-5)', textAlign: 'center' }}>
          Please set a new password for your account to continue.
        </p>

        {error && <ErrorDisplay error={error} style={{ marginBottom: 'var(--space-4)' }} />}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div>
            <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 6, textTransform: 'uppercase' }}>
              New Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={inputStyle}
              placeholder="Enter new password"
              required
              minLength={6}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text-dim)', marginBottom: 6, textTransform: 'uppercase' }}>
              Confirm Password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              style={inputStyle}
              placeholder="Confirm new password"
              required
              minLength={6}
            />
          </div>

          <Button type="submit" variant="primary" loading={loading} style={{ width: '100%', marginTop: 'var(--space-2)' }}>
            Update Password
          </Button>
        </form>
      </AuthCard>
    </div>
  );
}
