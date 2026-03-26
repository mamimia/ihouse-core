/**
 * Phase 873 — Shared password validation rules
 * Phase 948b — i18n: labels returned from translation keys, not hardcoded English
 *
 * Canonical password policy for all surfaces:
 *   - 8+ characters
 *   - 1 uppercase letter
 *   - 1 number
 *   - 1 special character
 *
 * Used by: /register, /login/forgot, /update-password, /invite/[token], /profile, /get-started
 *
 * Usage (Phase 948b):
 *   const { t } = useLanguage();
 *   const pwRules = usePasswordRules(password, t);
 */

export interface PasswordRule {
    key: string;
    label: string;
    pass: boolean;
}

type TFn = (key: string) => string;

const DEFAULT_LABELS = {
    length:  '8+ characters',
    upper:   '1 uppercase letter',
    number:  '1 number',
    special: '1 special character',
};

/**
 * Phase 948b: Accept optional `t` translation function.
 * Falls back to English labels if t is not provided.
 */
export function usePasswordRules(password: string, t?: TFn): PasswordRule[] {
    const label = (key: keyof typeof DEFAULT_LABELS, tKey: string) =>
        t ? (t(tKey) || DEFAULT_LABELS[key]) : DEFAULT_LABELS[key];

    return [
        { key: 'length',  label: label('length',  'auth.pw_rule_length'),  pass: password.length >= 8 },
        { key: 'upper',   label: label('upper',   'auth.pw_rule_upper'),   pass: /[A-Z]/.test(password) },
        { key: 'number',  label: label('number',  'auth.pw_rule_number'),  pass: /[0-9]/.test(password) },
        { key: 'special', label: label('special', 'auth.pw_rule_special'), pass: /[^A-Za-z0-9]/.test(password) },
    ];
}

export function allPasswordRulesPass(password: string): boolean {
    return usePasswordRules(password).every(r => r.pass);
}
