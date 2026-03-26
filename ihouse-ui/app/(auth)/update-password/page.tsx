'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch, performClientLogout, getToken, setToken } from '../../../lib/api';
import { getRoleRoute } from '../../../lib/roleRoute';
import AuthCard from '../../../components/auth/AuthCard';
import PasswordInput from '../../../components/auth/PasswordInput';
import { usePasswordRules } from '@/hooks/usePasswordRules';
import { useLanguage } from '../../../lib/LanguageContext';

export default function UpdatePasswordPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const [userRole, setUserRole] = useState<string>('');
  const [userName, setUserName] = useState<string>('');

  // Decode JWT to extract role for welcome copy
  useEffect(() => {
    try {
      const token = getToken();
      if (!token) return;
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUserRole(payload.role || '');
      setUserName(payload.full_name || payload.display_name || '');
    } catch { /* ignore decode errors */ }
  }, []);

  const pwRules = usePasswordRules(password);
  const allRulesPass = pwRules.every(r => r.pass);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!allRulesPass) {
      setError('Password does not meet all requirements.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await apiFetch<{ message: string, token?: string, expires_in?: number }>('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ new_password: password })
      });
      
      if (data.token) {
        setToken(data.token);
        const isHttps = typeof window !== 'undefined' && window.location.protocol === 'https:';
        document.cookie = `ihouse_token=${data.token}; path=/; max-age=${data.expires_in || 86400}; SameSite=Lax${isHttps ? '; Secure' : ''}`;
        
        sessionStorage.setItem('ihouse_welcome', 'true');
        
        window.location.href = getRoleRoute(data.token);
      } else {
        alert('Password updated successfully. Please log in again.');
        performClientLogout('/login');
      }
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

  const ROLE_LABELS: Record<string, string> = {
    worker: 'Staff Member',
    cleaner: 'Cleaner',
    maintenance: 'Maintenance',
    checkin: 'Check-in Agent',
    checkout: 'Check-out Agent',
    admin: 'Administrator',
    manager: 'Operations Manager',
    ops: 'Operations Manager',
    owner: 'Property Owner',
  };
  const roleLabel = ROLE_LABELS[userRole] || '';
  const defaultWelcomeTitle = userName ? `Welcome, ${userName}` : 'Set Your Password';
  const defaultWelcomeSubtitle = roleLabel
    ? `You're joining Domaniqo as ${roleLabel}. Please set a secure password to continue.`
    : 'Please set a new password for your account to continue.';

  const welcomeTitle = userName ? t('auth.welcome_name').replace('{name}', userName) : t('auth.set_your_password');
  const welcomeSubtitle = roleLabel 
    ? t('auth.joining_as_role').replace('{role}', roleLabel)
    : t('auth.set_password_desc');

  return (
    <AuthCard title={welcomeTitle} subtitle={welcomeSubtitle}>
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
            {t('auth.new_password')}
          </label>
          <PasswordInput
            id="input-new-password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setError(null); }}
            onFocus={() => setPasswordFocused(true)}
            onBlur={() => setPasswordFocused(false)}
            placeholder={t('auth.create_strong_password')}
            autoComplete="new-password"
            autoFocus
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
            {t('auth.confirm_password')}
          </label>
          <PasswordInput
            id="input-confirm-password"
            value={confirmPassword}
            onChange={(e) => { setConfirmPassword(e.target.value); setError(null); }}
            placeholder={t('auth.reenter_password')}
            autoComplete="new-password"
          />
        </div>

        {/* Phase 873: Live password rules checklist */}
        {(passwordFocused || password.length > 0) && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', fontSize: 11, lineHeight: 1.8 }}>
                {pwRules.map(r => (
                    <span key={r.key} style={{
                        color: password.length === 0
                            ? 'rgba(234,229,222,0.25)'
                            : r.pass ? '#4A7C59' : 'rgba(234,229,222,0.3)',
                        transition: 'color 0.2s',
                    }}>
                        {password.length > 0 && r.pass ? '✓' : '○'} {r.label}
                    </span>
                ))}
            </div>
        )}
        {confirmPassword.length > 0 && password !== confirmPassword && (
            <div style={{ fontSize: 12, color: '#D64545' }}>✗ Passwords do not match</div>
        )}
        {confirmPassword.length > 0 && password === confirmPassword && password.length > 0 && (
            <div style={{ fontSize: 12, color: '#4A7C59' }}>✓ Passwords match</div>
        )}

        <button
            type="submit"
            className="auth-btn"
            disabled={loading || !allRulesPass || password !== confirmPassword}
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
                cursor: loading || !allRulesPass || password !== confirmPassword ? 'not-allowed' : 'pointer',
                opacity: loading || !allRulesPass || password !== confirmPassword ? 0.4 : 1,
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
