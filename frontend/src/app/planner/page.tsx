"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import CompletedCoursesInput from "../CompletedCoursesInput";
import ProgramSelectInput from "../ProgramSelectInput";
import PlanEditor, { PlanTerm } from "../PlanEditor";

type ProgramInfo = {
  school: string;
  degree_level: string;
  major_name: string;
  catalog_year: string;
  display_name: string;
};

type PlanResponse = {
  terms: PlanTerm[];
  remaining_courses: string[];
  warnings: string[];
  completion_term: string | null;
  completed_credits: number;
  total_credits: number;
};

function safeGetStorage(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function safeRemoveStorage(key: string) {
  try { localStorage.removeItem(key); } catch { /* ignore */ }
}

const ALL_SEASONS = ["Spring", "Summer", "Fall", "Winter"];
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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

export default function PlannerPage() {
  const router = useRouter();
  const [selectedMajors, setSelectedMajors] = useState<string[]>([]);
  const [selectedMinors, setSelectedMinors] = useState<string[]>([]);
  const [completedCourses, setCompletedCourses] = useState<string[]>([]);
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
    const token = safeGetStorage("ru_planner_token");
    const email = safeGetStorage("ru_planner_email");
    if (!token) {
      router.push("/");
      return;
    }
    setUserEmail(email);

    fetch(`${apiBase}/programs`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data: ProgramInfo[]) => setPrograms(data))
      .catch(() => {});
  }, [router]);

  const DEGREE_FILTERS = [
    { key: "bachelor",      label: "Bachelor's",    levels: new Set(["bachelor_ba","bachelor_bs","bachelor_bfa","bachelor_bm","bachelor_bsba","bachelor_bsla"]) },
    { key: "master",        label: "Master's",      levels: new Set(["master","master_ms","master_ma","master_mat","master_meng"]) },
    { key: "concentration", label: "Concentration", levels: new Set(["concentration"]) },
  ];
  const activeFilter = DEGREE_FILTERS.find((f) => f.key === degreeFilter)!;
  const majorPrograms = programs.filter(
    (p) => p.degree_level !== "minor" && activeFilter.levels.has(p.degree_level)
  );
  const minorPrograms = programs.filter((p) => p.degree_level === "minor");

  function toggleSeason(season: string) {
    setPreferredSeasons((prev) =>
      prev.includes(season) ? prev.filter((s) => s !== season) : [...prev, season]
    );
  }

  function handleSignOut() {
    safeRemoveStorage("ru_planner_token");
    safeRemoveStorage("ru_planner_email");
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
      minors: selectedMinors,
      completed_courses: completedCourses,
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
    const token = safeGetStorage("ru_planner_token");
    if (!token) {
      router.push("/");
      return;
    }
    if (!plan) return;

    setSaveStatus("Saving…");
    const name = `${selectedMajors[0] ?? "My"} — ${targetGradTerm}`;

    const plan_data = {
      ...plan,
      terms: editedTermsRef.current,
    };

    const res = await fetch(`${apiBase}/schedules`, {
      method: "POST",
      headers: { "content-type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name, plan_data }),
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
          <Link href="/schedules" className="topbar-nav-item" prefetch>Course Sniper</Link>
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
          <div className="sidebar-section-label">Plan settings</div>
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
                  onChange={setSelectedMinors}
                  placeholder="Search minors…"
                />
              </div>

              <div className="sidebar-section">
                <label className="label">Completed courses</label>
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
                {completedCourses.length > 0 && (
                  <div className="plan-completed" style={{ marginBottom: 12 }}>
                    <div className="plan-completed-label">
                      {completedCourses.length} completed course{completedCourses.length !== 1 ? "s" : ""} applied
                    </div>
                    <div className="plan-completed-chips">
                      {completedCourses.map((code) => (
                        <span key={code} className="plan-completed-chip">{code}</span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="plan-editor-hint">
                  Drag courses between terms to reorder · Click <strong>Swap</strong> on electives to pick a different course
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
                <p className="empty-state-sub">
                  Fill in your major, completed courses, and preferences on the left, then hit Generate.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
