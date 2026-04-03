import { useState } from "react";
import { Home, Wrench, CheckSquare, Settings, ChevronRight, ArrowLeft, MapPin, Clock, Calendar, Camera, Star, Navigation, User, AlertTriangle, Phone, Image, Check, X, Shield, Droplets, Zap, Wind, Hammer } from "lucide-react";

// ─── DESIGN TOKENS ───────────────────────────────────────────
// Maintenance uses amber/red urgency accents (priority-driven identity)
const T = {
  bg: "#0F1214",
  surface: "#1A1E22",
  card: "#1E2328",
  cardBorder: "#2A2F35",
  text: "#E8E4DE",
  textDim: "#8A8680",
  textMuted: "#5C5955",
  moss: "#334036",
  copper: "#B56E45",
  amber: "#F59E0B",
  amberDark: "#B47A0B",
  red: "#DC2626",
  redDark: "#991B1B",
  blue: "#3B82F6",
  green: "#22C55E",
  white: "#FFFFFF",
  bottomNav: "#141719",
};

// ─── BOTTOM NAV [BUILT] ─────────────────────────────────────
// Screenshots show 4 tabs: Home | Maintenance | Tasks | Settings
function BottomNav({ active, onNavigate }) {
  const tabs = [
    { id: "home", label: "Home", icon: Home },
    { id: "maintenance", label: "Maintenance", icon: Wrench },
    { id: "tasks", label: "Tasks", icon: CheckSquare },
    { id: "settings", label: "Settings", icon: Settings },
  ];
  return (
    <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, height: 56, background: T.bottomNav, display: "flex", borderTop: `1px solid ${T.cardBorder}`, zIndex: 50 }}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = active === tab.id;
        return (
          <button key={tab.id} onClick={() => onNavigate(tab.id)} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2, background: "none", border: "none", cursor: "pointer", color: isActive ? T.amber : T.textMuted }}>
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

// ─── CATEGORY ICON ───────────────────────────────────────────
function CategoryIcon({ category, size = 14 }) {
  const icons = {
    pool: Droplets,
    plumbing: Droplets,
    electrical: Zap,
    ac_heating: Wind,
    furniture: Hammer,
    general: Wrench,
  };
  const Icon = icons[category] || Wrench;
  return <Icon size={size} />;
}

// ═════════════════════════════════════════════════════════════
// S00 — HOME SCREEN [BUILT]
// Confirmed from screenshot 22.33.20: Empty state (all zeros)
// ═════════════════════════════════════════════════════════════
function HomeScreen({ onNavigate, hasJobs }) {
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
        <Badge label="Maintenance" color={T.amber} />
      </div>

      {/* MY STATUS [BUILT] */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>MY STATUS</div>
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { label: "Open", value: hasJobs ? 4 : 0, icon: "📋", color: T.amber },
            { label: "Overdue", value: 0, icon: "●", color: T.green },
            { label: "Today", value: hasJobs ? 2 : 0, icon: "📅", color: T.blue },
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

      {/* WORK [BUILT] */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>WORK</div>
        <button onClick={() => onNavigate("maintenance")} style={{ width: "100%", background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 12, padding: "14px 16px", display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: `${T.amber}22`, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Wrench size={18} color={T.amber} />
          </div>
          <div style={{ flex: 1, textAlign: "left" }}>
            <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Go to Maintenance</div>
            <div style={{ fontSize: 11, color: T.textDim }}>{hasJobs ? "4 open issues" : "No open tasks"}</div>
          </div>
          <ChevronRight size={18} color={T.textMuted} />
        </button>
      </div>

      {/* NEXT UP — only shown when there are jobs [INFERRED] */}
      {hasJobs && (
        <div style={{ padding: "0 16px" }}>
          <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>NEXT UP</div>
          <div style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.red}44`, padding: 14, marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
              <div>
                <div style={{ fontSize: 9, color: T.textMuted, display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
                  <span>🔧</span> MAINTENANCE
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Pool pump failure</div>
              </div>
              <Badge label="CRITICAL" color={T.red} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textDim, marginBottom: 2 }}>
              <span>🏠</span> Villa Emuna
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <Badge label="SLA: 4m" color={T.red} />
              <button style={{ background: T.red, border: "none", borderRadius: 6, padding: "5px 10px", fontSize: 10, fontWeight: 600, color: T.white, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
                <Navigation size={12} /> Navigate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S01 — JOB QUEUE [BUILT — empty state confirmed, populated INFERRED]
// Screenshot 22.33.29: Summary strip (OPEN ISSUES / CRITICAL / TASKS)
// Empty: green checkmark + "No open issues"
// ═════════════════════════════════════════════════════════════
function JobQueueScreen({ onSelectJob, showPopulated }) {
  const jobs = [
    { id: 1, title: "Pool pump failure", property: "Villa Emuna", category: "pool", severity: "CRITICAL", sla: "4m remaining", reported: "12:34 today", status: "new", priorityColor: T.red },
    { id: 2, title: "AC not cooling", property: "KPG Residence", category: "ac_heating", severity: "HIGH", reported: "2h ago", status: "new", priorityColor: T.amber },
    { id: 3, title: "Leaking faucet", property: "Baan Suan", category: "plumbing", severity: "MEDIUM", reported: "45m ago", status: "new", priorityColor: T.blue },
    { id: 4, title: "Replace ceiling fan", property: "Baan Suan", category: "electrical", severity: "MEDIUM", reported: "Yesterday", status: "in_progress", elapsed: "1h 20m", priorityColor: T.moss },
  ];

  return (
    <div style={{ paddingBottom: 72 }}>
      <div style={{ padding: "12px 16px 0", fontSize: 10, color: T.textMuted, fontFamily: "Inter, sans-serif" }}>
        Home &nbsp;›&nbsp; Operations &nbsp;›&nbsp; Maintenance
      </div>

      <ScreenHeader title="Maintenance" />

      <div style={{ padding: "0 16px 4px", fontSize: 10, fontWeight: 600, fontFamily: "Manrope, sans-serif", color: T.textMuted, textTransform: "uppercase" }}>
        WEDNESDAY, MARCH 25
      </div>

      {/* Summary strip [BUILT] — OPEN ISSUES / CRITICAL / TASKS */}
      <div style={{ display: "flex", gap: 8, padding: "8px 16px 16px" }}>
        {[
          { label: "OPEN ISSUES", value: showPopulated ? "4" : "0", color: T.amber },
          { label: "CRITICAL", value: showPopulated ? "1" : "0", color: T.red },
          { label: "TASKS", value: showPopulated ? "2" : "0", color: T.blue },
        ].map((s) => (
          <div key={s.label} style={{ flex: 1, background: T.card, borderRadius: 10, padding: "8px 10px", border: `1px solid ${T.cardBorder}` }}>
            <div style={{ fontSize: 8, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 2 }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      {!showPopulated ? (
        /* Empty state [BUILT] — green checkmark + "No open issues" */
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 60 }}>
          <div style={{ width: 48, height: 48, borderRadius: 8, background: `${T.green}22`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 12 }}>
            <Check size={28} color={T.green} />
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>No open issues</div>
        </div>
      ) : (
        <>
          {/* CRITICAL section [INFERRED] */}
          <div style={{ padding: "0 16px 8px", fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.red }}>CRITICAL</div>
          {jobs.filter(j => j.severity === "CRITICAL").map((job) => (
            <div key={job.id} onClick={() => onSelectJob(job)} style={{ margin: "0 16px 10px", background: T.card, borderRadius: 12, border: `1px solid ${T.red}44`, padding: 14, cursor: "pointer" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                <div style={{ fontSize: 15, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>{job.title}</div>
                <Badge label="CRITICAL" color={T.red} />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textDim, marginBottom: 4 }}>
                <MapPin size={11} /> {job.property}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: T.red }}>
                  <AlertTriangle size={10} /> SLA: {job.sla}
                </div>
                <Badge label={job.category} color={T.textDim} />
              </div>
              <button style={{ width: "100%", padding: "10px 0", borderRadius: 8, border: "none", background: T.red, color: T.white, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                Start Job
              </button>
            </div>
          ))}

          {/* OPEN section [INFERRED] */}
          <div style={{ padding: "8px 16px 8px", fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.amber }}>OPEN</div>
          {jobs.filter(j => j.status === "new" && j.severity !== "CRITICAL").map((job) => (
            <div key={job.id} onClick={() => onSelectJob(job)} style={{ margin: "0 16px 10px", background: T.card, borderRadius: 12, border: `1px solid ${job.priorityColor}33`, padding: 14, cursor: "pointer" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                <div style={{ fontSize: 15, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>{job.title}</div>
                <Badge label={job.severity} color={job.priorityColor} />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textDim, marginBottom: 4 }}>
                <MapPin size={11} /> {job.property}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <span style={{ fontSize: 10, color: T.textDim }}>🔧 Reported {job.reported}</span>
                <Badge label={job.category} color={T.textDim} />
              </div>
              <button style={{ width: "100%", padding: "10px 0", borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                Acknowledge
              </button>
            </div>
          ))}

          {/* IN PROGRESS section [INFERRED] */}
          <div style={{ padding: "8px 16px 8px", fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.moss }}>IN PROGRESS</div>
          {jobs.filter(j => j.status === "in_progress").map((job) => (
            <div key={job.id} onClick={() => onSelectJob(job)} style={{ margin: "0 16px 10px", background: T.card, borderRadius: 12, border: `1px solid ${T.moss}44`, padding: 14, cursor: "pointer" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                <div style={{ fontSize: 15, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>{job.title}</div>
                <Badge label="In Progress" color={T.moss} />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textDim, marginBottom: 4 }}>
                <MapPin size={11} /> {job.property}
              </div>
              <div style={{ fontSize: 10, color: T.textDim, marginBottom: 10 }}>In progress · {job.elapsed}</div>
              <button style={{ width: "100%", padding: "10px 0", borderRadius: 8, border: "none", background: T.moss, color: T.white, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                Resume →
              </button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S02 — JOB DETAIL [INFERRED]
// Full issue context before starting work
// ═════════════════════════════════════════════════════════════
function JobDetailScreen({ job, onStart, onBack }) {
  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title={job.title} onBack={onBack} />

      {/* Priority banner */}
      <div style={{ margin: "4px 16px 12px", padding: "10px 14px", borderRadius: 10, background: `${job.priorityColor}15`, border: `1px solid ${job.priorityColor}44`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <AlertTriangle size={14} color={job.priorityColor} />
          <span style={{ fontSize: 12, fontWeight: 700, color: job.priorityColor }}>{job.severity}</span>
        </div>
        {job.sla && <span style={{ fontSize: 11, fontWeight: 600, color: job.priorityColor }}>SLA: {job.sla}</span>}
      </div>

      {/* Info block */}
      <div style={{ margin: "0 16px 12px", padding: 14, background: T.card, borderRadius: 12, border: `1px solid ${T.cardBorder}` }}>
        {[
          { label: "Property", value: job.property },
          { label: "Category", value: job.category, capitalize: true },
          { label: "Severity", value: job.severity },
          { label: "Reported", value: job.reported },
          { label: "Reporter", value: "Cleaner" },
        ].map((row, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: i < 4 ? `1px solid ${T.cardBorder}` : "none" }}>
            <span style={{ fontSize: 11, color: T.textDim }}>{row.label}</span>
            <span style={{ fontSize: 11, fontWeight: 600, color: T.text, textTransform: row.capitalize ? "capitalize" : "none" }}>{row.value}</span>
          </div>
        ))}
      </div>

      {/* Description */}
      <div style={{ margin: "0 16px 12px", padding: 12, background: T.surface, borderRadius: 10, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 6 }}>DESCRIPTION</div>
        <p style={{ fontSize: 12, color: T.text, margin: 0, lineHeight: 1.5 }}>
          "Pool pump making loud grinding noise, water not circulating properly. Noticed during morning check."
        </p>
      </div>

      {/* Before photos */}
      <div style={{ margin: "0 16px 12px" }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 6 }}>BEFORE PHOTOS</div>
        <div style={{ display: "flex", gap: 8 }}>
          {[1, 2].map((n) => (
            <div key={n} style={{ width: 80, height: 80, borderRadius: 8, background: T.card, border: `1px solid ${T.cardBorder}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Image size={20} color={T.textMuted} />
            </div>
          ))}
        </div>
        <div style={{ fontSize: 10, color: T.textMuted, marginTop: 4 }}>Tap to zoom</div>
      </div>

      {/* Property access */}
      <div style={{ margin: "0 16px 12px", padding: 12, background: T.card, borderRadius: 10, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>PROPERTY ACCESS</div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: 14, fontWeight: 700, color: T.text }}>
          🔑 Access Code: <span style={{ letterSpacing: "0.1em" }}>4521</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button style={{ flex: 1, padding: 10, borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.text, fontSize: 11, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
            <Navigation size={14} /> Navigate
          </button>
          <button style={{ flex: 1, padding: 10, borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.text, fontSize: 11, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
            <Phone size={14} /> Call Manager
          </button>
        </div>
      </div>

      <div style={{ padding: "0 16px" }}>
        <button onClick={onStart} style={{ width: "100%", padding: 14, borderRadius: 10, background: job.severity === "CRITICAL" ? T.red : T.amber, color: T.white, border: "none", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
          {job.status === "in_progress" ? "Resume Job →" : "Start Job 🔧"}
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S03 — ACTIVE WORK [INFERRED + V1 PROPOSAL]
// Freeform workspace: notes + after photos + blocked flow
// ═════════════════════════════════════════════════════════════
function ActiveWorkScreen({ job, onComplete, onBlocked, onBack }) {
  const [notes, setNotes] = useState("");
  const [afterPhotos, setAfterPhotos] = useState(0);
  const [showBlockedForm, setShowBlockedForm] = useState(false);

  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title={job.title} subtitle="Active Work" onBack={onBack} />

      {/* Issue summary (compact) */}
      <div style={{ margin: "4px 16px 12px", padding: 10, background: T.surface, borderRadius: 8, border: `1px solid ${T.cardBorder}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textDim }}>
          <CategoryIcon category={job.category} size={12} />
          <span style={{ textTransform: "capitalize" }}>{job.category}</span> · {job.property}
        </div>
      </div>

      {/* SLA status */}
      <div style={{ margin: "0 16px 12px", padding: "8px 12px", borderRadius: 8, background: `${job.priorityColor}15`, border: `1px solid ${job.priorityColor}33`, display: "flex", alignItems: "center", gap: 6 }}>
        {job.severity === "CRITICAL" ? (
          <>
            <AlertTriangle size={12} color={T.red} />
            <span style={{ fontSize: 11, fontWeight: 700, color: T.red }}>CRITICAL — SLA: 2m remaining</span>
          </>
        ) : (
          <>
            <Wrench size={12} color={T.amber} />
            <span style={{ fontSize: 11, fontWeight: 600, color: T.amber }}>Working · 45m elapsed</span>
          </>
        )}
      </div>

      {/* Before evidence (read-only) */}
      <div style={{ margin: "0 16px 12px" }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 6 }}>BEFORE EVIDENCE</div>
        <div style={{ display: "flex", gap: 6 }}>
          {[1, 2].map((n) => (
            <div key={n} style={{ width: 60, height: 60, borderRadius: 8, background: T.card, border: `1px solid ${T.cardBorder}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Image size={16} color={T.textMuted} />
            </div>
          ))}
        </div>
      </div>

      {/* Work log (freeform notes) */}
      <div style={{ margin: "0 16px 12px" }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 6 }}>WORK LOG</div>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="What did you do? What was the issue?"
          style={{ width: "100%", minHeight: 80, padding: 10, background: T.card, border: `1px solid ${T.cardBorder}`, borderRadius: 8, color: T.text, fontSize: 12, fontFamily: "Inter, sans-serif", resize: "vertical", boxSizing: "border-box" }}
        />
      </div>

      {/* After evidence (capture) */}
      <div style={{ margin: "0 16px 12px" }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 6 }}>AFTER EVIDENCE</div>
        <button onClick={() => setAfterPhotos(p => p + 1)} style={{ width: "100%", padding: 12, borderRadius: 8, border: `2px dashed ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6, marginBottom: 6 }}>
          <Camera size={16} /> Take After Photo
        </button>
        {afterPhotos > 0 && (
          <div style={{ display: "flex", gap: 6 }}>
            {Array.from({ length: afterPhotos }).map((_, i) => (
              <div key={i} style={{ width: 60, height: 60, borderRadius: 8, background: `${T.green}15`, border: `1px solid ${T.green}44`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Check size={16} color={T.green} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Completion */}
      <div style={{ margin: "0 16px 12px" }}>
        <button onClick={onComplete} disabled={!notes} style={{ width: "100%", padding: 14, borderRadius: 10, background: notes ? T.green : T.cardBorder, color: notes ? T.white : T.textMuted, border: "none", fontSize: 14, fontWeight: 700, cursor: notes ? "pointer" : "not-allowed" }}>
          ✅ Complete & Resolve
        </button>
      </div>

      {/* Cannot Complete [V1 PROPOSAL] */}
      <div style={{ margin: "0 16px 16px" }}>
        <button onClick={() => setShowBlockedForm(!showBlockedForm)} style={{ width: "100%", padding: 12, borderRadius: 10, border: `1px solid ${T.amber}44`, background: `${T.amber}08`, color: T.amber, fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
          <AlertTriangle size={14} /> Cannot Complete
        </button>

        {showBlockedForm && (
          <div style={{ marginTop: 8, padding: 14, background: T.card, borderRadius: 10, border: `1px solid ${T.amber}33` }}>
            <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>REASON</div>
            {["Parts needed", "Need specialist", "Access blocked", "Waiting for guest to vacate", "Other"].map((reason) => (
              <button key={reason} style={{ display: "block", width: "100%", padding: "8px 12px", marginBottom: 4, borderRadius: 6, border: `1px solid ${T.cardBorder}`, background: T.surface, color: T.text, fontSize: 11, textAlign: "left", cursor: "pointer" }}>
                {reason}
              </button>
            ))}
            <textarea placeholder="Additional notes..." style={{ width: "100%", minHeight: 50, padding: 8, background: T.surface, border: `1px solid ${T.cardBorder}`, borderRadius: 6, color: T.text, fontSize: 11, fontFamily: "Inter, sans-serif", resize: "vertical", marginTop: 8, boxSizing: "border-box" }} />
            <button onClick={onBlocked} style={{ width: "100%", padding: 10, marginTop: 8, borderRadius: 8, border: "none", background: T.amber, color: T.white, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
              Submit Blocked
            </button>
          </div>
        )}
      </div>

      {/* Call manager — always available */}
      <div style={{ padding: "0 16px" }}>
        <button style={{ width: "100%", padding: 10, borderRadius: 8, border: `1px solid ${T.cardBorder}`, background: "transparent", color: T.textDim, fontSize: 11, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
          <Phone size={14} /> Call Manager
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S04 — BLOCKED CONFIRMATION [V1 PROPOSAL]
// ═════════════════════════════════════════════════════════════
function BlockedScreen({ job, onDone }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24, textAlign: "center" }}>
      <div style={{ width: 72, height: 72, borderRadius: 36, background: `${T.amber}22`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16 }}>
        <AlertTriangle size={36} color={T.amber} />
      </div>

      <h1 style={{ fontSize: 20, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text, margin: "0 0 6px" }}>Job Flagged as Blocked</h1>
      <p style={{ fontSize: 13, color: T.textDim, margin: "0 0 4px" }}>"{job.title}"</p>
      <p style={{ fontSize: 12, color: T.textDim, margin: "0 0 16px" }}>{job.property}</p>

      <div style={{ padding: "8px 16px", background: `${T.amber}15`, borderRadius: 8, border: `1px solid ${T.amber}33`, marginBottom: 16 }}>
        <span style={{ fontSize: 11, color: T.amber, fontWeight: 600 }}>Reason: Parts needed</span>
      </div>

      <p style={{ fontSize: 12, color: T.textDim, margin: "0 0 24px" }}>Your manager has been notified.</p>

      <button onClick={onDone} style={{ width: "100%", maxWidth: 300, padding: 14, borderRadius: 10, background: T.amber, color: T.white, border: "none", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
        Done — Return to Jobs
      </button>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// S05 — COMPLETE CONFIRMATION [INFERRED]
// ═════════════════════════════════════════════════════════════
function CompleteScreen({ job, onDone }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24, textAlign: "center" }}>
      <div style={{ width: 72, height: 72, borderRadius: 36, background: `${T.green}22`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16 }}>
        <Check size={36} color={T.green} />
      </div>

      <h1 style={{ fontSize: 22, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text, margin: "0 0 6px" }}>Issue Resolved</h1>
      <p style={{ fontSize: 13, color: T.textDim, margin: "0 0 4px" }}>"{job.title}"</p>
      <p style={{ fontSize: 12, color: T.textDim, margin: "0 0 16px" }}>{job.property}</p>

      <div style={{ width: "100%", maxWidth: 260, padding: 12, background: T.card, borderRadius: 10, border: `1px solid ${T.cardBorder}`, marginBottom: 24 }}>
        <div style={{ fontSize: 11, color: T.textDim, marginBottom: 2 }}>Time on job</div>
        <div style={{ fontSize: 20, fontWeight: 800, fontFamily: "Manrope, sans-serif", color: T.text }}>1h 20m</div>
      </div>

      <button onClick={onDone} style={{ width: "100%", maxWidth: 300, padding: 14, borderRadius: 10, background: T.green, color: T.white, border: "none", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
        Done — Return to Jobs
      </button>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// TASKS SCREEN [BUILT — empty state confirmed]
// Screenshot 22.33.38: "All clear!" with party emoji
// ═════════════════════════════════════════════════════════════
function TasksScreen() {
  const [tab, setTab] = useState("pending");

  return (
    <div style={{ paddingBottom: 72 }}>
      <ScreenHeader title="My Tasks" subtitle="Today · Wednesday, Mar 25" />

      <div style={{ display: "flex", margin: "8px 16px 16px", borderRadius: 8, overflow: "hidden", border: `1px solid ${T.cardBorder}` }}>
        {["pending", "done"].map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{ flex: 1, padding: "10px 0", border: "none", background: tab === t ? T.amber : T.card, color: tab === t ? T.white : T.textDim, fontSize: 12, fontWeight: 700, cursor: "pointer", textTransform: "capitalize" }}>
            {t}
          </button>
        ))}
      </div>

      {/* Empty state [BUILT] */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 48 }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>🎉</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: T.text }}>All clear!</div>
        <div style={{ fontSize: 12, color: T.textDim, marginTop: 4 }}>No pending tasks assigned to you right now.</div>
      </div>
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
        <div style={{ width: 48, height: 48, borderRadius: 24, background: `${T.amber}22`, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <User size={22} color={T.amber} />
        </div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "Manrope, sans-serif", color: T.text }}>Admin User</div>
          <div style={{ fontSize: 11, color: T.textDim }}>Maintenance Staff</div>
        </div>
      </div>

      {/* Specialty chips [V1 PROPOSAL — unique to maintenance] */}
      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>SPECIALTY</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {["Plumbing", "Electrical", "General"].map((spec) => (
            <span key={spec} style={{ padding: "6px 12px", borderRadius: 16, background: `${T.amber}15`, border: `1px solid ${T.amber}33`, color: T.amber, fontSize: 10, fontWeight: 600 }}>
              {spec}
            </span>
          ))}
        </div>
      </div>

      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>ASSIGNED PROPERTIES</div>
        {["Villa Emuna", "KPG Residence", "Baan Suan"].map((p, i) => (
          <div key={i} style={{ padding: "10px 12px", background: T.card, borderRadius: 8, border: `1px solid ${T.cardBorder}`, marginBottom: 6, fontSize: 12, color: T.text, display: "flex", alignItems: "center", gap: 8 }}>
            <MapPin size={14} color={T.amber} /> {p}
          </div>
        ))}
      </div>

      <div style={{ padding: "0 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, fontWeight: 700, fontFamily: "Manrope, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em", color: T.textMuted, marginBottom: 8 }}>NOTIFICATIONS</div>
        {[
          { label: "LINE notifications", enabled: true },
          { label: "Phone notifications", enabled: true },
        ].map((n, i) => (
          <div key={i} style={{ padding: "10px 12px", background: T.card, borderRadius: 8, border: `1px solid ${T.cardBorder}`, marginBottom: 6, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: T.text }}>{n.label}</span>
            <div style={{ width: 36, height: 20, borderRadius: 10, background: n.enabled ? T.amber : T.cardBorder, position: "relative", cursor: "pointer" }}>
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
export default function MaintenanceV1() {
  const [screen, setScreen] = useState("home");
  const [workPhase, setWorkPhase] = useState(null);
  const [activeJob, setActiveJob] = useState(null);
  const [showPopulated, setShowPopulated] = useState(true); // toggle to show populated vs empty

  const defaultJob = { id: 1, title: "Pool pump failure", property: "Villa Emuna", category: "pool", severity: "CRITICAL", sla: "4m remaining", reported: "12:34 today", status: "new", priorityColor: T.red };

  const selectJob = (job) => {
    setActiveJob(job);
    setWorkPhase("detail");
    setScreen("work");
  };

  const handleNav = (id) => {
    if (id === "work") return;
    setScreen(id);
    setWorkPhase(null);
  };

  const renderScreen = () => {
    if (screen === "work") {
      const job = activeJob || defaultJob;
      switch (workPhase) {
        case "detail": return <JobDetailScreen job={job} onStart={() => setWorkPhase("active")} onBack={() => handleNav("maintenance")} />;
        case "active": return <ActiveWorkScreen job={job} onComplete={() => setWorkPhase("complete")} onBlocked={() => setWorkPhase("blocked")} onBack={() => setWorkPhase("detail")} />;
        case "blocked": return <BlockedScreen job={job} onDone={() => handleNav("maintenance")} />;
        case "complete": return <CompleteScreen job={job} onDone={() => handleNav("maintenance")} />;
        default: return <JobQueueScreen onSelectJob={selectJob} showPopulated={showPopulated} />;
      }
    }
    switch (screen) {
      case "home": return <HomeScreen onNavigate={handleNav} hasJobs={showPopulated} />;
      case "maintenance": return <JobQueueScreen onSelectJob={selectJob} showPopulated={showPopulated} />;
      case "tasks": return <TasksScreen />;
      case "settings": return <SettingsScreen />;
      default: return <HomeScreen onNavigate={handleNav} hasJobs={showPopulated} />;
    }
  };

  const activeTab = screen === "work" ? "maintenance" : screen;

  return (
    <div style={{ maxWidth: 390, margin: "0 auto", background: T.bg, minHeight: "100vh", fontFamily: "Inter, sans-serif", color: T.text, position: "relative" }}>
      {renderScreen()}
      {(workPhase !== "blocked" && workPhase !== "complete") && <BottomNav active={activeTab} onNavigate={handleNav} />}
    </div>
  );
}