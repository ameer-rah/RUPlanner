"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import CompletedCoursesInput from "./CompletedCoursesInput";
import ProgramSelectInput from "./ProgramSelectInput";
import PlanEditor, { PlanTerm } from "./PlanEditor";

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
};

const ALL_SEASONS = ["Spring", "Summer", "Fall"];
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function getSeasonBtnClass(season: string, active: boolean) {
  if (!active) return "season-btn";
  if (season === "Fall") return "season-btn active-fall";
  if (season === "Spring") return "season-btn active-spring";
  return "season-btn active-summer";
}

export default function HomePage() {
  const router = useRouter();
  const [selectedMajors, setSelectedMajors] = useState<string[]>([]);
  const [selectedMinors, setSelectedMinors] = useState<string[]>([]);
  const [completedCourses, setCompletedCourses] = useState<string[]>([]);
  const [startTerm, setStartTerm] = useState("Fall 2026");
  const [targetGradTerm, setTargetGradTerm] = useState("Spring 2028");
  const [maxCredits, setMaxCredits] = useState(15);
  const [preferredSeasons, setPreferredSeasons] = useState<string[]>(["Spring", "Fall"]);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [planKey, setPlanKey] = useState(0); // forces PlanEditor remount on new plan
  const [status, setStatus] = useState("");
  const [programs, setPrograms] = useState<ProgramInfo[]>([]);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState("");

  // Tracks current edited terms from PlanEditor (kept in sync via callback)
  const editedTermsRef = useRef<PlanTerm[]>([]);

  useEffect(() => {
    fetch(`${apiBase}/programs`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data: ProgramInfo[]) => setPrograms(data))
      .catch(() => {});

    const token = localStorage.getItem("ru_planner_token");
    const email = localStorage.getItem("ru_planner_email");
    if (!token) {
      router.push("/auth");
      return;
    }
    setUserEmail(email);
  }, [router]);

  const majorPrograms = programs.filter((p) => p.degree_level !== "minor");
  const minorPrograms = programs.filter((p) => p.degree_level === "minor");

  function toggleSeason(season: string) {
    setPreferredSeasons((prev) =>
      prev.includes(season) ? prev.filter((s) => s !== season) : [...prev, season]
    );
  }

  function handleSignOut() {
    localStorage.removeItem("ru_planner_token");
    localStorage.removeItem("ru_planner_email");
    setUserEmail(null);
    router.push("/auth");
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
      majors: selectedMajors,
      minors: selectedMinors,
      completed_courses: completedCourses,
      start_term: startTerm.trim() || undefined,
      target_grad_term: targetGradTerm,
      max_credits_per_term: maxCredits,
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
    setPlanKey((k) => k + 1); // remount PlanEditor with fresh state
    setStatus("");
  }

  // Stable callback so PlanEditor doesn't re-render unnecessarily
  const handleTermsChange = useCallback((terms: PlanTerm[]) => {
    editedTermsRef.current = terms;
  }, []);

  async function handleSave() {
    const token = localStorage.getItem("ru_planner_token");
    if (!token) {
      router.push("/auth");
      return;
    }
    if (!plan) return;

    setSaveStatus("Saving…");
    const name = `${selectedMajors[0] ?? "My"} — ${targetGradTerm}`;

    // Use the currently edited terms (may have been reordered/modified)
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
      localStorage.removeItem("ru_planner_token");
      localStorage.removeItem("ru_planner_email");
      setUserEmail(null);
      router.push("/auth");
      return;
    }

    if (!res.ok) {
      setSaveStatus("Failed to save. Please try again.");
      return;
    }

    setSaveStatus("Schedule saved!");
  }

  return (
    <div className="app-shell">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <img src="/RUPlanner_logo.png" alt="RU Planner" className="sidebar-logo-img" />
          <span className="logo-text">RU Planner</span>
        </div>

        <div className="sidebar-body">
          <form className="form" onSubmit={handleSubmit}>
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
              <label className="label" htmlFor="startTerm">
                Starting term
              </label>
              <div className="start-term-row">
                {["Fall", "Spring", "Summer"].map((s) => (
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
              <label className="label" htmlFor="targetGradTerm">
                Target graduation
              </label>
              <input
                id="targetGradTerm"
                className="input"
                value={targetGradTerm}
                onChange={(e) => setTargetGradTerm(e.target.value)}
                placeholder="e.g. Spring 2028"
              />
            </div>

            <div className="sidebar-section">
              <label className="label" htmlFor="maxCredits">
                Max credits / term
              </label>
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
                <p style={{ fontSize: "11px", color: "#f87171", marginTop: "6px", marginBottom: 0 }}>
                  Select at least one semester.
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

      {/* ── Main panel ── */}
      <div className="main-panel">
        <header className="topbar">
          <div className="topbar-right">
            {userEmail ? (
              <>
                <span className="topbar-email">{userEmail}</span>
                <button className="topbar-btn" onClick={() => router.push("/schedules")}>
                  My schedules
                </button>
                <button className="topbar-btn" onClick={handleSignOut}>
                  Sign out
                </button>
              </>
            ) : (
              <button className="topbar-btn" onClick={() => router.push("/auth")}>
                Sign in
              </button>
            )}
          </div>
        </header>

        <div className="main-content">
          {plan ? (
            <>
              {/* Status banners */}
              {completedCourses.length > 0 && (
                <div className="plan-completed">
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

              {plan.completion_term && (
                <div className="plan-completion">
                  <span>✓</span>
                  <span>
                    All requirements fit by <strong>{plan.completion_term}</strong> — you&apos;re on track.
                  </span>
                </div>
              )}

              {plan.warnings.length > 0 && (
                <div className="plan-warning">
                  <strong>Notes</strong>
                  <ul>
                    {plan.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {plan.remaining_courses.length > 0 && (
                <div className="plan-warning danger">
                  <strong>Could not schedule before graduation</strong>
                  <ul>
                    {plan.remaining_courses.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="plan-editor-hint">
                Drag courses between terms to reorder · Click <strong>Swap</strong> on electives to pick a different course
              </div>

              {/* Interactive plan editor */}
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
                {!userEmail && (
                  <span className="save-hint">You&apos;ll be asked to sign in first.</span>
                )}
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
  );
}
