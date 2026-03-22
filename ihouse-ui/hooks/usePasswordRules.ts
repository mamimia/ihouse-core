/**
 * Phase 873 — Shared password validation rules
 *
 * Canonical password policy for all surfaces:
 *   - 8+ characters
 *   - 1 uppercase letter
 *   - 1 number
 *   - 1 special character
 *
 * Used by: /register, /login/reset, /update-password, /invite/[token], /profile, /get-started
 */

export interface PasswordRule {
    key: string;
    label: string;
    pass: boolean;
}

export function usePasswordRules(password: string): PasswordRule[] {
    return [
        { key: 'length', label: '8+ characters', pass: password.length >= 8 },
        { key: 'upper', label: '1 uppercase letter', pass: /[A-Z]/.test(password) },
        { key: 'number', label: '1 number', pass: /[0-9]/.test(password) },
        { key: 'special', label: '1 special character', pass: /[^A-Za-z0-9]/.test(password) },
    ];
}

export function allPasswordRulesPass(password: string): boolean {
    return usePasswordRules(password).every(r => r.pass);
}
