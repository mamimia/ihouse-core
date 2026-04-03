import { useState } from "react";
import { Home, ClipboardList, CheckSquare, Settings, ChevronRight, ArrowLeft, MapPin, Clock, Calendar, AlertTriangle, Camera, Phone, Mail, ChevronDown, Star, Navigation, User, Bell, Wifi } from "lucide-react";

// ─── DESIGN TOKENS ───────────────────────────────────────────
const T = {
  bg: "#0F1214",
  surface: "#1A1E22",
  card: "#1E2328",
  cardBorder: "#2A2F35",
  text: "#E8E4DE",
  textDim: "#8A8680",
  textMuted: "#5C5955",
  moss: "#334036",
  mossLight: "#3D5043",
  mossBright: "#5A8C66",
  copper: "#B56E45",
  amber: "#F59E0B",
  red: "#DC2626",
  blue: "#3B82F6",
  green: "#22C55E",
  white: "#FFFFFF",
  bottomNav: "#141719",
};

// ─── BOTTOM NAV ──────────────────────────────────────────────
function BottomNav({ active, onNavigate }) {
  const tabs = [
    { id: "home", label: "Home", icon: Home },
    { id: "checkin", label: "Check-in", icon: ClipboardList },
    { id: "tasks", label: "Tasks", icon: CheckSquare },
    { id: "settings", label: "Settings", icon: Settings },
  ];
  return (
    <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, height: 56, background: T.bottomNav, display: "flex", borderTop: `1px solid ${T.cardBorder}`, zIndex: 50 }}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = active === tab.id;
        return (
          <button key={tab.id} onClick={() => onNavigate(tab.id)} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2, background: "none", border: "none", cursor: "pointer", color: isActive ? T.mossBright : T.textMuted }}>
            <Icon size={20} strokeWidth={isActive ? 2.2 : 1.5} />
            <span style={{ fontSize: 10, fontWeight: isActive ? 700 : 400 }}>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

// ─── STATUS BADGE ────────────────────────────────────────────
function Badge({ label, color }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", padding: "2px 8px", borderRadius: 4, background: color + "22", color, letterSpacing: 0.5 }}>{label}</span>
  );
}

// ─── SCREEN: S00 — WORKER HOME ──────────────────────────────
function HomeScreen({ onNavigate }) {
  return (
    <div style={{ padding: "16px 16px 72px", minHeight: "100vh", background: T.bg }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <span style={{ fontSize: 18, fontWeight: 700, color: T.text }}>Home</span>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span style={{ fontSize: 12, color: T.textDim }}>EN</span>
          <span style={{ fontSize: 12, color: T.textDim }}>→ Sign Out</span>
        </div>
      </div>

      {/* Welcome */}
      <div style={{ background: T.card, borderRadius: 12, padding: 16, marginBottom: 16, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 11, color: T.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>Welcome</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ fontSize: 22, fontWeight: 700, color: T.text }}>Hello, Somchai</span>
          <Badge label="Check-in Staff" color={T.mossBright} />
        </div>
      </div>

      {/* My Status */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: T.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>My Status</div>
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { icon: "📁", label: "Open", value: 9, color: T.amber },
            { icon: "●", label: "Overdue", value: 0, color: T.green },
            { icon: "📅", label: "Today", value: 2, color: T.copper },
          ].map((s) => (
            <div key={s.label} style={{ flex: 1, background: T.card, borderRadius: 10, padding: "12px 10px", border: `1px solid ${T.cardBorder}` }}>
              <div style={{ fontSize: 10, color: T.textMuted, marginBottom: 4 }}>
                <span style={{ color: s.color, marginRight: 4 }}>{s.icon}</span>{s.label}
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, color: T.text }}>{s.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Work CTA */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, color: T.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>Work</div>
        <button onClick={() => onNavigate("checkin")} style={{ width: "100%", background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 16, display: "flex", alignItems: "center", gap: 12, cursor: "pointer", textAlign: "left" }}>
          <div style={{ width: 40, height: 40, borderRadius: 10, background: T.moss, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <ClipboardList size={20} color={T.mossBright} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: T.text }}>Go to Check-ins</div>
            <div style={{ fontSize: 12, color: T.textDim }}>9 tasks waiting</div>
          </div>
          <ChevronRight size={18} color={T.textMuted} />
        </button>
      </div>

      {/* Next Up */}
      <div>
        <div style={{ fontSize: 11, color: T.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>Next Up</div>
        {[
          { property: "Zen Pool Villa", date: "Thu, Mar 26", status: "Acknowledged", priority: "HIGH", countdown: "15h 36m" },
          { property: "Emuna Villa", date: "Sat, Mar 28", status: "Pending", priority: "HIGH", countdown: "63h 36m" },
        ].map((task, i) => (
          <div key={i} style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 14, marginBottom: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <Badge label="CHECKIN" color={T.mossBright} />
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <Badge label={task.priority} color={task.priority === "HIGH" ? T.red : T.amber} />
              </div>
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: T.text, marginBottom: 2 }}>Check-in Prep</div>
            <div style={{ fontSize: 12, color: T.textDim, marginBottom: 2 }}>{task.status}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: T.textDim, marginBottom: 8 }}>
              <Home size={12} /> {task.property}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: T.textDim, marginBottom: 10 }}>
              <Calendar size={12} /> {task.date}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button style={{ background: T.copper, color: T.white, border: "none", borderRadius: 8, padding: "6px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
                <Navigation size={12} /> Navigate
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── SCREEN: S01 — ARRIVALS LIST ─────────────────────────────
function ArrivalsScreen({ onNavigate, onSelectTask }) {
  const tasks = [
    { id: 1, property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-26", countdown: "15h 36m 38s", status: "Upcoming", acknowledged: true },
    { id: 2, property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", ref: "CHECKIN_PREP — KPG-500", countdown: "63h 36m 38s", status: "Upcoming", acknowledged: false, priority: true },
    { id: 3, property: "Emuna Villa", code: "KPG-568", date: "2026-04-11", countdown: "399h 36m", status: "Upcoming", acknowledged: false },
  ];

  return (
    <div style={{ padding: "0 0 72px", minHeight: "100vh", background: T.bg }}>
      {/* Breadcrumb */}
      <div style={{ padding: "12px 16px 0", fontSize: 11, color: T.textMuted }}>
        Home &nbsp;›&nbsp; Operations &nbsp;›&nbsp; <span style={{ color: T.textDim }}>Check-In</span>
      </div>

      {/* Title */}
      <div style={{ padding: "8px 16px 16px" }}>
        <div style={{ fontSize: 14, color: T.textDim, marginBottom: 2 }}>Check-in</div>
        <div style={{ fontSize: 11, color: T.textMuted, textTransform: "uppercase", marginBottom: 2 }}>Wednesday, March 25</div>
        <div style={{ fontSize: 28, fontWeight: 800, color: T.text, marginBottom: 4 }}>Arrivals</div>
        <div style={{ fontSize: 12, color: T.textDim }}>Today + next 7 days</div>
      </div>

      {/* Summary Strip */}
      <div style={{ display: "flex", gap: 8, padding: "0 16px 16px" }}>
        {[
          { label: "TODAY", value: "0" },
          { label: "UPCOMING", value: "10" },
          { label: "NEXT", value: "in 15h 36m", sub: "by 14:00" },
        ].map((s, i) => (
          <div key={i} style={{ flex: 1, background: T.card, borderRadius: 10, padding: "10px 10px", border: `1px solid ${T.cardBorder}` }}>
            <div style={{ fontSize: 9, color: T.textMuted, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>{s.label}</div>
            <div style={{ fontSize: i === 2 ? 13 : 24, fontWeight: 700, color: i === 2 ? T.mossBright : T.text }}>{s.value}</div>
            {s.sub && <div style={{ fontSize: 10, color: T.textDim }}>{s.sub}</div>}
          </div>
        ))}
      </div>

      {/* Section label */}
      <div style={{ padding: "0 16px 8px", fontSize: 11, color: T.textMuted, textTransform: "uppercase", letterSpacing: 1 }}>Upcoming</div>

      {/* Task Cards */}
      <div style={{ padding: "0 16px" }}>
        {tasks.map((task) => (
          <div key={task.id} onClick={() => onSelectTask(task)} style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 14, marginBottom: 10, cursor: "pointer" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: T.text }}>{task.property}</div>
              <div style={{ fontSize: 12, color: T.textDim, display: "flex", alignItems: "center", gap: 4 }}>
                <Clock size={11} /> {task.countdown}
              </div>
            </div>
            <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 6 }}>{task.code}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <Badge label="Check-in" color={T.mossBright} />
              <span style={{ fontSize: 11, color: T.textDim }}>📅 {task.date}</span>
              {task.ref && <span style={{ fontSize: 10, color: T.textMuted }}>{task.ref}</span>}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10 }}>
              <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 6, width: "100%" }}>
                <span style={{ fontSize: 11, color: T.textDim, textTransform: "uppercase" }}>{task.status}</span>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              {!task.acknowledged && (
                <button style={{ flex: 1, background: "transparent", border: `1px solid ${T.cardBorder}`, borderRadius: 8, padding: "8px 0", color: T.textDim, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Acknowledge</button>
              )}
              <button style={{ flex: 2, background: T.moss, border: "none", borderRadius: 8, padding: "8px 0", color: T.mossBright, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>Start Check-in →</button>
              {task.priority && <Star size={16} color={T.amber} style={{ alignSelf: "center" }} />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── SCREEN: S02 — WIZARD STEP 1: ARRIVAL CONFIRMATION ──────
function WizardStep1({ onBack, onNext, task }) {
  return (
    <div style={{ padding: "0 0 72px", minHeight: "100vh", background: T.bg }}>
      {/* Step Header */}
      <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim }}><ArrowLeft size={20} /></button>
        <span style={{ fontSize: 13, color: T.textDim }}>Step 1 of 7</span>
      </div>
      <div style={{ height: 3, background: T.card, margin: "0 16px 16px" }}>
        <div style={{ height: 3, width: "14%", background: T.mossBright, borderRadius: 2 }} />
      </div>

      <div style={{ padding: "0 16px" }}>
        {/* Property Status */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <span style={{ fontSize: 14, color: T.textDim }}>Property:</span>
          <span style={{ fontSize: 16, fontWeight: 700, color: T.text }}>Villa Emuna</span>
          <Badge label="● Ready" color={T.green} />
        </div>

        {/* Booking Block */}
        <div style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
          {[
            ["Guest", "Bon Voyage"],
            ["Guests", "2"],
            ["Property", "Villa Emuna"],
            ["Check-in", "Wed Dec 20, 14:00"],
            ["Check-out", "Sat Dec 23, 11:00"],
            ["Nights", "3"],
            ["Source", "Airbnb"],
            ["Ref", "ABCD-1234"],
          ].map(([k, v]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: `1px solid ${T.cardBorder}` }}>
              <span style={{ fontSize: 12, color: T.textMuted }}>{k}</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{v}</span>
            </div>
          ))}
        </div>

        {/* Operator Note */}
        <div style={{ background: T.amber + "15", border: `1px solid ${T.amber}40`, borderRadius: 10, padding: 12, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
            <AlertTriangle size={14} color={T.amber} />
            <span style={{ fontSize: 12, fontWeight: 600, color: T.amber }}>Operator Note</span>
          </div>
          <div style={{ fontSize: 12, color: T.textDim }}>Late arrival expected — guest confirmed 16:00 instead of 14:00</div>
        </div>

        {/* Settlement Policy */}
        <div style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 10, padding: 12, marginBottom: 20 }}>
          <div style={{ fontSize: 12, color: T.textDim, marginBottom: 6 }}>Settlement Policy</div>
          <div style={{ display: "flex", gap: 16 }}>
            <span style={{ fontSize: 13, color: T.text }}>💰 Deposit: THB 1,000</span>
            <span style={{ fontSize: 13, color: T.text }}>⚡ Electricity: 5.5/kWh</span>
          </div>
        </div>

        {/* CTAs */}
        <button style={{ width: "100%", background: "transparent", border: `1px solid ${T.cardBorder}`, borderRadius: 10, padding: 12, color: T.textDim, fontSize: 13, marginBottom: 10, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
          <MapPin size={14} /> Navigate to Property
        </button>
        <button onClick={onNext} style={{ width: "100%", background: T.moss, border: "none", borderRadius: 10, padding: 14, color: T.mossBright, fontSize: 15, fontWeight: 700, cursor: "pointer" }}>
          Guest Arrived ✓
        </button>
      </div>
    </div>
  );
}

// ─── SCREEN: S03 — WIZARD STEP 2: WALK-THROUGH PHOTOS ───────
function WizardStep2({ onBack, onNext }) {
  const [photos, setPhotos] = useState([true, true, false, false]);
  const captured = photos.filter(Boolean).length;
  return (
    <div style={{ padding: "0 0 72px", minHeight: "100vh", background: T.bg }}>
      <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim }}><ArrowLeft size={20} /></button>
        <span style={{ fontSize: 13, color: T.textDim }}>Step 2 of 7</span>
      </div>
      <div style={{ height: 3, background: T.card, margin: "0 16px 16px" }}>
        <div style={{ height: 3, width: "28%", background: T.mossBright, borderRadius: 2 }} />
      </div>
      <div style={{ padding: "0 16px" }}>
        <div style={{ fontSize: 12, color: T.textDim, marginBottom: 8 }}>Counter: {captured} of {photos.length} captured</div>
        {["Living Room", "Bedroom", "Bathroom", "Kitchen"].map((room, i) => (
          <div key={room} style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 14, marginBottom: 10, display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 60, height: 60, borderRadius: 8, background: T.surface, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: 10, color: T.textMuted }}>Ref<br />photo</span>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: T.text, marginBottom: 4 }}>{room}</div>
              {photos[i] ? (
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Badge label="✅ Captured" color={T.green} />
                  <span style={{ fontSize: 11, color: T.textMuted, cursor: "pointer" }}>Retake</span>
                </div>
              ) : (
                <button onClick={() => { const p = [...photos]; p[i] = true; setPhotos(p); }} style={{ background: T.moss, border: "none", borderRadius: 6, padding: "6px 12px", color: T.mossBright, fontSize: 11, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
                  <Camera size={12} /> Capture
                </button>
              )}
            </div>
          </div>
        ))}
        <button onClick={onNext} style={{ width: "100%", background: captured === photos.length ? T.moss : T.card, border: captured === photos.length ? "none" : `1px solid ${T.amber}40`, borderRadius: 10, padding: 14, color: captured === photos.length ? T.mossBright : T.amber, fontSize: 14, fontWeight: 700, cursor: "pointer", marginTop: 8 }}>
          {captured === photos.length ? "Continue →" : `Continue (${captured}/${photos.length}) →`}
        </button>
        {captured < photos.length && <div style={{ textAlign: "center", fontSize: 11, color: T.amber, marginTop: 6 }}>⚠ Not all rooms captured</div>}
      </div>
    </div>
  );
}

// ─── SCREEN: S04 — WIZARD STEP 3: ELECTRICITY METER ─────────
function WizardStep3({ onBack, onNext }) {
  return (
    <div style={{ padding: "0 0 72px", minHeight: "100vh", background: T.bg }}>
      <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim }}><ArrowLeft size={20} /></button>
        <span style={{ fontSize: 13, color: T.textDim }}>Step 3 of 7</span>
      </div>
      <div style={{ height: 3, background: T.card, margin: "0 16px 16px" }}>
        <div style={{ height: 3, width: "42%", background: T.mossBright, borderRadius: 2 }} />
      </div>
      <div style={{ padding: "0 16px" }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: T.text, marginBottom: 4 }}>Capture the opening meter reading</div>
        <div style={{ fontSize: 13, color: T.textDim, marginBottom: 20 }}>⚡ Rate: 5.5 THB/kWh</div>

        {/* OCR Capture Area */}
        <div style={{ background: T.card, border: `2px dashed ${T.cardBorder}`, borderRadius: 16, padding: 40, textAlign: "center", marginBottom: 20 }}>
          <Camera size={40} color={T.textMuted} style={{ marginBottom: 12 }} />
          <div style={{ fontSize: 14, color: T.textDim, marginBottom: 4 }}>Tap to capture meter photo</div>
          <div style={{ fontSize: 11, color: T.textMuted }}>Camera will auto-detect reading via OCR</div>
        </div>

        {/* Confidence Indicator (shown after capture) */}
        <div style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 10, padding: 14, marginBottom: 20, display: "none" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontSize: 12, color: T.textDim }}>Detected Reading</span>
            <span style={{ fontSize: 16, fontWeight: 700, color: T.text }}>312 kWh</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 11, color: T.textDim }}>Confidence:</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: T.green }}>●●● HIGH (96%)</span>
          </div>
        </div>

        {/* Simulated captured state */}
        <div style={{ background: T.card, border: `1px solid ${T.mossBright}40`, borderRadius: 10, padding: 14, marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontSize: 12, color: T.textDim }}>Detected Reading</span>
            <span style={{ fontSize: 20, fontWeight: 700, color: T.text }}>312 kWh</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 11, color: T.textDim }}>Confidence:</span>
            <div style={{ display: "flex", gap: 2 }}>
              {[1,2,3].map(i => <div key={i} style={{ width: 8, height: 8, borderRadius: "50%", background: T.green }} />)}
            </div>
            <span style={{ fontSize: 11, fontWeight: 600, color: T.green }}>HIGH</span>
          </div>
          <input style={{ marginTop: 10, width: "100%", background: T.surface, border: `1px solid ${T.cardBorder}`, borderRadius: 8, padding: "8px 12px", color: T.text, fontSize: 14 }} defaultValue="312" placeholder="Manual correction" />
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <button style={{ flex: 1, background: "transparent", border: `1px solid ${T.cardBorder}`, borderRadius: 10, padding: 12, color: T.textDim, fontSize: 13, cursor: "pointer" }}>Skip</button>
          <button onClick={onNext} style={{ flex: 2, background: T.moss, border: "none", borderRadius: 10, padding: 12, color: T.mossBright, fontSize: 14, fontWeight: 700, cursor: "pointer" }}>Complete ✓</button>
        </div>
      </div>
    </div>
  );
}

// ─── SCREEN: S05 — WIZARD STEP 4: GUEST CONTACT ─────────────
function WizardStep4({ onBack, onNext }) {
  return (
    <div style={{ padding: "0 0 72px", minHeight: "100vh", background: T.bg }}>
      <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim }}><ArrowLeft size={20} /></button>
        <span style={{ fontSize: 13, color: T.textDim }}>Step 4 of 7</span>
      </div>
      <div style={{ height: 3, background: T.card, margin: "0 16px 16px" }}>
        <div style={{ height: 3, width: "57%", background: T.mossBright, borderRadius: 2 }} />
      </div>
      <div style={{ padding: "0 16px" }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: T.text, marginBottom: 4 }}>Capture guest contact</div>
        <div style={{ fontSize: 13, color: T.textDim, marginBottom: 20 }}>For portal link delivery</div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 12, color: T.textDim, marginBottom: 6, display: "block" }}>Phone Number *</label>
          <div style={{ display: "flex", gap: 8 }}>
            <input style={{ width: 60, background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 8, padding: "10px 8px", color: T.text, fontSize: 14, textAlign: "center" }} defaultValue="+66" />
            <input style={{ flex: 1, background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 8, padding: "10px 12px", color: T.text, fontSize: 14 }} defaultValue="812 345 678" placeholder="Phone number" />
          </div>
          <div style={{ fontSize: 11, color: T.amber, marginTop: 4 }}>⚠ Phone is recommended for portal access</div>
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{ fontSize: 12, color: T.textDim, marginBottom: 6, display: "block" }}>Email (optional)</label>
          <input style={{ width: "100%", background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 8, padding: "10px 12px", color: T.text, fontSize: 14 }} placeholder="guest@example.com" />
        </div>

        <button onClick={onNext} style={{ width: "100%", background: T.moss, border: "none", borderRadius: 10, padding: 14, color: T.mossBright, fontSize: 15, fontWeight: 700, cursor: "pointer" }}>Continue →</button>
      </div>
    </div>
  );
}

// ─── SCREEN: S06 — WIZARD STEP 5: DEPOSIT ───────────────────
function WizardStep5({ onBack, onNext }) {
  const [method, setMethod] = useState("cash");
  return (
    <div style={{ padding: "0 0 72px", minHeight: "100vh", background: T.bg }}>
      <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim }}><ArrowLeft size={20} /></button>
        <span style={{ fontSize: 13, color: T.textDim }}>Step 5 of 7</span>
      </div>
      <div style={{ height: 3, background: T.card, margin: "0 16px 16px" }}>
        <div style={{ height: 3, width: "71%", background: T.mossBright, borderRadius: 2 }} />
      </div>
      <div style={{ padding: "0 16px" }}>
        <div style={{ background: T.amber + "18", border: `1px solid ${T.amber}50`, borderRadius: 16, padding: 20, textAlign: "center", marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: T.amber, textTransform: "uppercase", marginBottom: 4 }}>Deposit Required</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: T.text }}>THB 1,000</div>
        </div>

        <div style={{ fontSize: 13, color: T.textDim, marginBottom: 12 }}>Payment Method</div>
        {[
          { id: "cash", icon: "💵", label: "Cash received" },
          { id: "transfer", icon: "🏦", label: "Transfer received" },
          { id: "card", icon: "💳", label: "Card hold" },
        ].map((m) => (
          <button key={m.id} onClick={() => setMethod(m.id)} style={{ width: "100%", background: method === m.id ? T.moss + "30" : T.card, border: `1px solid ${method === m.id ? T.mossBright : T.cardBorder}`, borderRadius: 10, padding: 14, marginBottom: 8, display: "flex", alignItems: "center", gap: 10, cursor: "pointer", textAlign: "left" }}>
            <div style={{ width: 20, height: 20, borderRadius: "50%", border: `2px solid ${method === m.id ? T.mossBright : T.textMuted}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
              {method === m.id && <div style={{ width: 10, height: 10, borderRadius: "50%", background: T.mossBright }} />}
            </div>
            <span style={{ fontSize: 16, marginRight: 6 }}>{m.icon}</span>
            <span style={{ fontSize: 14, color: T.text }}>{m.label}</span>
          </button>
        ))}

        <div style={{ marginTop: 16, marginBottom: 20 }}>
          <label style={{ fontSize: 12, color: T.textDim, marginBottom: 6, display: "block" }}>Note (optional)</label>
          <textarea style={{ width: "100%", background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 8, padding: "10px 12px", color: T.text, fontSize: 13, minHeight: 60, resize: "vertical" }} placeholder="Any notes about the deposit..." />
        </div>

        <button onClick={onNext} style={{ width: "100%", background: T.moss, border: "none", borderRadius: 10, padding: 14, color: T.mossBright, fontSize: 15, fontWeight: 700, cursor: "pointer" }}>Confirm & Record →</button>
      </div>
    </div>
  );
}

// ─── SCREEN: S07 — WIZARD STEP 6: IDENTITY OCR ──────────────
function WizardStep6({ onBack, onNext }) {
  const [docType, setDocType] = useState(null);
  return (
    <div style={{ padding: "0 0 72px", minHeight: "100vh", background: T.bg }}>
      <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim }}><ArrowLeft size={20} /></button>
        <span style={{ fontSize: 13, color: T.textDim }}>Step 6 of 7</span>
      </div>
      <div style={{ height: 3, background: T.card, margin: "0 16px 16px" }}>
        <div style={{ height: 3, width: "85%", background: T.mossBright, borderRadius: 2 }} />
      </div>
      <div style={{ padding: "0 16px" }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: T.text, marginBottom: 4 }}>Guest Identity</div>
        <div style={{ fontSize: 13, color: T.textDim, marginBottom: 16 }}>Select document type and capture</div>

        {!docType ? (
          <>
            {[
              { id: "passport", icon: "📘", label: "Passport" },
              { id: "national_id", icon: "🪪", label: "National ID" },
              { id: "driving", icon: "🚗", label: "Driving License" },
            ].map((d) => (
              <button key={d.id} onClick={() => setDocType(d.id)} style={{ width: "100%", background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 16, marginBottom: 8, display: "flex", alignItems: "center", gap: 12, cursor: "pointer", textAlign: "left" }}>
                <span style={{ fontSize: 24 }}>{d.icon}</span>
                <span style={{ fontSize: 15, fontWeight: 600, color: T.text }}>{d.label}</span>
                <ChevronRight size={16} color={T.textMuted} style={{ marginLeft: "auto" }} />
              </button>
            ))}
          </>
        ) : (
          <>
            <div style={{ fontSize: 13, color: T.mossBright, marginBottom: 12, cursor: "pointer" }} onClick={() => setDocType(null)}>← Change document type</div>

            {/* OCR Result Form */}
            <div style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
              {[
                { label: "Full Name", value: "Bon Voyage", conf: 98 },
                { label: "Document Number", value: "AB1234567", conf: 72 },
                { label: "Date of Birth", value: "1990-05-15", conf: 95 },
                { label: "Nationality", value: "French", conf: 94 },
                { label: "Expiry", value: "2028-11-30", conf: 91 },
              ].map((field) => (
                <div key={field.label} style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 11, color: T.textMuted }}>{field.label}</span>
                    {field.conf < 85 && <Badge label={`⚠ Low (${field.conf}%)`} color={T.red} />}
                  </div>
                  <input style={{ width: "100%", background: T.surface, border: `1px solid ${field.conf < 85 ? T.red : T.cardBorder}`, borderRadius: 8, padding: "8px 12px", color: T.text, fontSize: 13 }} defaultValue={field.value} />
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              <button style={{ flex: 1, background: "transparent", border: `1px solid ${T.cardBorder}`, borderRadius: 10, padding: 12, color: T.textDim, fontSize: 13, cursor: "pointer" }}>Skip</button>
              <button onClick={onNext} style={{ flex: 2, background: T.moss, border: "none", borderRadius: 10, padding: 12, color: T.mossBright, fontSize: 14, fontWeight: 700, cursor: "pointer" }}>Complete ✓</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── SCREEN: S08 — WIZARD STEP 7: SUMMARY ───────────────────
function WizardStep7({ onBack, onComplete }) {
  return (
    <div style={{ padding: "0 0 72px", minHeight: "100vh", background: T.bg }}>
      <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim }}><ArrowLeft size={20} /></button>
        <span style={{ fontSize: 13, color: T.textDim }}>Step 7 of 7</span>
      </div>
      <div style={{ height: 3, background: T.card, margin: "0 16px 16px" }}>
        <div style={{ height: 3, width: "100%", background: T.mossBright, borderRadius: 2 }} />
      </div>
      <div style={{ padding: "0 16px" }}>
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🏠</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: T.text }}>Ready to complete</div>
          <div style={{ fontSize: 13, color: T.textDim, marginTop: 4 }}>This will mark the booking as InStay and the property as Occupied.</div>
        </div>

        <div style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 16, marginBottom: 24 }}>
          {[
            ["Guest", "Bon Voyage"],
            ["Property", "Villa Emuna"],
            ["Walk-through", "4/4 ✓"],
            ["Meter", "312 kWh"],
            ["Contact", "+66 812 345 678"],
            ["Deposit", "THB 1,000 · Cash"],
            ["Identity", "Passport · AB1234567"],
          ].map(([k, v]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: `1px solid ${T.cardBorder}` }}>
              <span style={{ fontSize: 13, color: T.textMuted }}>{k}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{v}</span>
            </div>
          ))}
        </div>

        <button onClick={onComplete} style={{ width: "100%", background: T.mossBright, border: "none", borderRadius: 12, padding: 16, color: T.white, fontSize: 16, fontWeight: 700, cursor: "pointer" }}>✅ Complete Check-in</button>
      </div>
    </div>
  );
}

// ─── SCREEN: S09 — SUCCESS / QR HANDOFF ──────────────────────
function SuccessScreen({ onDone }) {
  return (
    <div style={{ padding: "0 0 72px", minHeight: "100vh", background: T.bg, display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ padding: "40px 16px 0", textAlign: "center", width: "100%", maxWidth: 360 }}>
        <div style={{ width: 64, height: 64, borderRadius: "50%", background: T.mossBright + "30", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
          <span style={{ fontSize: 32 }}>✅</span>
        </div>
        <div style={{ fontSize: 22, fontWeight: 800, color: T.text, marginBottom: 4 }}>Check-in Complete</div>
        <div style={{ fontSize: 14, color: T.textDim, marginBottom: 24 }}>Guest is now checked in at Villa Emuna</div>

        {/* QR Code */}
        <div style={{ background: T.white, borderRadius: 16, padding: 24, marginBottom: 20 }}>
          <div style={{ width: 160, height: 160, background: "#f0f0f0", margin: "0 auto 12px", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ width: 120, height: 120, background: `repeating-conic-gradient(#333 0% 25%, #fff 0% 50%) 0 0 / 12px 12px`, borderRadius: 4 }} />
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#333" }}>Guest Portal QR</div>
          <div style={{ fontSize: 12, color: "#666" }}>Show this to the guest</div>
        </div>

        <div style={{ fontSize: 12, color: T.textDim, marginBottom: 16 }}>Guest scans → opens their stay portal</div>

        <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
          <button style={{ flex: 1, background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 10, padding: 12, color: T.text, fontSize: 13, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
            <Phone size={14} /> Send via SMS
          </button>
          <button style={{ flex: 1, background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 10, padding: 12, color: T.text, fontSize: 13, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
            <Mail size={14} /> Send via Email
          </button>
        </div>

        <button onClick={onDone} style={{ width: "100%", background: T.moss, border: "none", borderRadius: 10, padding: 14, color: T.mossBright, fontSize: 15, fontWeight: 700, cursor: "pointer" }}>Done — Return to Arrivals</button>
      </div>
    </div>
  );
}

// ─── SCREEN: TASKS ───────────────────────────────────────────
function TasksScreen() {
  const [tab, setTab] = useState("pending");
  const tasks = [
    { property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-26", countdown: "15h 36m 03s", status: "ACKNOWLEDGED" },
    { property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", ref: "CHECKIN_PREP — KPG-500", countdown: "63h 36m 03s", status: "PENDING" },
    { property: "Emuna Villa", code: "KPG-568", date: "2026-04-11", countdown: "399h 36m 03s", status: "PENDING" },
    { property: "Emuna Villa", code: "KPG-569", date: "2026-04-17", countdown: "543h 38m 03s", status: "PENDING" },
  ];
  return (
    <div style={{ padding: "16px 16px 72px", minHeight: "100vh", background: T.bg }}>
      <div style={{ fontSize: 13, color: T.textDim, marginBottom: 4 }}>My Tasks</div>
      <div style={{ fontSize: 24, fontWeight: 800, color: T.text, marginBottom: 2 }}>My Tasks</div>
      <div style={{ fontSize: 12, color: T.textDim, marginBottom: 16 }}>Today · Wednesday, Mar 25</div>

      {/* Tabs */}
      <div style={{ display: "flex", marginBottom: 16, background: T.card, borderRadius: 10, padding: 3 }}>
        {["pending", "done"].map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{ flex: 1, padding: "8px 0", borderRadius: 8, border: "none", fontSize: 13, fontWeight: 600, cursor: "pointer", background: tab === t ? T.moss : "transparent", color: tab === t ? T.mossBright : T.textMuted, textTransform: "capitalize" }}>{t}</button>
        ))}
      </div>

      {tab === "pending" ? (
        tasks.map((task, i) => (
          <div key={i} style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 14, marginBottom: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: T.text }}>{task.property}</div>
              <div style={{ fontSize: 11, color: T.textDim, display: "flex", alignItems: "center", gap: 4 }}><Clock size={10} /> {task.countdown}</div>
            </div>
            <div style={{ fontSize: 10, color: T.textMuted, marginBottom: 6 }}>{task.code}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <Badge label="Check-in" color={T.mossBright} />
              <span style={{ fontSize: 11, color: T.textDim }}>📅 {task.date}</span>
              {task.ref && <span style={{ fontSize: 9, color: T.textMuted }}>{task.ref}</span>}
            </div>
            <div style={{ textAlign: "right", fontSize: 10, color: T.textDim, textTransform: "uppercase", marginBottom: 8 }}>{task.status}</div>
            <div style={{ display: "flex", gap: 8 }}>
              {task.status === "PENDING" && (
                <button style={{ flex: 1, background: "transparent", border: `1px solid ${T.cardBorder}`, borderRadius: 8, padding: "8px 0", color: T.textDim, fontSize: 12, cursor: "pointer" }}>Acknowledge</button>
              )}
              <button style={{ flex: 2, background: T.moss, border: "none", borderRadius: 8, padding: "8px 0", color: T.mossBright, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>Start Check-in →</button>
              <Star size={14} color={T.amber} style={{ alignSelf: "center" }} />
            </div>
          </div>
        ))
      ) : (
        <div style={{ textAlign: "center", padding: 40 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>🎉</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: T.text, marginBottom: 4 }}>All clear!</div>
          <div style={{ fontSize: 13, color: T.textDim }}>No pending tasks assigned to you right now.</div>
        </div>
      )}
    </div>
  );
}

// ─── SCREEN: SETTINGS ────────────────────────────────────────
function SettingsScreen() {
  return (
    <div style={{ padding: "16px 16px 72px", minHeight: "100vh", background: T.bg }}>
      <div style={{ fontSize: 24, fontWeight: 800, color: T.text, marginBottom: 24 }}>Profile & Settings</div>

      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <div style={{ width: 64, height: 64, borderRadius: "50%", background: T.moss, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 8px" }}>
          <User size={28} color={T.mossBright} />
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, color: T.text }}>Somchai</div>
        <div style={{ fontSize: 13, color: T.textDim }}>Check-in Staff · Active</div>
      </div>

      <div style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: T.textMuted, textTransform: "uppercase", marginBottom: 12 }}>Assigned Properties</div>
        {["Villa Emuna", "Zen Pool Villa", "KPG Residence"].map((p) => (
          <div key={p} style={{ padding: "8px 0", borderBottom: `1px solid ${T.cardBorder}`, fontSize: 14, color: T.text }}>{p}</div>
        ))}
      </div>

      <div style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: T.textMuted, textTransform: "uppercase", marginBottom: 12 }}>Notifications</div>
        <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: `1px solid ${T.cardBorder}` }}>
          <span style={{ fontSize: 13, color: T.textDim }}>LINE</span>
          <span style={{ fontSize: 13, color: T.green }}>Connected ✓</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0" }}>
          <span style={{ fontSize: 13, color: T.textDim }}>Phone</span>
          <span style={{ fontSize: 13, color: T.text }}>+66 812 345 678</span>
        </div>
      </div>

      <div style={{ background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: 16 }}>
        <div style={{ fontSize: 11, color: T.textMuted, textTransform: "uppercase", marginBottom: 12 }}>Session</div>
        <div style={{ fontSize: 13, color: T.textDim, marginBottom: 12 }}>Logged in as: somchai</div>
        <button style={{ width: "100%", background: T.red + "20", border: `1px solid ${T.red}40`, borderRadius: 8, padding: 10, color: T.red, fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Log Out</button>
      </div>
    </div>
  );
}

// ─── MAIN APP ────────────────────────────────────────────────
export default function CheckInStaffV1() {
  const [screen, setScreen] = useState("home");
  const [wizardStep, setWizardStep] = useState(0);

  const navigate = (s) => {
    setScreen(s);
    setWizardStep(0);
  };

  const renderScreen = () => {
    if (screen === "wizard") {
      switch (wizardStep) {
        case 0: return <WizardStep1 onBack={() => navigate("checkin")} onNext={() => setWizardStep(1)} />;
        case 1: return <WizardStep2 onBack={() => setWizardStep(0)} onNext={() => setWizardStep(2)} />;
        case 2: return <WizardStep3 onBack={() => setWizardStep(1)} onNext={() => setWizardStep(3)} />;
        case 3: return <WizardStep4 onBack={() => setWizardStep(2)} onNext={() => setWizardStep(4)} />;
        case 4: return <WizardStep5 onBack={() => setWizardStep(3)} onNext={() => setWizardStep(5)} />;
        case 5: return <WizardStep6 onBack={() => setWizardStep(4)} onNext={() => setWizardStep(6)} />;
        case 6: return <WizardStep7 onBack={() => setWizardStep(5)} onComplete={() => setScreen("success")} />;
        default: return null;
      }
    }
    switch (screen) {
      case "home": return <HomeScreen onNavigate={navigate} />;
      case "checkin": return <ArrivalsScreen onNavigate={navigate} onSelectTask={() => { setScreen("wizard"); setWizardStep(0); }} />;
      case "tasks": return <TasksScreen />;
      case "settings": return <SettingsScreen />;
      case "success": return <SuccessScreen onDone={() => navigate("checkin")} />;
      default: return <HomeScreen onNavigate={navigate} />;
    }
  };

  const activeTab = screen === "wizard" || screen === "success" ? "checkin" : screen;

  return (
    <div style={{ maxWidth: 390, margin: "0 auto", background: T.bg, minHeight: "100vh", position: "relative", fontFamily: "'Inter', -apple-system, sans-serif", WebkitFontSmoothing: "antialiased" }}>
      {renderScreen()}
      <BottomNav active={activeTab} onNavigate={navigate} />
    </div>
  );
}
