"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import CompletedCoursesInput from "../CompletedCoursesInput";
import TranscriptUpload from "../TranscriptUpload";
import ProgramSelectInput from "../ProgramSelectInput";
import PlanEditor, { PlanTerm } from "../PlanEditor";

type ProgramInfo = {
  school: string;
  degree_level: string;
  major_name: string;
  catalog_year: string;
  display_name: string;
  tracks: string[];
};

type CoreCurriculumBlock = {
  title: string;
  total_courses: number | null;
  courses: string[];
  is_elective: boolean;
  completed: string[];
  needed: number;
  available_courses: string[];
};

type CourseStatus = {
  code: string;
  status: "completed" | "in_progress" | "planned" | "not_scheduled";
};

type ProgramSummary = {
  name: string;
  type: "major" | "minor";
  required: CourseStatus[];
  electives_needed: number;
  electives_completed: string[];
  electives_planned: string[];
  science_completed: string[];
  stats_completed: string[];
};

type PlanResponse = {
  terms: PlanTerm[];
  remaining_courses: string[];
  warnings: string[];
  completion_term: string | null;
  completed_credits: number;
  total_credits: number;
  core_curriculum_name?: string;
  core_curriculum_blocks: CoreCurriculumBlock[];
  completed_course_map?: Record<string, string>;
  programs_summary?: ProgramSummary[];
};

const ALL_SEASONS = ["Spring", "Summer", "Fall", "Winter"];
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://api.ruplanner.com";

function safeRemoveStorage(key: string) {
  try { localStorage.removeItem(key); } catch {}
}

function getSeasonBtnClass(season: string, active: boolean) {
  if (!active) return "season-btn";
  if (season === "Fall") return "season-btn active-fall";
  if (season === "Spring") return "season-btn active-spring";
  if (season === "Summer") return "season-btn active-summer";
  return "season-btn active-winter";
}

function getUserInitials(email: string | null): string {
  if (!email) return "?";
  return email.charAt(0).toUpperCase();
}

function UserMenu({ email, onSignOut }: { email: string | null; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <button
        className="topbar-avatar"
        onClick={() => setOpen((v) => !v)}
        title={email ?? ""}
      >
        {getUserInitials(email)}
      </button>
      {open && (
        <>
          <div
            style={{ position: "fixed", inset: 0, zIndex: 199 }}
            onClick={() => setOpen(false)}
          />
          <div style={{
            position: "absolute", top: "calc(100% + 8px)", right: 0,
            background: "var(--surface)", border: "1.5px solid var(--border-2)",
            borderRadius: 12, boxShadow: "var(--shadow-lg)",
            minWidth: 200, zIndex: 200, overflow: "hidden",
          }}>
            <div style={{
              padding: "12px 16px 10px",
              borderBottom: "1px solid var(--border)",
            }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text)" }}>
                {email ?? ""}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>
                Signed in
              </div>
            </div>
            <button
              onClick={() => { setOpen(false); onSignOut(); }}
              style={{
                width: "100%", padding: "10px 16px", background: "none", border: "none",
                textAlign: "left", fontSize: 13, color: "var(--ru-red)", cursor: "pointer",
                fontFamily: "inherit", fontWeight: 500,
                transition: "background var(--transition-fast)",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--ru-red-light)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
            >
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function blockStatusIcon(block: CoreCurriculumBlock): { icon: string; color: string } {
  if (!block.total_courses) return { icon: "○", color: "var(--text-3)" };
  if (block.needed === 0) return { icon: "✓", color: "#22c55e" };
  if (block.completed.length > 0) return { icon: "◑", color: "#f59e0b" };
  return { icon: "○", color: "var(--text-3)" };
}

function blockShortTitle(title: string): string {
  // Strip leading "R# : " prefix and keep the rest
  return title.replace(/^R\d+\s*:\s*/, "");
}

function CollapsiblePanel({ title, badge, defaultOpen = false, children }: {
  title: string;
  badge?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{
      background: "var(--surface)",
      border: "1.5px solid var(--border-2)",
      borderRadius: 14,
      marginBottom: 16,
      overflow: "hidden",
    }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 20px",
          background: "none",
          border: "none",
          cursor: "pointer",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}>{title}</span>
          {badge && (
            <span style={{ fontSize: 11, background: "var(--border-2)", color: "var(--text-3)", borderRadius: 99, padding: "1px 8px", fontWeight: 600 }}>
              {badge}
            </span>
          )}
        </div>
        <span style={{ fontSize: 11, color: "var(--text-3)", transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}>▼</span>
      </button>
      {open && (
        <div style={{ padding: "0 20px 16px" }}>
          {children}
        </div>
      )}
    </div>
  );
}

function CoreBlockRow({ block }: { block: CoreCurriculumBlock }) {
  const [expanded, setExpanded] = useState(false);
  const short = blockShortTitle(block.title);
  const isComplete = block.needed === 0;
  const isPartial = !isComplete && block.completed.length > 0;
  const isOpenBlock = !isComplete && block.courses.length === 0;

  const badgeStyle = isComplete
    ? { background: "rgba(34,197,94,0.12)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.2)" }
    : isPartial
    ? { background: "rgba(245,158,11,0.12)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.2)" }
    : { background: "var(--surface-2)", color: "var(--text-3)", border: "1px solid var(--border-2)" };

  const badgeText = isComplete ? "Complete" : isPartial ? "Partial" : "Not Started";

  return (
    <div style={{
      background: isComplete ? "rgba(34,197,94,0.03)" : "var(--surface-2)",
      border: `1px solid ${isComplete ? "rgba(34,197,94,0.15)" : "var(--border)"}`,
      borderRadius: 10,
      overflow: "hidden",
      transition: "border-color 150ms",
    }}>
      <button
        onClick={() => !isComplete && setExpanded((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          background: "none",
          border: "none",
          cursor: isComplete ? "default" : "pointer",
          gap: 10,
          textAlign: "left",
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", flex: 1 }}>{short}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 99, letterSpacing: "0.04em", textTransform: "uppercase" as const, ...badgeStyle }}>
            {badgeText}
          </span>
          {!isComplete && (
            <span style={{ fontSize: 10, color: "var(--text-3)", display: "inline-block", transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}>▼</span>
          )}
        </div>
      </button>

      {!isComplete && expanded && (
        <div style={{ padding: "0 14px 12px" }}>
          {block.completed.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
              {block.completed.map((code) => (
                <span key={code} style={{ fontSize: 11, fontWeight: 600, padding: "2px 7px", borderRadius: 4, background: "rgba(34,197,94,0.12)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.2)" }}>
                  {code}
                </span>
              ))}
            </div>
          )}
          <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 8 }}>
            {isOpenBlock
              ? `Need ${block.needed} more — select from Degree Navigator`
              : `Need ${block.needed} more course${block.needed !== 1 ? "s" : ""}`}
          </div>
          {!isOpenBlock && block.available_courses.length > 0 && (
            <>
              <div style={{ fontSize: 10, color: "var(--text-3)", marginBottom: 5, textTransform: "uppercase" as const, letterSpacing: "0.05em", fontWeight: 600 }}>
                Courses that satisfy this
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {block.available_courses.slice(0, 30).map((code) => (
                  <span key={code} style={{ fontSize: 11, fontWeight: 500, padding: "2px 7px", borderRadius: 4, background: "var(--surface-3)", color: "var(--text-2)", border: "1px solid var(--border-2)" }}>
                    {code}
                  </span>
                ))}
                {block.available_courses.length > 30 && (
                  <span style={{ fontSize: 11, color: "var(--text-3)", alignSelf: "center" }}>
                    +{block.available_courses.length - 30} more
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {isComplete && block.completed.length > 0 && (
        <div style={{ padding: "0 14px 10px", display: "flex", flexWrap: "wrap", gap: 4 }}>
          {block.completed.map((code) => (
            <span key={code} style={{ fontSize: 11, fontWeight: 600, padding: "2px 7px", borderRadius: 4, background: "rgba(34,197,94,0.12)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.2)" }}>
              {code}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function CoreCurriculumPanel({ name, blocks }: { name: string; blocks: CoreCurriculumBlock[] }) {
  if (!blocks.length) return null;
  const doneCount = blocks.filter((b) => b.needed === 0).length;
  const pct = Math.round((doneCount / blocks.length) * 100);
  const badge = `${doneCount}/${blocks.length} complete`;
  return (
    <CollapsiblePanel title={name} badge={badge}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-3)", marginBottom: 5 }}>
          <span>Overall completion</span>
          <span>{pct}%</span>
        </div>
        <div style={{ height: 4, background: "var(--surface-3)", borderRadius: 99, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`, background: "var(--ru-red)", borderRadius: 99, transition: "width 0.4s cubic-bezier(0.4,0,0.2,1)" }} />
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {blocks.map((blk, i) => (
          <CoreBlockRow key={i} block={blk} />
        ))}
      </div>
    </CollapsiblePanel>
  );
}

function CourseChip({ code, status }: { code: string; status: "completed" | "in_progress" | "planned" | "not_scheduled" }) {
  const style =
    status === "completed"     ? { background: "#dcfce7", color: "#166534", borderColor: "#bbf7d0" } :
    status === "in_progress"   ? { background: "#fef3c7", color: "#92400e", borderColor: "#fde68a" } :
    status === "planned"       ? { background: "var(--surface-2,#f3f4f6)", color: "var(--text-2)", borderColor: "var(--border-2)" } :
                                 { background: "#fff1f2", color: "#9f1239", borderColor: "#fecdd3" };
  return <span className="plan-completed-chip" style={style}>{code}</span>;
}

function ReqRow({ label, items }: { label: string; items: CourseStatus[] }) {
  if (!items.length) return null;
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
      <span style={{ fontSize: 10, fontWeight: 600, color: "var(--text-3)", minWidth: 120, flexShrink: 0, textTransform: "uppercase", letterSpacing: "0.05em", paddingTop: 3 }}>
        {label}
      </span>
      <div className="plan-completed-chips" style={{ margin: 0, flexWrap: "wrap" }}>
        {items.map((cs) => <CourseChip key={cs.code} code={cs.code} status={cs.status} />)}
      </div>
    </div>
  );
}

function ProgramRequirementsPanel({ prog }: { prog: ProgramSummary }) {
  const doneCount = prog.required.filter((c) => c.status === "completed" || c.status === "in_progress").length;
  const totalReq = prog.required.length;
  const elecDone = prog.electives_completed.length;
  const elecNeeded = prog.electives_needed;
  const allDone = doneCount === totalReq && elecDone >= elecNeeded;
  const badge = allDone ? "Complete" : `${doneCount}/${totalReq} req · ${elecDone}/${elecNeeded} elec`;

  const typeLabel = prog.type === "major" ? "Major" : prog.type === "minor" ? "Minor" : "Concentration";

  return (
    <CollapsiblePanel title={`${typeLabel}: ${prog.name}`} badge={badge} defaultOpen>
      <div style={{ marginBottom: 4 }}>
        <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 6 }}>
          <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#dcfce7", border: "1px solid #bbf7d0", marginRight: 4 }} />completed&nbsp;
          <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#fef3c7", border: "1px solid #fde68a", marginRight: 4, marginLeft: 8 }} />in progress&nbsp;
          <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "var(--surface-2,#f3f4f6)", border: "1px solid var(--border-2)", marginRight: 4, marginLeft: 8 }} />planned&nbsp;
          <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#fff1f2", border: "1px solid #fecdd3", marginRight: 4, marginLeft: 8 }} />not scheduled
        </div>
      </div>

      <ReqRow label="Required" items={prog.required} />

      {prog.science_completed.length > 0 && (
        <ReqRow label="Science Req" items={prog.science_completed.map((c) => ({ code: c, status: "completed" as const }))} />
      )}
      {prog.stats_completed.length > 0 && (
        <ReqRow label="Stats Req" items={prog.stats_completed.map((c) => ({ code: c, status: "completed" as const }))} />
      )}

      {elecNeeded > 0 && (
        <ReqRow
          label={`Electives (${elecDone}/${elecNeeded})`}
          items={[
            ...prog.electives_completed.map((c) => ({ code: c, status: "completed" as const })),
            ...prog.electives_planned.map((c) => ({ code: c, status: "planned" as const })),
          ]}
        />
      )}
    </CollapsiblePanel>
  );
}

export default function PlannerPage() {
  const router = useRouter();
  const [selectedMajors, setSelectedMajors] = useState<string[]>([]);
  const [selectedMinors, setSelectedMinors] = useState<string[]>([]);
  // Maps minor display_name → chosen track (only for minors that have tracks)
  const [selectedMinorTracks, setSelectedMinorTracks] = useState<Record<string, string>>({});
  const [completedCourses, setCompletedCourses] = useState<string[]>([]);
  const [inProgressCourses, setInProgressCourses] = useState<string[]>([]);
  const [startTerm, setStartTerm] = useState("Fall 2026");
  const [targetGradTerm, setTargetGradTerm] = useState("Spring 2028");
  const [maxCredits, setMaxCredits] = useState(15);
  const [preferredSeasons, setPreferredSeasons] = useState<string[]>(["Spring", "Fall"]);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [planKey, setPlanKey] = useState(0);
  const [status, setStatus] = useState("");
  const [programs, setPrograms] = useState<ProgramInfo[]>([]);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState("");
  const [degreeFilter, setDegreeFilter] = useState<string>("bachelor");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const editedTermsRef = useRef<PlanTerm[]>([]);

  const handleTermsChange = useCallback((terms: PlanTerm[]) => {
    editedTermsRef.current = terms;
  }, []);

  useEffect(() => {
    router.prefetch("/schedules");
    async function checkAuthAndLoadPrograms() {
      try {
        const meRes = await fetch(`${apiBase}/auth/me`, { credentials: 'include' });
        if (!meRes.ok) {
          router.push("/");
          return;
        }
        const me = await meRes.json();
        setUserEmail(me.email);

        const programsRes = await fetch(`${apiBase}/programs`, { credentials: 'include' });
        if (programsRes.ok) {
          const data = await programsRes.json();
          setPrograms(data);
        }
      } catch {
        router.push("/");
      }
    }
    checkAuthAndLoadPrograms();
  }, [router]);

  const DEGREE_FILTERS = [
    { key: "bachelor", label: "Bachelor's", levels: new Set(["bachelor_ba","bachelor_bs","bachelor_bfa","bachelor_bm","bachelor_bsba","bachelor_bsla"]) },
    { key: "master",   label: "Master's",   levels: new Set(["master","master_ms","master_ma","master_mat","master_meng"]) },
  ];
  const activeFilter = DEGREE_FILTERS.find((f) => f.key === degreeFilter)!;
  const majorPrograms = programs.filter(
    (p) => p.degree_level !== "minor" && p.degree_level !== "concentration" && activeFilter.levels.has(p.degree_level)
  );
  const minorPrograms = programs.filter((p) => p.degree_level === "minor");

  function toggleSeason(season: string) {
    setPreferredSeasons((prev) =>
      prev.includes(season) ? prev.filter((s) => s !== season) : [...prev, season]
    );
  }

  async function handleSignOut() {
    safeRemoveStorage("ru_planner_token");
    safeRemoveStorage("ru_planner_email");
    try {
      await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" });
    } catch {}
    router.push("/");
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();

    if (preferredSeasons.length === 0) {
      setStatus("Select at least one semester to enroll in.");
      return;
    }

    setStatus("Generating plan…");
    setSaveStatus("");
    const payload = {
      degree_level: degreeFilter,
      majors: selectedMajors,
      minors: selectedMinors.map((m) => {
        const track = selectedMinorTracks[m];
        const prog = minorPrograms.find((p) => p.display_name === m);
        if (track && prog) {
          // "Statistics (Minor, SAS)" → "Statistics — Data Science (Minor, SAS)"
          return m.replace(prog.major_name, `${prog.major_name} — ${track}`);
        }
        return m;
      }),
      concentrations: [],
      completed_courses: [...new Set([...completedCourses, ...inProgressCourses])],
      start_term: startTerm.trim() || undefined,
      target_grad_term: targetGradTerm,
      max_credits_per_term: maxCredits,
      summer_max_credits: 12,
      winter_max_credits: 4,
      preferred_seasons: preferredSeasons,
    };

    const res = await fetch(`${apiBase}/plan`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      credentials: 'include',
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Unknown error" }));
      setStatus(`Error: ${err.detail ?? "Failed to generate plan."}`);
      return;
    }

    const data = (await res.json()) as PlanResponse;
    editedTermsRef.current = data.terms;
    setPlan(data);
    setPlanKey((k) => k + 1);
    setStatus("");
    setSidebarOpen(false);
  }

  async function handleSave() {
    if (!plan) return;

    setSaveStatus("Saving…");
    const name = `${selectedMajors[0] ?? "My"} — ${targetGradTerm}`;

    const plan_data = {
      ...plan,
      terms: editedTermsRef.current,
    };

    const res = await fetch(`${apiBase}/schedules`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, plan_data }),
      credentials: 'include',
    });

    if (res.status === 401) {
      safeRemoveStorage("ru_planner_token");
      safeRemoveStorage("ru_planner_email");
      router.push("/");
      return;
    }

    if (!res.ok) {
      setSaveStatus("Failed to save. Please try again.");
      return;
    }

    setSaveStatus("Schedule saved!");
  }

  const totalPlanCredits = plan?.terms.reduce((s, t) => s + t.total_credits, 0) ?? 0;

  return (
    <div style={{ minHeight: "100vh", background: "var(--lavender-50)" }}>
      {/* ── Topbar ── */}
      <header className="topbar">
        <div style={{ display: "flex", alignItems: "center", gap: 4, marginRight: 28 }}>
          <img src="/RUPlanner Logo.svg" alt="RU Planner" style={{ height: 36, width: "auto" }} />
        </div>
        <nav className="topbar-nav">
          <span className="topbar-nav-item active">My Planner</span>
          <Link href="/schedules" className="topbar-nav-item" prefetch>Schedules</Link>
          <Link href="/sniper" className="topbar-nav-item" prefetch>Course Sniper</Link>
        </nav>
        <div className="topbar-right">
          <button
            className="mobile-sidebar-btn"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="Plan settings"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <line x1="2" y1="4" x2="14" y2="4"/>
              <line x1="2" y1="8" x2="14" y2="8"/>
              <line x1="2" y1="12" x2="14" y2="12"/>
              <circle cx="5" cy="4" r="1.5" fill="var(--surface-2)" stroke="currentColor"/>
              <circle cx="11" cy="8" r="1.5" fill="var(--surface-2)" stroke="currentColor"/>
              <circle cx="7" cy="12" r="1.5" fill="var(--surface-2)" stroke="currentColor"/>
            </svg>
          </button>
          <UserMenu email={userEmail} onSignOut={handleSignOut} />
        </div>
      </header>

      {/* Mobile sidebar overlay */}
      <div
        className={`mobile-sidebar-overlay${sidebarOpen ? " visible" : ""}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* ── App shell ── */}
      <div className="app-shell">
        {/* Sidebar */}
        <aside className={`sidebar${sidebarOpen ? " mobile-open" : ""}`}>

          <div className="sidebar-body">
            <form className="form" onSubmit={handleSubmit}>
              <div className="sidebar-section">
                <label className="label">Degree type</label>
                <div className="degree-filter-tabs">
                  {DEGREE_FILTERS.map((f) => (
                    <button
                      key={f.key}
                      type="button"
                      className={`degree-filter-tab${degreeFilter === f.key ? " active" : ""}`}
                      onClick={() => { setDegreeFilter(f.key); setSelectedMajors([]); }}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="sidebar-section">
                <label className="label">Major(s)</label>
                <ProgramSelectInput
                  programs={majorPrograms}
                  value={selectedMajors}
                  onChange={setSelectedMajors}
                  placeholder="Search by name or school…"
                />
              </div>

              <div className="sidebar-section">
                <label className="label">
                  Minor(s) <span className="label-optional">optional</span>
                </label>
                <ProgramSelectInput
                  programs={minorPrograms}
                  value={selectedMinors}
                  onChange={(next) => {
                    setSelectedMinors(next);
                    // Remove track state for any minors that were deselected
                    setSelectedMinorTracks((prev) => {
                      const kept: Record<string, string> = {};
                      for (const m of next) if (prev[m]) kept[m] = prev[m];
                      return kept;
                    });
                  }}
                  placeholder="Search minors…"
                />
                {/* Track selector — appears per-minor when tracks exist */}
                {selectedMinors.map((minorName) => {
                  const prog = minorPrograms.find((p) => p.display_name === minorName);
                  if (!prog || !prog.tracks || prog.tracks.length === 0) return null;
                  return (
                    <div key={minorName} style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 11, color: "var(--text-3)", flexShrink: 0 }}>
                        {prog.major_name} track:
                      </span>
                      <select
                        value={selectedMinorTracks[minorName] ?? ""}
                        onChange={(e) => setSelectedMinorTracks((prev) => ({ ...prev, [minorName]: e.target.value }))}
                        style={{ fontSize: 12, padding: "3px 6px", borderRadius: 6, border: "1px solid var(--border-2)", background: "var(--surface)", color: "var(--text)", flex: 1 }}
                      >
                        <option value="">Select track…</option>
                        {prog.tracks.map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>

              <div className="sidebar-section">
                <label className="label">Completed courses</label>
                <TranscriptUpload
                  onCoursesDetected={(codes) =>
                    setCompletedCourses((prev) => [...new Set([...prev, ...codes])])
                  }
                  onInProgressDetected={(codes) =>
                    setInProgressCourses((prev) => [...new Set([...prev, ...codes])])
                  }
                />
                <CompletedCoursesInput value={completedCourses} onChange={setCompletedCourses} />
              </div>

              <div className="sidebar-section">
                <label className="label" htmlFor="startTerm">Starting term</label>
                <div className="start-term-row">
                  {["Fall", "Spring", "Summer", "Winter"].map((s) => (
                    <button
                      key={s}
                      type="button"
                      className={`season-btn${startTerm.startsWith(s) ? ` active-${s.toLowerCase()}` : ""}`}
                      onClick={() =>
                        setStartTerm((prev) => {
                          const year = prev.split(" ")[1] ?? "2026";
                          return `${s} ${year}`;
                        })
                      }
                    >
                      {s}
                    </button>
                  ))}
                  <input
                    id="startTerm"
                    className="input start-term-year"
                    value={startTerm.split(" ")[1] ?? ""}
                    onChange={(e) =>
                      setStartTerm((prev) => `${prev.split(" ")[0]} ${e.target.value}`)
                    }
                    placeholder="2026"
                    maxLength={4}
                  />
                </div>
              </div>

              <div className="sidebar-section">
                <label className="label" htmlFor="targetGradTerm">Target graduation</label>
                <input
                  id="targetGradTerm"
                  className="input"
                  value={targetGradTerm}
                  onChange={(e) => setTargetGradTerm(e.target.value)}
                  placeholder="e.g. Spring 2028"
                />
              </div>

              <div className="sidebar-section">
                <label className="label" htmlFor="maxCredits">Max credits / term</label>
                <div className="credit-slider-row">
                  <input
                    id="maxCredits"
                    type="range"
                    min={6}
                    max={21}
                    value={maxCredits}
                    onChange={(e) => setMaxCredits(Number(e.target.value))}
                    className="credit-slider"
                  />
                  <span className="credit-value">{maxCredits}</span>
                </div>
              </div>

              <div className="sidebar-section">
                <label className="label">Semesters</label>
                <div className="season-toggles">
                  {ALL_SEASONS.map((season) => (
                    <button
                      key={season}
                      type="button"
                      className={getSeasonBtnClass(season, preferredSeasons.includes(season))}
                      onClick={() => toggleSeason(season)}
                    >
                      {season}
                    </button>
                  ))}
                </div>
                {preferredSeasons.length === 0 && (
                  <p style={{ fontSize: "11px", color: "var(--ru-red)", marginTop: "6px", marginBottom: 0 }}>
                    Select at least one semester.
                  </p>
                )}
                {preferredSeasons.includes("Summer") && (
                  <p style={{ fontSize: "10px", color: "var(--text-3)", marginTop: "6px", marginBottom: 0, lineHeight: 1.4 }}>
                    Summer: max 12 credits total.
                  </p>
                )}
                {preferredSeasons.includes("Winter") && (
                  <p style={{ fontSize: "10px", color: "var(--text-3)", marginTop: "6px", marginBottom: 0, lineHeight: 1.4 }}>
                    Winter: max 4 credits (1 course). Not for first-years or GPA &lt; 2.0.
                  </p>
                )}
              </div>

              <button className="primary-button" type="submit">
                Generate my plan
              </button>
              {status && <p className="status-msg">{status}</p>}
            </form>
          </div>
        </aside>

        {/* Main panel */}
        <div className="main-panel">
          <div className="main-content">
            {plan ? (
              <>
                {/* Stats bar */}
                <div className="stats-bar">
                  <div className="stats-bar-item" style={{ paddingLeft: 4 }}>
                    <span className="stats-bar-number">{totalPlanCredits}</span>
                    <span className="stats-bar-label">total credits</span>
                  </div>
                  <div className="stats-bar-item">
                    <span className="stats-bar-number">{plan.terms.length}</span>
                    <span className="stats-bar-label">semesters</span>
                  </div>
                  <div className="stats-bar-progress">
                    <div className="stats-bar-progress-labels">
                      <span className="stats-bar-progress-title">Degree progress</span>
                      <span className="stats-bar-progress-value">
                        {plan.completed_credits} / {plan.total_credits} cr
                        {plan.total_credits > 0 ? ` (${Math.round((plan.completed_credits / plan.total_credits) * 100)}%)` : ""}
                      </span>
                    </div>
                    <div className="stats-bar-progress-track">
                      <div
                        className="stats-bar-progress-fill"
                        style={{ width: plan.total_credits > 0 ? `${Math.round((plan.completed_credits / plan.total_credits) * 100)}%` : "0%" }}
                      />
                    </div>
                  </div>
                </div>

                {/* Planner title */}
                <div className="planner-header">
                  <div className="planner-title">
                    {selectedMajors[0] ?? "My Plan"}
                    {plan.completion_term && (
                      <span className="planner-title-grad">— {plan.completion_term}</span>
                    )}
                  </div>
                  <div className="planner-subtitle">
                    {plan.terms.length} semesters · {totalPlanCredits} total credits
                  </div>
                </div>

                {plan.terms.length === 0 && plan.remaining_courses.length === 0 && (
                  <div className="plan-warning" style={{ marginBottom: 12 }}>
                    <strong>No course data available.</strong> This program hasn&apos;t been published yet.
                  </div>
                )}
                {plan.warnings.length > 0 && (
                  <div className="plan-warning" style={{ marginBottom: 12 }}>
                    <strong>Notes</strong>
                    <ul>{plan.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
                  </div>
                )}
                {plan.remaining_courses.length > 0 && (
                  <div className="plan-warning danger" style={{ marginBottom: 12 }}>
                    <strong>Could not schedule before graduation</strong>
                    <ul>{plan.remaining_courses.map((c) => <li key={c}>{c}</li>)}</ul>
                  </div>
                )}
                {(plan.programs_summary ?? []).map((prog, i) => (
                  <ProgramRequirementsPanel key={i} prog={prog} />
                ))}

                {plan.core_curriculum_blocks?.length > 0 && (
                  <CoreCurriculumPanel
                    name={plan.core_curriculum_name ?? "Core Curriculum"}
                    blocks={plan.core_curriculum_blocks}
                  />
                )}

                <div className="plan-editor-hint">
                  Drag courses between terms to reorder · Hover a course to delete it · Click <strong>+ Add course</strong> to add one · Click <strong>Swap</strong> on electives to pick a different course
                </div>

                <PlanEditor
                  key={planKey}
                  initialTerms={plan.terms}
                  completedCourses={completedCourses}
                  onTermsChange={handleTermsChange}
                />

                <div className="save-bar">
                  <button className="save-button" onClick={handleSave}>
                    Save schedule
                  </button>
                  {saveStatus && (
                    <span className={saveStatus === "Schedule saved!" ? "save-success" : "save-hint"}>
                      {saveStatus}
                    </span>
                  )}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">🎓</div>
                <p className="empty-state-title">Build your degree plan</p>
                <p className="empty-state-sub desktop-only-text">
                  Fill in your major, completed courses, and preferences on the left, then hit Generate.
                </p>
                <p className="empty-state-sub mobile-only-text">
                  Tap the settings icon above to enter your major, completed courses, and preferences, then hit Generate.
                </p>
                <button
                  className="primary-button mobile-only-text"
                  style={{ marginTop: 20, padding: "12px 28px" }}
                  onClick={() => setSidebarOpen(true)}
                >
                  Get started →
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
