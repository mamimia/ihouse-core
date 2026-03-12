/*
 * Phase 367 — Error Boundary Component
 *
 * React error boundary to catch runtime errors in child components
 * and display a graceful fallback UI instead of a blank screen.
 */
'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
    children: ReactNode;
    fallbackMessage?: string;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('[ErrorBoundary] Caught error:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{
                    minHeight: '40vh',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontFamily: "'Inter', system-ui, sans-serif",
                    color: '#e2e8f0',
                    gap: 16,
                    padding: 32,
                }}>
                    <div style={{
                        width: 64, height: 64, borderRadius: '50%',
                        background: '#1e293b', display: 'flex',
                        alignItems: 'center', justifyContent: 'center',
                        fontSize: 28,
                    }}>⚠</div>
                    <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
                        {this.props.fallbackMessage || 'Something went wrong'}
                    </h2>
                    <p style={{ margin: 0, color: '#64748b', fontSize: 13, maxWidth: 400, textAlign: 'center' }}>
                        An unexpected error occurred. Try refreshing the page.
                    </p>
                    {this.state.error && (
                        <code style={{
                            fontSize: 11, color: '#ef4444', background: '#1e293b',
                            padding: '8px 14px', borderRadius: 8, maxWidth: 500,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                            {this.state.error.message}
                        </code>
                    )}
                    <button
                        id="error-boundary-retry"
                        onClick={() => {
                            this.setState({ hasError: false, error: null });
                            window.location.reload();
                        }}
                        style={{
                            marginTop: 8, padding: '8px 24px', borderRadius: 8,
                            border: 'none', background: '#6366f1', color: '#fff',
                            fontSize: 13, fontWeight: 600, cursor: 'pointer',
                        }}
                    >
                        ↻ Reload Page
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
