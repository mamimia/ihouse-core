import { useState } from "react";
import { Home, ClipboardList, CheckSquare, Settings, ChevronRight, ArrowLeft, MapPin, Clock, Calendar, AlertTriangle, Camera, Phone, Mail, Star, Navigation, User, Bell, Wifi, Eye, DollarSign, FileText, ChevronDown, Zap, Image, Flag } from "lucide-react";

// ─── DESIGN TOKENS ───────────────────────────────────────────
const T = {
  bg: "#0F1214",
  surface: "#1A1E22",
  card: "#1E2328",
  cardBorder: "#2A2F35",
  text: "#E8E4DE",
  textDim: "#8A8680",
  textMuted: "#5C5955",
  // Check-out uses signal-copper as primary accent (vs deep-moss for check-in)
  copper: "#B56E45",
  copperLight: "#C4865E",
  copperDark: "#8F5736",
  moss: "#334036",
  mossLight: "#3D5043",
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
    { id: "checkout", label: "Check-out", icon: ClipboardList },
    { id: "tasks", label: "Tasks", icon: CheckSquare },
    { id: "settings", label: "Settings", icon: Settings },
  ];
  return (
    <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, height: 56, background: T.bottomNav, display: "flex", borderTop: `1px solid ${T.cardBorder}`, zIndex: 50 }}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = active === tab.id;
        return (
          <button key={tab.id} onClick={() => onNavigate(tab.id)} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2, background: "none", border: "none", cursor: "pointer", color: isActive ? T.copper : T.textMuted }}>
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
    <span style={{ display: "inline-block", fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.05em", padding: "2px 8px", borderRadius: 4, background: `${color}22`, color }}>
      {label}
    </span>
  );
}

// ─── SCREEN HEADER ───────────────────────────────────────────
function ScreenHeader({ title, subtitle, onBack, breadcrumb }) {
  return (
    <div style={{ padding: "16px 16px 8px" }}>
      {breadcrumb && (
        <div style={{ fontSize: 10, color: T.textMuted, marginBottom: 8, fontFamily: "Inter, sans-serif" }}>
          {breadcrumb}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {onBack && (
          <button onClick={onBack} style={{ background: "none", border: "none", color: T.text, cursor: "pointer", padding: 4 }}>
            <ArrowLeft size={20} />
          </button>
        )}
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text, margin: 0 }}>{title}</h1>
          {subtitle && <p style={{ fontSize: 11, color: T.textDim, margin: "2px 0 0", fontFamily: "Inter, sans-serif" }}>{subtitle}</p>}
        </div>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S00 — HOME SCREEN [BUILT]
// Confirmed from screenshot 22.26.47: Welcome, MY STATUS, WORK, NEXT UP
// ═════════════════════════════════════════════════════════════
function HomeScreen({ onNavigate }) {
  return (
    <div style={{ paddingBottom: 72 }}>
      {/* Top bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px" }}>
        <span style={{ fontSize: 16, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text }}>Home</span>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 11, color: T.textDim }}>EN</span>
          <span style={{ fontSize: 11, color: T.textDim, cursor: "pointer" }}>→ Sign Out</span>
        </div>
      </div>

      {/* Welcome block [BUILT] */}
      <div style={{ margin: "0 16px 16px", padding: 16, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 4 }}>WELCOME</div>
        <div style={{ fontSize: 20, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text }}>
          Hello, admin
        </div>
        <Badge label="Check-out Staff" color={T.copper} />
      </div>

      {/* MY STATUS strip [BUILT] — 3 counters: Open, Overdue, Today */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>MY STATUS</div>
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { label: "Open", value: 8, icon: "📋", color: T.copper },
            { label: "Overdue", value: 0, icon: "●", color: T.green },
            { label: "Today", value: 0, icon: "📅", color: T.blue },
          ].map((s) => (
            <div key={s.label} style={{ flex: 1, background: T.card, borderRadius: 10, padding: "10px 12px", border: `1px solid ${T.cardBorder}` }}>
              <div style={{ fontSize: 9, color: T.textMuted, marginBottom: 4, display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ color: s.color }}>{s.icon}</span> {s.label}
              </div>
              <div style={{ fontSize: 26, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text }}>{s.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* WORK section [BUILT] — "Go to Check-outs" CTA */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>WORK</div>
        <button onClick={() => onNavigate("checkout")} style={{ width: "100%", background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: "14px 16px", display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: T.copperDark, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <ClipboardList size={18} color={T.copper} />
          </div>
          <div style={{ flex: 1, textAlign: "left" }}>
            <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Go to Check-outs</div>
            <div style={{ fontSize: 11, color: T.textDim }}>8 tasks waiting</div>
          </div>
          <ChevronRight size={18} color={T.textMuted} />
        </button>
      </div>

      {/* NEXT UP [BUILT] — upcoming task preview cards */}
      <div style={{ padding: "0 16px" }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>NEXT UP</div>
        {[
          { property: "Zen Pool Villa", date: "Sat, Mar 28", priority: "MEDIUM" },
          { property: "Emuna Villa", date: "Sat, Mar 28", priority: "MEDIUM" },
        ].map((task, i) => (
          <div key={i} style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}`, padding: 14, marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
              <div>
                <div style={{ fontSize: 9, color: T.textMuted, display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
                  <span>📋</span> CHECKOUT
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Checkout Verification</div>
              </div>
              <Badge label={task.priority} color={T.amber} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textDim, marginBottom: 2 }}>
              <span>🏠</span> {task.property}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textDim }}>
                <span>●</span> {task.date}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <Badge label="Pending" color={T.textDim} />
                <button style={{ background: T.copperDark, border: "none", borderRadius: 6, padding: "5px 10px", fontSize: 10, fontWeight: 600, color: T.text, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
                  <Navigation size={12} /> Navigate
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S01 — DEPARTURES LIST [BUILT]
// Confirmed from screenshot 22.27.48: title, date, summary strip, task cards
// ═════════════════════════════════════════════════════════════
function DeparturesScreen({ onStartWizard }) {
  const tasks = [
    { property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-28", countdown: "60h 32m 11s", status: "PENDING" },
    { property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", countdown: "60h 32m 11s", status: "PENDING" },
    { property: "Emuna Villa", code: "KPG-594", date: "2026-04-11", countdown: "396h 32m 11s", status: "PENDING" },
  ];

  return (
    <div style={{ paddingBottom: 72 }}>
      {/* Breadcrumb [BUILT] */}
      <div style={{ padding: "12px 16px 0", fontSize: 10, color: T.textMuted, fontFamily: "Inter, sans-serif" }}>
        Home &nbsp;›&nbsp; Operations &nbsp;›&nbsp; Check-Out
      </div>

      <ScreenHeader title="Check-out" subtitle="Departures · task world" />

      {/* Date line [BUILT] */}
      <div style={{ padding: "0 16px 4px", fontSize: 10, fontWeight: 600, fontFamily: "Manrope, sans-serif", color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.05em" }}>
        WEDNESDAY, MARCH 25
      </div>

      {/* Summary strip [BUILT] — OVERDUE / TODAY / NEXT */}
      <div style={{ display: "flex", gap: 8, padding: "8px 16px 16px" }}>
        {[
          { label: "OVERDUE", value: "0", color: T.red },
          { label: "TODAY", value: "0", color: T.copper },
          { label: "NEXT", value: "in 2d", sub: "Checkout 11:00", color: T.blue },
        ].map((s) => (
          <div key={s.label} style={{ flex: 1, background: T.card, borderRadius: 10, padding: "8px 10px", border: `1px solid ${T.cardBorder}` }}>
            <div style={{ fontSize: 8, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 2 }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: s.color }}>{s.value}</div>
            {s.sub && <div style={{ fontSize: 9, color: T.textMuted }}>{s.sub}</div>}
          </div>
        ))}
      </div>

      {/* Section label */}
      <div style={{ padding: "0 16px 8px", fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted }}>UPCOMING</div>

      {/* Task cards [BUILT] — dark cards, countdown, Acknowledge + Start, priority star */}
      {tasks.map((task, i) => (
        <div key={i} style={{ margin: "0 16px 10px", background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}`, padding: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>{task.property}</div>
              <div style={{ fontSize: 10, color: T.textMuted }}>{task.code}</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Clock size={12} color={T.textDim} />
              <span style={{ fontSize: 11, color: T.textDim }}>{task.countdown}</span>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
            <Badge label="Check-out" color={T.copper} />
            <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: T.textDim }}>
              <Calendar size={10} /> {task.date}
            </div>
            <span style={{ marginLeft: "auto", fontSize: 10, color: T.textDim }}>{task.status}</span>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button style={{ flex: 1, padding: "10px 0", borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
              Acknowledge
            </button>
            <button onClick={() => onStartWizard(task)} style={{ flex: 2, padding: "10px 0", borderRadius: 8, border: "none", background: T.copper, color: T.white, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
              Start Check-out →
            </button>
            <button style={{ width: 36, height: 36, borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
              <Star size={14} color={T.amber} />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S02 — WIZARD STEP 1: PROPERTY INSPECTION [V1 PROPOSAL]
// Three-tab photo comparison: Reference / Check-in / Check-out
// ═════════════════════════════════════════════════════════════
function WizardStep1_Inspection({ task, onNext, onBack }) {
  const [activeTab, setActiveTab] = useState("reference");
  const [activeRoom, setActiveRoom] = useState("living");
  const [captured, setCaptured] = useState({});
  const rooms = ["living", "bedroom", "kitchen", "bathroom", "balcony"];

  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="Property Inspection" subtitle={`${task.property} · Step 1 of 5`} onBack={onBack} />

      {/* Room selector */}
      <div style={{ display: "flex", gap: 6, padding: "8px 16px", overflowX: "auto" }}>
        {rooms.map((room) => (
          <button key={room} onClick={() => setActiveRoom(room)} style={{ padding: "6px 14px", borderRadius: 20, border: `1px solid ${activeRoom === room ? T.copper : T.cardBorder}`, background: activeRoom === room ? `${T.copper}22` : "transparent", color: activeRoom === room ? T.copper : T.textDim, fontSize: 11, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap", textTransform: "capitalize" }}>
            {room}
          </button>
        ))}
      </div>

      {/* Photo comparison tabs [V1 PROPOSAL] */}
      <div style={{ display: "flex", margin: "12px 16px 0", borderRadius: 8, overflow: "hidden", border: `1px solid ${T.cardBorder}` }}>
        {["reference", "check-in", "check-out"].map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)} style={{ flex: 1, padding: "8px 0", border: "none", background: activeTab === tab ? T.copper : T.card, color: activeTab === tab ? T.white : T.textDim, fontSize: 10, fontWeight: 700, cursor: "pointer", textTransform: "capitalize" }}>
            {tab}
          </button>
        ))}
      </div>

      {/* Photo area */}
      <div style={{ margin: "12px 16px", height: 220, borderRadius: 12, border: `2px dashed ${T.cardBorder}`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8, background: T.surface }}>
        {activeTab === "check-out" ? (
          captured[activeRoom] ? (
            <>
              <div style={{ width: "90%", height: 160, background: T.card, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Image size={32} color={T.green} />
              </div>
              <button onClick={() => setCaptured(prev => ({ ...prev, [activeRoom]: false }))} style={{ fontSize: 11, color: T.copper, background: "none", border: "none", cursor: "pointer", fontWeight: 600 }}>
                Retake
              </button>
            </>
          ) : (
            <>
              <Camera size={32} color={T.textMuted} />
              <span style={{ fontSize: 12, color: T.textDim }}>Capture {activeRoom} photo</span>
              <button onClick={() => setCaptured(prev => ({ ...prev, [activeRoom]: true }))} style={{ padding: "8px 24px", borderRadius: 8, background: T.copper, color: T.white, border: "none", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                Take Photo
              </button>
            </>
          )
        ) : (
          <>
            <Image size={32} color={T.textMuted} />
            <span style={{ fontSize: 12, color: T.textDim }}>{activeTab === "reference" ? "Reference photo" : "Check-in photo"} for {activeRoom}</span>
            <span style={{ fontSize: 10, color: T.textMuted }}>From property records</span>
          </>
        )}
      </div>

      {/* Progress counter */}
      <div style={{ padding: "0 16px", marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: T.textDim, marginBottom: 4 }}>
          <span>Rooms photographed</span>
          <span>{Object.keys(captured).filter(k => captured[k]).length} / {rooms.length}</span>
        </div>
        <div style={{ height: 4, background: T.cardBorder, borderRadius: 2, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${(Object.keys(captured).filter(k => captured[k]).length / rooms.length) * 100}%`, background: T.copper, borderRadius: 2, transition: "width 0.3s" }} />
        </div>
      </div>

      {/* Inspection notes */}
      <div style={{ margin: "0 16px 12px" }}>
        <label style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, display: "block", marginBottom: 4 }}>Inspection Notes</label>
        <textarea placeholder="Any issues, damage, or notes about property condition..." style={{ width: "100%", minHeight: 70, padding: 10, background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 8, color: T.text, fontSize: 12, fontFamily: "Inter, sans-serif", resize: "vertical", boxSizing: "border-box" }} />
      </div>

      {/* Status toggle */}
      <div style={{ margin: "0 16px 16px", padding: 12, background: T.card, borderRadius: 10, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: T.text, marginBottom: 8 }}>Property Condition</div>
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { label: "Good", color: T.green },
            { label: "Issues Found", color: T.amber },
            { label: "Damaged", color: T.red },
          ].map((opt) => (
            <button key={opt.label} style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: `1px solid ${opt.color}44`, background: `${opt.color}11`, color: opt.color, fontSize: 10, fontWeight: 600, cursor: "pointer" }}>
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ padding: "0 16px" }}>
        <button onClick={onNext} style={{ width: "100%", padding: 14, borderRadius: 10, background: T.copper, color: T.white, border: "none", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
          Continue to Meter Reading →
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S03 — WIZARD STEP 2: CLOSING METER [V1 PROPOSAL]
// Closing electricity read + delta preview (usage + estimated charge)
// ═════════════════════════════════════════════════════════════
function WizardStep2_Meter({ task, onNext, onBack }) {
  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="Closing Meter" subtitle={`${task.property} · Step 2 of 5`} onBack={onBack} />

      {/* Opening reading reference */}
      <div style={{ margin: "8px 16px 12px", padding: 12, background: T.surface, borderRadius: 10, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 6 }}>OPENING READING (FROM CHECK-IN)</div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontSize: 28, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text }}>45,231</span>
          <span style={{ fontSize: 11, color: T.textDim }}>kWh · Mar 22, 11:00</span>
        </div>
      </div>

      {/* OCR Capture area */}
      <div style={{ margin: "0 16px 12px" }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 6 }}>CLOSING READING</div>
        <div style={{ height: 160, border: `2px dashed ${T.copper}44`, borderRadius: 12, background: T.card, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8 }}>
          <Camera size={28} color={T.copper} />
          <span style={{ fontSize: 12, color: T.textDim }}>Photograph the electricity meter</span>
          <button style={{ padding: "8px 20px", borderRadius: 8, background: T.copper, border: "none", color: T.white, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
            Capture Meter
          </button>
        </div>
      </div>

      {/* OCR Result + Manual correction */}
      <div style={{ margin: "0 16px 12px", padding: 12, background: T.card, borderRadius: 10, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: T.text }}>Detected Reading</span>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 6, height: 6, borderRadius: 3, background: T.green }} />
            <span style={{ fontSize: 9, color: T.green, fontWeight: 600 }}>HIGH CONFIDENCE</span>
          </div>
        </div>
        <input type="text" defaultValue="45,387" style={{ width: "100%", padding: "10px 12px", background: T.surface, border: `1px solid ${T.cardBorder}`, borderRadius: 8, color: T.text, fontSize: 22, fontWeight: 800, fontFamily: "Manrope, sans-serif", textAlign: "center", boxSizing: "border-box" }} />
        <div style={{ fontSize: 10, color: T.textMuted, textAlign: "center", marginTop: 4 }}>Tap to correct manually</div>
      </div>

      {/* Delta preview [V1 PROPOSAL] — shows usage + estimated charge */}
      <div style={{ margin: "0 16px 16px", padding: 14, background: `${T.copper}11`, borderRadius: 10, border: `1px solid ${T.copper}33` }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.copper, marginBottom: 8 }}>USAGE DELTA</div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 11, color: T.textDim }}>Units consumed</div>
            <div style={{ fontSize: 22, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text }}>156 kWh</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11, color: T.textDim }}>Estimated charge</div>
            <div style={{ fontSize: 22, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.copper }}>฿ 780</div>
          </div>
        </div>
        <div style={{ fontSize: 10, color: T.textMuted, marginTop: 6 }}>Rate: ฿5.00/kWh · 3 nights</div>
      </div>

      <div style={{ display: "flex", gap: 8, padding: "0 16px" }}>
        <button style={{ flex: 1, padding: 14, borderRadius: 10, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
          Skip
        </button>
        <button onClick={onNext} style={{ flex: 2, padding: 14, borderRadius: 10, background: T.copper, color: T.white, border: "none", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
          Continue →
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S04 — WIZARD STEP 3: REPORT ISSUES [V1 PROPOSAL]
// Conditional — only shown when condition != "Good"
// ═════════════════════════════════════════════════════════════
function WizardStep3_Issues({ task, onNext, onBack }) {
  const categories = ["Damage", "Cleanliness", "Missing Items", "Appliances", "Plumbing", "Electrical", "Other"];
  const severities = ["Minor", "Moderate", "Severe"];

  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="Report Issues" subtitle={`${task.property} · Step 3 of 5`} onBack={onBack} />

      <div style={{ margin: "8px 16px 12px", padding: 10, background: `${T.amber}15`, borderRadius: 8, border: `1px solid ${T.amber}33` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.amber }}>
          <AlertTriangle size={14} /> Issues were flagged during inspection
        </div>
      </div>

      {/* Issue form */}
      <div style={{ margin: "0 16px 12px" }}>
        <label style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, display: "block", marginBottom: 6 }}>CATEGORY</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
          {categories.map((cat) => (
            <button key={cat} style={{ padding: "6px 12px", borderRadius: 6, border: `1px solid ${T.cardBorder}`, background: T.card, color: T.textDim, fontSize: 10, fontWeight: 600, cursor: "pointer" }}>
              {cat}
            </button>
          ))}
        </div>

        <label style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, display: "block", marginBottom: 6 }}>SEVERITY</label>
        <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
          {severities.map((sev) => (
            <button key={sev} style={{ flex: 1, padding: "8px 0", borderRadius: 6, border: `1px solid ${T.cardBorder}`, background: T.card, color: T.textDim, fontSize: 11, fontWeight: 600, cursor: "pointer" }}>
              {sev}
            </button>
          ))}
        </div>

        <label style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, display: "block", marginBottom: 6 }}>DESCRIPTION</label>
        <textarea placeholder="Describe the issue..." style={{ width: "100%", minHeight: 60, padding: 10, background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 8, color: T.text, fontSize: 12, fontFamily: "Inter, sans-serif", resize: "vertical", boxSizing: "border-box" }} />

        <div style={{ marginTop: 12 }}>
          <label style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, display: "block", marginBottom: 6 }}>PHOTO EVIDENCE</label>
          <button style={{ width: "100%", padding: 14, borderRadius: 8, border: `2px dashed ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
            <Camera size={16} /> Add Photo
          </button>
        </div>
      </div>

      {/* Issue list (if multiple) */}
      <div style={{ margin: "0 16px 12px", padding: 10, background: T.card, borderRadius: 8, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 10, color: T.textMuted, marginBottom: 6 }}>Issues reported: 0</div>
        <button style={{ width: "100%", padding: 8, borderRadius: 6, border: `1px solid ${T.copper}44`, background: `${T.copper}11`, color: T.copper, fontSize: 11, fontWeight: 600, cursor: "pointer" }}>
          + Add Another Issue
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, padding: "0 16px" }}>
        <button style={{ flex: 1, padding: 14, borderRadius: 10, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
          No Issues
        </button>
        <button onClick={onNext} style={{ flex: 2, padding: 14, borderRadius: 10, background: T.copper, color: T.white, border: "none", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
          Continue →
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S05 — WIZARD STEP 4: DEPOSIT RESOLUTION [V1 PROPOSAL]
// Shows deposit held, deductions, resolution options
// ═════════════════════════════════════════════════════════════
function WizardStep4_Deposit({ task, onNext, onBack }) {
  const [resolution, setResolution] = useState("full");

  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="Deposit Resolution" subtitle={`${task.property} · Step 4 of 5`} onBack={onBack} />

      {/* Deposit summary */}
      <div style={{ margin: "8px 16px 12px", padding: 16, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>DEPOSIT HELD</div>
        <div style={{ fontSize: 32, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text, marginBottom: 4 }}>฿ 5,000</div>
        <div style={{ fontSize: 11, color: T.textDim }}>Collected at check-in · Cash</div>
      </div>

      {/* Deductions breakdown */}
      <div style={{ margin: "0 16px 12px", padding: 14, background: T.surface, borderRadius: 10, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 10 }}>DEDUCTIONS</div>

        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, color: T.textDim }}>
            <Zap size={12} color={T.copper} /> Electricity (156 kWh)
          </div>
          <span style={{ color: T.text, fontWeight: 600 }}>฿ 780</span>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, color: T.textDim }}>
            <AlertTriangle size={12} color={T.amber} /> Issues / Damage
          </div>
          <span style={{ color: T.text, fontWeight: 600 }}>฿ 0</span>
        </div>

        <div style={{ borderTop: `1px solid ${T.cardBorder}`, marginTop: 8, paddingTop: 8, display: "flex", justifyContent: "space-between", fontSize: 13 }}>
          <span style={{ color: T.text, fontWeight: 700 }}>Total Deductions</span>
          <span style={{ color: T.copper, fontWeight: 800 }}>฿ 780</span>
        </div>
      </div>

      {/* Resolution options */}
      <div style={{ margin: "0 16px 12px" }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>RESOLUTION</div>

        {[
          { id: "full", label: "Return Deposit (minus deductions)", amount: "฿ 4,220 returned", desc: "Standard checkout — deduct electricity only" },
          { id: "deduct", label: "Additional Damage Deduction", amount: "Custom amount", desc: "Deduct for damage or missing items" },
        ].map((opt) => (
          <button key={opt.id} onClick={() => setResolution(opt.id)} style={{ width: "100%", padding: 14, marginBottom: 8, borderRadius: 10, border: `1px solid ${resolution === opt.id ? T.copper : T.cardBorder}`, background: resolution === opt.id ? `${T.copper}11` : T.card, cursor: "pointer", textAlign: "left" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{opt.label}</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: T.copper }}>{opt.amount}</span>
            </div>
            <div style={{ fontSize: 10, color: T.textDim }}>{opt.desc}</div>
          </button>
        ))}

        {resolution === "deduct" && (
          <div style={{ padding: 12, background: T.card, borderRadius: 8, border: `1px solid ${T.cardBorder}`, marginBottom: 8 }}>
            <label style={{ fontSize: 10, color: T.textMuted, display: "block", marginBottom: 4 }}>Deduction amount</label>
            <input type="text" placeholder="฿ 0" style={{ width: "100%", padding: "8px 10px", background: T.surface, border: `1px solid ${T.cardBorder}`, borderRadius: 6, color: T.text, fontSize: 18, fontWeight: 700, fontFamily: "Manrope, sans-serif", boxSizing: "border-box" }} />
            <label style={{ fontSize: 10, color: T.textMuted, display: "block", marginTop: 8, marginBottom: 4 }}>Reason</label>
            <textarea placeholder="Describe reason for deduction..." style={{ width: "100%", minHeight: 50, padding: 8, background: T.surface, border: `1px solid ${T.cardBorder}`, borderRadius: 6, color: T.text, fontSize: 11, fontFamily: "Inter, sans-serif", resize: "vertical", boxSizing: "border-box" }} />
          </div>
        )}
      </div>

      {/* Refund summary */}
      <div style={{ margin: "0 16px 16px", padding: 12, background: `${T.green}11`, borderRadius: 10, border: `1px solid ${T.green}33` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>Guest Receives</span>
          <span style={{ fontSize: 24, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.green }}>฿ 4,220</span>
        </div>
      </div>

      <div style={{ padding: "0 16px" }}>
        <button onClick={onNext} style={{ width: "100%", padding: 14, borderRadius: 10, background: T.copper, color: T.white, border: "none", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
          Continue to Summary →
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S06 — WIZARD STEP 5: CHECKOUT SUMMARY [V1 PROPOSAL]
// Final review before completing checkout
// ═════════════════════════════════════════════════════════════
function WizardStep5_Summary({ task, onNext, onBack }) {
  const rows = [
    { label: "Property", value: task.property },
    { label: "Booking", value: "Mar 22 – Mar 25 (3 nights)" },
    { label: "Guest", value: "Sarah Johnson" },
    { label: "Condition", value: "Good", color: T.green },
    { label: "Rooms Inspected", value: "5 / 5" },
    { label: "Opening Meter", value: "45,231 kWh" },
    { label: "Closing Meter", value: "45,387 kWh" },
    { label: "Electricity Used", value: "156 kWh (฿ 780)" },
    { label: "Issues", value: "None", color: T.green },
    { label: "Deposit Held", value: "฿ 5,000" },
    { label: "Deductions", value: "฿ 780 (electricity)" },
    { label: "Guest Receives", value: "฿ 4,220", color: T.green },
  ];

  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="Checkout Summary" subtitle={`${task.property} · Step 5 of 5`} onBack={onBack} />

      <div style={{ margin: "8px 16px" }}>
        {rows.map((row, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: i < rows.length - 1 ? `1px solid ${T.cardBorder}` : "none" }}>
            <span style={{ fontSize: 12, color: T.textDim }}>{row.label}</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: row.color || T.text }}>{row.value}</span>
          </div>
        ))}
      </div>

      {/* Note about auto-triggered cleaning */}
      <div style={{ margin: "16px 16px", padding: 10, background: `${T.moss}22`, borderRadius: 8, border: `1px solid ${T.moss}44` }}>
        <div style={{ fontSize: 10, color: T.textDim }}>
          <strong style={{ color: T.text }}>Auto-trigger:</strong> Completing this checkout will create a CLEANING task for this property.
        </div>
      </div>

      <div style={{ padding: "12px 16px" }}>
        <button onClick={onNext} style={{ width: "100%", padding: 16, borderRadius: 10, background: T.copper, color: T.white, border: "none", fontSize: 15, fontWeight: 800, cursor: "pointer" }}>
          Complete Check-out ✓
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S07 — SUCCESS SCREEN [V1 PROPOSAL]
// ═════════════════════════════════════════════════════════════
function SuccessScreen({ task, onDone }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24, textAlign: "center" }}>
      <div style={{ width: 72, height: 72, borderRadius: 36, background: `${T.green}22`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16 }}>
        <CheckSquare size={36} color={T.green} />
      </div>

      <h1 style={{ fontSize: 22, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text, margin: "0 0 6px" }}>Checkout Complete</h1>
      <p style={{ fontSize: 13, color: T.textDim, margin: "0 0 20px" }}>{task.property} · {task.date}</p>

      <div style={{ width: "100%", maxWidth: 300, padding: 14, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}`, marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 4 }}>Deposit returned to guest</div>
        <div style={{ fontSize: 24, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.green }}>฿ 4,220</div>
      </div>

      <div style={{ width: "100%", maxWidth: 300, padding: 12, background: `${T.moss}15`, borderRadius: 10, border: `1px solid ${T.moss}33`, marginBottom: 24 }}>
        <div style={{ fontSize: 11, color: T.textDim }}>
          Cleaning task auto-created for {task.property}
        </div>
      </div>

      <button onClick={onDone} style={{ width: "100%", maxWidth: 300, padding: 14, borderRadius: 10, background: T.copper, color: T.white, border: "none", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
        Return to Departures
      </button>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// TASKS SCREEN [BUILT]
// Confirmed from screenshot 22.28.00: Pending/Done tabs, checkout task cards
// ═════════════════════════════════════════════════════════════
function TasksScreen() {
  const [tab, setTab] = useState("pending");
  const tasks = [
    { property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", countdown: "60h 31m 59s" },
    { property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-28", countdown: "60h 31m 59s" },
    { property: "Emuna Villa", code: "KPG-594", date: "2026-04-11", countdown: "396h 31m 59s" },
    { property: "Emuna Villa", code: "KPG-600", date: "2026-04-17", countdown: "540h 31m 59s" },
  ];

  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="My Tasks" subtitle="Today · Wednesday, Mar 25" />

      {/* Tabs [BUILT] */}
      <div style={{ display: "flex", margin: "8px 16px 16px", borderRadius: 8, overflow: "hidden", border: `1px solid ${T.cardBorder}` }}>
        {["pending", "done"].map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{ flex: 1, padding: "10px 0", border: "none", background: tab === t ? T.copper : T.card, color: tab === t ? T.white : T.textDim, fontSize: 12, fontWeight: 700, cursor: "pointer", textTransform: "capitalize" }}>
            {t}
          </button>
        ))}
      </div>

      {tab === "pending" ? (
        tasks.map((task, i) => (
          <div key={i} style={{ margin: "0 16px 10px", background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}`, padding: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>{task.property}</div>
                <div style={{ fontSize: 10, color: T.textMuted }}>{task.code}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <Clock size={12} color={T.textDim} />
                <span style={{ fontSize: 11, color: T.textDim }}>{task.countdown}</span>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
              <Badge label="Check-out" color={T.copper} />
              <span style={{ fontSize: 10, color: T.textDim }}>{task.date}</span>
              <span style={{ marginLeft: "auto", fontSize: 10, color: T.textDim }}>PENDING</span>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button style={{ flex: 1, padding: "10px 0", borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                Acknowledge
              </button>
              <button style={{ flex: 2, padding: "10px 0", borderRadius: 8, border: "none", background: T.copper, color: T.white, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                Start Check-out →
              </button>
              <button style={{ width: 36, height: 36, borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
                <Star size={14} color={T.amber} />
              </button>
            </div>
          </div>
        ))
      ) : (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 48 }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🎉</div>
          <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>All clear!</div>
          <div style={{ fontSize: 11, color: T.textDim }}>No completed tasks yet today</div>
        </div>
      )}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// SETTINGS SCREEN [V1 PROPOSAL]
// ═════════════════════════════════════════════════════════════
function SettingsScreen() {
  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="Settings" />

      {/* Profile card */}
      <div style={{ margin: "8px 16px 16px", padding: 16, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}`, display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ width: 48, height: 48, borderRadius: 24, background: T.copperDark, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <User size={22} color={T.copper} />
        </div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Admin User</div>
          <div style={{ fontSize: 11, color: T.textDim }}>Check-out Staff</div>
        </div>
      </div>

      {/* Assigned Properties */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>ASSIGNED PROPERTIES</div>
        {["Zen Pool Villa · KPG-582", "Emuna Villa · KPG-588"].map((p, i) => (
          <div key={i} style={{ padding: "10px 12px", background: T.card, borderRadius: 8, border: `1px solid ${T.cardBorder}`, marginBottom: 6, fontSize: 12, color: T.text, display: "flex", alignItems: "center", gap: 8 }}>
            <MapPin size={14} color={T.copper} /> {p}
          </div>
        ))}
      </div>

      {/* Notification Settings */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>NOTIFICATIONS</div>
        {[
          { label: "LINE notifications", enabled: true },
          { label: "Phone notifications", enabled: false },
        ].map((n, i) => (
          <div key={i} style={{ padding: "10px 12px", background: T.card, borderRadius: 8, border: `1px solid ${T.cardBorder}`, marginBottom: 6, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: T.text }}>{n.label}</span>
            <div style={{ width: 36, height: 20, borderRadius: 10, background: n.enabled ? T.copper : T.cardBorder, position: "relative", cursor: "pointer" }}>
              <div style={{ width: 16, height: 16, borderRadius: 8, background: T.white, position: "absolute", top: 2, left: n.enabled ? 18 : 2, transition: "left 0.2s" }} />
            </div>
          </div>
        ))}
      </div>

      {/* Session */}
      <div style={{ padding: "0 16px" }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>SESSION</div>
        <button style={{ width: "100%", padding: 12, borderRadius: 8, border: `1px solid ${T.red}44`, background: `${T.red}11`, color: T.red, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
          Sign Out
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// MAIN COMPONENT — CHECK OUT STAFF V1
// ═════════════════════════════════════════════════════════════
export default function CheckOutStaffV1() {
  const [screen, setScreen] = useState("home");
  const [wizardStep, setWizardStep] = useState(0);
  const [activeTask, setActiveTask] = useState(null);

  const defaultTask = { property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-28" };

  const startWizard = (task) => {
    setActiveTask(task || defaultTask);
    setWizardStep(1);
    setScreen("wizard");
  };

  const handleNav = (id) => {
    if (id === "wizard") return;
    setScreen(id);
    setWizardStep(0);
  };

  const renderScreen = () => {
    if (screen === "wizard") {
      const task = activeTask || defaultTask;
      switch (wizardStep) {
        case 1: return <WizardStep1_Inspection task={task} onNext={() => setWizardStep(2)} onBack={() => handleNav("checkout")} />;
        case 2: return <WizardStep2_Meter task={task} onNext={() => setWizardStep(3)} onBack={() => setWizardStep(1)} />;
        case 3: return <WizardStep3_Issues task={task} onNext={() => setWizardStep(4)} onBack={() => setWizardStep(2)} />;
        case 4: return <WizardStep4_Deposit task={task} onNext={() => setWizardStep(5)} onBack={() => setWizardStep(3)} />;
        case 5: return <WizardStep5_Summary task={task} onNext={() => setWizardStep(6)} onBack={() => setWizardStep(4)} />;
        case 6: return <SuccessScreen task={task} onDone={() => handleNav("checkout")} />;
        default: return <DeparturesScreen onStartWizard={startWizard} />;
      }
    }
    switch (screen) {
      case "home": return <HomeScreen onNavigate={handleNav} />;
      case "checkout": return <DeparturesScreen onStartWizard={startWizard} />;
      case "tasks": return <TasksScreen />;
      case "settings": return <SettingsScreen />;
      default: return <HomeScreen onNavigate={handleNav} />;
    }
  };

  const activeTab = screen === "wizard" ? "checkout" : screen;

  return (
    <div style={{ maxWidth: 390, margin: "0 auto", background: T.bg, minHeight: "100vh", fontFamily: "Inter, sans-serif", color: T.text, position: "relative" }}>
      {renderScreen()}
      {screen !== "wizard" || wizardStep === 0 ? (
        <BottomNav active={activeTab} onNavigate={handleNav} />
      ) : null}
    </div>
  );
}