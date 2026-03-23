'use client';
/**
 * Phase 845 — Staff Onboarding Form (Public)
 * /staff/apply
 *
 * Correction pass: mobile layout, first+last name, phone country code,
 * bilingual language label, inline comms validation, preferred channel.
 */

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

const COUNTRY_CODES = [
  { code: '+66', label: '🇹🇭 +66' },
  { code: '+972', label: '🇮🇱 +972' },
  { code: '+1', label: '🇺🇸 +1' },
  { code: '+44', label: '🇬🇧 +44' },
  { code: '+61', label: '🇦🇺 +61' },
  { code: '+81', label: '🇯🇵 +81' },
  { code: '+65', label: '🇸🇬 +65' },
  { code: '+60', label: '🇲🇾 +60' },
  { code: '+62', label: '🇮🇩 +62' },
  { code: '+63', label: '🇵🇭 +63' },
  { code: '+82', label: '🇰🇷 +82' },
  { code: '+86', label: '🇨🇳 +86' },
];

const TRANSLATIONS = {
  en: {
    loading: 'Loading application...',
    errInvalid: 'Invalid or missing invitation token.',
    errExpired: 'Invitation link is invalid, expired, or already used.',
    errValidate: 'Failed to validate the invitation link.',
    errSubmit: 'Submission failed. Your link might have expired.',
    errNetwork: 'Network error',
    errAppMissing: 'Please provide at least one communication channel — Telegram, LINE, or WhatsApp.',
    sysTitle: 'Staff Onboarding',
    sysSub: 'Please provide your details below to complete your registration.',
    fEmail: 'Email Address *',
    fFirstName: 'First Name *',
    pFirstName: 'e.g. Somchai',
    fLastName: 'Surname / Last Name *',
    pLastName: 'e.g. Jaidee',
    fDisplayName: 'Display Name / Nickname',
    pDisplayName: 'Optional — nickname used at work',
    fPhoto: 'Selfie / Profile Photo *',
    photoReq: 'Upload a photo to continue',
    photoUpld: 'Uploading...',
    photoInfo: 'JPG, PNG, WEBP (Max 15MB). Auto-compressed.',
    fPhone: 'Phone Number *',
    pPhone: '081 234 5678',
    fLang: 'Language *',
    fEcTitle: 'Emergency Contact',
    fEcName: 'Name',
    pEcName: 'e.g. Papa',
    fEcPhone: 'Phone',
    pEcPhone: '+66 X',
    fRoles: 'Select your roles (Choose all that apply)',
    rCleaner: 'Cleaner',
    rCheckin: 'Check-in',
    rCheckout: 'Check-out',
    rBoth: 'Check-in & Check-out',
    rMaint: 'Maintenance',
    rOp: 'Op Manager',
    fDob: 'Date of Birth *',
    fIdPhoto: 'ID / Passport Photo *',
    idPhotoReq: 'Upload ID / Passport to continue',
    idPhotoUpld: 'Uploading ID document...',
    fIdNumber: 'ID / Passport Number',
    pIdNumber: 'e.g. AB1234567',
    fIdExpiry: 'ID / Passport Expiry',
    fWpTitle: 'Work Permit (optional)',
    fWpPhoto: 'Work Permit Photo',
    wpPhotoUpld: 'Uploading work permit...',
    fWpNumber: 'Work Permit Number',
    pWpNumber: 'e.g. WP-2025-12345',
    fWpExpiry: 'Work Permit Expiry',
    fTg: 'Telegram ID (Numeric)',
    btnTg: 'Get My ID →',
    pTg: 'e.g. 123456789',
    hTg: "Click 'Get My ID', press Start on Telegram, copy the number, and PASTE it here.",
    fLine: 'LINE ID',
    pLine: 'e.g. U1a2b3c4d5e',
    hLine: 'Open your LINE settings, copy your User ID, and PASTE it here manually.',
    fWa: 'WhatsApp Number',
    pWa: '081 234 5678',
    hWa: 'Ensure it matches your registered WhatsApp phone number.',
    fPreferredChannel: 'Preferred Contact Channel',
    btnSubmit: 'Submit Application',
    btnSubmitting: 'Submitting...',
    succTitle: 'Application Submitted',
    succDesc: 'Thank you for submitting your details. Our team will review your application soon.',
    designatedRoles: 'Your Assigned Roles'
  },
  th: {
    loading: 'กำลังโหลดแอปพลิเคชัน...',
    errInvalid: 'ลิงก์คำเชิญไม่ถูกต้องหรือขาดหายไป',
    errExpired: 'ลิงก์คำเชิญไม่ถูกต้อง หมดอายุ หรือใช้ไปแล้ว',
    errValidate: 'การตรวจสอบคำเชิญล้มเหลว',
    errSubmit: 'การส่งข้อมูลล้มเหลว ลิงก์ของคุณอาจหมดอายุ',
    errNetwork: 'เกิดข้อผิดพลาดในการเชื่อมต่อ',
    errAppMissing: 'กรุณาระบุช่องทางการติดต่ออย่างน้อยหนึ่งช่องทาง — Telegram, LINE หรือ WhatsApp',
    sysTitle: 'Staff Onboarding',
    sysSub: 'กรุณากรอกข้อมูลของคุณด้านล่างเพื่อลงทะเบียน',
    fEmail: 'อีเมล *',
    fFirstName: 'ชื่อ *',
    pFirstName: 'เช่น สมชาย',
    fLastName: 'นามสกุล *',
    pLastName: 'เช่น ใจดี',
    fDisplayName: 'ชื่อเล่น / ชื่อที่ต้องการใช้',
    pDisplayName: 'ไม่บังคับ — ชื่อที่ใช้ในที่ทำงาน',
    fPhoto: 'รูปถ่ายโปรไฟล์ *',
    photoReq: 'อัปโหลดรูปถ่ายเพื่อดำเนินการต่อ',
    photoUpld: 'กำลังอัปโหลด...',
    photoInfo: 'JPG, PNG, WEBP (สูงสุด 15MB) บีบอัดอัตโนมัติ',
    fPhone: 'เบอร์โทรศัพท์ *',
    pPhone: '081 234 5678',
    fLang: 'Language / ภาษา *',
    fEcTitle: 'ผู้ติดต่อฉุกเฉิน',
    fEcName: 'ชื่อ',
    pEcName: 'เช่น พ่อ',
    fEcPhone: 'เบอร์โทร',
    pEcPhone: '+66 X',
    fRoles: 'เลือกบทบาทของคุณ (เลือกทั้งหมดที่ใช้)',
    rCleaner: 'แม่บ้าน',
    rCheckin: 'เช็คอิน',
    rCheckout: 'เช็คเอาท์',
    rBoth: 'เช็คอิน & เช็คเอาท์',
    rMaint: 'ช่างซ่อมบำรุง',
    rOp: 'ผู้จัดการฝ่ายปฏิบัติการ',
    fDob: 'วันเดือนปีเกิด *',
    fIdPhoto: 'รูปถ่ายบัตรประชาชน / พาสปอร์ต *',
    idPhotoReq: 'อัปโหลดบัตรประชาชนเพื่อดำเนินการต่อ',
    idPhotoUpld: 'กำลังอัปโหลดเอกสาร...',
    fIdNumber: 'เลขบัตรประชาชน / พาสปอร์ต',
    pIdNumber: 'เช่น AB1234567',
    fIdExpiry: 'วันหมดอายุบัตร',
    fWpTitle: 'ใบอนุญาตทำงาน (ถ้ามี)',
    fWpPhoto: 'รูปถ่ายใบอนุญาตทำงาน',
    wpPhotoUpld: 'กำลังอัปโหลดใบอนุญาต...',
    fWpNumber: 'เลขที่ใบอนุญาตทำงาน',
    pWpNumber: 'เช่น WP-2025-12345',
    fWpExpiry: 'วันหมดอายุใบอนุญาต',
    fTg: 'Telegram ID (ตัวเลข)',
    btnTg: 'รับ ID ของฉัน →',
    pTg: 'เช่น 123456789',
    hTg: "คลิก 'รับ ID ของฉัน' กด Start ใน Telegram คัดลอกตัวเลข แล้ววางที่นี่",
    fLine: 'LINE ID',
    pLine: 'เช่น U1a2b3c4d5e',
    hLine: 'เปิดการตั้งค่า LINE ของคุณ คัดลอก User ID และวางที่นี่ด้วยตนเอง',
    fWa: 'เบอร์ WhatsApp',
    pWa: '081 234 5678',
    hWa: 'ตรวจสอบให้แน่ใจว่าตรงกับเบอร์โทรศัพท์ที่ใช้งาน WhatsApp',
    fPreferredChannel: 'Language / ช่องทางการติดต่อที่ต้องการ',
    btnSubmit: 'ส่งการลงทะเบียน',
    btnSubmitting: 'กำลังส่ง...',
    succTitle: 'รับเรื่องเรียบร้อยแล้ว',
    succDesc: 'ขอบคุณสำหรับการลงทะเบียน ทีมงานของเราจะตรวจสอบใบสมัครของคุณและเปิดสิทธิ์การใช้งานเร็วๆ นี้',
    designatedRoles: 'บทบาทที่คุณได้รับมอบหมาย'
  },
  he: {
    loading: 'טוען טופס...',
    errInvalid: 'קישור ההזמנה אינו תקין או חסר.',
    errExpired: 'קישור ההזמנה אינו תקין, פג תוקף, או כבר נעשה בו שימוש.',
    errValidate: 'אימות קישור ההזמנה נכשל.',
    errSubmit: 'שליחת הטופס נכשלה. ייתכן שהקישור פג תוקף.',
    errNetwork: 'שגיאת רשת',
    errAppMissing: 'יש לספק לפחות ערוץ תקשורת אחד — Telegram, LINE, או WhatsApp.',
    sysTitle: 'Staff Onboarding',
    sysSub: 'אנא מלא/י את הפרטים לסיום הרשמה.',
    fEmail: 'כתובת אימייל *',
    fFirstName: 'שם פרטי *',
    pFirstName: 'לדוגמה: יוסי',
    fLastName: 'שם משפחה *',
    pLastName: 'לדוגמה: כהן',
    fDisplayName: 'כינוי / שם תצוגה',
    pDisplayName: 'אופציונלי — שם המשמש בעבודה',
    fPhoto: 'תמונת פרופיל (סלפי) *',
    photoReq: 'העלה/י תמונה כדי להמשיך',
    photoUpld: 'מעלה...',
    photoInfo: 'JPG, PNG, WEBP (מקסימום 15MB). דחיסה אוטומטית.',
    fPhone: 'מספר טלפון *',
    pPhone: '050 123 4567',
    fLang: 'Language / שפת ממשק *',
    fEcTitle: 'איש קשר לחירום',
    fEcName: 'שם',
    pEcName: 'לדוגמה: אבא',
    fEcPhone: 'טלפון',
    pEcPhone: '+972 X',
    fRoles: 'בחר/י תפקידים (בחר/י את כל הרלוונטיים)',
    rCleaner: 'ניקיון',
    rCheckin: 'צ׳ק-אין',
    rCheckout: 'צ׳ק-אאוט',
    rBoth: 'צ׳ק-אין וצ׳ק-אאוט',
    rMaint: 'תחזוקה',
    rOp: 'מנהל תפעול',
    fDob: 'תאריך לידה *',
    fIdPhoto: 'צילום תעודת זהות / דרכון *',
    idPhotoReq: 'העלה/י תעודה כדי להמשיך',
    idPhotoUpld: 'מעלה מסמך מזהה...',
    fIdNumber: 'מספר תעודת זהות / דרכון',
    pIdNumber: 'למשל AB1234567',
    fIdExpiry: 'תאריך תפוגה',
    fWpTitle: 'היתר עבודה (אופציונלי)',
    fWpPhoto: 'צילום היתר עבודה',
    wpPhotoUpld: 'מעלה היתר עבודה...',
    fWpNumber: 'מספר היתר עבודה',
    pWpNumber: 'למשל WP-2025-12345',
    fWpExpiry: 'תאריך תפוגה היתר',
    fTg: 'מזהה Telegram (מספר)',
    btnTg: 'קבל את ה-ID שלי ←',
    pTg: 'למשל 123456789',
    hTg: "לחץ/י על 'קבל את ה-ID שלי', בחר/י Start ב-Telegram, העתק את המספר והדבק/י כאן.",
    fLine: 'מזהה LINE',
    pLine: 'למשל U1a2b3c4d5e',
    hLine: "פתח/י את הגדרות ה-LINE שלך, העתק את ה-User ID, והדבק/י כאן.",
    fWa: 'מספר וואטסאפ',
    pWa: '050 123 4567',
    hWa: 'וודא/י שמספר זה רשום בוואטסאפ במכשיר שלך.',
    fPreferredChannel: 'Language / ערוץ תקשורת מועדף',
    btnSubmit: 'שלח הרשמה',
    btnSubmitting: 'שולח...',
    succTitle: 'ההרשמה ננקלטה בהצלחה',
    succDesc: 'תודה על שליחת הפרטים. הצוות שלנו יבדוק ויאשר את קליטתך במערכת בקרוב.',
    designatedRoles: 'התפקידים שהוגדרו עבורך'
  }
};

const ROLES_LIST = [
  { id: 'cleaner', labelKey: 'rCleaner' },
  { id: 'checkin', labelKey: 'rCheckin' },
  { id: 'checkout', labelKey: 'rCheckout' },
  { id: 'checkin/checkout', labelKey: 'rBoth' },
  { id: 'maintenance', labelKey: 'rMaint' },
  { id: 'op_manager', labelKey: 'rOp' }
];

function ApplyForm() {
  const searchParams = useSearchParams();
  const token = searchParams?.get('token');
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validToken, setValidToken] = useState(false);
  const [email, setEmail] = useState('');
  const [emailLocked, setEmailLocked] = useState(false);
  
  // Name
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [displayName, setDisplayName] = useState('');
  
  // Phone
  const [countryCode, setCountryCode] = useState('+66');
  const [phoneLocal, setPhoneLocal] = useState('');
  
  const [language, setLanguage] = useState('th');
  const [ecName, setEcName] = useState('');
  const [ecPhone, setEcPhone] = useState('');
  const [photoUrl, setPhotoUrl] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [idPhotoUrl, setIdPhotoUrl] = useState('');
  const [idNumber, setIdNumber] = useState('');
  const [idExpiryDate, setIdExpiryDate] = useState('');
  const [workPermitPhotoUrl, setWorkPermitPhotoUrl] = useState('');
  const [workPermitNumber, setWorkPermitNumber] = useState('');
  const [workPermitExpiryDate, setWorkPermitExpiryDate] = useState('');
  const [workerRoles, setWorkerRoles] = useState<string[]>([]);
  const [telegram, setTelegram] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [line, setLine] = useState('');
  const [preferredChannel, setPreferredChannel] = useState('');
  const [commsError, setCommsError] = useState(false);
  
  const [rolesLocked, setRolesLocked] = useState(false);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [idPhotoUploading, setIdPhotoUploading] = useState(false);
  const [wpPhotoUploading, setWpPhotoUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('errInvalid');
      setLoading(false);
      return;
    }

    fetch(`${BASE}/staff-onboarding/validate/${token}`)
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok || !data.valid) {
          setError(data.error || 'errExpired');
        } else {
          setValidToken(true);
          if (data.email) { setEmail(data.email); setEmailLocked(true); }
          if (data.language) setLanguage(data.language);
          if (data.worker_roles?.length) { setWorkerRoles(data.worker_roles); setRolesLocked(true); }
        }
      })
      .catch(() => setError('errValidate'))
      .finally(() => setLoading(false));
  }, [token]);

  const t = TRANSLATIONS[language as keyof typeof TRANSLATIONS] || TRANSLATIONS.en;
  const resolveError = (err: string | null) => {
    if (!err) return null;
    return (t as any)[err] || err;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    
    const hasComms = telegram.trim() || whatsapp.trim() || line.trim();
    if (!hasComms) {
      setCommsError(true);
      setError('errAppMissing');
      return;
    }
    setCommsError(false);

    if (!dateOfBirth) { setError('Date of birth is required'); return; }
    if (!idPhotoUrl) { setError(t.idPhotoReq); return; }
    
    setSubmitting(true);
    setError(null);
    
    const fullName = `${firstName.trim()} ${lastName.trim()}`.trim();
    const phone = `${countryCode}${phoneLocal.replace(/^0/, '')}`;

    const payload = {
      email: email.trim(),
      full_name: fullName,
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      display_name: displayName.trim() || fullName,
      phone,
      language,
      emergency_contact: `${ecName} | ${ecPhone}`.trim(),
      photo_url: photoUrl,
      worker_roles: workerRoles,
      comm_preference: {
        telegram,
        whatsapp,
        line,
        email: email.trim(),
        date_of_birth: dateOfBirth,
        id_photo_url: idPhotoUrl,
        id_number: idNumber,
        id_expiry_date: idExpiryDate,
        work_permit_photo_url: workPermitPhotoUrl,
        work_permit_number: workPermitNumber,
        work_permit_expiry_date: workPermitExpiryDate,
        preferred_channel: preferredChannel,
        preferred_name: displayName.trim(),
      }
    };

    try {
      const res = await fetch(`${BASE}/staff-onboarding/submit/${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        try {
          const errBody = await res.json();
          if (errBody?.error === 'EMAIL_REQUIRED') {
            setError(errBody.message || 'An email address is required to complete your application.');
          } else {
            setError(errBody?.message || errBody?.error || 'errSubmit');
          }
        } catch { setError('errSubmit'); }
        return;
      }
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'errNetwork');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleRole = (r: string) => {
    setWorkerRoles(prev => prev.includes(r) ? prev.filter(x => x !== r) : [...prev, r]);
  };

  const makeUploadHandler = (setter: (url: string) => void, setUploading: (v: boolean) => void) =>
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file || !token) return;
      const mime = file.type || '';
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(mime)) { alert('Only JPG, PNG, and WebP images are allowed.'); return; }
      if (file.size > 15 * 1024 * 1024) { alert('Image exceeds 15MB limit.'); return; }
      try {
        setUploading(true);
        setError(null);
        const form = new FormData();
        form.append('file', file);
        const res = await fetch(`${BASE}/staff-onboarding/upload-photo/${token}`, { method: 'POST', body: form });
        if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || err.error || 'Upload failed'); }
        const data = await res.json();
        setter(data.url);
      } catch (err: any) {
        alert(err.message || 'Network error during upload');
      } finally {
        setUploading(false);
      }
    };

  const handlePhotoUpload = makeUploadHandler(setPhotoUrl, setPhotoUploading);
  const handleIdPhotoUpload = makeUploadHandler(setIdPhotoUrl, setIdPhotoUploading);
  const handleWpPhotoUpload = makeUploadHandler(setWorkPermitPhotoUrl, setWpPhotoUploading);

  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}>{t.loading}</div>;
  if (error && !validToken) return (
    <div style={{ maxWidth: 400, margin: '80px auto', padding: 24, textAlign: 'center', background: '#fff', border: '1px solid #e1e4e8', borderRadius: 8 }}>
      <p style={{ color: '#d73a49', margin: 0 }}>{resolveError(error)}</p>
    </div>
  );
  
  if (success) return (
    <div style={{ maxWidth: 480, margin: '80px auto', padding: 32, textAlign: 'center', background: '#fff', border: '1px solid #e1e4e8', borderRadius: 8, direction: language === 'he' ? 'rtl' : 'ltr' }}>
      <div style={{ fontSize: 40, marginBottom: 16 }}>✅</div>
      <h2 style={{ margin: '0 0 12px 0', fontSize: 20 }}>{t.succTitle}</h2>
      <p style={{ color: '#586069', margin: 0, fontSize: 14 }}>{t.succDesc}</p>
    </div>
  );

  const isRTL = language === 'he';

  // ─── Shared styles ─────────────────────────────────────────────────────────
  const inputStyle: React.CSSProperties = {
    width: '100%', boxSizing: 'border-box',
    padding: '10px 12px', borderRadius: 6, border: '1px solid #d0d7de',
    fontSize: 14, outline: 'none', background: '#f6f8fa',
    textAlign: isRTL ? 'right' : 'left',
  };
  const labelStyle: React.CSSProperties = {
    display: 'block', fontSize: 11, fontWeight: 600, color: '#57606a',
    marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.04em',
  };
  const gridTwo: React.CSSProperties = {
    display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12,
  };
  const fieldWrap: React.CSSProperties = { minWidth: 0 };

  const isSubmitDisabled = submitting || photoUploading || idPhotoUploading || wpPhotoUploading || !photoUrl || !idPhotoUrl;

  return (
    <div style={{
      maxWidth: 480, margin: '24px auto 60px', background: '#fff',
      border: '1px solid #d0d7de', borderRadius: 12, overflow: 'hidden',
      direction: isRTL ? 'rtl' : 'ltr', boxSizing: 'border-box',
    }}>
      {/* Header */}
      <div style={{ padding: '20px 20px', borderBottom: '1px solid #d0d7de', background: '#fafbfc' }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 4px 0', color: '#24292e' }}>{t.sysTitle}</h1>
        <p style={{ margin: 0, color: '#57606a', fontSize: 13 }}>{t.sysSub}</p>
      </div>

      <form onSubmit={handleSubmit} style={{ padding: '20px 20px', display: 'flex', flexDirection: 'column', gap: 18 }}>

        {/* Top-level error */}
        {error && (
          <div style={{ padding: '10px 14px', background: '#fff0f0', color: '#cb2431', borderRadius: 6, fontSize: 13, border: '1px solid #ffc1c1' }}>
            {resolveError(error)}
          </div>
        )}

        {/* Email */}
        <div>
          <label style={labelStyle}>{t.fEmail}</label>
          {emailLocked ? (
            <div style={{ ...inputStyle, background: '#eaeef2', color: '#57606a' }}>{email}</div>
          ) : (
            <input required type="email" style={{ ...inputStyle, direction: 'ltr' }} value={email} onChange={e => setEmail(e.target.value)} placeholder="worker@example.com" />
          )}
        </div>

        {/* First Name + Last Name */}
        <div style={gridTwo}>
          <div style={fieldWrap}>
            <label style={labelStyle}>{t.fFirstName}</label>
            <input required style={inputStyle} value={firstName} onChange={e => setFirstName(e.target.value)} placeholder={t.pFirstName} />
          </div>
          <div style={fieldWrap}>
            <label style={labelStyle}>{t.fLastName}</label>
            <input required style={inputStyle} value={lastName} onChange={e => setLastName(e.target.value)} placeholder={t.pLastName} />
          </div>
        </div>

        {/* Display Name */}
        <div>
          <label style={labelStyle}>{t.fDisplayName}</label>
          <input style={inputStyle} value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder={t.pDisplayName} />
        </div>

        {/* Selfie Photo */}
        <div>
          <label style={labelStyle}>{t.fPhoto}</label>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <div style={{ width: 60, height: 60, borderRadius: '50%', background: '#f6f8fa', border: '1px dashed #d0d7de', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, color: '#d0d7de', flexShrink: 0, overflow: 'hidden' }}>
              {photoUrl ? <img src={photoUrl} alt="Preview" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : '📷'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <input type="file" accept=".jpg,.jpeg,.png,.webp" onChange={handlePhotoUpload} disabled={photoUploading} style={{ fontSize: 12, display: 'block', width: '100%', boxSizing: 'border-box' }} />
              {photoUploading && <span style={{ fontSize: 11, color: '#b08800', display: 'block', marginTop: 3 }}>{t.photoUpld}</span>}
              {!photoUploading && <p style={{ margin: '3px 0 0', fontSize: 11, color: '#57606a' }}>{t.photoInfo}</p>}
            </div>
          </div>
        </div>

        {/* Phone + DOB */}
        <div style={gridTwo}>
          <div style={fieldWrap}>
            <label style={labelStyle}>{t.fPhone}</label>
            <div style={{ display: 'flex', gap: 6 }}>
              <select
                value={countryCode}
                onChange={e => setCountryCode(e.target.value)}
                style={{ ...inputStyle, width: 'auto', flex: '0 0 auto', padding: '10px 6px', fontSize: 12 }}
              >
                {COUNTRY_CODES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
              </select>
              <input
                required
                style={{ ...inputStyle, flex: 1, direction: 'ltr', minWidth: 0 }}
                value={phoneLocal}
                onChange={e => setPhoneLocal(e.target.value)}
                placeholder={t.pPhone}
                type="tel"
              />
            </div>
          </div>
          <div style={fieldWrap}>
            <label style={labelStyle}>{t.fDob}</label>
            <input required type="date" style={{ ...inputStyle, boxSizing: 'border-box' }} value={dateOfBirth} onChange={e => setDateOfBirth(e.target.value)} />
          </div>
        </div>

        {/* ID / Passport Photo */}
        <div>
          <label style={labelStyle}>{t.fIdPhoto}</label>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <div style={{ width: 60, height: 60, borderRadius: 8, background: '#f6f8fa', border: '1px dashed #d0d7de', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, color: '#d0d7de', flexShrink: 0, overflow: 'hidden' }}>
              {idPhotoUrl ? <img src={idPhotoUrl} alt="ID" style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> : '🪪'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <input type="file" accept=".jpg,.jpeg,.png,.webp" onChange={handleIdPhotoUpload} disabled={idPhotoUploading} style={{ fontSize: 12, display: 'block', width: '100%', boxSizing: 'border-box' }} />
              {idPhotoUploading && <span style={{ fontSize: 11, color: '#b08800', display: 'block', marginTop: 3 }}>{t.idPhotoUpld}</span>}
            </div>
          </div>
        </div>

        {/* ID Number + Expiry */}
        <div style={gridTwo}>
          <div style={fieldWrap}>
            <label style={labelStyle}>{t.fIdNumber}</label>
            <input style={{ ...inputStyle, direction: 'ltr' }} value={idNumber} onChange={e => setIdNumber(e.target.value)} placeholder={t.pIdNumber} />
          </div>
          <div style={fieldWrap}>
            <label style={labelStyle}>{t.fIdExpiry}</label>
            <input type="date" style={{ ...inputStyle, boxSizing: 'border-box' }} value={idExpiryDate} onChange={e => setIdExpiryDate(e.target.value)} />
          </div>
        </div>

        {/* Work Permit Section */}
        <div style={{ padding: 14, background: '#f6f8fa', borderRadius: 8, border: '1px solid #d0d7de' }}>
          <h4 style={{ margin: '0 0 12px', fontSize: 11, textTransform: 'uppercase', color: '#57606a', letterSpacing: '0.04em', fontWeight: 700 }}>{t.fWpTitle}</h4>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
            <div style={{ width: 56, height: 56, borderRadius: 6, background: '#fff', border: '1px dashed #d0d7de', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, color: '#d0d7de', flexShrink: 0, overflow: 'hidden' }}>
              {workPermitPhotoUrl ? <img src={workPermitPhotoUrl} alt="WP" style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> : '📄'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <label style={labelStyle}>{t.fWpPhoto}</label>
              <input type="file" accept=".jpg,.jpeg,.png,.webp" onChange={handleWpPhotoUpload} disabled={wpPhotoUploading} style={{ fontSize: 12, display: 'block', width: '100%', boxSizing: 'border-box' }} />
              {wpPhotoUploading && <span style={{ fontSize: 11, color: '#b08800', display: 'block', marginTop: 3 }}>{t.wpPhotoUpld}</span>}
            </div>
          </div>
          <div style={gridTwo}>
            <div style={fieldWrap}>
              <label style={labelStyle}>{t.fWpNumber}</label>
              <input style={{ ...inputStyle, background: '#fff', direction: 'ltr' }} value={workPermitNumber} onChange={e => setWorkPermitNumber(e.target.value)} placeholder={t.pWpNumber} />
            </div>
            <div style={fieldWrap}>
              <label style={labelStyle}>{t.fWpExpiry}</label>
              <input type="date" style={{ ...inputStyle, background: '#fff', boxSizing: 'border-box' }} value={workPermitExpiryDate} onChange={e => setWorkPermitExpiryDate(e.target.value)} />
            </div>
          </div>
        </div>

        {/* Language */}
        <div>
          <label style={labelStyle}>Language *</label>
          <select style={{ ...inputStyle, cursor: 'pointer' }} value={language} onChange={e => setLanguage(e.target.value)}>
            <option value="th">ภาษาไทย (Thai)</option>
            <option value="en">English</option>
            <option value="he">עברית (Hebrew)</option>
          </select>
        </div>

        {/* Emergency Contact */}
        <div style={{ padding: 14, background: '#f6f8fa', borderRadius: 8, border: '1px solid #d0d7de' }}>
          <h4 style={{ margin: '0 0 12px', fontSize: 11, textTransform: 'uppercase', color: '#57606a', letterSpacing: '0.04em', fontWeight: 700 }}>{t.fEcTitle}</h4>
          <div style={gridTwo}>
            <div style={fieldWrap}>
              <label style={labelStyle}>{t.fEcName}</label>
              <input style={{ ...inputStyle, background: '#fff' }} value={ecName} onChange={e => setEcName(e.target.value)} placeholder={t.pEcName} />
            </div>
            <div style={fieldWrap}>
              <label style={labelStyle}>{t.fEcPhone}</label>
              <input style={{ ...inputStyle, background: '#fff', direction: 'ltr' }} value={ecPhone} onChange={e => setEcPhone(e.target.value)} placeholder={t.pEcPhone} />
            </div>
          </div>
        </div>

        {/* Roles */}
        <div>
          <label style={labelStyle}>{rolesLocked ? t.designatedRoles : t.fRoles}</label>
          <div style={gridTwo}>
            {ROLES_LIST.filter(r => rolesLocked ? workerRoles.includes(r.id) : true).map(r => {
              const selected = workerRoles.includes(r.id);
              return (
                <label key={r.id} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  cursor: rolesLocked ? 'default' : 'pointer', fontSize: 13, fontWeight: 600,
                  padding: '10px 12px', borderRadius: 8,
                  border: `2px solid ${selected ? '#0366d6' : '#d0d7de'}`,
                  background: selected ? 'rgba(3,102,214,0.05)' : '#fff',
                  color: selected ? '#0366d6' : '#24292e', minWidth: 0,
                }}>
                  <input type="checkbox" checked={selected} onChange={rolesLocked ? undefined : () => toggleRole(r.id)} style={{ flexShrink: 0, pointerEvents: rolesLocked ? 'none' : 'auto' }} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{(t as any)[r.labelKey]}</span>
                </label>
              );
            })}
          </div>
        </div>

        {/* Comms section header */}
        {commsError && (
          <div style={{ padding: '10px 14px', background: '#fff0f0', color: '#cb2431', borderRadius: 6, fontSize: 13, border: '1px solid #ffc1c1', fontWeight: 600 }}>
            ⚠ {t.errAppMissing}
          </div>
        )}

        {/* Telegram */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 5 }}>
            <label style={{ ...labelStyle, marginBottom: 0 }}>{t.fTg}</label>
            <a href="https://t.me/userinfobot" target="_blank" rel="noreferrer" style={{ fontSize: 11, color: '#0366d6', textDecoration: 'none', background: 'rgba(3,102,214,0.08)', padding: '3px 8px', borderRadius: 4 }}>{t.btnTg}</a>
          </div>
          <input style={{ ...inputStyle, direction: 'ltr' }} type="number" value={telegram} onChange={e => { setTelegram(e.target.value); if (e.target.value) setCommsError(false); }} placeholder={t.pTg} />
          <p style={{ margin: '3px 0 0', fontSize: 11, color: '#57606a' }}>{t.hTg}</p>
        </div>

        {/* LINE */}
        <div>
          <label style={labelStyle}>{t.fLine}</label>
          <input style={{ ...inputStyle, direction: 'ltr' }} value={line} onChange={e => { setLine(e.target.value); if (e.target.value) setCommsError(false); }} placeholder={t.pLine} />
          <p style={{ margin: '3px 0 0', fontSize: 11, color: '#57606a' }}>{t.hLine}</p>
        </div>

        {/* WhatsApp */}
        <div>
          <label style={labelStyle}>{t.fWa}</label>
          <input style={{ ...inputStyle, direction: 'ltr' }} value={whatsapp} onChange={e => { setWhatsapp(e.target.value); if (e.target.value) setCommsError(false); }} placeholder={t.pWa} />
          <p style={{ margin: '3px 0 0', fontSize: 11, color: '#57606a' }}>{t.hWa}</p>
        </div>

        {/* Preferred Contact Channel */}
        <div>
          <label style={labelStyle}>{t.fPreferredChannel}</label>
          <select style={{ ...inputStyle, cursor: 'pointer' }} value={preferredChannel} onChange={e => setPreferredChannel(e.target.value)}>
            <option value="">—</option>
            {telegram && <option value="telegram">Telegram</option>}
            {line && <option value="line">LINE</option>}
            {whatsapp && <option value="whatsapp">WhatsApp</option>}
            <option value="email">Email</option>
            <option value="sms">SMS</option>
          </select>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={isSubmitDisabled}
          style={{
            marginTop: 8, padding: '14px 0', width: '100%',
            background: isSubmitDisabled ? '#94d3a2' : '#2ea44f',
            color: '#fff', border: 'none', borderRadius: 6,
            fontSize: 15, fontWeight: 600,
            cursor: isSubmitDisabled ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s',
          }}
        >
          {submitting ? t.btnSubmitting : (!photoUrl ? t.photoReq : (!idPhotoUrl ? t.idPhotoReq : t.btnSubmit))}
        </button>
      </form>
    </div>
  );
}

export default function StaffApplyPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center' }}>Loading application form...</div>}>
      <ApplyForm />
    </Suspense>
  );
}
