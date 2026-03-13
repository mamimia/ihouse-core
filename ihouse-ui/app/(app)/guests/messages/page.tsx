'use client';

/**
 * Phase 534 — Guest Messaging Hub
 * Route: /guests/messages
 *
 * Conversation list per booking, AI suggestion panel, template picker.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface Conversation {
    booking_ref: string;
    guest_name: string;
    property_id: string;
    last_message: string;
    last_timestamp: string;
    unread: number;
    channel: string;
}

interface Message {
    id: string;
    direction: 'inbound' | 'outbound';
    content: string;
    timestamp: string;
    channel: string;
}

export default function GuestMessagingPage() {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [selectedRef, setSelectedRef] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [loading, setLoading] = useState(true);
    const [msgLoading, setMsgLoading] = useState(false);
    const [draft, setDraft] = useState('');
    const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);
    const [aiLoading, setAiLoading] = useState(false);

    const loadConversations = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getGuestConversations?.() || { conversations: [] };
            setConversations((res.conversations || []) as Conversation[]);
        } catch { /* graceful */ }
        setLoading(false);
    }, []);

    const loadMessages = useCallback(async (ref: string) => {
        setMsgLoading(true);
        setSelectedRef(ref);
        try {
            const res = await api.getGuestMessages?.(ref) || { messages: [] };
            setMessages((res.messages || []) as Message[]);
        } catch { /* graceful */ }
        setMsgLoading(false);
    }, []);

    const getAiSuggestion = useCallback(async () => {
        if (!selectedRef) return;
        setAiLoading(true);
        try {
            const res = await api.getGuestReplySuggestion?.(selectedRef) || { suggestion: '' };
            setAiSuggestion(res.suggestion || 'Thank you for your message. We will look into this right away.');
        } catch { setAiSuggestion('Thank you for reaching out. We will get back to you shortly.'); }
        setAiLoading(false);
    }, [selectedRef]);

    useEffect(() => { loadConversations(); }, [loadConversations]);

    const channelBadge = (ch: string) => {
        const color = ch === 'whatsapp' ? '#25D366' : ch === 'line' ? '#00B900' : ch === 'email' ? '#3b82f6' : '#6b7280';
        return <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color, textTransform: 'uppercase' }}>{ch}</span>;
    };

    const selected = conversations.find(c => c.booking_ref === selectedRef);

    return (
        <div style={{ maxWidth: 1200, display: 'grid', gridTemplateColumns: selected ? '340px 1fr' : '1fr', gap: 0, height: 'calc(100vh - 120px)' }}>
            {/* Conversation list */}
            <div style={{ borderRight: selected ? '1px solid var(--color-border)' : 'none', overflowY: 'auto', padding: 'var(--space-4)' }}>
                <div style={{ marginBottom: 'var(--space-4)' }}>
                    <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--color-text)' }}>
                        Guest <span style={{ color: 'var(--color-primary)' }}>Messages</span>
                    </h1>
                </div>
                {loading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                {!loading && conversations.length === 0 && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>No conversations yet.</p>}
                {conversations.map(c => (
                    <div key={c.booking_ref} onClick={() => loadMessages(c.booking_ref)} style={{
                        padding: 'var(--space-3) var(--space-4)',
                        background: selectedRef === c.booking_ref ? 'rgba(59,130,246,0.08)' : 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        marginBottom: 'var(--space-2)',
                        cursor: 'pointer',
                        transition: 'all var(--transition-fast)',
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                            <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text)' }}>{c.guest_name}</span>
                            {c.unread > 0 && <span style={{ background: 'var(--color-primary)', color: '#fff', borderRadius: 99, fontSize: 10, fontWeight: 700, padding: '1px 7px', minWidth: 16, textAlign: 'center' }}>{c.unread}</span>}
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.last_message}</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>{c.property_id}</span>
                            {channelBadge(c.channel)}
                        </div>
                    </div>
                ))}
            </div>

            {/* Chat panel */}
            {selected && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    {/* Header */}
                    <div style={{ padding: 'var(--space-4)', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--color-text)' }}>{selected.guest_name}</div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)' }}>{selected.booking_ref} · {selected.property_id}</div>
                        </div>
                        {channelBadge(selected.channel)}
                    </div>

                    {/* Messages */}
                    <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                        {msgLoading && <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>Loading…</p>}
                        {messages.map(m => (
                            <div key={m.id} style={{
                                alignSelf: m.direction === 'outbound' ? 'flex-end' : 'flex-start',
                                maxWidth: '70%',
                                background: m.direction === 'outbound' ? 'var(--color-primary)' : 'var(--color-surface-2)',
                                color: m.direction === 'outbound' ? '#fff' : 'var(--color-text)',
                                borderRadius: 12,
                                padding: 'var(--space-3) var(--space-4)',
                                fontSize: 'var(--text-sm)',
                                lineHeight: 1.5,
                            }}>
                                {m.content}
                                <div style={{ fontSize: 'var(--text-xs)', opacity: 0.7, marginTop: 4, textAlign: 'right' }}>
                                    {new Date(m.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* AI suggestion */}
                    {aiSuggestion && (
                        <div style={{ padding: 'var(--space-3) var(--space-4)', background: 'rgba(59,130,246,0.06)', borderTop: '1px solid var(--color-border)', fontSize: 'var(--text-xs)' }}>
                            <div style={{ color: 'var(--color-primary)', fontWeight: 600, marginBottom: 4 }}>🤖 AI Suggestion</div>
                            <div style={{ color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>{aiSuggestion}</div>
                            <button onClick={() => { setDraft(aiSuggestion); setAiSuggestion(null); }} style={{ background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: '4px 12px', fontSize: 'var(--text-xs)', fontWeight: 600, cursor: 'pointer', marginRight: 'var(--space-2)' }}>Use</button>
                            <button onClick={() => setAiSuggestion(null)} style={{ background: 'none', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '4px 12px', fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', cursor: 'pointer' }}>Dismiss</button>
                        </div>
                    )}

                    {/* Input */}
                    <div style={{ padding: 'var(--space-4)', borderTop: '1px solid var(--color-border)', display: 'flex', gap: 'var(--space-2)' }}>
                        <button onClick={getAiSuggestion} disabled={aiLoading} title="AI suggest" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', fontSize: 14, cursor: 'pointer', color: 'var(--color-primary)' }}>🤖</button>
                        <input value={draft} onChange={e => setDraft(e.target.value)} placeholder="Type a message…" style={{ flex: 1, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text)', fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)' }} />
                        <button disabled={!draft.trim()} style={{ background: draft.trim() ? 'var(--color-primary)' : 'var(--color-surface-3)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-4)', fontSize: 'var(--text-sm)', fontWeight: 600, cursor: draft.trim() ? 'pointer' : 'not-allowed' }}>Send</button>
                    </div>
                </div>
            )}
        </div>
    );
}
