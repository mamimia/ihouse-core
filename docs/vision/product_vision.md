# 📖 חזון המוצר — Domaniqo / iHouse Core
### גרסה 2.0 — עדכון אחרי הערות מנהל המוצר

> [!IMPORTANT]
> ספר הייחוס הרשמי. כל פיתוח ייבדק מול מסמך זה. Living document — מתעדכן עם כל שיחה.

---

## 1. 🎯 זהות המוצר

**Domaniqo = Backend Operations App** — מנהלת את כל מה שקורה מאחורי הקלעים של השכרות לטווח קצר.

### מה אנחנו **לא**:
```
❌ לא אתר listings — אורחים לא רואים אותנו, לא מזמינים דרכנו
❌ לא payment gateway — כסף לא עובר דרכנו
❌ לא ערוץ הזמנות — לא מתחרים ב-Airbnb/Booking.com
❌ לא חברת ביטוח, לא מנפיקים חשבוניות לאורח
```

### למי מיועדת:
| סוג | דוגמה | גודל |
|-----|-------|------|
| חברת ניהול גדולה | 50-1,000 וילות, צוות שלם | כמה מנהלים + עובדים |
| חברת ניהול קטנה | 5-50 וילות | 2-10 אנשים |
| בעל וילות פרטי | 2-5 וילות | יחיד + מנקה |

### ה-Value:
> **"חבר את הנכסים שלך — Domaniqo תעשה את כל השאר."**

---

## 2. 👥 תפקידים (Roles)

| תפקיד | תיאור | גישה |
|--------|--------|------|
| **Admin** | מנהל חברת הניהול | מלאה |
| **Operations Manager** | מנהל תפעולי — יורד לשטח | נכסים שהוקצו + urgent alerts + **Take-Over** |
| **Check-in/out Worker** | עובד שטח | Tasks + טופס + QR + דיווח + deposit |
| **Cleaner** | מנקה/ת | Tasks + צ'קליסט + צילומים + דיווח |
| **Maintenance** | תחזוקה (פנימי או חיצוני) | Tasks ספציפיים + דיווח |
| **Owner** | בעל הנכס האמיתי | Portal מוגבל — שקיפות מבוקרת |
| **Guest** | האורח (אחרי צ'ק-אין) | QR portal — מידע + extras + chat |

> [!NOTE]
> **כל עובד מקבל Worker ID ייחודי** במערכת (מעבר לשם). כל פעולה מתועדת עם ה-ID של מי שביצע אותה.

---

## 3. 🏠 רישום נכסים

### שיטה 1 — ייבוא מ-OTA (Wizard)
```
Admin מחבר ערוץ (Airbnb / Booking.com / etc.)
   ↓
המערכת מושכת: שם, תיאור, תמונות, amenities
(כולל dryer, hair dryer, AC — כל מה שה-OTA מפרסם)
   ↓
נפתח דף עם כל המידע שנמשך ← Admin יכול:
  ✏️ לערוך כל שדה (גם מה שנמשך אוטומטית)
  ➕ להוסיף מה שחסר
  🗑️ למחוק מה שלא רלוונטי
   ↓
נכס מקבל ID פנימי אוטומטי
```

> [!NOTE]
> **לגבי כמה נכסים**: כל נכס ב-Airbnb יש לו URL בפני עצמו. אבל דרך ה-API אפשר למשוך את כל ה-listings של אותו חשבון בבת אחת — ולכן ה-wizard מציג "Found X properties".

### שיטה 2 — רישום ידני
Admin יוצר נכס חדש מאפס ומילוי כל השדות ידנית.

### שדות נכס:
```
📝 פרטים בסיסיים:
├── שם הנכס
├── כתובת מלאה
├── 📍 GPS Location ← כפתור "Save Current Location"
│   (חשוב באיים בתאילנד — קשה להגיע לפי שם, קל לפי נקודה)
├── סוג נכס (villa, apartment, house, studio, room)
├── מספר חדרי שינה
├── מספר שירותים/מקלחות
├── מקסימום אורחים
├── שטח (מ"ר)
└── תיאור (multi-language)

⏰ שעות צ'ק-אין / צ'ק-אאוט:
├── Check-in Time: [3:00 PM] (default)
├── Check-out Time: [11:00 AM] (default)
└── (רק שעות — לא תאריכים. תאריכים מגיעים מההזמנה)

📸 תמונות — 2 סוגים:
├── 🖼️ תמונות הנכס: תמונות marketing (מ-Airbnb או upload)
└── 📷 תמונות Reference: תמונות ספציפיות לצוות ←
    "ככה הבית צריך להיראות אחרי ניקיון"
    ├── תמונה per חדר שינה
    ├── תמונה סלון
    ├── תמונה מטבח
    ├── תמונה חצר/חוץ (אם רלוונטי)
    └── מספר תמונות = מספר חדרים + אזורים משותפים

🏡 מידע על הבית:
├── 🔑 קוד דלת / מפתח (איפה נמצא?)
├── 📶 WiFi שם + סיסמה
├── ❄️ הוראות מזגן
├── 🚿 מים חמים — איך עובד (boiler? solar?)
├── 🍳 הוראות כיריים/תנור
├── 🔌 מיקום לוח חשמל (main breaker)
├── 🗑️ איפה לזרוק אשפה / מיחזור
├── 🅿️ חנייה — איפה ואיך
├── 🏊 בריכה — הוראות (אם יש)
├── 🧺 מכונת כביסה / מייבש — הוראות
├── 📺 טלוויזיה — שלט, ערוצים, Netflix code
├── 🔒 כספת — קוד (אם יש)
├── 🚨 חירום — מספרי חירום מקומיים
├── 📋 House Rules ← (חשוב! הbase של מה שהאורח יראה ב-QR portal)
└── 📝 הערות נוספות (free text)

🧹 Amenities (מתקנים):
├── נמשכים אוטומטית מ-OTA (אם קיימים)
├── ניתן להוסיף/לערוך ידנית
└── קטגוריות: kitchen, bathroom, bedroom, outdoor,
    entertainment, safety, parking, accessibility

🛍️ Extras זמינים (מוגדרים ע"י מנהל הנכסים):
├── Catalog מוכן מראש עם extras קלאסיים
│   (אופנוע, רכב, מסאז', שף, כביסה, סיור, late checkout...)
├── Admin יכול להפעיל/לכבות per property
├── Admin יכול להוסיף extras חדשים + תמחור
│   (שדות בהתאמה אישית לכל אזור/מקום)
└── כל extra = שם + תיאור + מחיר + מטבע + active/inactive

💰 Deposit (פיקדון):
├── האם הנכס דורש deposit? (כן/לא)
├── סכום deposit
├── מטבע (THB, USD, EUR...)
└── שיטת גבייה (מזומן ב-check-in)

👤 הקצאת עובדים:
├── מנקה default
├── Worker צ'ק-אין default
└── Maintenance worker (או חיצוני)
```

---

## 4. 🔄 מחזור חיי ההזמנה

### שלב 1 — הזמנה נכנסת מ-OTA
```
John Doe מזמין וילה דרך Airbnb
   ↓
Airbnb שולח webhook/iCal → Domaniqo מקבלת
   ↓
⚡ אוטומטי:
├── 📅 חוסמת תאריכים בכל הערוצים האחרים
├── 🧹 יוצרת Task ניקיון (לפני צ'ק-אין)
├── 🚶 יוצרת Task צ'ק-אין (ביום ההגעה)
├── 🚪 יוצרת Task צ'ק-אאוט (ביום העזיבה)
├── 📊 מושכת מידע פיננסי לדשבורד
├── 👤 שומרת פרטי אורח
└── 📧 (אופציונלי) שולחת מייל pre-arrival לאורח

📧 מייל Pre-Arrival (אופציונלי):
"Hi John! Welcome to [Property Name].
 Your check-in is on [date] at [time].
 We're [management company name], managing this property.
 
 Want to save time? Fill out your details now:
 [Link to digital check-in form]
 
 Or complete it when you arrive — your choice! 🌴"
```

### שלב 1B — הזמנה ידנית (Manual Booking)
```
מנהל יוצר הזמנה ב-Domaniqo:
├── בוחר נכס + תאריכים + שם אורח (אופציונלי)
├── בוחר סיבה:
│   ├── "הזמנה ישירה" (אורח לא מ-OTA)
│   ├── "שימוש עצמי" (המנהל עצמו)
│   ├── "בעל הבית בנכס" (owner משתמש)
│   └── "תחזוקה / חסימה"
│
├── 📅 חוסם תאריכים בכל ה-OTAs (אוטומטי)
│
└── 🔧 Tasks — אפשרות ביטול סלקטיבי:
    אם סיבה = "שימוש עצמי" או "בעל הבית":
    ┌────────────────────────────────┐
    │ Create tasks for this booking? │
    │                                │
    │ ☐ Check-in (often not needed)  │
    │ ☑ Check-out                    │
    │ ☐ Cleaning (owner may decline) │
    │                                │
    │       [Confirm]                │
    └────────────────────────────────┘
    
    אם סיבה = "הזמנה ישירה":
    → כל ה-tasks נוצרים כרגיל
```

---

## 5. 🚶 צ'ק-אין (Worker App)

```
📱 Worker מקבל התראה → Navigate (GPS) → מגיע לוילה
   ↓
מקבל את John → עובר על הבית → פותח טופס:

┌────────────────────────────────────┐
│  📋 Check-in Form                   │
│  Sunset Villa — Booking #BK-4892    │
│                                      │
│  👤 Guest Details                    │
│  (ממולא מראש מהבוקינג אם קיים)     │
│  Name: [John Doe          ]          │
│  Email: [john@email.com   ]          │
│  Phone: [+1 555-123-4567  ]          │
│                                      │
│  🛂 Passport / ID — Guest 1          │
│  ID Type: [Passport ▼]               │
│  ID Number: [AB1234567    ]           │
│  📸 [Take Photo of Passport]         │
│                                      │
│  🛂 Passport / ID — Guest 2          │
│  ID Type: [Passport ▼]               │
│  ID Number: [CD7654321    ]           │
│  📸 [Take Photo of Passport]         │
│                                      │
│  [+ Add Guest] (עד 5 אורחים בדוגמה)│
│                                      │
│  👥 Total Guests: [2]                │
│                                      │
│  💰 Deposit                          │
│  (visible only if property requires) │
│  Amount: ฿5,000                      │
│  📸 [Take Photo of Cash]             │
│  Status: [Collected ✅]              │
│                                      │
│  ✍️ Guest Signature                  │
│  ┌──────────────────────────┐        │
│  │      [signature pad]     │        │
│  └──────────────────────────┘        │
│                                      │
│              [Submit ✅]              │
└────────────────────────────────────┘
   ↓
Submit → Generate QR Code
   ↓
┌──────────────────────────┐
│  📱 Show QR to Guest      │
│                            │
│     ┌──────────────┐      │
│     │  [QR CODE]   │      │
│     └──────────────┘      │
│                            │
│  Guest scans → Portal opens│
│         [Done ✅]          │
└──────────────────────────┘
```

> [!NOTE]
> האורח יכול למלא חלק מהטופס **לפני ההגעה** (מהלינק במייל Pre-Arrival). מה שהוא ממלא מראש — כבר מולא. Worker רק משלים את מה שחסר (צילום דרכון, חתימה, deposit).

---

## 6. 📱 Guest QR Portal

```
John סורק QR → נפתח:
┌──────────────────────────────┐
│  🌴 Welcome, John!            │
│  Sunset Villa, Koh Phangan    │
│                                │
│  📅 Check-out: March 22, 11AM │
│  📶 WiFi: SunsetVilla/koh2026 │
│  🔑 Door Code: 4892           │
│  📋 House Rules →              │
│  📍 Location on Map →          │
│  📞 Emergency: 085-xxx-xxxx    │
│  ❄️ AC Instructions →          │
│  🚿 Hot Water Instructions →   │
│                                │
│  ── 🛍️ Available Extras ──    │
│  🏍️ Motorbike ₿350/day        │
│  🚗 Car Rental ₿1,500/day     │
│  💆 Thai Massage ₿500          │
│  👨‍🍳 Private Chef ₿2,500     │
│  🧺 Laundry ₿200/bag          │
│  🤿 Snorkeling ₿800            │
│  ⏰ Late Checkout ₿500         │
│  🚐 Island Tour ₿1,500        │
│  🎣 Deep Sea Fishing ₿3,000   │
│  [Order Extra →]               │
│                                │
│  ── 💬 Need Help? ──           │
│  💬 [Chat with us]             │
│  📱 [WhatsApp]                 │
│                                │
│  כתוב לנו: "בוקר טוב, אני     │
│  רוצה לצאת לטיול מחר עם אשתי  │
│  לג'ונגלים. אפשר להסדר?"      │
│                                │
└──────────────────────────────┘

extras שמוצגים = מה שהAdmin הפעיל לנכס הזה.
הזמנת extra → alert למנהל → המנהל מטפל.
chat → הודעה למנהל/ops manager.
```

---

## 7. 🚪 צ'ק-אאוט (Worker App)

```
📱 Worker מקבל התראה → מגיע לוילה
   ↓
פותח מסך צ'ק-אאוט:
├── רואה תמונות Reference (מרישום הנכס)
├── רואה תמונות ניקיון אחרון (שהמנקה צילמה לפני הצ'ק-אין הזה)
│   → רק תמונות רלוונטיות לבוקינג האחרון
│
├── עובר על הבית עם האורח
├── אם יש deposit:
│   ├── בודק מצב הבית
│   ├── אם הכל תקין → מחזיר deposit מלא
│   ├── אם יש deductions:
│   │   ┌────────────────────────────────┐
│   │   │ 💰 Deposit Settlement           │
│   │   │                                │
│   │   │ Original Deposit: ฿10,000      │
│   │   │                                │
│   │   │ Deductions:                    │
│   │   │ ├── ⚡ Electricity: -฿2,000    │
│   │   │ ├── 🔧 Broken lamp: -฿1,500   │
│   │   │ ├── 🧺 Extra laundry: -฿500   │
│   │   │ └── Total Deductions: -฿4,000  │
│   │   │                                │
│   │   │ Refund Amount: ฿6,000          │
│   │   │                                │
│   │   │ 📸 [Photo Evidence]            │
│   │   │ ✍️ Guest Signature             │
│   │   │      [Confirm Settlement ✅]   │
│   │   └────────────────────────────────┘
│   └── מסמן: Deposit [Full Return ✅] / [Partial ⚠️ +amount]
│
├── ⚠️ Report Problem (אם יש)
│
└── ✅ Complete Check-out
   ↓
🧹 Task ניקיון → מנקה מקבלת alert
   (המנקה כבר יודעת מראש — זה בקלנדר שלה)
```

---

## 8. 🧹 ניקיון (Cleaner App)

```
המנקה יודעת מראש (מהקלנדר) על כל צ'ק-אאוט.
ביום הצ'ק-אאוט → alert חי: "Sunset Villa ready for cleaning"
   ↓
לוחצת Navigate → GPS → מגיעה

📋 Cleaning Checklist:
(ה-UI בשפת המנקה — תאילנדית, אנגלית, עברית, etc.)

┌──────────────────────────────────┐
│  🧹 รายการทำความสะอาด              │
│  (Cleaning Checklist)              │
│  Sunset Villa                      │
│                                    │
│  📸 Reference Photos: [view →]     │
│                                    │
│  🛏️ ห้องนอน 1 (Bedroom 1):       │
│  ☐ เปลี่ยนผ้าปูที่นอน (change sheets) │
│  ☐ เปลี่ยนปลอกหมอน (pillowcases)  │
│  ☐ ทำความสะอาดห้อง (clean room)   │
│  ☐ 📸 ถ่ายรูป (take photo)         │
│                                    │
│  🛏️ ห้องนอน 2 (Bedroom 2):       │
│  ☐ (same as above)                 │
│  ☐ 📸 ถ่ายรูป                      │
│                                    │
│  🚿 ห้องน้ำ (Bathroom):            │
│  ☐ ทำความสะอาด (clean)             │
│  ☐ ตรวจสบู่/แชมพู (soap/shampoo)  │
│  ☐ ผ้าขนหนูสะอาด (clean towels)   │
│  ☐ 📸 ถ่ายรูป                      │
│                                    │
│  🍳 ห้องครัว (Kitchen):            │
│  ☐ เคาน์เตอร์ (counters)           │
│  ☐ เตา (stove)                     │
│  ☐ ทิ้งขยะ (trash)                 │
│  ☐ 📸 ถ่ายรูป                      │
│                                    │
│  🛋️ ห้องนั่งเล่น (Living Room):   │
│  ☐ ทำความสะอาด + จัดเรียบร้อย     │
│  ☐ 📸 ถ่ายรูป                      │
│                                    │
│  📦 คลังสินค้า (Storage/Supplies):  │
│  ☐ ผ้าปูที่นอนเพียงพอ? (sheets ok?) │
│  ☐ ผ้าขนหนูเพียงพอ? (towels ok?)   │
│  ☐ สบู่/แชมพูเพียงพอ? (soap ok?)   │
│  ☐ กระดาษชำระเพียงพอ? (TP ok?)    │
│  ☐ 📸 ถ่ายรูปคลัง (photo storage)  │
│                                    │
│  ⚠️ รายงานปัญหา (Report Problem)   │
│                                    │
│  ⛔ "Complete" disabled until ALL   │
│     photos taken + checklist done   │
│         [Complete Task ✅]          │
└──────────────────────────────────┘
```

> [!IMPORTANT]
> **i18n**: המנקה כותבת בעיות **בשפה שלה** (תאילנדית). המנהל/Admin רואה את זה **בשפה שהוא בחר** (אנגלית/עברית). המערכת מתרגמת אוטומטית.

---

## 9. ⚠️ דיווח בעיות (כל התפקידים)

```
זמין ל: Worker, Cleaner, Maintenance, Ops Manager

┌────────────────────────────────┐
│  ⚠️ Report a Problem            │
│                                  │
│  Property: [Sunset Villa]        │
│                                  │
│  📍 מקור הבעיה:                  │
│  [▼ בחר קטגוריה]                │
│  ├── 🏊 Pool / בריכה             │
│  ├── 🔧 Plumbing / אינסטלציה     │
│  ├── ⚡ Electrical / חשמל        │
│  ├── ❄️ AC/Heating / מיזוג       │
│  ├── 🪑 Furniture / ריהוט        │
│  ├── 🏠 Structure / מבנה         │
│  ├── 📺 TV/Electronics            │
│  ├── 🚿 Bathroom / שירותים       │
│  ├── 🍳 Kitchen / מטבח           │
│  ├── 🌿 Garden/Outdoor / חוץ     │
│  ├── 🐛 Pest / מזיקים            │
│  ├── 🧹 Cleanliness / ניקיון     │
│  ├── 🔐 Security / אבטחה         │
│  └── ❓ Other / אחר              │
│                                  │
│  📝 Description:                 │
│  [น้ำร้อนไม่ทำงานในห้องน้ำ      │
│   ใหญ่]                          │
│  (hot water not working in       │
│   master bathroom)               │
│                                  │
│  Priority: (•)Urgent ( )Normal   │
│                                  │
│  📸 [Take Photo] [Add More]      │
│  📷 photo1  📷 photo2            │
│                                  │
│         [Submit ⚠️]              │
└────────────────────────────────┘
   ↓
⚡ Urgent items → auto-appear on:
├── Admin Dashboard (main)
├── Operations Manager Dashboard
└── Maintenance Worker (if internal)

For external maintenance:
Admin/Ops Manager reviews → decides → pushes task to external worker
```

---

## 10. 🔧 Maintenance Worker

### מודל גמיש — Admin שולט:
```
Admin → Settings → Maintenance Team:

Toggle: [One maintenance worker] / [Multiple specialists]

אם One ← עסק קטן (5-20 נכסים):
└── Maintenance אחד → רואה הכל: בריכה, חשמל, צבע, ריהוט, gardening
    → UI אחד עם כל ה-tasks

אם Multiple ← עסק גדול (50+ נכסים):
┌──────────────────────────────────┐
│ 🔧 Maintenance Specialists        │
│                                    │
│ [+ Add Specialist]                 │
│                                    │
│ 🏊 Pool Tech — Somchai (WRK-050) │
│    Sees: Pool tasks only           │
│                                    │
│ 🔧 Plumber — Anon (WRK-051)      │
│    Sees: Plumbing tasks only       │
│                                    │
│ ⚡ Electrician — Chai (WRK-052)   │
│    Sees: Electrical tasks only     │
│                                    │
│ 🎨 General Fix — Noi (WRK-053)   │
│    Sees: Furniture, paint, other   │
│                                    │
│ 🌿 Gardener — Lek (WRK-054)      │
│    Sees: Garden/outdoor tasks only │
└──────────────────────────────────┘

כל specialist → UI ייחודי בטלפון שלו
רואה רק tasks מהקטגוריות שהוקצו לו
Admin מוסיף סוגים חדשים לפי הצורך

פנימי vs חיצוני:
├── פנימי: מקבל alerts ישירות
└── חיצוני: Admin/Ops Manager צריך לדחוף לו task ← גישה מוגבלת
```

### מה Maintenance Worker רואה באפליקציה:
```
├── 📋 רשימת Tasks פתוחים (רק הקטגוריות שלו)
├── 📸 תמונות הבעיה (אם צולמו)
├── 📝 תיאור הבעיה + קטגוריה
├── 📍 Navigate לנכס
├── ☐ צ'קליסט (מה צריך לעשות)
├── 📸 צילום אחרי תיקון
├── ⚠️ דיווח על בעיות נוספות שמצא
└── ✅ Complete Task
```

---

## 11. 🔀 Task Take-Over — מנהל "לוקח" task

```
מצב: המנקה לא מגיעה / Maintenance לא זמין / Worker חולה
   ↓
Ops Manager רואה task פתוח + worker לא מגיב
   ↓
לוחץ כפתור [🔀 Take Over]
   ↓
┌────────────────────────────────────┐
│  🔀 Take Over Task                  │
│                                      │
│  Task: Cleaning — Sunset Villa       │
│  Assigned to: Somchai (WRK-042)      │
│  Status: No response                 │
│                                      │
│  ⚠️ This will reassign the task      │
│  to you (MGR-003).                   │
│                                      │
│  Reason: [Worker unavailable ▼]      │
│  ├── Worker unavailable              │
│  ├── Worker sick                     │
│  ├── Emergency situation             │
│  └── Other                           │
│                                      │
│     [Cancel]  [Take Over ✅]         │
└────────────────────────────────────┘
   ↓
Ops Manager:                          Worker (Somchai):
├── מקבל את ה-task על שמו              ├── רואה באפליקציה:
├── רואה צ'קליסט, reference photos     │   "Task taken over by
├── עובד (או מביא מנקה חלופית)         │    Manager Yossi (MGR-003)"
├── משלים צ'קליסט + תמונות             │   Status: Completed by other
└── ✅ Complete                         └── ❌ Task locked — read only
```

> המערכת ממשיכה לפעול רגיל אחרי Take-Over — tasks הבאים נוצרים כרגיל.

---

## 12. 👁️ Owner Portal — שקיפות מבוקרת

```
Admin → Owners → [owner] → Access Settings:

📊 מה Owner רואה? (configurable per owner):
├── ✅/☐ מספר הזמנות החודש
├── ✅/☐ תאריכי תפוסה (לוח שנה)
├── ✅/☐ שמות אורחים
├── ✅/☐ מחירים ללילה
├── ✅/☐ סכום הכנסות
├── ✅/☐ סטטוס ניקיון
├── ✅/☐ דיווחי תחזוקה + תמונות
├── ✅/☐ עלויות תפעול
├── ✅/☐ ביקורות אורחים
└── ✅/☐ פרטי עובדים

בעל בית A → רואה 100% (שקיפות מלאה)
בעל בית B → רואה 50% (רק תפוסה + תחזוקה)
```

---

## 13. 📋 טופס צ'ק-אין — פשוט ולא פולשני

> [!NOTE]
> **TM.30 הוא לא אחריות שלנו.** האורח ממלא TM.30 לפני ההגעה לתאילנד. אנחנו לא הממשלה ולא ההגירה. אנחנו פשוט מקבלים אורח לוילה — כמו מלון.

### 🌐 שפת הטופס:
הטופס מוצג **בשפת האורח** — בוחר בהתחלה:
```
┌──────────────────────────┐
│  🌐 Select Language       │
│  🇬🇧 English              │
│  🇹🇭 ภาษาไทย              │
│  🇮🇱 עברית                 │
└──────────────────────────┘
```

### 👤 סוג אורח (Guest Type):
```
┌──────────────────────────────┐
│  Guest Type:                  │
│  (•) 🌍 Tourist (תייר)       │
│  ( ) 🏠 Resident (תושב)      │
└──────────────────────────────┘
```

### הטופס שלנו — לפי סוג אורח:
```
═══ אם Tourist (תייר) ═══
שדות חובה:
├── Full Name (שם מלא — נמשך מהבוקינג אם אפשר)
├── Nationality (אזרחות / מדינה)
├── Passport Number (מספר דרכון)
├── 📸 צילום דרכון (עמוד פתוח)
├── Phone Number (טלפון)
└── מספר אורחים כולל

שדות אופציונליים:
├── Email (לפעמים נמשך מהבוקינג)
├── Arrival Time (שעת הגעה פיזית)
└── Special Requests / Notes

═══ אם Resident (תושב מקומי) ═══
שדות חובה:
├── Full Name (ชื่อ-นามสกุล / שם מלא)
├── Thai ID Number (เลขบัตรประชาชน)
├── 📸 צילום תעודת זהות
├── Phone Number (เบอร์โทร)
└── מספר אורחים כולל

שדות אופציונליים:
├── Email
└── Special Requests / Notes
```

> **הרעיון:** פשוט, כמו שנכנסים לחדר במלון. לא פולשני — לא שואלים על ויזה, לא על תאריך לידה, לא על כתובת מגורים. אנחנו פשוט חברת operations. תייר = דרכון, תושב = תעודת זהות.

---

### 🌍 טפסים למדינות אחרות (עתידי — לא פעיל עכשיו)

<details>
<summary>🇪🇸 ספרד — SES Hospedajes (לפתיחה עתידית)</summary>

```
שדות חובה לכל אורח (כולל קטינים):
├── First Name + Last Name (+ second last name)
├── Gender
├── Date of Birth
├── Nationality
├── Document Type + Number
├── Email + Phone
├── Place of Habitual Residence
├── Kinship (minors)
├── Check-in/out Date + Time
├── Guest Signature (14+)
├── Deadline: 24 שעות
└── Penalty: €100-€30,000
```

נפתח כשנתרחב לאירופה. המערכת מוכנה לתמוך במדינות נוספות עם הזמן.
</details>

---

## 14. 📌 מה ללמוד מחברת X (מעודכן)

| פיצ'ר | רלוונטי? | הסבר |
|-------|----------|------|
| Wizard חיבור נכסים + import amenities | ✅ כן | **חיוני מאוד** — הדרך הראשונה של לקוח להתחבר, צריך להיות חלק |
| Guest Extras (QR portal) | ✅ כן | דרך QR, לא booking |
| טופס צ'ק-אין דיגיטלי | ✅ כן | פשוט, לא פולשני, מותאם לתאילנד |
| OTP Login | ✅ כן | passwordless |
| Dashboard + data pull | ✅ כן | read-only financial |
| Pre-arrival email | ✅ כן | send form before arrival |
| Direct Booking Website | ❌ לא | אנחנו לא ערוץ |
| Payment Processing | ❌ לא | כסף לא דרכנו |
| Split Payouts | ❌ לא | לא מטפלים בכסף |
| Damage Protection | ❌ לא | לא ביטוח |
| Unified Inbox (cross-OTA) | ❌ לא כרגע | לא MVP |

---

## 15. 🚀 Wizard חיבור נכסים — רעיונות ל-Bulk Import

כשמגיע מנהל עם 50 נכסים — הוא לא צריך לעבוד שעות.

```
💡 רעיונות להקלה:

1️⃣ One-Click Connect:
   “Connect your Airbnb” → OAuth login → מושך את כל ה-listings בבת אחת
   אותו דבר ל-Booking.com, Trip.com, etc.

2️⃣ Bulk Select & Import:
   ┌────────────────────────────────┐
   │ Found 50 properties on Airbnb  │
   │                                │
   │ [☑ Select All]                 │
   │ ☑ Villa 1  ☑ Villa 2  ☑ Villa 3 │
   │ ...                            │
   │                                │
   │      [Import 50 Properties]    │
   └────────────────────────────────┘

3️⃣ Smart Defaults:
   אחרי import → המערכת מגדירה אוטומטית:
   ├── Check-in: 3:00 PM, Check-out: 11:00 AM (default)
   ├── Cleaning checklist = standard template
   └── מנהל משנה רק מה שרוצה

4️⃣ iCal Fallback:
   אם API לא זמין → “Paste your iCal URL” → סנכרון בסיסי

5️⃣ CSV/Spreadsheet Import:
   “Upload a spreadsheet with your properties”
   עמודות: Name, Address, Rooms, Bathrooms, Max Guests, WiFi, Door Code
   → יוצר 50 נכסים בבת אחת

6️⃣ Duplicate Detection:
   אם אותו נכס קיים ב-Airbnb וגם ב-Booking →
   “This looks like the same property — merge?”
   → מאחד נכסים כפולים אוטומטית
```
