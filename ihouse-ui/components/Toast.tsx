'use client';

/**
 * Phase 550 — Toast Notification Component
 *
 * Global toast notification system.
 * Usage: import { toast } from '@/components/Toast';
 *        toast.success('Saved!');
 *        toast.error('Failed to save');
 *        toast.info('Processing...');
 */

import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastItem {
    id: number;
    type: ToastType;
    message: string;
    duration: number;
}

interface ToastContextType {
    addToast: (type: ToastType, message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

let _globalAdd: ((type: ToastType, message: string, duration?: number) => void) | null = null;

// Global imperative API
export const toast = {
    success: (msg: string, ms = 3000) => _globalAdd?.('success', msg, ms),
    error: (msg: string, ms = 5000) => _globalAdd?.('error', msg, ms),
    warning: (msg: string, ms = 4000) => _globalAdd?.('warning', msg, ms),
    info: (msg: string, ms = 3000) => _globalAdd?.('info', msg, ms),
};

const ICONS: Record<ToastType, string> = { success: '✓', error: '✗', warning: '⚠', info: 'ℹ' };
const COLORS: Record<ToastType, string> = {
    success: '#10b981',
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#3b82f6',
};

function ToastMessage({ item, onDismiss }: { item: ToastItem; onDismiss: () => void }) {
    useEffect(() => {
        const t = setTimeout(onDismiss, item.duration);
        return () => clearTimeout(t);
    }, [item.duration, onDismiss]);

    return (
        <div
            role="alert"
            onClick={onDismiss}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 18px',
                background: '#1f2937',
                border: `1px solid ${COLORS[item.type]}44`,
                borderLeft: `3px solid ${COLORS[item.type]}`,
                borderRadius: 10,
                color: '#f9fafb',
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
                animation: 'slideIn 0.2s ease-out',
                maxWidth: 380,
            }}
        >
            <span style={{ color: COLORS[item.type], fontSize: 16, fontWeight: 700 }}>{ICONS[item.type]}</span>
            <span>{item.message}</span>
        </div>
    );
}

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);
    let counter = 0;

    const addToast = useCallback((type: ToastType, message: string, duration = 3000) => {
        const id = Date.now() + counter++;
        setToasts(prev => [...prev.slice(-4), { id, type, message, duration }]);
    }, []);

    // Register global
    useEffect(() => { _globalAdd = addToast; return () => { _globalAdd = null; }; }, [addToast]);

    const dismiss = useCallback((id: number) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ addToast }}>
            {children}
            <div style={{
                position: 'fixed',
                bottom: 24,
                right: 24,
                zIndex: 9999,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
            }}>
                {toasts.map(t => (
                    <ToastMessage key={t.id} item={t} onDismiss={() => dismiss(t.id)} />
                ))}
            </div>
            <style>{`@keyframes slideIn { from { opacity: 0; transform: translateX(40px); } to { opacity: 1; transform: translateX(0); } }`}</style>
        </ToastContext.Provider>
    );
}

export function useToast() {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
    return ctx;
}
