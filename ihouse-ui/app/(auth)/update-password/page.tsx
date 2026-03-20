'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch, performClientLogout } from '../../../lib/api';
import AuthCard from '../../../components/auth/AuthCard';

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
    padding: '12px 14px',
    background: 'var(--color-midnight, #171A1F)',
    border: '1px solid rgba(234,229,222,0.1)',
    borderRadius: 'var(--radius-md, 12px)',
    color: 'var(--color-stone, #EAE5DE)',
    fontSize: 'var(--text-sm, 14px)',
    transition: 'border-color 0.2s, box-shadow 0.2s',
    fontFamily: 'var(--font-sans, inherit)',
    boxSizing: 'border-box',
  };

  return (
    <AuthCard title="Set Your Password" subtitle="Please set a new password for your account to continue.">
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4, 16px)' }}>
        
        {error && (
            <div style={{
                background: 'rgba(155,58,58,0.1)',
                border: '1px solid rgba(155,58,58,0.25)',
                borderRadius: 'var(--radius-md, 12px)',
                padding: '10px 14px',
                fontSize: 'var(--text-sm, 14px)',
                color: '#EF4444',
            }}>
                ⚠ {error}
            </div>
        )}

        <div>
          <label style={{
              display: 'block',
              fontSize: 'var(--text-xs, 12px)',
              fontWeight: 600,
              color: 'rgba(234,229,222,0.5)',
              marginBottom: 'var(--space-2, 8px)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
          }}>
            New Password
          </label>
          <input
            className="auth-input"
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setError(null); }}
            style={inputStyle}
            placeholder="Enter new password"
            required
            minLength={6}
          />
        </div>

        <div>
          <label style={{
              display: 'block',
              fontSize: 'var(--text-xs, 12px)',
              fontWeight: 600,
              color: 'rgba(234,229,222,0.5)',
              marginBottom: 'var(--space-2, 8px)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
          }}>
            Confirm Password
          </label>
          <input
            className="auth-input"
            type="password"
            value={confirmPassword}
            onChange={(e) => { setConfirmPassword(e.target.value); setError(null); }}
            style={inputStyle}
            placeholder="Confirm new password"
            required
            minLength={6}
          />
        </div>

        <button
            type="submit"
            className="auth-btn"
            disabled={loading || !password || !confirmPassword}
            style={{
                width: '100%',
                padding: '14px',
                background: 'var(--color-moss, #334036)',
                border: 'none',
                borderRadius: 'var(--radius-md, 12px)',
                color: 'var(--color-white, #F8F6F2)',
                fontSize: 'var(--text-base, 16px)',
                fontWeight: 600,
                fontFamily: 'var(--font-brand, "Inter", sans-serif)',
                letterSpacing: '-0.01em',
                cursor: loading || !password || !confirmPassword ? 'not-allowed' : 'pointer',
                opacity: loading || !password || !confirmPassword ? 0.4 : 1,
                transition: 'all 0.2s',
                marginTop: 'var(--space-1, 4px)',
                minHeight: 48,
            }}
        >
          {loading ? 'Updating...' : 'Update Password'}
        </button>
      </form>
    </AuthCard>
  );
}
