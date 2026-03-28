'use client';

/**
 * Phase 988 — OcrCaptureFlow
 * ===========================
 *
 * Shared OCR capture component for the 3 permitted wizard steps:
 *   - identity_document_capture   (check-in identity step)
 *   - checkin_opening_meter_capture  (check-in meter step)
 *   - checkout_closing_meter_capture (checkout meter step)
 *
 * Enforces INV-OCR-02: review_required is always true.
 * OCR is always optional — worker can skip to manual entry at any point.
 *
 * Props:
 *   captureType    — one of the 3 allowed types
 *   bookingId      — to scope OCR results
 *   onComplete     — called with final field values when worker confirms
 *   onSkip         — called when worker elects manual entry entirely
 *   initialDocType — optional preset doc type (PASSPORT / NATIONAL_ID / DRIVING_LICENSE)
 */

import { useRef, useState, useEffect, useCallback } from 'react';
import { apiFetch } from '@/lib/staffApi';

// ─── Types ────────────────────────────────────────────────────────

export type OcrCaptureType =
    | 'identity_document_capture'
    | 'checkin_opening_meter_capture'
    | 'checkout_closing_meter_capture';

export type DocType = 'PASSPORT' | 'NATIONAL_ID' | 'DRIVING_LICENSE';

export type IdentityFields = {
    full_name: string;
    document_number: string;
    document_type: DocType;
    date_of_birth: string;
    passport_expiry: string;
    nationality: string;
    issuing_country: string;
    ocr_result_id?: string;
};

export type MeterFields = {
    meter_value: string;
    ocr_result_id?: string;
};

type OcrFlowPhase =
    | 'doc_type_select'   // identity only: choose doc type
    | 'camera'            // live camera with overlay
    | 'processing'        // OCR in flight
    | 'review'            // OCR result / manual form
    | 'failed';           // OCR timed out or hard-failed — manual only

interface OcrProcessResponse {
    result_id: string | null;
    status: string;
    extracted_fields: Record<string, string>;
    field_confidences: Record<string, number>;
    quality_warnings: string[];
    review_required: boolean;
    error_message?: string;
}

interface OcrCaptureFlowProps {
    captureType: OcrCaptureType;
    bookingId: string;
    onComplete: (fields: IdentityFields | MeterFields, photoUrl?: string) => void;
    onSkip?: () => void;
    initialDocType?: DocType;
}

// ─── Constants ────────────────────────────────────────────────────

const OCR_TIMEOUT_MS = 6000;
const LOW_CONFIDENCE_THRESHOLD = 0.85;

const DOC_TYPE_LABELS: Record<DocType, { label: string; icon: string; hint: string; aspect: 'portrait' | 'landscape' }> = {
    PASSPORT: {
        label: 'Passport',
        icon: '📘',
        hint: 'International travel document',
        aspect: 'portrait',
    },
    NATIONAL_ID: {
        label: 'National ID',
        icon: '🪪',
        hint: 'Thai or local government ID card',
        aspect: 'landscape',
    },
    DRIVING_LICENSE: {
        label: 'Driving License',
        icon: '🚗',
        hint: 'Thai or international driving license',
        aspect: 'landscape',
    },
};

// Fields shown per doc type — determines which inputs appear in review
const DOC_TYPE_FIELDS: Record<DocType, Array<{ key: keyof Omit<IdentityFields, 'document_type' | 'ocr_result_id'>; label: string; required: boolean; type?: string }>> = {
    PASSPORT: [
        { key: 'full_name',       label: 'Full Name',        required: true  },
        { key: 'document_number', label: 'Passport Number',  required: true  },
        { key: 'date_of_birth',   label: 'Date of Birth',    required: false, type: 'date' },
        { key: 'passport_expiry', label: 'Expiry Date',      required: false, type: 'date' },
        { key: 'nationality',     label: 'Nationality',      required: false },
        { key: 'issuing_country', label: 'Issuing Country',  required: false },
    ],
    NATIONAL_ID: [
        { key: 'full_name',       label: 'Full Name',        required: true  },
        { key: 'document_number', label: 'ID Number',        required: true  },
        { key: 'date_of_birth',   label: 'Date of Birth',    required: false, type: 'date' },
        { key: 'nationality',     label: 'Nationality',      required: false },
    ],
    DRIVING_LICENSE: [
        { key: 'full_name',       label: 'Full Name',        required: true  },
        { key: 'document_number', label: 'License Number',   required: true  },
        { key: 'date_of_birth',   label: 'Date of Birth',    required: false, type: 'date' },
        { key: 'issuing_country', label: 'Issuing Authority', required: false },
    ],
};

// ─── Utility ──────────────────────────────────────────────────────

function isMeterCapture(t: OcrCaptureType): boolean {
    return t === 'checkin_opening_meter_capture' || t === 'checkout_closing_meter_capture';
}

function toBase64(canvas: HTMLCanvasElement): string {
    return canvas.toDataURL('image/jpeg', 0.85).split(',')[1];
}

function confidenceColor(conf: number): string {
    if (conf >= 0.92) return 'var(--color-ok)';
    if (conf >= LOW_CONFIDENCE_THRESHOLD) return 'var(--color-warn)';
    return '#e05c5c';
}

function confidenceLabel(conf: number): string {
    if (conf >= 0.92) return 'High confidence';
    if (conf >= LOW_CONFIDENCE_THRESHOLD) return 'Medium confidence';
    return 'Low — please verify';
}

// ─── Styles ───────────────────────────────────────────────────────

const S = {
    root: {
        display: 'flex',
        flexDirection: 'column' as const,
        gap: 'var(--space-4)',
    },
    docTypeCard: (selected: boolean): React.CSSProperties => ({
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        padding: 'var(--space-4)',
        borderRadius: 'var(--radius-md)',
        border: `2px solid ${selected ? 'var(--color-sage)' : 'var(--color-border)'}`,
        background: selected ? 'rgba(88,166,255,0.07)' : 'var(--color-surface-2)',
        cursor: 'pointer',
        transition: 'border-color 0.15s, background 0.15s',
    }),
    field: {
        display: 'flex',
        flexDirection: 'column' as const,
        gap: 4,
    },
    label: (isLow: boolean): React.CSSProperties => ({
        fontSize: 'var(--text-xs)',
        color: isLow ? 'var(--color-warn)' : 'var(--color-text-dim)',
        fontWeight: isLow ? 600 : 400,
        display: 'flex',
        alignItems: 'center',
        gap: 4,
    }),
    input: (isLow: boolean, isEmpty: boolean): React.CSSProperties => ({
        width: '100%',
        padding: '10px 12px',
        borderRadius: 'var(--radius-sm)',
        border: `1.5px solid ${isLow ? 'var(--color-warn)' : isEmpty ? 'var(--color-border)' : 'rgba(88,166,255,0.35)'}`,
        background: 'var(--color-surface-2)',
        color: 'var(--color-text)',
        fontSize: 'var(--text-sm)',
        boxSizing: 'border-box' as const,
        outline: 'none',
    }),
    primaryBtn: {
        width: '100%',
        padding: '14px 0',
        borderRadius: 'var(--radius-md)',
        background: 'var(--color-sage)',
        color: '#fff',
        border: 'none',
        fontWeight: 700,
        fontSize: 'var(--text-md)',
        cursor: 'pointer',
        letterSpacing: 0.3,
    } as React.CSSProperties,
    ghostBtn: {
        width: '100%',
        padding: '10px 0',
        borderRadius: 'var(--radius-md)',
        background: 'transparent',
        color: 'var(--color-text-dim)',
        border: 'none',
        fontWeight: 500,
        fontSize: 'var(--text-sm)',
        cursor: 'pointer',
        textAlign: 'center' as const,
    },
    notice: (type: 'warn' | 'info'): React.CSSProperties => ({
        padding: 'var(--space-2) var(--space-3)',
        borderRadius: 'var(--radius-sm)',
        background: type === 'warn' ? 'rgba(210,153,34,0.1)' : 'rgba(88,166,255,0.08)',
        border: `1px solid ${type === 'warn' ? 'rgba(210,153,34,0.3)' : 'rgba(88,166,255,0.2)'}`,
        fontSize: 'var(--text-xs)',
        color: type === 'warn' ? 'var(--color-warn)' : 'var(--color-sage)',
    }),
    meterValue: {
        fontSize: 56,
        fontWeight: 800,
        letterSpacing: -2,
        color: 'var(--color-text)',
        textAlign: 'center' as const,
        lineHeight: 1.1,
    },
    meterUnit: {
        fontSize: 'var(--text-md)',
        color: 'var(--color-text-dim)',
        textAlign: 'center' as const,
        marginTop: -4,
    },
};

// ─── Sub-components ───────────────────────────────────────────────

function DocTypeSelector({ selected, onSelect }: { selected: DocType; onSelect: (d: DocType) => void }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)', marginBottom: 'var(--space-2)' }}>
                Select the document type you will scan:
            </div>
            {(Object.keys(DOC_TYPE_LABELS) as DocType[]).map(dt => {
                const info = DOC_TYPE_LABELS[dt];
                const sel = selected === dt;
                return (
                    <button key={dt} onClick={() => onSelect(dt)} style={S.docTypeCard(sel)}>
                        <span style={{ fontSize: 28 }}>{info.icon}</span>
                        <div style={{ flex: 1, textAlign: 'left' }}>
                            <div style={{ fontWeight: 700, fontSize: 'var(--text-md)', color: sel ? 'var(--color-sage)' : 'var(--color-text)' }}>
                                {info.label}
                            </div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-dim)', marginTop: 2 }}>
                                {info.hint}
                            </div>
                        </div>
                        {sel && <span style={{ color: 'var(--color-sage)', fontWeight: 700, fontSize: 18 }}>✓</span>}
                    </button>
                );
            })}
        </div>
    );
}

interface CameraOverlayProps {
    aspect: 'portrait' | 'landscape';
    captureType: OcrCaptureType;
    docType?: DocType;
    qualityHint: string;
    onCapture: () => void;
    onCancel: () => void;
}

function CameraOverlay({ aspect, captureType, docType, qualityHint, onCapture, onCancel }: CameraOverlayProps) {
    const isLandscape = aspect === 'landscape';
    const frameStyle: React.CSSProperties = isLandscape
        ? { top: '25%', left: '6%', right: '6%', bottom: '20%' }
        : { top: '15%', left: '18%', right: '18%', bottom: '10%' };

    const isMeter = isMeterCapture(captureType);
    const guideText = isMeter
        ? 'Point camera at meter display — fill the frame'
        : `Keep full ${docType ? DOC_TYPE_LABELS[docType].label : 'document'} inside frame`;

    return (
        <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 2 }}>
            {/* Dimmed areas outside the frame */}
            <div style={{
                position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                boxShadow: `inset 0 0 0 9999px rgba(0,0,0,0.52)`,
                ...frameStyle,
                boxSizing: 'border-box',
            }} />
            {/* Frame border with corner accents */}
            <div style={{
                position: 'absolute',
                ...frameStyle,
                border: '2px solid rgba(255,255,255,0.85)',
                borderRadius: 10,
                boxSizing: 'border-box',
            }}>
                {/* Corner accents */}
                {[
                    { top: -2, left: -2, borderTop: '3px solid #58a6ff', borderLeft: '3px solid #58a6ff' },
                    { top: -2, right: -2, borderTop: '3px solid #58a6ff', borderRight: '3px solid #58a6ff' },
                    { bottom: -2, left: -2, borderBottom: '3px solid #58a6ff', borderLeft: '3px solid #58a6ff' },
                    { bottom: -2, right: -2, borderBottom: '3px solid #58a6ff', borderRight: '3px solid #58a6ff' },
                ].map((style, i) => (
                    <div key={i} style={{ position: 'absolute', width: 20, height: 20, borderRadius: 2, ...style }} />
                ))}
            </div>
            {/* Quality hint text below frame */}
            <div style={{
                position: 'absolute',
                bottom: '4%',
                width: '100%',
                textAlign: 'center',
                color: qualityHint.includes('blur') || qualityHint.includes('glare') || qualityHint.includes('dark')
                    ? '#ffca28' : 'rgba(255,255,255,0.92)',
                fontSize: 13,
                fontWeight: 600,
                textShadow: '0 1px 4px rgba(0,0,0,0.8)',
                padding: '0 16px',
                pointerEvents: 'none',
            }}>
                {qualityHint || guideText}
            </div>
            {/* Capture + cancel buttons — pointer-events re-enabled */}
            <div style={{ pointerEvents: 'auto' }}>
                <button onClick={onCapture} style={{
                    position: 'absolute', bottom: 56, left: '50%', transform: 'translateX(-50%)',
                    width: 66, height: 66, borderRadius: '50%',
                    background: '#fff', border: 'none', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 2px 16px rgba(0,0,0,0.35)',
                }}>
                    <div style={{ width: 52, height: 52, borderRadius: '50%', border: '2.5px solid #111' }} />
                </button>
                <button onClick={onCancel} style={{
                    position: 'absolute', top: 16, right: 16,
                    background: 'rgba(0,0,0,0.55)', color: '#fff',
                    border: 'none', borderRadius: 20, padding: '6px 16px',
                    fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}>
                    Cancel
                </button>
            </div>
        </div>
    );
}

// ─── Main Component ───────────────────────────────────────────────

export default function OcrCaptureFlow({
    captureType,
    bookingId,
    onComplete,
    onSkip,
    initialDocType = 'PASSPORT',
}: OcrCaptureFlowProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const isMeter = isMeterCapture(captureType);

    // Phase state
    const [phase, setPhase] = useState<OcrFlowPhase>(
        isMeter ? 'camera' : 'doc_type_select'
    );
    const [docType, setDocType] = useState<DocType>(initialDocType);
    const [qualityHint, setQualityHint] = useState('');
    const [thumbnail, setThumbnail] = useState<string | null>(null);

    // OCR result state
    const [ocrResultId, setOcrResultId] = useState<string | null>(null);
    const [extractedFields, setExtractedFields] = useState<Record<string, string>>({});
    const [fieldConfs, setFieldConfs] = useState<Record<string, number>>({});
    const [qualityWarnings, setQualityWarnings] = useState<string[]>([]);
    const [ocrStatus, setOcrStatus] = useState<string>('none');
    const [partialFields, setPartialFields] = useState(false);

    // Form fields (editable, pre-filled by OCR)
    const [fields, setFields] = useState<IdentityFields>({
        full_name: '', document_number: '', document_type: docType,
        date_of_birth: '', passport_expiry: '', nationality: '', issuing_country: '',
    });
    const [meterValue, setMeterValue] = useState('');
    const [meterConf, setMeterConf] = useState<number | null>(null);

    // Load existing OCR prefill on mount (recovery from back-navigation)
    useEffect(() => {
        async function loadPrefill() {
            try {
                const res = await apiFetch<any>(
                    `/worker/ocr/prefill/${encodeURIComponent(bookingId)}/${captureType}`
                );
                const d = res?.data;
                if (!d || d.ocr_status === 'none' || !d.result_id) return;

                // There is a prior OCR result — jump straight to review
                setOcrResultId(d.result_id);
                setOcrStatus(d.ocr_status);
                setFieldConfs(d.field_confidences || {});
                setQualityWarnings(d.quality_warnings || []);

                if (isMeter) {
                    const val = d.prefill_fields?.meter_value ?? '';
                    setMeterValue(String(val));
                    setMeterConf(d.overall_confidence ?? null);
                } else {
                    setFields(prev => ({
                        ...prev,
                        document_type: docType,
                        ...(d.prefill_fields || {}),
                    }));
                    const fieldCount = Object.keys(d.prefill_fields || {}).length;
                    const requiredFields = DOC_TYPE_FIELDS[docType];
                    setPartialFields(fieldCount < requiredFields.filter(f => f.required).length);
                }
                setPhase('review');
            } catch {
                // Prefill failure is silent — worker starts fresh
            }
        }
        void loadPrefill();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Camera management
    const startCamera = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
            });
            streamRef.current = stream;
            if (videoRef.current) videoRef.current.srcObject = stream;
        } catch {
            // Camera permission denied — skip to manual
            setPhase('review');
        }
    }, []);

    const stopCamera = useCallback(() => {
        streamRef.current?.getTracks().forEach(t => t.stop());
        streamRef.current = null;
    }, []);

    useEffect(() => {
        if (phase === 'camera') void startCamera();
        else stopCamera();
        return stopCamera;
    }, [phase, startCamera, stopCamera]);

    // Capture & OCR
    const handleCapture = useCallback(async () => {
        if (!videoRef.current) return;

        // Grab frame from video
        const video = videoRef.current;
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.drawImage(video, 0, 0);

        const thumb = canvas.toDataURL('image/jpeg', 0.6);
        setThumbnail(thumb);
        setPhase('processing');

        // Hard timeout — if OCR doesn't respond in 6s, fall through to manual
        timerRef.current = setTimeout(() => {
            setPhase('review');   // show form with whatever we have (empty = manual)
        }, OCR_TIMEOUT_MS);

        try {
            const imageBase64 = toBase64(canvas);
            const res = await apiFetch<{ data: OcrProcessResponse }>('/worker/ocr/process', {
                method: 'POST',
                body: JSON.stringify({
                    capture_type: captureType,
                    image_data: imageBase64,
                    booking_id: bookingId,
                    document_type: isMeter ? undefined : docType,
                }),
            });

            if (timerRef.current) clearTimeout(timerRef.current);

            const d = res?.data;
            if (!d) { setPhase('review'); return; }

            setOcrResultId(d.result_id);
            setOcrStatus(d.status);
            setFieldConfs(d.field_confidences || {});
            setQualityWarnings(d.quality_warnings || []);

            if (isMeter) {
                const val = d.extracted_fields?.meter_value ?? '';
                setMeterValue(String(val));
                const conf = d.field_confidences?.meter_value ?? null;
                setMeterConf(conf);
            } else {
                const ef = d.extracted_fields || {};
                setExtractedFields(ef);
                const required = DOC_TYPE_FIELDS[docType].filter(f => f.required).map(f => f.key);
                setPartialFields(required.some(k => !ef[k]));
                setFields(prev => ({
                    ...prev,
                    document_type: docType,
                    full_name: ef.full_name ?? prev.full_name,
                    document_number: ef.document_number ?? prev.document_number,
                    date_of_birth: ef.date_of_birth ?? prev.date_of_birth,
                    passport_expiry: ef.passport_expiry ?? prev.passport_expiry,
                    nationality: ef.nationality ?? prev.nationality,
                    issuing_country: ef.issuing_country ?? prev.issuing_country,
                }));
            }

            setPhase('review');
        } catch {
            if (timerRef.current) clearTimeout(timerRef.current);
            setPhase('review');
        }
    }, [bookingId, captureType, docType, isMeter]);

    // Confirm: call /confirm, then fire onComplete
    const handleConfirm = useCallback(async () => {
        // Best-effort confirm call — non-blocking
        if (ocrResultId) {
            try {
                await apiFetch(`/worker/ocr/result/${ocrResultId}/confirm`, { method: 'PATCH', body: '{}' });
            } catch { /* non-blocking */ }
        }

        if (isMeter) {
            onComplete({ meter_value: meterValue, ocr_result_id: ocrResultId ?? undefined });
        } else {
            onComplete({ ...fields, document_type: docType, ocr_result_id: ocrResultId ?? undefined });
        }
    }, [docType, fields, isMeter, meterValue, ocrResultId, onComplete]);

    // Field edit — fires /correct for audit, but does not block UI
    const updateIdentityField = useCallback((key: keyof IdentityFields, value: string) => {
        setFields(prev => ({ ...prev, [key]: value }));

        if (ocrResultId && extractedFields[key] !== undefined && value !== extractedFields[key]) {
            // Fire-and-forget correction call
            apiFetch(`/worker/ocr/result/${ocrResultId}/correct`, {
                method: 'PATCH',
                body: JSON.stringify({ corrections: { [key]: value } }),
            }).catch(() => { /* non-blocking */ });
        }
    }, [extractedFields, ocrResultId]);

    // ─── Render helpers ──────────────────────────────────────────

    function renderDocTypeSelect() {
        return (
            <div style={S.root}>
                <DocTypeSelector selected={docType} onSelect={dt => {
                    setDocType(dt);
                    setFields(prev => ({ ...prev, document_type: dt }));
                }} />
                <button style={S.primaryBtn} onClick={() => setPhase('camera')}>
                    Scan Document →
                </button>
                <button style={S.ghostBtn} onClick={() => setPhase('review')}>
                    Enter manually instead
                </button>
            </div>
        );
    }

    function renderCamera() {
        const aspect = isMeter ? 'landscape' : DOC_TYPE_LABELS[docType].aspect;
        return (
            <div style={{ position: 'relative', width: '100%', height: 320, background: '#111', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
                <video ref={videoRef} autoPlay playsInline muted
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                <CameraOverlay
                    aspect={aspect}
                    captureType={captureType}
                    docType={isMeter ? undefined : docType}
                    qualityHint={qualityHint}
                    onCapture={handleCapture}
                    onCancel={() => setPhase(isMeter ? 'review' : 'doc_type_select')}
                />
            </div>
        );
    }

    function renderProcessing() {
        return (
            <div style={S.root}>
                {thumbnail && (
                    <img src={thumbnail} alt="Captured" style={{
                        width: '100%', maxHeight: 180, objectFit: 'contain',
                        borderRadius: 'var(--radius-md)', background: '#000',
                    }} />
                )}
                <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                    <div className="spinner" style={{ margin: '0 auto var(--space-3)' }} />
                    <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)' }}>
                        Reading document…
                    </div>
                </div>
                <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <button style={{ ...S.ghostBtn, flex: 1 }} onClick={() => { setPhase('camera'); }}>
                        Scan again
                    </button>
                    <button style={{ ...S.ghostBtn, flex: 1 }} onClick={() => {
                        if (timerRef.current) clearTimeout(timerRef.current);
                        setPhase('review');
                    }}>
                        Enter manually
                    </button>
                </div>
            </div>
        );
    }

    function renderMeterReview() {
        const hasValue = meterValue.trim() !== '';
        const conf = meterConf ?? 0;
        const confColor = hasValue ? confidenceColor(conf) : 'var(--color-text-dim)';
        const confLabel = hasValue ? confidenceLabel(conf) : '';
        const isHighConf = conf >= 0.92;
        const hasWarnings = qualityWarnings.length > 0;

        return (
            <div style={S.root}>
                {thumbnail && (
                    <img src={thumbnail} alt="Meter" style={{
                        width: '100%', maxHeight: 150, objectFit: 'contain',
                        borderRadius: 'var(--radius-md)', background: '#000',
                    }} />
                )}

                {hasWarnings && (
                    <div style={S.notice('warn')}>
                        ⚠ {qualityWarnings.map(w => w.replace(/_/g, ' ')).join(' · ')} — please verify the reading
                    </div>
                )}

                {/* The reading: large and prominent */}
                <div style={{ padding: 'var(--space-4) 0', textAlign: 'center' }}>
                    {hasValue ? (
                        <>
                            <div style={S.meterValue}>{meterValue}</div>
                            <div style={S.meterUnit}>kWh</div>
                            <div style={{
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                gap: 6, marginTop: 'var(--space-2)',
                            }}>
                                <span style={{
                                    width: 8, height: 8, borderRadius: '50%',
                                    background: confColor, display: 'inline-block',
                                }} />
                                <span style={{ fontSize: 'var(--text-xs)', color: confColor }}>{confLabel}</span>
                            </div>
                        </>
                    ) : (
                        <div style={{ color: 'var(--color-text-dim)', fontSize: 'var(--text-sm)', padding: 'var(--space-4)' }}>
                            Couldn't read meter — enter reading below
                        </div>
                    )}
                </div>

                {/* Edit field — always accessible, prominent when low confidence or empty */}
                <div style={S.field}>
                    <label style={S.label(!isHighConf || !hasValue)}>
                        {(!isHighConf || !hasValue) && '⚠ '}
                        Meter Reading (kWh) *
                    </label>
                    <input
                        type="number"
                        inputMode="decimal"
                        step="0.1"
                        value={meterValue}
                        onChange={e => setMeterValue(e.target.value)}
                        placeholder="e.g. 12345.6"
                        style={S.input(!isHighConf && hasValue, !hasValue)}
                        autoFocus={!hasValue}
                    />
                </div>

                <button
                    style={{ ...S.primaryBtn, opacity: meterValue.trim() ? 1 : 0.5 }}
                    disabled={!meterValue.trim()}
                    onClick={handleConfirm}
                >
                    Confirm Reading →
                </button>
                <button style={S.ghostBtn} onClick={() => setPhase('camera')}>
                    Scan again
                </button>
                {onSkip && (
                    <button style={S.ghostBtn} onClick={onSkip}>
                        Skip — no meter reading
                    </button>
                )}
            </div>
        );
    }

    function renderIdentityReview() {
        const fieldDefs = DOC_TYPE_FIELDS[docType];
        const hasOcr = ocrStatus !== 'none' && Object.keys(extractedFields).length > 0;
        const lowConfFields = Object.entries(fieldConfs)
            .filter(([, c]) => c < LOW_CONFIDENCE_THRESHOLD)
            .map(([k]) => k);
        const hasLowConf = lowConfFields.length > 0;

        return (
            <div style={S.root}>
                {/* Thumbnail */}
                {thumbnail && (
                    <img src={thumbnail} alt="Document" style={{
                        width: '100%', maxHeight: 130, objectFit: 'contain',
                        borderRadius: 'var(--radius-md)', background: '#000',
                    }} />
                )}

                {/* Header state */}
                {hasOcr ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 18 }}>✓</span>
                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-ok)', fontWeight: 600 }}>
                            Document scanned — review and confirm all fields
                        </span>
                    </div>
                ) : (
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-dim)' }}>
                        Enter document details below
                    </div>
                )}

                {/* Partial result warning */}
                {partialFields && hasOcr && (
                    <div style={S.notice('warn')}>
                        ⚠ Some fields couldn't be read — please fill them in
                    </div>
                )}

                {/* Quality warnings */}
                {qualityWarnings.length > 0 && (
                    <div style={S.notice('warn')}>
                        ⚠ {qualityWarnings.map(w => w.replace(/_/g, ' ')).join(' · ')} — try scanning again for better results
                    </div>
                )}

                {/* Low confidence notice */}
                {hasLowConf && (
                    <div style={S.notice('warn')}>
                        ⚠ Fields marked with ⚠ were not read clearly — please verify before confirming
                    </div>
                )}

                {/* Doc type selector — compact version */}
                <div style={S.field}>
                    <label style={S.label(false)}>Document Type</label>
                    <select
                        value={docType}
                        onChange={e => {
                            const newType = e.target.value as DocType;
                            setDocType(newType);
                            setFields(prev => ({ ...prev, document_type: newType }));
                        }}
                        style={S.input(false, false)}
                    >
                        <option value="PASSPORT">Passport</option>
                        <option value="NATIONAL_ID">National ID</option>
                        <option value="DRIVING_LICENSE">Driving License</option>
                    </select>
                </div>

                {/* Editable fields */}
                {fieldDefs.map(({ key, label, required, type }) => {
                    const raw = fields[key] ?? '';
                    const conf = fieldConfs[key];
                    const isLow = conf !== undefined && conf < LOW_CONFIDENCE_THRESHOLD;
                    const isEmpty = raw === '';
                    const wasOcrFilled = Boolean(extractedFields[key as string]);

                    return (
                        <div key={key} style={S.field}>
                            <label style={S.label(isLow)}>
                                {isLow && '⚠ '}
                                {label}{required ? ' *' : ''}
                                {isLow && (
                                    <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--color-warn)', fontWeight: 400 }}>
                                        {conf !== undefined ? `${Math.round(conf * 100)}%` : ''}
                                    </span>
                                )}
                                {wasOcrFilled && !isLow && (
                                    <span style={{ marginLeft: 'auto', fontSize: 9, color: 'var(--color-ok)', fontWeight: 400 }}>
                                        auto-filled
                                    </span>
                                )}
                            </label>
                            <input
                                type={type ?? 'text'}
                                value={raw}
                                onChange={e => updateIdentityField(key, e.target.value)}
                                placeholder={type === 'date' ? 'YYYY-MM-DD' : `Enter ${label.toLowerCase()}`}
                                style={S.input(isLow, isEmpty)}
                            />
                        </div>
                    );
                })}

                {/* Actions */}
                <button
                    style={{ ...S.primaryBtn, opacity: fields.full_name.trim() ? 1 : 0.5 }}
                    disabled={!fields.full_name.trim()}
                    onClick={handleConfirm}
                >
                    Confirm & Continue →
                </button>
                <button style={S.ghostBtn} onClick={() => setPhase('camera')}>
                    Scan again
                </button>
                {onSkip && (
                    <button style={S.ghostBtn} onClick={onSkip}>
                        Skip OCR — enter manually
                    </button>
                )}
            </div>
        );
    }

    // ─── Phase router ────────────────────────────────────────────

    switch (phase) {
        case 'doc_type_select': return renderDocTypeSelect();
        case 'camera':         return renderCamera();
        case 'processing':     return renderProcessing();
        case 'review':
            return isMeter ? renderMeterReview() : renderIdentityReview();
        case 'failed':
            return (
                <div style={S.root}>
                    <div style={S.notice('warn')}>
                        Couldn't read document automatically
                    </div>
                    <button style={S.primaryBtn} onClick={() => setPhase('camera')}>Try scanning again</button>
                    <button style={S.ghostBtn} onClick={() => setPhase('review')}>Enter details manually</button>
                </div>
            );
    }
}
