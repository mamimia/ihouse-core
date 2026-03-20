'use client';
/**
 * Phase 845 — Staff Onboarding Form (Public)
 * /staff/apply
 */

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

const TRANSLATIONS = {
  en: {
    loading: 'Loading application...',
    errInvalid: 'Invalid or missing invitation token.',
    errExpired: 'Invitation link is invalid, expired, or already used.',
    errValidate: 'Failed to validate the invitation link.',
    errSubmit: 'Submission failed. Your link might have expired.',
    errNetwork: 'Network error',
    errAppMissing: 'Please provide at least one communication app (Telegram, LINE, or WhatsApp).',
    sysTitle: 'Staff Onboarding',
    sysSub: 'Please provide your details below to complete your registration.',
    fEmail: 'Email Address *',
    fName: 'Full Name *',
    pName: 'e.g. Somchai Jaidee',
    fPhoto: 'Selfie / Profile Photo *',
    photoReq: 'Upload a photo to continue',
    photoUpld: 'Uploading and compressing... (~2MB limit)',
    photoInfo: 'JPG, PNG, WEBP (Max 15MB). We will automatically compress it.',
    fPhone: 'Phone Number *',
    pPhone: '+66 81 X',
    fLang: 'App Language / שפת ממשק *',
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
    fTg: 'Telegram ID (Numeric)',
    btnTg: 'Get My ID →',
    pTg: 'e.g. 123456789',
    hTg: "Click 'Get My ID', press Start on Telegram, copy the number, and PASTE it here.",
    fLine: 'LINE ID',
    pLine: 'e.g. U1a2b3c4d5e',
    hLine: 'Open your LINE settings, copy your User ID, and PASTE it here manually.',
    fWa: 'WhatsApp Number',
    pWa: '+66 81 234 5678',
    hWa: 'Ensure it matches your registered WhatsApp phone number.',
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
    errSubmit: 'การส่งล้มเหลว ลิงก์ของคุณอาจหมดอายุแล้ว',
    errNetwork: 'เกิดข้อผิดพลาดเครือข่าย',
    errAppMissing: 'โปรดระบุแอปพลิเคชันสำหรับการสื่อสารอย่างน้อยหนึ่งแอป (Telegram, LINE หรือ WhatsApp)',
    sysTitle: 'การลงทะเบียนพนักงาน',
    sysSub: 'โปรดกรอกรายละเอียดของคุณด้านล่างเพื่อเสร็จสิ้นการลงทะเบียน',
    fEmail: 'ที่อยู่อีเมล *',
    fName: 'ชื่อ-นามสกุล *',
    pName: 'เช่น สมชาย ใจดี',
    fPhoto: 'ภาพเซลฟี่ / รูปโปรไฟล์ *',
    photoReq: 'อัปโหลดรูปภาพเพื่อดำเนินการต่อ',
    photoUpld: 'กำลังอัปโหลดและบีบอัด... (จำกัด ~2MB)',
    photoInfo: 'JPG, PNG, WEBP (สูงสุด 15MB) ระบบจะบีบอัดให้โดยอัตโนมัติ',
    fPhone: 'เบอร์โทรศัพท์ *',
    pPhone: '+66 81 X',
    fLang: 'ภาษาของแอปพลิเคชัน *',
    fEcTitle: 'ผู้ติดต่อกรณีฉุกเฉิน',
    fEcName: 'ชื่อ',
    pEcName: 'เช่น พ่อ หรือ แม่',
    fEcPhone: 'เบอร์โทรศัพท์',
    pEcPhone: '+66 X',
    fRoles: 'เลือกบทบาทของคุณ (เลือกได้มากกว่าหนึ่ง)',
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
    fTg: 'Telegram ID (ตัวเลข)',
    btnTg: 'รับ ID ของฉัน →',
    pTg: 'เช่น 123456789',
    hTg: "คลิก 'รับ ID ของฉัน' กด Start ใน Telegram คัดลอกตัวเลข แล้ววางที่นี่",
    fLine: 'LINE ID',
    pLine: 'เช่น U1a2b3c4d5e',
    hLine: 'เปิดการตั้งค่า LINE ของคุณ คัดลอก User ID และวางที่นี่ด้วยตนเอง',
    fWa: 'เบอร์ WhatsApp',
    pWa: '+66 81 234 5678',
    hWa: 'ตรวจสอบให้แน่ใจว่าตรงกับเบอร์โทรศัพท์ที่ใช้งาน WhatsApp',
    btnSubmit: 'ส่งการลงทะเบียน',
    btnSubmitting: 'กำลังส่ง...',
    succTitle: 'รับเรื่องเรียบร้อยแล้ว',
    succDesc: 'ขอบคุณสำหรับการลงทะเบียน ทีมงานของเราจะตรวจสอบใบสมัครของคุณและเปิดสิทธิการใช้งานเร็วๆ นี้',
    designatedRoles: 'บทบาทที่คุณได้รับมอบหมาย'
  },
  he: {
    loading: 'טוען אפליקציה...',
    errInvalid: 'קישור הזמנה רוק או לא תקין.',
    errExpired: 'הקישור שברשותך לא חוקי, פג תוקף, או שכבר השתמשו בו.',
    errValidate: 'שגיאה באימות קישור ההזמנה.',
    errSubmit: 'שליחת הטופס נכשלה. ייתכן שהקישור פג תוקף.',
    errNetwork: 'שגיאת רשת',
    errAppMissing: 'אנא ספק/י פרטים לפחות לאפליקציית תקשורת אחת (טלגרם, LINE או וואטסאפ).',
    sysTitle: 'קליטת עובד חדש',
    sysSub: 'אנא מלא/י את הפרטים שלך למטה כדי להשלים את ההרשמה.',
    fEmail: 'כתובת אימייל *',
    fName: 'שם מלא *',
    pName: 'למשל ישראל ישראלי',
    fPhoto: 'תמונת סלפי / פרופיל *',
    photoReq: 'העלה/י תמונה כדי להמשיך',
    photoUpld: 'מעלה ודוחס... (עד ~2MB)',
    photoInfo: 'JPG, PNG, WEBP (עד 15MB). נדחוס את התמונה אוטומטית.',
    fPhone: 'מספר טלפון *',
    pPhone: '054 X',
    fLang: 'שפת אפליקציה / App Language *',
    fEcTitle: 'איש קשר לחירום',
    fEcName: 'שם איש קשר',
    pEcName: 'למשל אמא, אבא',
    fEcPhone: 'טלפון',
    pEcPhone: '054 X',
    fRoles: 'בחר/י את התפקידים שלך (ניתן לבחור יותר מאחד)',
    rCleaner: 'ניקיון',
    rCheckin: 'צ\'ק-אין',
    rCheckout: 'צ\'ק-אאוט',
    rBoth: 'צ\'ק-אין ואאוט (משולב)',
    rMaint: 'תחזוקה',
    rOp: 'מנהל תפעול',
    fDob: 'תאריך לידה *',
    fIdPhoto: 'צילום תעודת זהות / דרכון *',
    idPhotoReq: 'העלה/י תעודה כדי להמשיך',
    idPhotoUpld: 'מעלה מסמך מזהה...',
    fTg: 'מזהה טלגרם (מספר)',
    btnTg: 'קבל את ה-ID שלי ←',
    pTg: 'למשל 123456789',
    hTg: "לחץ על 'קבל את ה-ID שלי', בחר Start בטלגרם, העתק את המספר המדויק והדבק אותו כאן.",
    fLine: 'מזהה LINE',
    pLine: 'למשל U1a2b3c4d5e',
    hLine: "פתח/י את הגדרות ה-LINE שלך, העתק את ה-User ID, והדבק כאן.",
    fWa: 'מספר וואטסאפ',
    pWa: '+972 54 123 4567',
    hWa: 'וודא/י שקר מספר זה רשום בוואטסאפ במכשיר שלך.',
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
  
  // Form state
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [language, setLanguage] = useState('th');
  const [ecName, setEcName] = useState('');
  const [ecPhone, setEcPhone] = useState('');
  const [photoUrl, setPhotoUrl] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [idPhotoUrl, setIdPhotoUrl] = useState('');
  const [workerRoles, setWorkerRoles] = useState<string[]>([]);
  const [telegram, setTelegram] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [line, setLine] = useState('');
  
  const [rolesLocked, setRolesLocked] = useState(false);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [idPhotoUploading, setIdPhotoUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('errInvalid'); // map error in UI
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
          if (data.email) {
            setEmail(data.email);
            setEmailLocked(true);
          }
          if (data.language) setLanguage(data.language);
          if (data.worker_roles && Array.isArray(data.worker_roles) && data.worker_roles.length > 0) {
            setWorkerRoles(data.worker_roles);
            setRolesLocked(true);
          }
        }
      })
      .catch(() => setError('errValidate'))
      .finally(() => setLoading(false));
  }, [token]);

  const t = TRANSLATIONS[language as keyof typeof TRANSLATIONS] || TRANSLATIONS.en;

  // Resolve error text from TRANSLATIONS if it matches a key, otherwise show raw
  const resolveError = (err: string | null) => {
    if (!err) return null;
    return (t as any)[err] || err;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    
    if (!telegram.trim() && !whatsapp.trim() && !line.trim()) {
      setError('errAppMissing');
      return;
    }
    if (!dateOfBirth) {
      setError('Date of birth is required');
      return;
    }
    if (!idPhotoUrl) {
      setError('ID / Passport Photo is required');
      return;
    }
    
    setSubmitting(true);
    setError(null);
    
    const payload = {
      email: email.trim(),
      full_name: fullName,
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
        id_photo_url: idPhotoUrl 
      }
    };

    try {
      const res = await fetch(`${BASE}/staff-onboarding/submit/${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        // Phase 856B: try to read a structured backend error first
        try {
          const errBody = await res.json();
          if (errBody?.error === 'EMAIL_REQUIRED') {
            setError(errBody.message || 'An email address is required to complete your application.');
          } else {
            setError(errBody?.message || errBody?.error || 'errSubmit');
          }
        } catch {
          setError('errSubmit');
        }
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

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    
    const mime = file.type || '';
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(mime)) {
      alert('Only JPG, PNG, and WebP images are allowed.');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      alert('Image exceeds 15MB limit. Please choose a smaller file.');
      return;
    }

    try {
      setPhotoUploading(true);
      setError(null);
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${BASE}/staff-onboarding/upload-photo/${token}`, {
        method: 'POST',
        body: form
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.error || 'Upload failed');
      }
      const data = await res.json();
      setPhotoUrl(data.url);
    } catch (err: any) {
      alert(err.message || 'Network error during upload');
    } finally {
      setPhotoUploading(false);
    }
  };

  const handleIdPhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    
    const mime = file.type || '';
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(mime)) {
      alert('Only JPG, PNG, and WebP images are allowed.');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      alert('Image exceeds 15MB limit. Please choose a smaller file.');
      return;
    }

    try {
      setIdPhotoUploading(true);
      setError(null);
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${BASE}/staff-onboarding/upload-photo/${token}`, {
        method: 'POST',
        body: form
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.error || 'Upload failed');
      }
      const data = await res.json();
      setIdPhotoUrl(data.url);
    } catch (err: any) {
      alert(err.message || 'Network error during upload');
    } finally {
      setIdPhotoUploading(false);
    }
  };

  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}>{t.loading}</div>;
  if (error && !validToken) return (
    <div style={{ maxWidth: 400, margin: '80px auto', padding: 24, textAlign: 'center', background: '#fff', border: '1px solid #e1e4e8', borderRadius: 8 }}>
      <p style={{ color: '#d73a49', margin: 0 }}>{resolveError(error)}</p>
    </div>
  );
  
  if (success) return (
    <div style={{ maxWidth: 400, margin: '80px auto', padding: 32, textAlign: 'center', background: '#fff', border: '1px solid #e1e4e8', borderRadius: 8, direction: language === 'he' ? 'rtl' : 'ltr' }}>
      <div style={{ fontSize: 40, marginBottom: 16 }}>✅</div>
      <h2 style={{ margin: '0 0 12px 0', fontSize: 20 }}>{t.succTitle}</h2>
      <p style={{ color: '#586069', margin: 0, fontSize: 14 }}>
        {t.succDesc}
      </p>
    </div>
  );

  const isRTL = language === 'he';
  const inputStyle = { width: '100%', padding: '10px 14px', borderRadius: 6, border: '1px solid #e1e4e8', fontSize: 14, outline: 'none', background: '#f6f8fa', textAlign: isRTL ? 'right' as const : 'left' as const };
  const labelStyle = { display: 'block', fontSize: 12, fontWeight: 600, color: '#24292e', marginBottom: 6, textTransform: 'uppercase' as const, letterSpacing: '0.04em' };

  return (
    <div style={{ maxWidth: 500, margin: '40px auto', background: '#fff', border: '1px solid #e1e4e8', borderRadius: 12, overflow: 'hidden', direction: isRTL ? 'rtl' : 'ltr' }}>
      <div style={{ padding: '24px 32px', borderBottom: '1px solid #eaecef', background: '#fafbfc' }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 4px 0', color: '#24292e' }}>{t.sysTitle}</h1>
        <p style={{ margin: 0, color: '#586069', fontSize: 14 }}>{t.sysSub}</p>
      </div>

      <form onSubmit={handleSubmit} style={{ padding: 32, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {error && <div style={{ padding: '12px 16px', background: '#ffeef0', color: '#cb2431', borderRadius: 6, fontSize: 14 }}>{resolveError(error)}</div>}

        <div>
          <label style={labelStyle}>{t.fEmail}</label>
          {emailLocked ? (
            <div style={{ ...inputStyle, background: '#e1e4e8', color: '#586069', textAlign: 'left' }}>{email}</div>
          ) : (
            <input required type="email" style={{ ...inputStyle, textAlign: 'left' }} value={email} onChange={e => setEmail(e.target.value)} placeholder="worker@example.com" />
          )}
        </div>

        <div>
          <label style={labelStyle}>{t.fName}</label>
          <input required style={inputStyle} value={fullName} onChange={e => setFullName(e.target.value)} placeholder={t.pName} />
        </div>

        <div>
          <label style={labelStyle}>{t.fPhoto}</label>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            {photoUrl ? (
              <img src={photoUrl} alt="Preview" style={{ width: 64, height: 64, objectFit: 'cover', imageOrientation: 'from-image' as any, borderRadius: '50%', border: '1px solid #e1e4e8' }} />
            ) : (
              <div style={{ width: 64, height: 64, borderRadius: '50%', background: '#f6f8fa', border: '1px dashed #d1d5da', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, color: '#d1d5da' }}>📷</div>
            )}
            <div style={{ flex: 1, textAlign: isRTL ? 'right' : 'left' }}>
              <input type="file" accept=".jpg,.jpeg,.png,.webp" onChange={handlePhotoUpload} disabled={photoUploading} style={{ fontSize: 13, display: 'block', maxWidth: '100%' }} />
              {photoUploading && <span style={{ fontSize: 12, color: '#b08800', display: 'block', marginTop: 4 }}>{t.photoUpld}</span>}
              {!photoUploading && <p style={{ margin: '4px 0 0 0', fontSize: 11, color: '#586069' }}>{t.photoInfo}</p>}
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <label style={labelStyle}>{t.fPhone}</label>
            <input required style={{ ...inputStyle, direction: 'ltr', textAlign: isRTL ? 'right' : 'left' }} value={phone} onChange={e => setPhone(e.target.value)} placeholder={t.pPhone} />
          </div>
          <div>
            <label style={labelStyle}>{t.fDob}</label>
            <input required type="date" style={inputStyle} value={dateOfBirth} onChange={e => setDateOfBirth(e.target.value)} />
          </div>
        </div>

        <div>
          <label style={labelStyle}>{t.fIdPhoto}</label>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            {idPhotoUrl ? (
              <img src={idPhotoUrl} alt="ID Preview" style={{ width: 64, height: 64, objectFit: 'contain', imageOrientation: 'from-image' as any, borderRadius: '8px', border: '1px solid #e1e4e8' }} />
            ) : (
              <div style={{ width: 64, height: 64, borderRadius: '8px', background: '#f6f8fa', border: '1px dashed #d1d5da', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, color: '#d1d5da' }}>🪪</div>
            )}
            <div style={{ flex: 1, textAlign: isRTL ? 'right' : 'left' }}>
              <input type="file" accept=".jpg,.jpeg,.png,.webp" onChange={handleIdPhotoUpload} disabled={idPhotoUploading} style={{ fontSize: 13, display: 'block', maxWidth: '100%' }} />
              {idPhotoUploading && <span style={{ fontSize: 12, color: '#b08800', display: 'block', marginTop: 4 }}>{(t as any).idPhotoUpld}</span>}
            </div>
          </div>
        </div>

        <div>
           <label style={labelStyle}>{t.fLang}</label>
           <select style={{ ...inputStyle, appearance: 'auto' }} value={language} onChange={e => setLanguage(e.target.value)}>
             <option value="th">ภาษาไทย (Thai)</option>
             <option value="en">English</option>
             <option value="he">עברית (Hebrew)</option>
           </select>
        </div>

        <div style={{ padding: 16, background: '#f6f8fa', borderRadius: 8, border: '1px solid #e1e4e8' }}>
          <h4 style={{ margin: '0 0 12px 0', fontSize: 13, textTransform: 'uppercase', color: '#24292e' }}>{t.fEcTitle}</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <label style={labelStyle}>{t.fEcName}</label>
              <input style={{ ...inputStyle, background: '#fff' }} value={ecName} onChange={e => setEcName(e.target.value)} placeholder={t.pEcName} />
            </div>
            <div>
              <label style={labelStyle}>{t.fEcPhone}</label>
              <input style={{ ...inputStyle, background: '#fff', direction: 'ltr', textAlign: isRTL ? 'right' : 'left' }} value={ecPhone} onChange={e => setEcPhone(e.target.value)} placeholder={t.pEcPhone} />
            </div>
          </div>
        </div>

        <div style={{ marginTop: 8 }}>
          <label style={labelStyle}>{rolesLocked ? (t as any).designatedRoles : t.fRoles}</label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {ROLES_LIST.filter(r => rolesLocked ? workerRoles.includes(r.id) : true).map(r => {
              const selected = workerRoles.includes(r.id);
              const labelTxt = (t as any)[r.labelKey];
              return (
                <label 
                  key={r.id} 
                  style={{ 
                    display: 'flex', alignItems: 'center', gap: 10, cursor: rolesLocked ? 'default' : 'pointer', fontSize: 14, fontWeight: 600,
                    padding: '12px', borderRadius: 8, border: `2px solid ${selected ? '#0366d6' : '#e1e4e8'}`,
                    background: selected ? 'rgba(3, 102, 214, 0.05)' : '#fff', transition: 'all 0.1s', 
                    color: selected ? '#0366d6' : '#24292e'
                  }}
                >
                  <input type="checkbox" checked={selected} onChange={rolesLocked ? undefined : () => toggleRole(r.id)} style={{ transform: 'scale(1.2)', pointerEvents: rolesLocked ? 'none' : 'auto' }} />
                  {labelTxt}
                </label>
              );
            })}
          </div>
        </div>

        <div>
           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 6 }}>
             <label style={{ ...labelStyle, marginBottom: 0 }}>{t.fTg}</label>
             <a href="https://t.me/userinfobot" target="_blank" rel="noreferrer" style={{ fontSize: 12, color: '#0366d6', textDecoration: 'none', background: 'rgba(3,102,214,0.1)', padding: '4px 8px', borderRadius: 4 }}>{t.btnTg}</a>
           </div>
           <input style={{ ...inputStyle, direction: 'ltr', textAlign: isRTL ? 'right' : 'left' }} type="number" value={telegram} onChange={e => setTelegram(e.target.value)} placeholder={t.pTg} />
           <p style={{ margin: '4px 0 0 0', fontSize: 11, color: '#586069' }}>{t.hTg}</p>
        </div>

        <div>
           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 6 }}>
             <label style={{ ...labelStyle, marginBottom: 0 }}>{t.fLine}</label>
           </div>
           <input style={{ ...inputStyle, direction: 'ltr', textAlign: isRTL ? 'right' : 'left' }} value={line} onChange={e => setLine(e.target.value)} placeholder={t.pLine} />
           <p style={{ margin: '4px 0 0 0', fontSize: 11, color: '#586069' }}>{t.hLine}</p>
        </div>

        <div>
           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 6 }}>
             <label style={{ ...labelStyle, marginBottom: 0 }}>{t.fWa}</label>
           </div>
           <input style={{ ...inputStyle, direction: 'ltr', textAlign: isRTL ? 'right' : 'left' }} value={whatsapp} onChange={e => setWhatsapp(e.target.value)} placeholder={t.pWa} />
           <p style={{ margin: '4px 0 0 0', fontSize: 11, color: '#586069' }}>{t.hWa}</p>
        </div>

        <button 
          type="submit" 
          disabled={submitting || photoUploading || idPhotoUploading || !photoUrl || !idPhotoUrl}
          style={{ 
            marginTop: 16, padding: '14px 0', width: '100%', 
            background: '#2ea44f', color: '#fff', border: 'none', borderRadius: 6, 
            fontSize: 16, fontWeight: 600, cursor: (submitting || photoUploading || idPhotoUploading || !photoUrl || !idPhotoUrl) ? 'not-allowed' : 'pointer', opacity: (submitting || photoUploading || idPhotoUploading || !photoUrl || !idPhotoUrl) ? 0.7 : 1 
          }}
        >
          {submitting ? t.btnSubmitting : (!photoUrl ? t.photoReq : (!idPhotoUrl ? (t as any).idPhotoReq : t.btnSubmit))}
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
