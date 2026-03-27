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

interface TestStep {
    n: number;
    title: string;
    body: string;
}

interface TestInstructions {
    steps: TestStep[];
    troubleshooting: React.ReactNode;
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
    testInstructions?: TestInstructions;
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
            text: 'A LINE Official Account. The free "Light" plan is enough to start.',
            link: { url: 'https://manager.line.biz/', label: 'Create a LINE Official Account →' }
        },
        {
            text: 'You must be logged into the LINE Developers Console with the same account.',
            link: { url: 'https://developers.line.biz/console/', label: 'Open LINE Developers Console →' }
        },
    ],
    steps: [
        {
            id: 'enable-api',
            title: 'Step 1 — Enable the Messaging API on your Official Account',
            description: 'Open the LINE Official Account Manager. In the left sidebar, click "Settings" → "Messaging API". Click the "Enable Messaging API" button.\n\nWhen prompted to link a Provider, choose an existing one if you have one, or create a new Provider (e.g. your company name). Do not create a second Provider if one already exists — just select it.',
            providerLink: { url: 'https://manager.line.biz/', label: 'Open LINE Official Account Manager →' },
            fields: [],
            troubleshooting: 'If you do not see "Messaging API" in the Settings menu, check that you are logged in with a LINE Official Account (not a personal LINE account). You must use the business manager at manager.line.biz, not the regular LINE app.',
        },
        {
            id: 'open-channel',
            title: 'Step 2 — Open your channel in the LINE Developers Console',
            description: 'Now open the LINE Developers Console. In the left sidebar you will see "Providers". Click your Provider name to expand it.\n\nUnder your Provider, you will see one or more Channels. Find the channel that matches your LINE Official Account — it will be labelled "Messaging API". Click on it to open the channel settings.',
            providerLink: { url: 'https://developers.line.biz/console/', label: 'Open LINE Developers Console →' },
            fields: [],
            troubleshooting: 'If you do not see any Providers or Channels, it means the Messaging API was not enabled yet in Step 1, or you are logged in with a different account. Make sure you use the same LINE account in both the Official Account Manager and the Developers Console.',
        },
        {
            id: 'channel-secret',
            title: 'Step 3 — Copy the Channel Secret',
            description: 'Inside your channel (from Step 2), click the "Basic settings" tab at the top.\n\nScroll down until you see "Channel secret". Click "Copy" next to it, then paste it into the field below.\n\nThis is a 32-character code that looks like: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4',
            providerLink: { url: 'https://developers.line.biz/console/', label: 'Open LINE Developers Console →' },
            fields: [
                {
                    key: 'channel_secret',
                    label: 'Channel Secret',
                    placeholder: 'Paste the 32-character Channel Secret here',
                    helpText: 'Found under the "Basic settings" tab of your Messaging API channel. It is a 32-character hexadecimal string.',
                    validation: { pattern: /^[0-9a-f]{32}$/i, message: 'Channel Secret should be exactly 32 hex characters (letters a–f and numbers)' },
                },
            ],
            troubleshooting: 'Important: the Channel Secret is NOT the same as the Channel Access Token. The secret is shorter (32 characters) and is found under "Basic settings", not "Messaging API". If the value you copied is very long (100+ characters), you have the wrong value — that is the access token from Step 4.',
        },
        {
            id: 'access-token',
            title: 'Step 4 — Issue and copy the Channel Access Token',
            description: 'Still inside your channel in the Developers Console, click the "Messaging API" tab at the top.\n\nScroll down to the section called "Channel access token (long-lived)". If the field is empty, click "Issue" to generate the token. Then click "Copy" next to the token and paste it into the field below.\n\nThis is a very long code (100+ characters).',
            providerLink: { url: 'https://developers.line.biz/console/', label: 'Open LINE Developers Console →' },
            fields: [
                {
                    key: 'channel_access_token',
                    label: 'Channel Access Token (long-lived)',
                    placeholder: 'Paste the long Channel Access Token here',
                    helpText: 'Found under the "Messaging API" tab → "Channel access token (long-lived)". It is over 100 characters long.',
                    validation: { pattern: /^[A-Za-z0-9+/=]{50,}$/, message: 'The access token should be a very long string (100+ characters). If it is short, you may have copied the wrong value.' },
                },
            ],
            troubleshooting: 'If the "Issue" button is grayed out: check that you accepted the LINE Developers terms of service when logging in. If you already issued a token before but cannot find it, you can click "Issue" again — this will generate a new token and the old one will stop working immediately.',
        },
        {
            id: 'webhook',
            title: 'Step 5 — Paste the webhook URL into LINE and enable it',
            description: 'You are still in the "Messaging API" tab of your channel in the Developers Console.\n\nScroll up slightly to the section called "Webhook settings". You will see a field labelled "Webhook URL".\n\n1. Copy the URL shown below\n2. Paste it into the "Webhook URL" field in LINE\n3. Click "Update" to save it\n4. Make sure the toggle for "Use webhook" is turned ON — it is OFF by default\n\nOnce you have done all four steps, come back here and click "Save & Activate".',
            providerLink: { url: 'https://developers.line.biz/console/', label: 'Open LINE Developers Console →' },
            fields: [
                {
                    key: 'webhook_url',
                    label: 'Your Webhook URL — copy this and paste it into LINE',
                    placeholder: '',
                    helpText: 'Paste this URL into the "Webhook URL" field in the LINE Developers Console under Messaging API → Webhook settings.',
                    readOnly: true,
                    copyable: true,
                },
            ],
            troubleshooting: '"Use webhook" must be toggled ON. If it is OFF, events from LINE will not reach our system and notifications will not work. The webhook URL must be a public HTTPS address — LINE will not accept plain HTTP or localhost addresses.',
        },
    ],
    testInstructions: {
        steps: [
            {
                n: 1,
                title: 'Open LINE on your phone',
                body: 'Open the LINE app on your mobile device. Make sure you are logged in with the same account as your LINE Official Account.',
            },
            {
                n: 2,
                title: 'Find your Official Account',
                body: 'In LINE, go to the "Chats" tab and search for the name of your LINE Official Account (the one you set up in this configuration). Add it as a friend if you have not already.',
            },
            {
                n: 3,
                title: 'Trigger a test notification',
                body: 'Go to a task or booking in Domaniqo and perform an action that triggers a notification — for example, assign a task to a worker who has LINE linked, or create a test check-in.',
            },
            {
                n: 4,
                title: 'What success looks like',
                body: 'Within a few seconds, you should receive a LINE message from your Official Account. The message will contain the task or notification details.',
            },
        ],
        troubleshooting: (
            <>
                1. Go back to the LINE Developers Console and check that "Use webhook" is ON under Messaging API → Webhook settings.<br />
                2. Check that the Webhook URL saved in LINE matches the one shown in Step 5 of this setup.<br />
                3. Make sure the worker has their LINE User ID linked in Domaniqo under their staff profile.<br />
                4. If all of the above are correct, contact support.
            </>
        ),
    },
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
        { text: 'A personal Telegram account on your phone or desktop', link: { url: 'https://telegram.org/', label: 'Get Telegram →' } },
    ],
    steps: [
        {
            id: 'create-bot',
            title: 'Step 1 — Create a new bot with @BotFather',
            description: 'Open your Telegram app. Search for the official @BotFather account (it has a blue verification tick). Send him the command /newbot.\n\nHe will ask for a name for your bot (e.g. "My Property Bot"). Then he will ask for a username, which must end with "bot" and be unique (e.g. "MyProperty123_bot").',
            providerLink: { url: 'https://t.me/BotFather', label: 'Open @BotFather in Telegram →' },
            fields: [],
            troubleshooting: 'BotFather will only accept usernames that end with "bot" or "_bot". If the username is already taken by someone else on Telegram, you will need to try a different one.',
        },
        {
            id: 'bot-token',
            title: 'Step 2 — Copy the HTTP API Token',
            description: 'Once you successfully choose a username, BotFather will reply with a long congratulatory message. In the middle of that message, you will see your HTTP API token.\n\nIt looks like this: 123456789:ABCDefGhIJKlmnOPQRsTUVwxyz. Copy the entire token and paste it here.',
            providerLink: { url: 'https://t.me/BotFather', label: 'Open @BotFather in Telegram →' },
            fields: [
                {
                    key: 'bot_token',
                    label: 'Bot Token',
                    placeholder: 'e.g. 123456789:ABCDefGhIJKlmnOPQRsTUVwxyz',
                    helpText: 'This authorizes our system to send messages through your Telegram bot. Keep it secret — anyone with this token can control the bot.',
                    validation: { pattern: /^\d+:[A-Za-z0-9_-]{35,}$/, message: 'Bot token should look like: 123456789:ABCDefGhIJKlmnOPQRsTUVwxyz' },
                },
            ],
            troubleshooting: 'If you lost the token, you can send /token or /mybots to @BotFather to view it again. You can also revoke and regenerate it with /revoke if you believe it was compromised.',
        },
    ],
    testInstructions: {
        steps: [
            {
                n: 1,
                title: 'Open Telegram and find your bot',
                body: 'Open the Telegram app and search for the bot username you just created. Select it to open the chat.',
            },
            {
                n: 2,
                title: 'Press START',
                body: 'Bots cannot initiate conversations with users. You must press the "Start" button (or send /start) at the bottom of the screen to allow the bot to message you.',
            },
            {
                n: 3,
                title: 'Trigger a test notification',
                body: 'Go to a task or booking in Domaniqo and perform an action that triggers a notification — for example, assign a task to a worker who has their Telegram ID linked.',
            },
            {
                n: 4,
                title: 'What success looks like',
                body: 'Within a few seconds, you should receive a Telegram message from your new bot containing the task details.',
            },
        ],
        troubleshooting: (
            <>
                1. Make sure you pressed Start or sent <code>/start</code> in the Telegram bot chat. The bot cannot message you otherwise.<br />
                2. Check that the worker has their correct Telegram User ID linked in Domaniqo under their staff profile.<br />
                3. Check that the bot token is copied perfectly, without extra spaces.<br />
                4. If all of the above are correct, contact support.
            </>
        ),
    },
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
    const [justActivated, setJustActivated] = useState(false);
    const [showTestGuide, setShowTestGuide] = useState(false);
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
            setJustActivated(true);
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
            {justActivated ? (
                /* ── Success state ── */
                <div style={{ marginTop: 24, padding: 28, background: 'var(--color-surface)', border: '1px solid var(--color-ok)44', borderRadius: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                        <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'var(--color-ok)1a', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22 }}>✓</div>
                        <div>
                            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-ok)' }}>{channel.name} is now connected</div>
                            <div style={{ fontSize: 13, color: 'var(--color-text-dim)', marginTop: 2 }}>Your configuration has been saved and this channel is active.</div>
                        </div>
                    </div>
                    {/* Test guide toggle */}
                    {channel.testInstructions && (
                        <div style={{ marginBottom: 20, padding: '16px 20px', background: 'var(--color-surface-2)', borderRadius: 10, border: '1px solid var(--color-border)' }}>
                            <button
                                onClick={() => setShowTestGuide(v => !v)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}
                            >
                                <div style={{ textAlign: 'left' }}>
                                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text)' }}>Let&apos;s test it — send your first message</div>
                                    <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 2 }}>Follow these steps to confirm {channel.name} is working correctly.</div>
                                </div>
                                <span style={{ fontSize: 18, color: 'var(--color-text-faint)', transform: showTestGuide ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▾</span>
                            </button>
                            {showTestGuide && (
                                <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
                                    {channel.testInstructions.steps.map(s => (
                                        <div key={s.n} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                                            <div style={{ minWidth: 24, height: 24, borderRadius: '50%', background: 'var(--color-primary)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700 }}>{s.n}</div>
                                            <div>
                                                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>{s.title}</div>
                                                <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 3, lineHeight: 1.55 }}>{s.body}</div>
                                            </div>
                                        </div>
                                    ))}
                                    <div style={{ marginTop: 4, padding: '12px 14px', background: 'var(--color-surface)', borderRadius: 8, border: '1px solid var(--color-border)' }}>
                                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text)', marginBottom: 6 }}>Message did not arrive?</div>
                                        <div style={{ fontSize: 12, color: 'var(--color-text-dim)', lineHeight: 1.6 }}>
                                            {channel.testInstructions.troubleshooting}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                        <button
                            onClick={() => router.push('/admin')}
                            style={{ padding: '11px 24px', fontSize: 13, fontWeight: 700, background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }}
                        >
                            ← Back to System Delivery Configuration
                        </button>
                        <button
                            onClick={() => { setSaved(false); setJustActivated(false); }}
                            style={{ padding: '11px 20px', fontSize: 13, fontWeight: 600, background: 'transparent', color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: 8, cursor: 'pointer' }}
                        >
                            Edit configuration
                        </button>
                    </div>
                </div>
            ) : (
                <div style={{ marginTop: 24, padding: 24, background: 'var(--color-surface)', border: `1px solid ${allStepsComplete ? 'var(--color-ok)33' : 'var(--color-border)'}`, borderRadius: 12 }}>
                    {allStepsComplete ? (
                        <>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                                <span style={{ fontSize: 24 }}>🎉</span>
                                <div>
                                    <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text)' }}>All steps complete</div>
                                    <div style={{ fontSize: 13, color: 'var(--color-text-dim)', marginTop: 2 }}>Save your configuration to activate this channel.</div>
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                                <button
                                    onClick={handleSave}
                                    disabled={saving}
                                    style={{
                                        padding: '12px 28px', fontSize: 14, fontWeight: 700, borderRadius: 8,
                                        border: 'none', cursor: saving ? 'wait' : 'pointer',
                                        background: 'var(--color-primary)', color: '#fff',
                                        opacity: saving ? 0.7 : 1,
                                    }}
                                >
                                    {saving ? 'Saving…' : 'Save & Activate Channel'}
                                </button>
                            </div>
                        </>
                    ) : (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
                            <div>
                                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)' }}>Setup in progress</div>
                                <div style={{ fontSize: 13, color: 'var(--color-text-dim)', marginTop: 2 }}>{completedSteps} of {totalSteps} steps complete. You can save progress and continue later.</div>
                            </div>
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                style={{
                                    padding: '10px 20px', fontSize: 13, fontWeight: 600, border: '1px solid var(--color-border)', borderRadius: 8,
                                    cursor: saving ? 'wait' : 'pointer', background: 'transparent', color: 'var(--color-text)', whiteSpace: 'nowrap',
                                }}
                            >
                                {saving ? 'Saving…' : saved ? '✓ Progress saved' : 'Save progress'}
                            </button>
                        </div>
                    )}
                </div>
            )}

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
