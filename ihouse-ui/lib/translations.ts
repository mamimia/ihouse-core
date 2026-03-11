/**
 * Phase 260 — UI Translation Strings (en / th / he)
 * ====================================================
 * Source of truth for all translateable UI strings.
 * Worker screen strings are prioritized for Thai quality.
 */

export type SupportedLang = 'en' | 'th' | 'he';

// Type for the English reference pack (source of truth for key names).
// th/he use Record<keyof typeof en, string> so translated values are OK.
type EnPack = typeof en;
type TranslationPack = { [K in keyof EnPack]: string };


const en = {
  // ── Navigation ──────────────────────────────────────
  'nav.dashboard':    'Dashboard',
  'nav.tasks':        'Tasks',
  'nav.bookings':     'Bookings',
  'nav.calendar':     'Calendar',
  'nav.financial':    'Financial',
  'nav.owner':        'Owner',
  'nav.manager':      'Manager',
  'nav.guests':       'Guests',
  'nav.admin':        'Admin',
  'nav.logout':       'Sign out',

  // ── Auth / Login ─────────────────────────────────────
  'auth.tagline':     'Calm command for modern hospitality.',
  'auth.sign_in':     'Sign in',
  'auth.tenant_id':   'Tenant ID',
  'auth.secret':      'Secret',
  'auth.sign_in_btn': 'Sign in →',
  'auth.signing_in':  'Signing in…',
  'auth.footer':      'Domaniqo · See every stay.',

  // ── Worker – Bottom Tabs ──────────────────────────────
  'worker.tab_todo':      'To Do',
  'worker.tab_active':    'Active',
  'worker.tab_done':      'Done',
  'worker.tab_channel':   'Channel',

  // ── Worker – Task list ───────────────────────────────
  'worker.my_tasks':      'My Tasks',
  'worker.no_tasks':      'No tasks here.',
  'worker.loading':       'Loading…',
  'worker.overdue':       'OVERDUE',

  // ── Worker – Task detail ─────────────────────────────
  'worker.property':      'Property',
  'worker.due':           'Due',
  'worker.priority':      'Priority',
  'worker.status':        'Status',
  'worker.role':          'Role',
  'worker.booking':       'Booking',
  'worker.notes':         'Notes',
  'worker.overdue_alert': 'This task is overdue — action required immediately',

  // ── Worker – Actions ──────────────────────────────────
  'worker.acknowledge':       'Acknowledge',
  'worker.acknowledge_crit':  '⚡ Acknowledge Now',
  'worker.mark_complete':     '✅ Mark as Complete',
  'worker.confirm_complete':  '✅ Confirm Complete',
  'worker.processing':        'Processing…',
  'worker.saving':            'Saving…',
  'worker.cancel':            'Cancel',
  'worker.add_notes':         'Add completion notes (optional)',
  'worker.notes_placeholder': 'E.g. All rooms cleaned, keys returned…',
  'worker.task_done':         'Task completed',

  // ── Worker – SLA ──────────────────────────────────────
  'worker.sla_expired':       'SLA EXPIRED',
  'worker.sla_to_ack':        'to acknowledge',

  // ── Worker – Status labels ────────────────────────────
  'status.pending':       'Pending',
  'status.acknowledged':  'Acknowledged',
  'status.in_progress':   'In Progress',
  'status.completed':     'Completed',
  'status.canceled':      'Canceled',

  // ── Worker – Channel tab ──────────────────────────────
  'channel.active':         'Active Channels',
  'channel.no_channels':    'No channels configured yet',
  'channel.no_channels_sub':'Add one below to receive task notifications',
  'channel.set':            'Set Notification Channel',
  'channel.save':           'Save Channel',
  'channel.saving':         'Saving…',
  'channel.remove':         'Remove',
  'channel.info':           'Set your preferred channel to receive task notifications.',
  'channel.recent':         'Recent Notifications',
  'channel.no_history':     'No notifications sent yet.',

  // ── Language switcher ────────────────────────────────
  'lang.label':   'Language',
  'lang.en':      'English',
  'lang.th':      'ภาษาไทย',
  'lang.he':      'עברית',
} as const;

const th: TranslationPack = {
  'nav.dashboard':    'แดชบอร์ด',
  'nav.tasks':        'งาน',
  'nav.bookings':     'การจอง',
  'nav.calendar':     'ปฏิทิน',
  'nav.financial':    'การเงิน',
  'nav.owner':        'เจ้าของ',
  'nav.manager':      'ผู้จัดการ',
  'nav.guests':       'แขก',
  'nav.admin':        'แอดมิน',
  'nav.logout':       'ออกจากระบบ',

  'auth.tagline':     'ควบคุมที่พักอย่างมืออาชีพ',
  'auth.sign_in':     'เข้าสู่ระบบ',
  'auth.tenant_id':   'รหัสผู้เช่า',
  'auth.secret':      'รหัสผ่าน',
  'auth.sign_in_btn': 'เข้าสู่ระบบ →',
  'auth.signing_in':  'กำลังเข้าสู่ระบบ…',
  'auth.footer':      'Domaniqo · ดูแลทุกการพัก',

  'worker.tab_todo':      'งานที่ต้องทำ',
  'worker.tab_active':    'กำลังทำ',
  'worker.tab_done':      'เสร็จแล้ว',
  'worker.tab_channel':   'ช่องทาง',

  'worker.my_tasks':      'งานของฉัน',
  'worker.no_tasks':      'ไม่มีงานในส่วนนี้',
  'worker.loading':       'กำลังโหลด…',
  'worker.overdue':       'เกินกำหนด',

  'worker.property':      'ทรัพย์สิน',
  'worker.due':           'กำหนดเวลา',
  'worker.priority':      'ความเร่งด่วน',
  'worker.status':        'สถานะ',
  'worker.role':          'บทบาท',
  'worker.booking':       'การจอง',
  'worker.notes':         'หมายเหตุ',
  'worker.overdue_alert': 'งานนี้เกินกำหนดแล้ว — ต้องดำเนินการทันที',

  'worker.acknowledge':       'รับทราบ',
  'worker.acknowledge_crit':  '⚡ รับทราบด่วน',
  'worker.mark_complete':     '✅ ทำเสร็จแล้ว',
  'worker.confirm_complete':  '✅ ยืนยันว่าเสร็จแล้ว',
  'worker.processing':        'กำลังดำเนินการ…',
  'worker.saving':            'กำลังบันทึก…',
  'worker.cancel':            'ยกเลิก',
  'worker.add_notes':         'เพิ่มบันทึกการเสร็จสิ้น (ไม่บังคับ)',
  'worker.notes_placeholder': 'เช่น ทำความสะอาดห้องเสร็จแล้ว, คืนกุญแจแล้ว…',
  'worker.task_done':         'งานเสร็จสิ้นแล้ว',

  'worker.sla_expired':       'SLA หมดเวลา',
  'worker.sla_to_ack':        'เพื่อรับทราบ',

  'status.pending':       'รอดำเนินการ',
  'status.acknowledged':  'รับทราบแล้ว',
  'status.in_progress':   'กำลังดำเนินการ',
  'status.completed':     'เสร็จสิ้น',
  'status.canceled':      'ยกเลิกแล้ว',

  'channel.active':          'ช่องทางที่เปิดใช้',
  'channel.no_channels':     'ยังไม่มีช่องทางที่ตั้งค่าไว้',
  'channel.no_channels_sub': 'เพิ่มช่องทางด้านล่างเพื่อรับการแจ้งเตือนงาน',
  'channel.set':             'ตั้งค่าช่องทางรับการแจ้งเตือน',
  'channel.save':            'บันทึกช่องทาง',
  'channel.saving':          'กำลังบันทึก…',
  'channel.remove':          'ลบ',
  'channel.info':            'ตั้งค่าช่องทางที่คุณต้องการรับการแจ้งเตือนงาน',
  'channel.recent':          'การแจ้งเตือนล่าสุด',
  'channel.no_history':      'ยังไม่มีการแจ้งเตือนที่ส่งออกไป',

  'lang.label': 'ภาษา',
  'lang.en':    'English',
  'lang.th':    'ภาษาไทย',
  'lang.he':    'עברית',
};

const he: TranslationPack = {
  'nav.dashboard':    'לוח בקרה',
  'nav.tasks':        'משימות',
  'nav.bookings':     'הזמנות',
  'nav.calendar':     'לוח שנה',
  'nav.financial':    'פיננסים',
  'nav.owner':        'בעלים',
  'nav.manager':      'מנהל',
  'nav.guests':       'אורחים',
  'nav.admin':        'ניהול',
  'nav.logout':       'התנתקות',

  'auth.tagline':     'פיקוד רגוע לאירוח מודרני.',
  'auth.sign_in':     'כניסה',
  'auth.tenant_id':   'מזהה דייר',
  'auth.secret':      'סיסמה',
  'auth.sign_in_btn': 'כניסה ←',
  'auth.signing_in':  'מתחבר…',
  'auth.footer':      'Domaniqo · ראה כל שהייה.',

  'worker.tab_todo':      'לביצוע',
  'worker.tab_active':    'פעיל',
  'worker.tab_done':      'הושלם',
  'worker.tab_channel':   'ערוץ',

  'worker.my_tasks':      'המשימות שלי',
  'worker.no_tasks':      'אין משימות כאן.',
  'worker.loading':       'טוען…',
  'worker.overdue':       'באיחור',

  'worker.property':      'נכס',
  'worker.due':           'מועד יעד',
  'worker.priority':      'עדיפות',
  'worker.status':        'סטטוס',
  'worker.role':          'תפקיד',
  'worker.booking':       'הזמנה',
  'worker.notes':         'הערות',
  'worker.overdue_alert': 'משימה זו באיחור — נדרש טיפול מיידי',

  'worker.acknowledge':       'אישור קבלה',
  'worker.acknowledge_crit':  '⚡ אישור מיידי',
  'worker.mark_complete':     '✅ סמן כהושלם',
  'worker.confirm_complete':  '✅ אשר השלמה',
  'worker.processing':        'מעבד…',
  'worker.saving':            'שומר…',
  'worker.cancel':            'ביטול',
  'worker.add_notes':         'הוסף הערות השלמה (אופציונלי)',
  'worker.notes_placeholder': 'לדוגמה: כל החדרים נוקו, המפתחות הוחזרו…',
  'worker.task_done':         'המשימה הושלמה',

  'worker.sla_expired':       'SLA פג תוקף',
  'worker.sla_to_ack':        'לאישור קבלה',

  'status.pending':       'ממתין',
  'status.acknowledged':  'אושר',
  'status.in_progress':   'בביצוע',
  'status.completed':     'הושלם',
  'status.canceled':      'בוטל',

  'channel.active':          'ערוצים פעילים',
  'channel.no_channels':     'אין ערוצים מוגדרים עדיין',
  'channel.no_channels_sub': 'הוסף ערוץ למטה כדי לקבל התראות משימה',
  'channel.set':             'הגדר ערוץ התראות',
  'channel.save':            'שמור ערוץ',
  'channel.saving':          'שומר…',
  'channel.remove':          'הסר',
  'channel.info':            'הגדר את הערוץ המועדף לקבלת התראות משימה.',
  'channel.recent':          'התראות אחרונות',
  'channel.no_history':      'לא נשלחו התראות עדיין.',

  'lang.label': 'שפה',
  'lang.en':    'English',
  'lang.th':    'ภาษาไทย',
  'lang.he':    'עברית',
};

export const translations: Record<SupportedLang, TranslationPack> = { en, th, he };
export type TranslationKey = keyof typeof en;
