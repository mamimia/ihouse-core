import { useState } from "react";
import { Home, Brush, CheckSquare, Settings, ChevronRight, ArrowLeft, MapPin, Clock, Calendar, Camera, Star, Navigation, User, AlertTriangle, Package, Check, X, Image } from "lucide-react";

// ─── DESIGN TOKENS ───────────────────────────────────────────
// Cleaner uses deep-moss green as primary accent (readiness/completion identity)
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

// ─── BOTTOM NAV [BUILT] ─────────────────────────────────────
// Confirmed: Home | Cleaner | Tasks | Settings (4 tabs)
function BottomNav({ active, onNavigate }) {
  const tabs = [
    { id: "home", label: "Home", icon: Home },
    { id: "cleaner", label: "Cleaner", icon: Brush },
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
// S00 — HOME SCREEN [BUILT]
// Confirmed from screenshot 22.18.48
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
        <Badge label="Cleaner" color={T.mossBright} />
      </div>

      {/* MY STATUS [BUILT] — Open 9, Overdue 0, Today 0 */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>MY STATUS</div>
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { label: "Open", value: 9, icon: "📋", color: T.mossBright },
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

      {/* WORK [BUILT] — "Go to Cleaning" CTA */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>WORK</div>
        <button onClick={() => onNavigate("cleaner")} style={{ width: "100%", background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: "14px 16px", display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: T.moss, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Brush size={18} color={T.mossBright} />
          </div>
          <div style={{ flex: 1, textAlign: "left" }}>
            <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Go to Cleaning</div>
            <div style={{ fontSize: 11, color: T.textDim }}>9 tasks waiting</div>
          </div>
          <ChevronRight size={18} color={T.textMuted} />
        </button>
      </div>

      {/* NEXT UP [BUILT] — task preview cards */}
      <div style={{ padding: "0 16px" }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>NEXT UP</div>
        {[
          { property: "Emuna Villa", date: "Sat, Mar 28", status: "Acknowledged", priority: "MEDIUM" },
          { property: "Zen Pool Villa", date: "Sat, Mar 28", status: "Pending", priority: "MEDIUM" },
        ].map((task, i) => (
          <div key={i} style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}`, padding: 14, marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
              <div>
                <div style={{ fontSize: 9, color: T.textMuted, display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
                  <span>🧹</span> CLEANER
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Cleaning</div>
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
                <Badge label={task.status} color={task.status === "Acknowledged" ? T.mossBright : T.textDim} />
                <button style={{ background: T.moss, border: "none", borderRadius: 6, padding: "5px 10px", fontSize: 10, fontWeight: 600, color: T.text, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
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
// S01 — TODAY'S TASKS (CLEANING LIST) [BUILT]
// Confirmed from screenshot 22.20.46
// ═════════════════════════════════════════════════════════════
function CleaningListScreen({ onStartTask }) {
  const tasks = [
    { property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-28", countdown: "59h 39m 14s", status: "PENDING", desc: "Checkout cleaning for MAN-KPG-502-20260326-f360" },
    { property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", countdown: "59h 38m 55s", status: "ACKNOWLEDGED", desc: "Pre-arrival cleaning for ICAL-36ff7d9905e0" },
    { property: "Emuna Villa", code: "KPG-594", date: "2026-04-11", countdown: "395h 39m 14s", status: "PENDING", desc: "Pre-arrival cleaning for ICAL-6240ffa80a91" },
  ];

  return (
    <div style={{ paddingBottom: 72 }}>
      <div style={{ padding: "12px 16px 0", fontSize: 10, color: T.textMuted, fontFamily: "Inter, sans-serif" }}>
        Home &nbsp;›&nbsp; Operations &nbsp;›&nbsp; Cleaner
      </div>

      <ScreenHeader title="Today's Tasks" subtitle="Cleaning tasks assigned to you" />

      <div style={{ padding: "0 16px 4px", fontSize: 10, fontWeight: 600, fontFamily: "Manrope, sans-serif", color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.05em" }}>
        WEDNESDAY, MARCH 25
      </div>

      {/* Summary strip [BUILT] — TASKS / DONE / NEXT */}
      <div style={{ display: "flex", gap: 8, padding: "8px 16px 16px" }}>
        {[
          { label: "TASKS", value: "10", color: T.mossBright },
          { label: "DONE", value: "0", color: T.green },
          { label: "NEXT", value: "in 2d", sub: "clean by 10:00", color: T.blue },
        ].map((s) => (
          <div key={s.label} style={{ flex: 1, background: T.card, borderRadius: 10, padding: "8px 10px", border: `1px solid ${T.cardBorder}` }}>
            <div style={{ fontSize: 8, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 2 }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: s.color }}>{s.value}</div>
            {s.sub && <div style={{ fontSize: 9, color: T.textMuted }}>{s.sub}</div>}
          </div>
        ))}
      </div>

      <div style={{ padding: "0 16px 8px", fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted }}>UPCOMING</div>

      {/* Task cards [BUILT] — green "Start Cleaning →" CTA */}
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

          {/* Description line [BUILT] — e.g. "Pre-arrival cleaning for ICAL-xxx" */}
          <div style={{ fontSize: 10, color: T.textMuted, marginBottom: 6, fontStyle: "italic" }}>
            {task.desc}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
            <Badge label="Cleaning" color={T.mossBright} />
            <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: T.textDim }}>
              <Calendar size={10} /> {task.date}
            </div>
            <span style={{ marginLeft: "auto", fontSize: 10, color: T.textDim }}>{task.status}</span>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {task.status !== "ACKNOWLEDGED" && (
              <button style={{ flex: 1, padding: "10px 0", borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                Acknowledge
              </button>
            )}
            <button onClick={() => onStartTask(task)} style={{ flex: 2, padding: "10px 0", borderRadius: 8, border: "none", background: T.moss, color: T.white, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
              Start Cleaning →
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
// S02 — TASK DETAIL [INFERRED]
// Overview before starting the clean
// ═════════════════════════════════════════════════════════════
function TaskDetailScreen({ task, onStart, onBack }) {
  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title={task.property} subtitle="Cleaning Task" onBack={onBack} />

      {/* Info block */}
      <div style={{ margin: "8px 16px 12px", padding: 14, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}` }}>
        {[
          { label: "Property", value: task.property },
          { label: "Property ID", value: task.code },
          { label: "Due Date", value: task.date },
          { label: "Task", value: "Cleaning" },
          { label: "Type", value: task.desc || "Pre-arrival cleaning" },
        ].map((row, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: i < 4 ? `1px solid ${T.cardBorder}` : "none" }}>
            <span style={{ fontSize: 11, color: T.textDim }}>{row.label}</span>
            <span style={{ fontSize: 11, fontWeight: 600, color: T.text }}>{row.value}</span>
          </div>
        ))}
      </div>

      {/* Operator note (if any) */}
      <div style={{ margin: "0 16px 12px", padding: 12, background: `${T.moss}22`, borderRadius: 10, border: `1px solid ${T.moss}44` }}>
        <div style={{ fontSize: 10, color: T.textDim }}>
          <strong style={{ color: T.text }}>Note:</strong> Guest checking in tomorrow at 15:00. Extra attention to bathroom — previous guest flagged showerhead.
        </div>
      </div>

      {/* Checklist preview */}
      <div style={{ margin: "0 16px 12px", padding: 12, background: T.card, borderRadius: 10, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>CHECKLIST PREVIEW</div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: T.textDim, marginBottom: 4 }}>
          <span>Items</span><span style={{ color: T.text, fontWeight: 600 }}>21 items across 5 rooms</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: T.textDim, marginBottom: 4 }}>
          <span>Photos required</span><span style={{ color: T.text, fontWeight: 600 }}>6</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: T.textDim }}>
          <span>Supply check</span><span style={{ color: T.text, fontWeight: 600 }}>7 items</span>
        </div>
      </div>

      <div style={{ padding: "0 16px", display: "flex", gap: 8 }}>
        <button style={{ flex: 1, padding: 14, borderRadius: 10, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 13, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
          <Navigation size={14} /> Navigate
        </button>
        <button onClick={onStart} style={{ flex: 2, padding: 14, borderRadius: 10, background: T.moss, color: T.white, border: "none", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
          Start Cleaning 🧹
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S03 — ACTIVE CHECKLIST (CORE SCREEN) [V1 PROPOSAL]
// Room-by-room checklist with progress, photos, supply check
// ═════════════════════════════════════════════════════════════
function ChecklistScreen({ task, onComplete, onBack }) {
  const [checkedItems, setCheckedItems] = useState({});
  const [photos, setPhotos] = useState({});
  const [supplies, setSupplies] = useState({});
  const [activeRoom, setActiveRoom] = useState(null);
  const [showIssueForm, setShowIssueForm] = useState(false);

  const rooms = [
    { id: "bedroom", label: "Bedroom", items: [
      { id: "b1", text: "Change bed sheets", photo: false },
      { id: "b2", text: "Replace pillowcases", photo: false },
      { id: "b3", text: "Dust surfaces", photo: false },
      { id: "b4", text: "Vacuum floor", photo: false },
      { id: "b5", text: "Empty trash", photo: true },
    ]},
    { id: "bathroom", label: "Bathroom", items: [
      { id: "ba1", text: "Clean toilet", photo: false },
      { id: "ba2", text: "Clean shower", photo: true },
      { id: "ba3", text: "Mirror & sink", photo: true },
      { id: "ba4", text: "Replace towels", photo: false },
      { id: "ba5", text: "Check soap/shampoo", photo: false },
      { id: "ba6", text: "Mop floor", photo: false },
    ]},
    { id: "kitchen", label: "Kitchen", items: [
      { id: "k1", text: "Clean countertops", photo: false },
      { id: "k2", text: "Wash dishes", photo: false },
      { id: "k3", text: "Clean fridge", photo: true },
      { id: "k4", text: "Wipe stove", photo: false },
      { id: "k5", text: "Empty trash", photo: true },
    ]},
    { id: "living", label: "Living Room", items: [
      { id: "l1", text: "Vacuum/sweep floor", photo: false },
      { id: "l2", text: "Dust surfaces", photo: false },
      { id: "l3", text: "Arrange cushions", photo: false },
      { id: "l4", text: "Clean windows", photo: true },
    ]},
    { id: "exterior", label: "Exterior", items: [
      { id: "e1", text: "Sweep patio/balcony", photo: true },
    ]},
  ];

  const supplyItems = [
    { id: "s1", label: "Sheets" },
    { id: "s2", label: "Towels" },
    { id: "s3", label: "Soap" },
    { id: "s4", label: "Shampoo" },
    { id: "s5", label: "Toilet Paper" },
    { id: "s6", label: "Trash Bags" },
    { id: "s7", label: "Cleaning Supplies" },
  ];

  const totalItems = rooms.reduce((sum, r) => sum + r.items.length, 0);
  const checkedCount = Object.values(checkedItems).filter(Boolean).length;
  const totalPhotos = rooms.reduce((sum, r) => sum + r.items.filter(i => i.photo).length, 0);
  const photoCount = Object.values(photos).filter(Boolean).length;
  const supplyCount = Object.keys(supplies).length;
  const allComplete = checkedCount === totalItems && photoCount === totalPhotos && supplyCount === supplyItems.length;

  const toggleCheck = (id) => setCheckedItems(prev => ({ ...prev, [id]: !prev[id] }));
  const togglePhoto = (id) => setPhotos(prev => ({ ...prev, [id]: !prev[id] }));
  const cycleSupply = (id) => {
    const states = ["ok", "low", "empty"];
    const current = supplies[id];
    const next = current ? states[(states.indexOf(current) + 1) % 3] : "ok";
    setSupplies(prev => ({ ...prev, [id]: next }));
  };

  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title={task.property} subtitle="Active Cleaning" onBack={onBack} />

      {/* Progress bars [V1 PROPOSAL] — always visible at top */}
      <div style={{ padding: "4px 16px 12px" }}>
        {[
          { label: "Items", current: checkedCount, total: totalItems, color: T.mossBright },
          { label: "Photos", current: photoCount, total: totalPhotos, color: T.blue },
          { label: "Supplies", current: supplyCount, total: supplyItems.length, color: T.amber },
        ].map((bar) => (
          <div key={bar.label} style={{ marginBottom: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: T.textDim, marginBottom: 2 }}>
              <span>{bar.label}</span>
              <span style={{ fontWeight: 600 }}>{bar.current}/{bar.total}</span>
            </div>
            <div style={{ height: 6, background: T.cardBorder, borderRadius: 3, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${(bar.current / bar.total) * 100}%`, background: bar.color, borderRadius: 3, transition: "width 0.3s" }} />
            </div>
          </div>
        ))}
      </div>

      {/* Room selector (quick-jump) [V1 PROPOSAL] */}
      <div style={{ display: "flex", gap: 6, padding: "0 16px 12px", overflowX: "auto" }}>
        {rooms.map((room) => {
          const roomChecked = room.items.filter(i => checkedItems[i.id]).length;
          const roomDone = roomChecked === room.items.length;
          return (
            <button key={room.id} onClick={() => setActiveRoom(activeRoom === room.id ? null : room.id)} style={{ padding: "5px 12px", borderRadius: 16, border: `1px solid ${roomDone ? T.green : activeRoom === room.id ? T.mossBright : T.cardBorder}`, background: roomDone ? `${T.green}15` : activeRoom === room.id ? `${T.mossBright}15` : "transparent", color: roomDone ? T.green : activeRoom === room.id ? T.mossBright : T.textDim, fontSize: 10, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 4 }}>
              {roomDone && <Check size={10} />} {room.label}
            </button>
          );
        })}
      </div>

      {/* Checklist by room */}
      {rooms.filter(r => !activeRoom || r.id === activeRoom).map((room) => (
        <div key={room.id} style={{ margin: "0 16px 12px" }}>
          <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.mossBright, marginBottom: 6, paddingBottom: 4, borderBottom: `1px solid ${T.cardBorder}` }}>
            {room.label}
          </div>
          {room.items.map((item) => (
            <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: `1px solid ${T.cardBorder}11` }}>
              <button onClick={() => toggleCheck(item.id)} style={{ width: 22, height: 22, borderRadius: 4, border: `1.5px solid ${checkedItems[item.id] ? T.green : T.cardBorder}`, background: checkedItems[item.id] ? `${T.green}22` : "transparent", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", flexShrink: 0 }}>
                {checkedItems[item.id] && <Check size={14} color={T.green} />}
              </button>
              <span style={{ flex: 1, fontSize: 12, color: checkedItems[item.id] ? T.textMuted : T.text, textDecoration: checkedItems[item.id] ? "line-through" : "none" }}>
                {item.text}
              </span>
              {item.photo && (
                <button onClick={() => togglePhoto(item.id)} style={{ width: 28, height: 28, borderRadius: 6, border: `1px solid ${photos[item.id] ? T.green : T.cardBorder}`, background: photos[item.id] ? `${T.green}15` : "transparent", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
                  {photos[item.id] ? <Check size={12} color={T.green} /> : <Camera size={12} color={T.textMuted} />}
                </button>
              )}
            </div>
          ))}
        </div>
      ))}

      {/* Supply check section */}
      <div style={{ margin: "0 16px 12px" }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.amber, marginBottom: 6, paddingBottom: 4, borderBottom: `1px solid ${T.cardBorder}` }}>
          SUPPLY CHECK
        </div>
        {supplyItems.map((item) => {
          const status = supplies[item.id];
          const statusColors = { ok: T.green, low: T.amber, empty: T.red };
          const statusLabels = { ok: "OK ✅", low: "Low ⚠️", empty: "Empty 🔴" };
          return (
            <div key={item.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: `1px solid ${T.cardBorder}11` }}>
              <span style={{ fontSize: 12, color: T.text }}>{item.label}</span>
              <button onClick={() => cycleSupply(item.id)} style={{ padding: "4px 12px", borderRadius: 6, border: `1px solid ${status ? statusColors[status] + "44" : T.cardBorder}`, background: status ? statusColors[status] + "15" : "transparent", color: status ? statusColors[status] : T.textMuted, fontSize: 10, fontWeight: 600, cursor: "pointer", minWidth: 60 }}>
                {status ? statusLabels[status] : "Check"}
              </button>
            </div>
          );
        })}
      </div>

      {/* Issue reporting toggle */}
      <div style={{ margin: "0 16px 12px" }}>
        <button onClick={() => setShowIssueForm(!showIssueForm)} style={{ width: "100%", padding: 10, borderRadius: 8, border: `1px solid ${T.red}33`, background: `${T.red}08`, color: T.red, fontSize: 11, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
          <AlertTriangle size={14} /> Report Issue
        </button>
        {showIssueForm && (
          <div style={{ marginTop: 8, padding: 12, background: T.card, borderRadius: 8, border: `1px solid ${T.cardBorder}` }}>
            <textarea placeholder="Describe the issue..." style={{ width: "100%", minHeight: 50, padding: 8, background: T.surface, border: `1px solid ${T.cardBorder}`, borderRadius: 6, color: T.text, fontSize: 11, fontFamily: "Inter, sans-serif", resize: "vertical", marginBottom: 8, boxSizing: "border-box" }} />
            <button style={{ width: "100%", padding: 8, borderRadius: 6, border: "none", background: T.red, color: T.white, fontSize: 11, fontWeight: 600, cursor: "pointer" }}>
              Submit Issue
            </button>
          </div>
        )}
      </div>

      {/* Completion gate */}
      <div style={{ padding: "0 16px 16px" }}>
        {allComplete ? (
          <button onClick={onComplete} style={{ width: "100%", padding: 16, borderRadius: 10, background: T.moss, color: T.white, border: "none", fontSize: 15, fontWeight: 800, cursor: "pointer" }}>
            ✅ Mark as Ready
          </button>
        ) : (
          <button disabled style={{ width: "100%", padding: 16, borderRadius: 10, background: T.cardBorder, color: T.textMuted, border: "none", fontSize: 14, fontWeight: 700, cursor: "not-allowed" }}>
            🔒 Complete All Items First
          </button>
        )}
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S04 — COMPLETE CONFIRMATION [V1 PROPOSAL]
// ═════════════════════════════════════════════════════════════
function CompleteConfirmScreen({ task, onConfirm, onBack }) {
  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="Ready to Submit" onBack={onBack} />

      <div style={{ margin: "8px 16px 16px", padding: 16, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}` }}>
        {[
          { label: "Property", value: task.property, color: T.text },
          { label: "Checklist", value: "21/21 ✓", color: T.green },
          { label: "Photos", value: "6/6 ✓", color: T.green },
          { label: "Supplies", value: "All OK ✓", color: T.green },
        ].map((row, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: i < 3 ? `1px solid ${T.cardBorder}` : "none" }}>
            <span style={{ fontSize: 13, color: T.textDim }}>{row.label}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: row.color }}>{row.value}</span>
          </div>
        ))}
      </div>

      <div style={{ padding: "0 16px" }}>
        <button onClick={onConfirm} style={{ width: "100%", padding: 16, borderRadius: 10, background: T.moss, color: T.white, border: "none", fontSize: 15, fontWeight: 800, cursor: "pointer" }}>
          ✅ Mark as Ready
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S05 — SUCCESS (PROPERTY READY) [V1 PROPOSAL]
// ═════════════════════════════════════════════════════════════
function SuccessScreen({ task, onDone }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24, textAlign: "center" }}>
      <div style={{ width: 80, height: 80, borderRadius: 40, background: `${T.green}22`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16 }}>
        <Check size={42} color={T.green} />
      </div>

      <h1 style={{ fontSize: 24, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text, margin: "0 0 6px" }}>Cleaning Complete</h1>
      <p style={{ fontSize: 14, color: T.textDim, margin: "0 0 4px" }}>{task.property} is now</p>
      <p style={{ fontSize: 20, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.green, margin: "0 0 24px" }}>Ready</p>

      <div style={{ width: "100%", maxWidth: 300, padding: 14, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}`, marginBottom: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: T.textDim, marginBottom: 4 }}>
          <span>Items completed</span><span style={{ color: T.green, fontWeight: 600 }}>21/21</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: T.textDim, marginBottom: 4 }}>
          <span>Photos captured</span><span style={{ color: T.green, fontWeight: 600 }}>6/6</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: T.textDim }}>
          <span>Supplies</span><span style={{ color: T.green, fontWeight: 600 }}>All OK</span>
        </div>
      </div>

      <button onClick={onDone} style={{ width: "100%", maxWidth: 300, padding: 14, borderRadius: 10, background: T.moss, color: T.white, border: "none", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
        Done — Return to Tasks
      </button>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// TASKS SCREEN [BUILT]
// Confirmed from screenshot 22.21.05: Pending/Done tabs, task descriptions
// ═════════════════════════════════════════════════════════════
function TasksScreen() {
  const [tab, setTab] = useState("pending");
  const tasks = [
    { property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", countdown: "59h 38m 55s", status: "ACKNOWLEDGED", desc: "Pre-arrival cleaning for ICAL-36ff7d9905e0" },
    { property: "Zen Pool Villa", code: "KPG-582", date: "2026-03-28", countdown: "59h 38m 55s", status: "PENDING", desc: "Checkout cleaning for MAN-KPG-502-20260326-f360" },
    { property: "Emuna Villa", code: "KPG-594", date: "2026-04-11", countdown: "395h 38m 55s", status: "PENDING", desc: "Pre-arrival cleaning for ICAL-6240ffa80a91" },
    { property: "Emuna Villa", code: "KPG-600", date: "2026-04-17", countdown: "539h 38m 55s", status: "PENDING", desc: "Pre-arrival cleaning for ICAL-f1aad581047" },
  ];

  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="My Tasks" subtitle="Today · Wednesday, Mar 25" />

      <div style={{ display: "flex", margin: "8px 16px 16px", borderRadius: 8, overflow: "hidden", border: `1px solid ${T.cardBorder}` }}>
        {["pending", "done"].map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{ flex: 1, padding: "10px 0", border: "none", background: tab === t ? T.moss : T.card, color: tab === t ? T.white : T.textDim, fontSize: 12, fontWeight: 700, cursor: "pointer", textTransform: "capitalize" }}>
            {t}
          </button>
        ))}
      </div>

      {tab === "pending" ? (
        tasks.map((task, i) => (
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

            {/* Task description [BUILT] — shows source context */}
            <div style={{ fontSize: 10, color: T.textMuted, marginBottom: 6, fontStyle: "italic" }}>{task.desc}</div>

            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
              <Badge label="Cleaning" color={T.mossBright} />
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
                Start Cleaning →
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

      <div style={{ margin: "8px 16px 16px", padding: 16, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}`, display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ width: 48, height: 48, borderRadius: 24, background: T.moss, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <User size={22} color={T.mossBright} />
        </div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Admin User</div>
          <div style={{ fontSize: 11, color: T.textDim }}>Cleaner</div>
        </div>
      </div>

      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>ASSIGNED PROPERTIES</div>
        {["Emuna Villa · KPG-588", "Zen Pool Villa · KPG-582"].map((p, i) => (
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
export default function CleanerV1() {
  const [screen, setScreen] = useState("home");
  const [cleaningPhase, setCleaningPhase] = useState(null); // "detail" | "checklist" | "confirm" | "success"
  const [activeTask, setActiveTask] = useState(null);

  const defaultTask = { property: "Emuna Villa", code: "KPG-588", date: "2026-03-28", desc: "Pre-arrival cleaning for ICAL-36ff7d9905e0" };

  const startTask = (task) => {
    setActiveTask(task || defaultTask);
    setCleaningPhase("detail");
    setScreen("cleaning");
  };

  const handleNav = (id) => {
    if (id === "cleaning") return;
    setScreen(id);
    setCleaningPhase(null);
  };

  const renderScreen = () => {
    if (screen === "cleaning") {
      const task = activeTask || defaultTask;
      switch (cleaningPhase) {
        case "detail": return <TaskDetailScreen task={task} onStart={() => setCleaningPhase("checklist")} onBack={() => handleNav("cleaner")} />;
        case "checklist": return <ChecklistScreen task={task} onComplete={() => setCleaningPhase("confirm")} onBack={() => setCleaningPhase("detail")} />;
        case "confirm": return <CompleteConfirmScreen task={task} onConfirm={() => setCleaningPhase("success")} onBack={() => setCleaningPhase("checklist")} />;
        case "success": return <SuccessScreen task={task} onDone={() => handleNav("cleaner")} />;
        default: return <CleaningListScreen onStartTask={startTask} />;
      }
    }
    switch (screen) {
      case "home": return <HomeScreen onNavigate={handleNav} />;
      case "cleaner": return <CleaningListScreen onStartTask={startTask} />;
      case "tasks": return <TasksScreen />;
      case "settings": return <SettingsScreen />;
      default: return <HomeScreen onNavigate={handleNav} />;
    }
  };

  const activeTab = screen === "cleaning" ? "cleaner" : screen;

  return (
    <div style={{ maxWidth: 390, margin: "0 auto", background: T.bg, minHeight: "100vh", fontFamily: "Inter, sans-serif", color: T.text, position: "relative" }}>
      {renderScreen()}
      {cleaningPhase !== "success" && <BottomNav active={activeTab} onNavigate={handleNav} />}
    </div>
  );
}