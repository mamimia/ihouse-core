import { useState } from "react";
import { Home, Calendar, ClipboardList, DoorOpen, CheckSquare, ChevronRight, ArrowLeft, MapPin, Clock, Star, Navigation, User, Settings } from "lucide-react";

// ─── DESIGN TOKENS ───────────────────────────────────────────
// Combined role uses dual accents: deep-moss (arrivals) + signal-copper (departures)
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
  copperLight: "#C4865E",
  copperDark: "#8F5736",
  amber: "#F59E0B",
  red: "#DC2626",
  blue: "#3B82F6",
  green: "#22C55E",
  white: "#FFFFFF",
  bottomNav: "#141719",
};

// ─── BOTTOM NAV [BUILT] ─────────────────────────────────────
// Combined role: Today | Arrivals | Departures | Tasks (4 tabs)
// Confirmed from screenshot 22.28.41 — "Today" tab shows calendar date icon
function BottomNav({ active, onNavigate }) {
  const tabs = [
    { id: "today", label: "Today", icon: Calendar },
    { id: "arrivals", label: "Arrivals", icon: ClipboardList },
    { id: "departures", label: "Departures", icon: DoorOpen },
    { id: "tasks", label: "Tasks", icon: CheckSquare },
  ];
  return (
    <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, height: 56, background: T.bottomNav, display: "flex", borderTop: `1px solid ${T.cardBorder}`, zIndex: 50 }}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = active === tab.id;
        const activeColor = tab.id === "arrivals" ? T.mossBright : tab.id === "departures" ? T.copper : T.white;
        return (
          <button key={tab.id} onClick={() => onNavigate(tab.id)} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2, background: "none", border: "none", cursor: "pointer", color: isActive ? activeColor : T.textMuted }}>
            <Icon size={20} strokeWidth={isActive ? 2.2 : 1.5} />
            <span style={{ fontSize: 10, fontWeight: isActive ? 700 : 400 }}>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

// ─── BADGE ───────────────────────────────────────────────────
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
      {breadcrumb && <div style={{ fontSize: 10, color: T.textMuted, marginBottom: 8, fontFamily: "Inter, sans-serif" }}>{breadcrumb}</div>}
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
// S00 — WORKER HOME [BUILT]
// Confirmed from screenshot 22.30.27
// Note: WORK section appears ABOVE MY STATUS (reversed from other roles)
// ═════════════════════════════════════════════════════════════
function HomeScreen({ onNavigate }) {
  return (
    <div style={{ paddingBottom: 72 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px" }}>
        <span style={{ fontSize: 16, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text }}>Home</span>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 11, color: T.textDim }}>EN</span>
          <span style={{ fontSize: 11, color: T.textDim, cursor: "pointer" }}>→ Sign Out</span>
        </div>
      </div>

      {/* Welcome [BUILT] */}
      <div style={{ margin: "0 16px 16px", padding: 16, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 4 }}>WELCOME</div>
        <div style={{ fontSize: 20, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text }}>Hello, admin</div>
        <Badge label="Check-in & Check-out" color={T.mossBright} />
      </div>

      {/* WORK [BUILT] — appears ABOVE MY STATUS for combined role */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <button onClick={() => onNavigate("today")} style={{ width: "100%", background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: "14px 16px", display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: `${T.moss}88`, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Home size={18} color={T.mossBright} />
          </div>
          <div style={{ flex: 1, textAlign: "left" }}>
            <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Go to Check-in & Check-out</div>
            <div style={{ fontSize: 11, color: T.textDim }}>Your combined operations hub</div>
          </div>
          <ChevronRight size={18} color={T.textMuted} />
        </button>
      </div>

      {/* MY STATUS [BUILT] — below WORK for this role */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>MY STATUS</div>
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { label: "Open", value: 0, icon: "📋", color: T.mossBright },
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
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S01 — OPERATIONS HUB ("Your Shifts") [BUILT]
// Confirmed from screenshot 22.28.41
// Two operational blocks (not cards), Profile & Settings link
// ═════════════════════════════════════════════════════════════
function HubScreen({ onNavigate }) {
  return (
    <div style={{ paddingBottom: 72 }}>
      <div style={{ padding: "12px 16px 0", fontSize: 10, color: T.textMuted, fontFamily: "Inter, sans-serif" }}>
        Home &nbsp;›&nbsp; Operations &nbsp;›&nbsp; Checkin Checkout
      </div>

      {/* Title block [BUILT] */}
      <div style={{ padding: "12px 16px 4px" }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: T.textDim }}>Check-in & Check-out</div>
        <div style={{ fontSize: 10, fontWeight: 600, fontFamily: "Manrope, sans-serif", color: T.textMuted, textTransform: "uppercase", marginTop: 8 }}>WEDNESDAY, MARCH 25</div>
        <h1 style={{ fontSize: 26, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text, margin: "2px 0 0" }}>Your Shifts</h1>
        <p style={{ fontSize: 11, color: T.textDim, margin: "2px 0 0" }}>Check-ins (7 days) & Check-outs (task world)</p>
      </div>

      {/* Check-in block [BUILT] — green CTA */}
      <div style={{ margin: "16px 16px 12px", padding: 16, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: T.moss, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <ClipboardList size={16} color={T.mossBright} />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Check-in</div>
              <div style={{ fontSize: 10, color: T.textDim }}>Next 7 days · task world</div>
            </div>
          </div>
          <div style={{ fontSize: 28, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.mossBright }}>10</div>
        </div>
        <div style={{ fontSize: 10, color: T.textDim, marginBottom: 10 }}>
          <Clock size={10} style={{ verticalAlign: "middle" }} /> Next arrival in 15h 31m
        </div>
        <button onClick={() => onNavigate("arrivals")} style={{ width: "100%", padding: "12px 0", borderRadius: 8, border: "none", background: T.moss, color: T.white, fontSize: 13, fontWeight: 700, cursor: "pointer" }}>
          Start Check-Ins (10 pending) →
        </button>
      </div>

      {/* Check-out block [BUILT] — copper CTA */}
      <div style={{ margin: "0 16px 12px", padding: 16, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: T.copperDark, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <DoorOpen size={16} color={T.copper} />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Check-out</div>
              <div style={{ fontSize: 10, color: T.textDim }}>Task world</div>
            </div>
          </div>
          <div style={{ fontSize: 28, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.copper }}>8 <span style={{ fontSize: 12, fontWeight: 500 }}>upcoming</span></div>
        </div>
        <div style={{ fontSize: 10, color: T.textDim, marginBottom: 10 }}>
          <Clock size={10} style={{ verticalAlign: "middle" }} /> Next checkout in 2d
        </div>
        <button onClick={() => onNavigate("departures")} style={{ width: "100%", padding: "12px 0", borderRadius: 8, border: "none", background: T.copper, color: T.white, fontSize: 13, fontWeight: 700, cursor: "pointer" }}>
          Process Check-outs (8) →
        </button>
      </div>

      {/* Same-Day Turns [V1 PROPOSAL] */}
      <div style={{ margin: "0 16px 12px", padding: 12, background: `${T.amber}08`, borderRadius: 10, border: `1px solid ${T.amber}22` }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.amber, marginBottom: 8 }}>SAME-DAY TURNS</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.text, marginBottom: 4 }}>
          <span style={{ fontWeight: 700 }}>Zen Pool Villa</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10, color: T.textDim }}>
          <Badge label="OUT 11:00" color={T.copper} />
          <span>→</span>
          <Badge label="CLEAN" color={T.textDim} />
          <span>→</span>
          <Badge label="IN 14:00" color={T.mossBright} />
        </div>
      </div>

      {/* Profile & Settings link [BUILT] */}
      <div style={{ margin: "0 16px" }}>
        <button onClick={() => onNavigate("settings")} style={{ width: "100%", background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: "12px 16px", display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
          <Settings size={18} color={T.textDim} />
          <div style={{ flex: 1, textAlign: "left" }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>Profile & Settings</div>
            <div style={{ fontSize: 10, color: T.textDim }}>Home · Sign out · Language</div>
          </div>
          <ChevronRight size={16} color={T.textMuted} />
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// ARRIVALS LIST (delegates to CHECK_IN_STAFF flow)
// Shown when "Arrivals" tab is active — uses moss/green accent
// ═════════════════════════════════════════════════════════════
function ArrivalsListScreen() {
  const tasks = [
    { property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-26", countdown: "15h 30m 52s", status: "ACKNOWLEDGED", type: "checkin" },
    { property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", countdown: "63h 30m 52s", status: "PENDING", type: "checkin" },
    { property: "Emuna Villa", code: "KPG-594", date: "2026-04-01", countdown: "159h 30m 52s", status: "PENDING", type: "checkin" },
  ];

  return (
    <div style={{ paddingBottom: 72 }}>
      <div style={{ padding: "12px 16px 0", fontSize: 10, color: T.textMuted, fontFamily: "Inter, sans-serif" }}>
        Home &nbsp;›&nbsp; Operations &nbsp;›&nbsp; Check-In
      </div>

      <ScreenHeader title="Check-in" subtitle="Arrivals · next 7 days" />

      <div style={{ padding: "0 16px 4px", fontSize: 10, fontWeight: 600, fontFamily: "Manrope, sans-serif", color: T.textMuted, textTransform: "uppercase" }}>WEDNESDAY, MARCH 25</div>

      {/* Summary strip */}
      <div style={{ display: "flex", gap: 8, padding: "8px 16px 16px" }}>
        {[
          { label: "TODAY", value: "1", color: T.mossBright },
          { label: "UPCOMING", value: "9", color: T.blue },
          { label: "NEXT", value: "15h", sub: "Check-in 14:00", color: T.mossBright },
        ].map((s) => (
          <div key={s.label} style={{ flex: 1, background: T.card, borderRadius: 10, padding: "8px 10px", border: `1px solid ${T.cardBorder}` }}>
            <div style={{ fontSize: 8, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 2 }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: s.color }}>{s.value}</div>
            {s.sub && <div style={{ fontSize: 9, color: T.textMuted }}>{s.sub}</div>}
          </div>
        ))}
      </div>

      {tasks.map((task, i) => (
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
            <Badge label="Check-in" color={T.mossBright} />
            <span style={{ fontSize: 10, color: T.textDim }}>{task.date}</span>
            <span style={{ marginLeft: "auto", fontSize: 10, color: task.status === "ACKNOWLEDGED" ? T.mossBright : T.textDim }}>{task.status}</span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {task.status !== "ACKNOWLEDGED" && (
              <button style={{ flex: 1, padding: "10px 0", borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                Acknowledge
              </button>
            )}
            <button style={{ flex: 2, padding: "10px 0", borderRadius: 8, border: "none", background: T.moss, color: T.white, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
              Start Check-in →
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
// DEPARTURES LIST (delegates to CHECK_OUT_STAFF flow)
// Shown when "Departures" tab is active — uses copper accent
// ═════════════════════════════════════════════════════════════
function DeparturesListScreen() {
  const tasks = [
    { property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", countdown: "60h 30m 52s", status: "PENDING", type: "checkout" },
    { property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-28", countdown: "60h 30m 52s", status: "PENDING", type: "checkout" },
    { property: "Emuna Villa", code: "KPG-594", date: "2026-04-11", countdown: "396h 30m 52s", status: "PENDING", type: "checkout" },
  ];

  return (
    <div style={{ paddingBottom: 72 }}>
      <div style={{ padding: "12px 16px 0", fontSize: 10, color: T.textMuted, fontFamily: "Inter, sans-serif" }}>
        Home &nbsp;›&nbsp; Operations &nbsp;›&nbsp; Check-Out
      </div>

      <ScreenHeader title="Check-out" subtitle="Departures · task world" />

      <div style={{ padding: "0 16px 4px", fontSize: 10, fontWeight: 600, fontFamily: "Manrope, sans-serif", color: T.textMuted, textTransform: "uppercase" }}>WEDNESDAY, MARCH 25</div>

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

      {tasks.map((task, i) => (
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
            <span style={{ marginLeft: "auto", fontSize: 10, color: T.textDim }}>{task.status}</span>
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
      ))}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S02 — MERGED TASK LIST [BUILT]
// Confirmed from screenshot 22.29.08: Mixed check-in + check-out cards
// ═════════════════════════════════════════════════════════════
function MergedTasksScreen() {
  const [tab, setTab] = useState("pending");
  const tasks = [
    { property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-26", countdown: "15h 30m 52s", status: "ACKNOWLEDGED", type: "checkin", desc: "" },
    { property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", countdown: "60h 30m 52s", status: "PENDING", type: "checkout", desc: "" },
    { property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-28", countdown: "60h 30m 52s", status: "PENDING", type: "checkout", desc: "" },
    { property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", countdown: "63h 30m 52s", status: "PENDING", type: "checkin", desc: "CHECKIN_PREP — KPG-500" },
  ];

  const typeConfig = {
    checkin: { label: "Check-in", color: T.mossBright, bg: T.moss, cta: "Start Check-in →" },
    checkout: { label: "Check-out", color: T.copper, bg: T.copper, cta: "Start Check-out →" },
  };

  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="My Tasks" subtitle="Today · Wednesday, Mar 25" />

      {/* Pending/Done tabs [BUILT] */}
      <div style={{ display: "flex", margin: "8px 16px 16px", borderRadius: 8, overflow: "hidden", border: `1px solid ${T.cardBorder}` }}>
        {["pending", "done"].map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{ flex: 1, padding: "10px 0", border: "none", background: tab === t ? T.moss : T.card, color: tab === t ? T.white : T.textDim, fontSize: 12, fontWeight: 700, cursor: "pointer", textTransform: "capitalize" }}>
            {t}
          </button>
        ))}
      </div>

      {tab === "pending" ? (
        tasks.map((task, i) => {
          const cfg = typeConfig[task.type];
          return (
            <div key={i} style={{ margin: "0 16px 10px", background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}`, padding: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>{task.property}</div>
                  <div style={{ fontSize: 10, color: T.textMuted }}>{task.code}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <Clock size={12} color={T.textDim} />
                  <span style={{ fontSize: 11, color: T.textDim }}>{task.countdown}</span>
                </div>
              </div>

              {task.desc && <div style={{ fontSize: 10, color: T.textMuted, marginBottom: 4, fontStyle: "italic" }}>{task.desc}</div>}

              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
                <Badge label={cfg.label} color={cfg.color} />
                <span style={{ fontSize: 10, color: T.textDim }}>{task.date}</span>
                <span style={{ marginLeft: "auto", fontSize: 10, color: task.status === "ACKNOWLEDGED" ? cfg.color : T.textDim }}>{task.status}</span>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {task.status !== "ACKNOWLEDGED" && (
                  <button style={{ flex: 1, padding: "10px 0", borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                    Acknowledge
                  </button>
                )}
                <button style={{ flex: 2, padding: "10px 0", borderRadius: 8, border: "none", background: cfg.bg, color: T.white, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                  {cfg.cta}
                </button>
                <button style={{ width: 36, height: 36, borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
                  <Star size={14} color={T.amber} />
                </button>
              </div>
            </div>
          );
        })
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
// SETTINGS / PROFILE [V1 PROPOSAL]
// Unique: shows dual capability chips (Arrivals + Departures)
// ═════════════════════════════════════════════════════════════
function SettingsScreen({ onBack }) {
  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="Profile & Settings" onBack={onBack} />

      <div style={{ margin: "8px 16px 16px", padding: 16, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}`, display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ width: 48, height: 48, borderRadius: 24, background: T.moss, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <User size={22} color={T.mossBright} />
        </div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Admin User</div>
          <div style={{ fontSize: 11, color: T.textDim }}>Check-in & Check-out Staff</div>
        </div>
      </div>

      {/* Capabilities [V1 PROPOSAL — unique to combined role] */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>CAPABILITIES</div>
        <div style={{ display: "flex", gap: 8 }}>
          <span style={{ padding: "6px 14px", borderRadius: 16, background: `${T.mossBright}15`, border: `1px solid ${T.mossBright}33`, color: T.mossBright, fontSize: 11, fontWeight: 600 }}>
            📋 Arrivals
          </span>
          <span style={{ padding: "6px 14px", borderRadius: 16, background: `${T.copper}15`, border: `1px solid ${T.copper}33`, color: T.copper, fontSize: 11, fontWeight: 600 }}>
            🚪 Departures
          </span>
        </div>
      </div>

      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>ASSIGNED PROPERTIES</div>
        {["Villa Emuna · KPG-588", "Zen Pool Villa · KPG-582", "Baan Suan · KPG-600"].map((p, i) => (
          <div key={i} style={{ padding: "10px 12px", background: T.card, borderRadius: 8, border: `1px solid ${T.cardBorder}`, marginBottom: 6, fontSize: 12, color: T.text, display: "flex", alignItems: "center", gap: 8 }}>
            <MapPin size={14} color={T.mossBright} /> {p}
          </div>
        ))}
      </div>

      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>NOTIFICATIONS</div>
        {[
          { label: "LINE notifications", enabled: true },
          { label: "Phone notifications", enabled: false },
        ].map((n, i) => (
          <div key={i} style={{ padding: "10px 12px", background: T.card, borderRadius: 8, border: `1px solid ${T.cardBorder}`, marginBottom: 6, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: T.text }}>{n.label}</span>
            <div style={{ width: 36, height: 20, borderRadius: 10, background: n.enabled ? T.mossBright : T.cardBorder, position: "relative", cursor: "pointer" }}>
              <div style={{ width: 16, height: 16, borderRadius: 8, background: T.white, position: "absolute", top: 2, left: n.enabled ? 18 : 2, transition: "left 0.2s" }} />
            </div>
          </div>
        ))}
      </div>

      <div style={{ padding: "0 16px" }}>
        <button style={{ width: "100%", padding: 12, borderRadius: 8, border: `1px solid ${T.red}44`, background: `${T.red}11`, color: T.red, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
          Sign Out
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═════════════════════════════════════════════════════════════
export default function CheckinCheckoutV1() {
  const [screen, setScreen] = useState("home");

  const handleNav = (id) => setScreen(id);

  const renderScreen = () => {
    switch (screen) {
      case "home": return <HomeScreen onNavigate={handleNav} />;
      case "today": return <HubScreen onNavigate={handleNav} />;
      case "arrivals": return <ArrivalsListScreen />;
      case "departures": return <DeparturesListScreen />;
      case "tasks": return <MergedTasksScreen />;
      case "settings": return <SettingsScreen onBack={() => handleNav("today")} />;
      default: return <HomeScreen onNavigate={handleNav} />;
    }
  };

  const activeTab = screen === "home" || screen === "today" || screen === "settings" ? "today" : screen;

  return (
    <div style={{ maxWidth: 390, margin: "0 auto", background: T.bg, minHeight: "100vh", fontFamily: "Inter, sans-serif", color: T.text, position: "relative" }}>
      {renderScreen()}
      {screen !== "settings" && <BottomNav active={activeTab} onNavigate={handleNav} />}
    </div>
  );
}