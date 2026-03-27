'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';

// ---------------------------------------------------------------------------
// Channel definitions — the source of truth for all setup flows
// ---------------------------------------------------------------------------

interface SetupField {
    key: string;
    label: string;
    placeholder: string;
    helpText: string;
    type?: string;
    readOnly?: boolean;
    copyable?: boolean;
    validation?: { pattern: RegExp; message: string };
}

interface SetupStep {
    id: string;
    title: string;
    description: string;
    providerLink?: { url: string; label: string };
    fields: SetupField[];
    troubleshooting?: string;
}

interface ChannelDefinition {
    id: string;
    name: string;
    icon: string;
    group: 'messaging' | 'email';
    whatItDoes: string;
    whoReceives: string;
    systemFlows: string[];
    prerequisites: { text: string; link?: { url: string; label: string } }[];
    steps: SetupStep[];
    comingSoon?: boolean;
}

// ---------------------------------------------------------------------------
// LINE Messaging API — full guided setup flow
// ---------------------------------------------------------------------------

const LINE_CHANNEL: ChannelDefinition = {
    id: 'line',
    name: 'LINE Messaging API',
    icon: '💬',
    group: 'messaging',
    whatItDoes: 'Sends real-time task alerts, SLA escalation warnings, and operational notifications to your staff through LINE — the most popular messaging app in Thailand and Japan.',
    whoReceives: 'Cleaning staff, check-in/check-out workers, maintenance teams, and managers who have linked their LINE accounts.',
    systemFlows: [
        'Task assignment notifications (new cleaning, check-in prep, maintenance)',
        'SLA escalation alerts (5-minute critical acknowledgement warning)',
        'Task acknowledgement and claim confirmations',
        'Shift reminders and schedule updates',
    ],
    prerequisites: [
        {
            text: 'A LINE Official Account (free tier is fine to start)',
            link: { url: 'https://manager.line.biz/', label: 'Create LINE Official Account →' }
        },
        {
            text: 'Access to the LINE Developers Console',
            link: { url: 'https://developers.line.biz/console/', label: 'Open LINE Developers Console →' }
        },
    ],
    steps: [
        {
            id: 'enable-api',
            title: 'Enable the Messaging API',
            description: 'In your LINE Official Account Manager, go to Settings → Messaging API and click "Enable Messaging API." If prompted to choose a provider, select your existing one — do not create a second.',
            providerLink: { url: 'https://manager.line.biz/', label: 'Open LINE Official Account Manager →' },
            fields: [],
            troubleshooting: 'If you don\'t see "Messaging API" in settings, make sure you\'re using a LINE Official Account (not a personal account). The option appears under Settings → Messaging API.',
        },
        {
            id: 'channel-secret',
            title: 'Copy your Channel Secret',
            description: 'In the LINE Developers Console, open your channel and go to the "Basic Settings" tab. Find "Channel Secret" and copy the full value.',
            providerLink: { url: 'https://developers.line.biz/console/', label: 'Open LINE Developers Console →' },
            fields: [
                {
                    key: 'channel_secret',
                    label: 'Channel Secret',
                    placeholder: 'Paste your Channel Secret here',
                    helpText: 'This is a hexadecimal string used to verify webhook signatures. Found under Basic Settings in the LINE Developers Console.',
                    validation: { pattern: /^[0-9a-f]{32}$/i, message: 'Channel Secret should be a 32-character hexadecimal string' },
                },
            ],
            troubleshooting: 'The Channel Secret is NOT the same as the Channel Access Token. It\'s shorter (32 characters) and found under "Basic Settings", not "Messaging API".',
        },
        {
            id: 'access-token',
            title: 'Issue and copy your Channel Access Token',
            description: 'In the same channel, go to the "Messaging API" tab. Scroll down to "Channel access token (long-lived)" and click "Issue" if you haven\'t already. Copy the full token.',
            providerLink: { url: 'https://developers.line.biz/console/', label: 'Open LINE Developers Console →' },
            fields: [
                {
                    key: 'channel_access_token',
                    label: 'Channel Access Token (long-lived)',
                    placeholder: 'Paste your Channel Access Token here',
                    helpText: 'This is a long string (100+ characters) that authorizes our system to send messages on behalf of your LINE account.',
                    validation: { pattern: /^[A-Za-z0-9+/=]{50,}$/, message: 'Access Token should be a long Base64-encoded string (100+ characters)' },
                },
            ],
            troubleshooting: 'If the "Issue" button is grayed out, you may need to accept the LINE Developers terms of service first. If you already issued a token but lost it, you can re-issue a new one (the old one will stop working).',
        },
        {
            id: 'webhook',
            title: 'Set the webhook URL in LINE',
            description: 'Copy the webhook URL below and paste it into your LINE channel settings under "Messaging API" → "Webhook URL". Make sure "Use webhook" is turned ON.',
            providerLink: { url: 'https://developers.line.biz/console/', label: 'Open LINE Developers Console →' },
            fields: [
                {
                    key: 'webhook_url',
                    label: 'Your Webhook URL (copy this into LINE)',
                    placeholder: '',
                    helpText: 'This is the URL where LINE will send incoming events. Copy it and paste it into your LINE channel webhook settings.',
                    readOnly: true,
                    copyable: true,
                },
            ],
            troubleshooting: 'Make sure "Use webhook" is toggled ON in LINE (it\'s off by default). The webhook URL must use HTTPS — LINE does not support plain HTTP.',
        },
    ],
};

// ---------------------------------------------------------------------------
// Telegram Bot — guided setup flow
// ---------------------------------------------------------------------------

const TELEGRAM_CHANNEL: ChannelDefinition = {
    id: 'telegram',
    name: 'Telegram Bot',
    icon: '✈️',
    group: 'messaging',
    whatItDoes: 'Sends task alerts and escalation notifications to staff through a Telegram bot. An alternative channel for workers who prefer Telegram over LINE.',
    whoReceives: 'Workers who have linked their Telegram account through the bot.',
    systemFlows: [
        'Task assignment notifications',
        'SLA escalation alerts',
        'Task status confirmations',
    ],
    prerequisites: [
        { text: 'A Telegram account (personal is fine)', link: { url: 'https://telegram.org/', label: 'Get Telegram →' } },
    ],
    steps: [
        {
            id: 'create-bot',
            title: 'Create a bot with @BotFather',
            description: 'Open Telegram and search for @BotFather. Send /newbot and follow the prompts to choose a name and username for your bot.',
            providerLink: { url: 'https://t.me/BotFather', label: 'Open @BotFather in Telegram →' },
            fields: [],
            troubleshooting: 'BotFather will ask for a name (human-readable, can be anything) and then a username (must end with "bot", e.g. MyPropertyBot). The username must be unique across all of Telegram.',
        },
        {
            id: 'bot-token',
            title: 'Copy the Bot Token',
            description: 'After creating the bot, BotFather will reply with a message containing your HTTP API token. It looks like: 123456789:ABCDefGhIJKlmnOPQRsTUVwxyz. Copy the entire token.',
            fields: [
                {
                    key: 'bot_token',
                    label: 'Bot Token',
                    placeholder: 'e.g. 123456789:ABCDefGhIJKlmnOPQRsTUVwxyz',
                    helpText: 'This authorizes our system to send messages through your Telegram bot. Keep it secret — anyone with this token can control the bot.',
                    validation: { pattern: /^\d+:[A-Za-z0-9_-]{35,}$/, message: 'Bot token should look like: 123456789:ABCDefGhIJKlmnOPQRsTUVwxyz' },
                },
            ],
            troubleshooting: 'If you lost the token, you can send /token to @BotFather, select your bot, and it will show the token again. You can also revoke and regenerate it with /revoke.',
        },
    ],
};

// ---------------------------------------------------------------------------
// WhatsApp Business — guided setup flow
// ---------------------------------------------------------------------------

const WHATSAPP_CHANNEL: ChannelDefinition = {
    id: 'whatsapp',
    name: 'WhatsApp Business',
    icon: '📱',
    group: 'messaging',
    whatItDoes: 'Sends guest-facing communication through WhatsApp Business API — booking confirmations, check-in instructions, and stay-related messages.',
    whoReceives: 'Guests with WhatsApp accounts. Also supports staff notifications as a secondary channel.',
    systemFlows: [
        'Guest check-in instructions',
        'Booking confirmations',
        'Stay-related updates and concierge messages',
    ],
    prerequisites: [
        { text: 'A Meta Business account', link: { url: 'https://business.facebook.com/', label: 'Create Meta Business Account →' } },
        { text: 'A Meta App with WhatsApp product added', link: { url: 'https://developers.facebook.com/apps/', label: 'Open Meta for Developers →' } },
        { text: 'A verified WhatsApp Business phone number' },
    ],
    steps: [
        {
            id: 'access-token',
            title: 'Copy your Access Token',
            description: 'In the Meta for Developers dashboard, open your app → WhatsApp → API Setup. Copy the "Temporary access token" for testing, or generate a permanent System User token for production.',
            providerLink: { url: 'https://developers.facebook.com/apps/', label: 'Open Meta for Developers →' },
            fields: [
                {
                    key: 'access_token',
                    label: 'Access Token',
                    placeholder: 'Paste your Meta Cloud API Access Token',
                    helpText: 'This token authorizes sending messages. Temporary tokens expire after 24 hours — use a System User token for production.',
                },
            ],
            troubleshooting: 'Temporary tokens expire quickly. For production, create a System User in Meta Business Suite → Business Settings → System Users, generate a token with whatsapp_business_messaging permission.',
        },
        {
            id: 'phone-number-id',
            title: 'Copy your Phone Number ID',
            description: 'In the same WhatsApp API Setup page, find your "Phone number ID" (not the phone number itself — the ID is a numeric string).',
            fields: [
                {
                    key: 'phone_number_id',
                    label: 'Phone Number ID',
                    placeholder: 'e.g. 112345678901234',
                    helpText: 'This identifies which WhatsApp number messages are sent from. Found in WhatsApp → API Setup.',
                    validation: { pattern: /^\d{10,20}$/, message: 'Phone Number ID should be a 10-20 digit number' },
                },
            ],
        },
        {
            id: 'app-secret',
            title: 'Copy your App Secret',
            description: 'Go to your Meta App → Settings → Basic. Find "App Secret" and click "Show." Copy it.',
            providerLink: { url: 'https://developers.facebook.com/apps/', label: 'Open Meta for Developers →' },
            fields: [
                {
                    key: 'app_secret',
                    label: 'App Secret',
                    placeholder: 'Paste your Meta App Secret',
                    helpText: 'Used to verify webhook payloads with HMAC-SHA256 signatures, ensuring messages actually come from Meta.',
                },
            ],
            troubleshooting: 'The App Secret is different from the Access Token. It\'s found under App Settings → Basic, not under WhatsApp API Setup.',
        },
        {
            id: 'verify-token',
            title: 'Set a Verify Token',
            description: 'Choose any secret phrase. You\'ll paste this same phrase into Meta\'s webhook configuration so they can verify our endpoint.',
            fields: [
                {
                    key: 'verify_token',
                    label: 'Verify Token',
                    placeholder: 'e.g. my-secret-verify-phrase',
                    helpText: 'This is a string you create yourself. It must match exactly in both our system and Meta\'s webhook config. Use any password-like string.',
                },
            ],
        },
    ],
};

// ---------------------------------------------------------------------------
// SMS (Twilio) — guided setup flow
// ---------------------------------------------------------------------------

const SMS_CHANNEL: ChannelDefinition = {
    id: 'sms',
    name: 'SMS (Twilio)',
    icon: '📲',
    group: 'messaging',
    whatItDoes: 'Sends SMS text messages as a fallback delivery channel when primary messaging channels (LINE, WhatsApp, Telegram) are unreachable or undelivered.',
    whoReceives: 'Staff and guests whose primary channels failed delivery. SMS is the last-resort channel.',
    systemFlows: [
        'Fallback task alerts when LINE/Telegram fail',
        'Critical SLA escalations that must reach the worker',
        'Guest communication when WhatsApp is unavailable',
    ],
    prerequisites: [
        { text: 'A Twilio account with billing configured', link: { url: 'https://www.twilio.com/try-twilio', label: 'Create Twilio Account →' } },
        { text: 'A Twilio phone number capable of sending SMS', link: { url: 'https://console.twilio.com/us1/develop/phone-numbers/manage/search', label: 'Buy a Twilio Number →' } },
    ],
    steps: [
        {
            id: 'account-sid',
            title: 'Copy your Account SID',
            description: 'On the Twilio Console dashboard, your Account SID is displayed prominently. It starts with "AC".',
            providerLink: { url: 'https://console.twilio.com/', label: 'Open Twilio Console →' },
            fields: [
                {
                    key: 'twilio_sid',
                    label: 'Account SID',
                    placeholder: 'AC...',
                    helpText: 'Your Account SID identifies your Twilio account. Starts with "AC" followed by 32 hexadecimal characters.',
                    validation: { pattern: /^AC[0-9a-f]{32}$/i, message: 'Account SID should start with "AC" followed by 32 hex characters' },
                },
            ],
        },
        {
            id: 'auth-token',
            title: 'Copy your Auth Token',
            description: 'On the same Twilio Console dashboard, click "Show" next to your Auth Token and copy it.',
            fields: [
                {
                    key: 'twilio_token',
                    label: 'Auth Token',
                    placeholder: 'Paste your Twilio Auth Token',
                    helpText: 'This secret authenticates API requests. Keep it secure — anyone with your SID + token can use your Twilio account.',
                },
            ],
            troubleshooting: 'If you suspect your Auth Token has been compromised, you can rotate it from the Twilio Console. The old token will immediately stop working.',
        },
        {
            id: 'from-number',
            title: 'Enter your Twilio phone number',
            description: 'Enter the phone number you purchased from Twilio. This is the number that SMS messages will be sent from.',
            fields: [
                {
                    key: 'twilio_from',
                    label: 'Twilio Phone Number',
                    placeholder: '+1234567890',
                    helpText: 'Must be in E.164 format: + followed by country code and number, no spaces or dashes.',
                    validation: { pattern: /^\+\d{10,15}$/, message: 'Phone number must be in E.164 format: +1234567890' },
                },
            ],
        },
    ],
};

// ---------------------------------------------------------------------------
// Email Sender — guided setup flow  
// ---------------------------------------------------------------------------

const EMAIL_GENERAL_CHANNEL: ChannelDefinition = {
    id: 'email_general',
    name: 'System Email Sender',
    icon: '✉️',
    group: 'email',
    whatItDoes: 'The default sender identity for all system-generated emails. When no specific sender is configured for a purpose (onboarding, guest, etc.), emails use this identity.',
    whoReceives: 'Anyone receiving system emails — staff, guests, owners.',
    systemFlows: [
        'Default sender for all email types',
        'Fallback when purpose-specific senders are not configured',
        'System notifications and alerts',
    ],
    prerequisites: [
        { text: 'A business email address you want to send from (e.g. noreply@yourcompany.com)' },
        { text: 'A monitored inbox for replies (can be the same email or a different support address)' },
    ],
    steps: [
        {
            id: 'from-name',
            title: 'Set the sender name',
            description: 'This is the name recipients will see in their inbox. Use your company or brand name.',
            fields: [
                {
                    key: 'from_name',
                    label: 'From Name',
                    placeholder: 'e.g. Domaniqo',
                    helpText: 'Recipients will see this as the sender. Example: "Domaniqo" will appear as "From: Domaniqo <your@email.com>".',
                },
            ],
        },
        {
            id: 'from-email',
            title: 'Set the sender email address',
            description: 'The email address that messages will appear to come from.',
            fields: [
                {
                    key: 'from_email',
                    label: 'From Email',
                    placeholder: 'e.g. noreply@domaniqo.com',
                    helpText: 'Use a professional address on your own domain. Free email addresses (Gmail, Yahoo) may be flagged as spam.',
                    validation: { pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: 'Please enter a valid email address' },
                },
            ],
        },
        {
            id: 'reply-to',
            title: 'Set the reply-to address',
            description: 'When someone replies to a system email, their reply will go to this address. Use a monitored inbox.',
            fields: [
                {
                    key: 'reply_to',
                    label: 'Reply-To Email',
                    placeholder: 'e.g. support@domaniqo.com',
                    helpText: 'This should be an inbox that someone checks. If left empty, replies go to the sender address.',
                    validation: { pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: 'Please enter a valid email address' },
                },
            ],
        },
    ],
};

// Coming-soon email senders (minimal definitions)
const makeComingSoonEmail = (id: string, name: string, whatItDoes: string, flows: string[]): ChannelDefinition => ({
    id, name, icon: '✉️', group: 'email', whatItDoes, whoReceives: '', systemFlows: flows,
    prerequisites: [], steps: [], comingSoon: true,
});

const CHANNEL_REGISTRY: Record<string, ChannelDefinition> = {
    line: LINE_CHANNEL,
    telegram: TELEGRAM_CHANNEL,
    whatsapp: WHATSAPP_CHANNEL,
    sms: SMS_CHANNEL,
    email_general: EMAIL_GENERAL_CHANNEL,
    email_onboarding: makeComingSoonEmail('email_onboarding', 'Staff Onboarding Sender', 'Sends invite emails, access links, and welcome messages to new staff.', ['Invite links', 'Setup instructions', 'Welcome messages']),
    email_password: makeComingSoonEmail('email_password', 'Password & Account Sender', 'Sends password reset and account recovery emails.', ['Password reset', 'Account recovery', 'Security alerts']),
    email_guest: makeComingSoonEmail('email_guest', 'Guest Communication Sender', 'Sends guest portal links, check-in instructions, and stay information.', ['Portal links', 'Check-in instructions', 'Stay updates']),
    email_owner: makeComingSoonEmail('email_owner', 'Owner Reports Sender', 'Sends financial statements, property reports, and owner notifications.', ['Financial statements', 'Property reports', 'Periodic summaries']),
};

// ---------------------------------------------------------------------------
// Setup page component
// ---------------------------------------------------------------------------

export default function ChannelSetupPage() {
    const params = useParams();
    const router = useRouter();
    const channelId = params.channel as string;
    const channel = CHANNEL_REGISTRY[channelId];

    const [credentials, setCredentials] = useState<Record<string, string>>({});
    const [activeStep, setActiveStep] = useState(0);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [errors, setErrors] = useState<Record<string, string>>({});
    const [expandedTroubleshooting, setExpandedTroubleshooting] = useState<Record<string, boolean>>({});
    const [loading, setLoading] = useState(true);
    const [isConfigured, setIsConfigured] = useState(false);
    const [copiedKey, setCopiedKey] = useState<string | null>(null);

    // Load existing credentials
    const loadExisting = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.getTenantIntegrations();
            const existing = (res.integrations || []).find((i: any) => i.provider === channelId);
            if (existing?.credentials) {
                setCredentials(existing.credentials);
                setIsConfigured(true);
                // If already configured, start at last step
                if (channel && channel.steps.length > 0) {
                    setActiveStep(channel.steps.length - 1);
                }
            }
        } catch { /* first time */ }
        // Auto-populate webhook_url for LINE
        if (channelId === 'line') {
            setCredentials(prev => {
                if (prev.webhook_url) return prev;
                const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
                return { ...prev, webhook_url: `${apiUrl}/line/webhook` };
            });
        }
        setLoading(false);
    }, [channelId, channel]);

    useEffect(() => { loadExisting(); }, [loadExisting]);

    // Validate a field
    const validateField = (field: SetupField, value: string): string | null => {
        if (!value && !field.readOnly) return null; // empty is ok, just incomplete
        if (field.validation && value && !field.validation.pattern.test(value)) {
            return field.validation.message;
        }
        return null;
    };

    // Save credentials
    const handleSave = async () => {
        if (!channel) return;
        setSaving(true);
        // Strip read-only fields
        const saveCreds = Object.fromEntries(
            Object.entries(credentials).filter(([k]) => {
                const allFields = channel.steps.flatMap(s => s.fields);
                const field = allFields.find(f => f.key === k);
                return !field?.readOnly;
            })
        );
        try {
            await api.updateTenantIntegration(channelId, {
                is_active: true,
                credentials: saveCreds,
            });
            setSaved(true);
            setIsConfigured(true);
            setTimeout(() => setSaved(false), 3000);
        } catch (err) {
            console.error('Save failed:', err);
        }
        setSaving(false);
    };

    const handleCopy = (key: string) => {
        navigator.clipboard.writeText(credentials[key] || '');
        setCopiedKey(key);
        setTimeout(() => setCopiedKey(null), 2000);
    };

    // Check if a step is complete (all required fields filled)
    const isStepComplete = (step: SetupStep): boolean => {
        if (step.fields.length === 0) return true; // instruction-only step
        return step.fields.every(f => f.readOnly || !!credentials[f.key]);
    };

    // Check how many steps are complete
    const completedSteps = channel?.steps.filter(isStepComplete).length ?? 0;
    const totalSteps = channel?.steps.length ?? 0;
    const allStepsComplete = completedSteps === totalSteps && totalSteps > 0;

    if (!channel) {
        return (
            <div style={{ maxWidth: 700, padding: '40px 0' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 700, color: 'var(--color-text)' }}>Channel not found</h1>
                <p style={{ color: 'var(--color-text-dim)', marginTop: 8 }}>The channel "{channelId}" does not exist.</p>
                <button onClick={() => router.push('/admin')} style={linkBtnStyle}>← Back to Admin Settings</button>
            </div>
        );
    }

    if (channel.comingSoon) {
        return (
            <div style={{ maxWidth: 700, padding: '40px 0' }}>
                <button onClick={() => router.push('/admin')} style={linkBtnStyle}>← Back to System Delivery Configuration</button>
                <div style={{ marginTop: 24, padding: 32, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, textAlign: 'center' }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>{channel.icon}</div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--color-text)' }}>{channel.name}</h1>
                    <p style={{ color: 'var(--color-text-dim)', marginTop: 8, maxWidth: 500, margin: '8px auto 0' }}>{channel.whatItDoes}</p>
                    <div style={{ marginTop: 24, display: 'inline-flex', padding: '8px 20px', background: 'var(--color-accent)11', border: '1px solid var(--color-accent)33', borderRadius: 8, color: 'var(--color-accent)', fontWeight: 600, fontSize: 13 }}>
                        Coming Soon
                    </div>
                </div>
            </div>
        );
    }

    if (loading) {
        return (
            <div style={{ maxWidth: 700, padding: '40px 0' }}>
                <p style={{ color: 'var(--color-text-dim)' }}>Loading configuration…</p>
            </div>
        );
    }

    return (
        <div style={{ maxWidth: 720, padding: '20px 0 60px' }}>
            {/* Back link */}
            <button onClick={() => router.push('/admin')} style={linkBtnStyle}>← Back to System Delivery Configuration</button>

            {/* Header */}
            <div style={{ marginTop: 20, marginBottom: 32 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                    <span style={{ fontSize: 32 }}>{channel.icon}</span>
                    <div>
                        <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--color-text)', margin: 0 }}>Set up {channel.name}</h1>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                            {isConfigured ? (
                                <span style={{ fontSize: 12, fontWeight: 600, padding: '2px 10px', borderRadius: 99, background: 'var(--color-ok)18', color: 'var(--color-ok)' }}>✓ Connected</span>
                            ) : (
                                <span style={{ fontSize: 12, fontWeight: 600, padding: '2px 10px', borderRadius: 99, background: 'var(--color-text-faint)18', color: 'var(--color-text-faint)' }}>Not connected</span>
                            )}
                            {totalSteps > 0 && (
                                <span style={{ fontSize: 12, color: 'var(--color-text-faint)' }}>{completedSteps} of {totalSteps} steps complete</span>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* What this channel does */}
            <div style={sectionCardStyle}>
                <h2 style={sectionTitleStyle}>What this channel does</h2>
                <p style={{ color: 'var(--color-text-dim)', fontSize: 14, lineHeight: 1.6, margin: '8px 0' }}>{channel.whatItDoes}</p>
                <p style={{ color: 'var(--color-text-dim)', fontSize: 13, margin: '8px 0 0' }}><strong style={{ color: 'var(--color-text)' }}>Who receives:</strong> {channel.whoReceives}</p>
                <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>System flows using this channel</div>
                    <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--color-text-dim)', fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {channel.systemFlows.map((f, i) => <li key={i}>{f}</li>)}
                    </ul>
                </div>
            </div>

            {/* Prerequisites */}
            {channel.prerequisites.length > 0 && (
                <div style={{ ...sectionCardStyle, marginTop: 16 }}>
                    <h2 style={sectionTitleStyle}>Before you start</h2>
                    <p style={{ fontSize: 13, color: 'var(--color-text-dim)', margin: '4px 0 12px' }}>Make sure you have the following ready:</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {channel.prerequisites.map((p, i) => (
                            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 14px', background: 'var(--color-surface-2)', borderRadius: 8 }}>
                                <span style={{ fontSize: 14, marginTop: 1 }}>☑️</span>
                                <div>
                                    <div style={{ fontSize: 13, color: 'var(--color-text)' }}>{p.text}</div>
                                    {p.link && (
                                        <a href={p.link.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--color-primary)', fontWeight: 600, textDecoration: 'none', marginTop: 4, display: 'inline-block' }}>
                                            {p.link.label}
                                        </a>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Setup steps */}
            <div style={{ marginTop: 24 }}>
                <h2 style={{ ...sectionTitleStyle, marginBottom: 16, paddingLeft: 0 }}>Setup steps</h2>
                {/* Progress bar */}
                <div style={{ height: 4, background: 'var(--color-border)', borderRadius: 4, marginBottom: 20, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0}%`, background: allStepsComplete ? 'var(--color-ok)' : 'var(--color-primary)', borderRadius: 4, transition: 'width 0.4s ease' }} />
                </div>

                {channel.steps.map((step, idx) => {
                    const isActive = idx === activeStep;
                    const isComplete = isStepComplete(step);
                    const isLocked = idx > 0 && !isStepComplete(channel.steps[idx - 1]) && idx > activeStep;

                    return (
                        <div key={step.id} style={{
                            marginBottom: 12,
                            border: `1px solid ${isActive ? 'var(--color-primary)44' : 'var(--color-border)'}`,
                            borderRadius: 12,
                            background: 'var(--color-surface)',
                            opacity: isLocked ? 0.5 : 1,
                            transition: 'all 0.2s ease',
                        }}>
                            {/* Step header — always visible, clickable */}
                            <button
                                onClick={() => !isLocked && setActiveStep(idx)}
                                style={{
                                    width: '100%', padding: '16px 20px', background: 'none', border: 'none', cursor: isLocked ? 'not-allowed' : 'pointer',
                                    display: 'flex', alignItems: 'center', gap: 12, textAlign: 'left',
                                }}
                            >
                                <div style={{
                                    width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: 13, fontWeight: 700,
                                    background: isComplete ? 'var(--color-ok)' : isActive ? 'var(--color-primary)' : 'var(--color-surface-2)',
                                    color: isComplete || isActive ? '#fff' : 'var(--color-text-dim)',
                                }}>
                                    {isComplete ? '✓' : idx + 1}
                                </div>
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)' }}>{step.title}</div>
                                    {!isActive && <div style={{ fontSize: 12, color: 'var(--color-text-faint)', marginTop: 2 }}>{isComplete ? 'Completed' : step.description.slice(0, 80) + '…'}</div>}
                                </div>
                                <span style={{ fontSize: 16, color: 'var(--color-text-faint)', transform: isActive ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s' }}>▾</span>
                            </button>

                            {/* Step body — expanded when active */}
                            {isActive && (
                                <div style={{ padding: '0 20px 20px' }}>
                                    <p style={{ fontSize: 13, color: 'var(--color-text-dim)', lineHeight: 1.65, margin: '0 0 16px' }}>{step.description}</p>

                                    {step.providerLink && (
                                        <a href={step.providerLink.url} target="_blank" rel="noopener noreferrer" style={{
                                            display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', fontSize: 12, fontWeight: 600,
                                            background: 'var(--color-primary)0d', border: '1px solid var(--color-primary)33', borderRadius: 8,
                                            color: 'var(--color-primary)', textDecoration: 'none', marginBottom: 16,
                                        }}>
                                            {step.providerLink.label} <span style={{ fontSize: 14 }}>↗</span>
                                        </a>
                                    )}

                                    {/* Fields */}
                                    {step.fields.map(field => (
                                        <div key={field.key} style={{ marginBottom: 16 }}>
                                            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--color-text)', marginBottom: 6 }}>{field.label}</label>
                                            {field.readOnly ? (
                                                <div style={{ display: 'flex', gap: 6 }}>
                                                    <input type="text" value={credentials[field.key] || ''} readOnly style={{
                                                        flex: 1, padding: '10px 14px', fontSize: 12, borderRadius: 8, border: '1px solid var(--color-border)',
                                                        background: 'var(--color-surface-2)', color: 'var(--color-text-dim)', outline: 'none', fontFamily: 'monospace',
                                                    }} />
                                                    {field.copyable && (
                                                        <button onClick={() => handleCopy(field.key)} style={{
                                                            padding: '10px 16px', fontSize: 12, fontWeight: 600, background: 'var(--color-surface-2)',
                                                            border: '1px solid var(--color-border)', borderRadius: 8, cursor: 'pointer',
                                                            color: copiedKey === field.key ? 'var(--color-ok)' : 'var(--color-text)', whiteSpace: 'nowrap',
                                                        }}>
                                                            {copiedKey === field.key ? '✓ Copied' : 'Copy'}
                                                        </button>
                                                    )}
                                                </div>
                                            ) : (
                                                <input
                                                    type={field.type || 'text'}
                                                    placeholder={field.placeholder}
                                                    value={credentials[field.key] || ''}
                                                    onChange={(e) => {
                                                        const val = e.target.value;
                                                        setCredentials(prev => ({ ...prev, [field.key]: val }));
                                                        const err = validateField(field, val);
                                                        setErrors(prev => err ? { ...prev, [field.key]: err } : (() => { const n = { ...prev }; delete n[field.key]; return n; })());
                                                    }}
                                                    style={{
                                                        width: '100%', padding: '10px 14px', fontSize: 13, borderRadius: 8, boxSizing: 'border-box',
                                                        border: `1px solid ${errors[field.key] ? 'var(--color-danger)' : 'var(--color-border)'}`,
                                                        background: 'var(--color-background)', color: 'var(--color-text)', outline: 'none',
                                                    }}
                                                    onFocus={(e) => e.target.style.borderColor = errors[field.key] ? 'var(--color-danger)' : 'var(--color-primary)'}
                                                    onBlur={(e) => e.target.style.borderColor = errors[field.key] ? 'var(--color-danger)' : 'var(--color-border)'}
                                                />
                                            )}
                                            {errors[field.key] && (
                                                <div style={{ fontSize: 12, color: 'var(--color-danger)', marginTop: 4 }}>⚠ {errors[field.key]}</div>
                                            )}
                                            <div style={{ fontSize: 12, color: 'var(--color-text-faint)', marginTop: 6, lineHeight: 1.5 }}>{field.helpText}</div>
                                        </div>
                                    ))}

                                    {/* Troubleshooting */}
                                    {step.troubleshooting && (
                                        <div style={{ marginTop: 8 }}>
                                            <button
                                                onClick={() => setExpandedTroubleshooting(prev => ({ ...prev, [step.id]: !prev[step.id] }))}
                                                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600, color: 'var(--color-text-faint)', padding: 0, display: 'flex', alignItems: 'center', gap: 4 }}
                                            >
                                                <span style={{ transform: expandedTroubleshooting[step.id] ? 'rotate(90deg)' : 'rotate(0)', transition: 'transform 0.15s', display: 'inline-block' }}>▸</span>
                                                What if I can&apos;t find this?
                                            </button>
                                            {expandedTroubleshooting[step.id] && (
                                                <div style={{ marginTop: 8, padding: '12px 14px', background: 'var(--color-surface-2)', borderRadius: 8, fontSize: 12, color: 'var(--color-text-dim)', lineHeight: 1.6, borderLeft: '3px solid var(--color-primary)44' }}>
                                                    {step.troubleshooting}
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Next step button */}
                                    {idx < channel.steps.length - 1 && isComplete && (
                                        <button onClick={() => setActiveStep(idx + 1)} style={{
                                            marginTop: 16, padding: '10px 20px', fontSize: 13, fontWeight: 600,
                                            background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer',
                                        }}>
                                            Continue to next step →
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Save + completion */}
            <div style={{ marginTop: 24, padding: 24, background: 'var(--color-surface)', border: `1px solid ${allStepsComplete ? 'var(--color-ok)33' : 'var(--color-border)'}`, borderRadius: 12 }}>
                {allStepsComplete ? (
                    <>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                            <span style={{ fontSize: 24 }}>🎉</span>
                            <div>
                                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text)' }}>All steps complete</div>
                                <div style={{ fontSize: 13, color: 'var(--color-text-dim)' }}>Save your configuration to activate this channel.</div>
                            </div>
                        </div>
                        <div style={{ display: 'flex', gap: 10 }}>
                            <button onClick={handleSave} disabled={saving} style={{
                                padding: '12px 28px', fontSize: 14, fontWeight: 700, border: 'none', borderRadius: 8, cursor: saving ? 'wait' : 'pointer',
                                background: saved ? 'var(--color-ok)' : 'var(--color-text)', color: 'var(--color-background)',
                            }}>
                                {saving ? 'Saving…' : saved ? '✓ Saved & Activated' : 'Save & Activate Channel'}
                            </button>
                        </div>
                    </>
                ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)' }}>Setup in progress</div>
                            <div style={{ fontSize: 13, color: 'var(--color-text-dim)' }}>{completedSteps} of {totalSteps} steps complete. You can save your progress and continue later.</div>
                        </div>
                        <button onClick={handleSave} disabled={saving} style={{
                            padding: '10px 20px', fontSize: 13, fontWeight: 600, border: '1px solid var(--color-border)', borderRadius: 8,
                            cursor: saving ? 'wait' : 'pointer', background: 'transparent', color: 'var(--color-text)',
                        }}>
                            {saving ? 'Saving…' : saved ? '✓ Progress saved' : 'Save progress'}
                        </button>
                    </div>
                )}
            </div>

            {/* Footer */}
            <div style={{ marginTop: 40, fontSize: 11, color: 'var(--color-text-faint)', display: 'flex', justifyContent: 'space-between' }}>
                <span>Domaniqo — Channel Setup · Phase 952</span>
                <span>{channel.name}</span>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const linkBtnStyle: React.CSSProperties = {
    background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
    color: 'var(--color-primary)', padding: 0, display: 'flex', alignItems: 'center', gap: 4,
};

const sectionCardStyle: React.CSSProperties = {
    padding: '20px 24px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12,
};

const sectionTitleStyle: React.CSSProperties = {
    fontSize: 14, fontWeight: 700, color: 'var(--color-text)', margin: 0,
};
