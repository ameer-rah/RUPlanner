"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getRegistrarCode, getCoursiclUrl } from "../registrar";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type PlannedCourse = {
  code: string;
  title: string;
  credits: number;
  is_elective: boolean;
};

type PlanTerm = {
  term: string;
  courses: PlannedCourse[];
  total_credits: number;
};

type SavedSchedule = {
  id: number;
  name: string;
  created_at: string;
  plan_data: {
    terms: PlanTerm[];
    remaining_courses: string[];
    warnings: string[];
    completion_term: string | null;
  };
};

function getTermClass(term: string) {
  if (term.includes("Fall")) return "plan-term term-fall";
  if (term.includes("Spring")) return "plan-term term-spring";
  if (term.includes("Summer")) return "plan-term term-summer";
  if (term.includes("Winter")) return "plan-term term-winter";
  return "plan-term";
}

function getTermPillStyle(term: string): React.CSSProperties {
  if (term.includes("Fall"))
    return { background: "#fffbeb", color: "#92400e", border: "1px solid #fcd34d" };
  if (term.includes("Spring"))
    return { background: "#eff6ff", color: "#1e3a8a", border: "1px solid #93c5fd" };
  if (term.includes("Summer"))
    return { background: "#ecfdf5", color: "#065f46", border: "1px solid #6ee7b7" };
  return { background: "#f5f3ff", color: "#4c1d95", border: "1px solid #c4b5fd" };
}

function totalCredits(terms: PlanTerm[]) {
  return terms.reduce((sum, t) => sum + t.total_credits, 0);
}

export default function SchedulesPage() {
  const router = useRouter();
  const [schedules, setSchedules] = useState<SavedSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("ru_planner_token");
    if (!token) {
      router.push("/auth");
      return;
    }

    fetch(`${apiBase}/schedules`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (r.status === 401) {
          localStorage.removeItem("ru_planner_token");
          localStorage.removeItem("ru_planner_email");
          router.push("/auth");
          return [];
        }
        return r.ok ? r.json() : [];
      })
      .then((data: SavedSchedule[]) => {
        setSchedules(data ?? []);
        if (data?.length > 0) setSelectedId(data[0].id);
      })
      .finally(() => setLoading(false));
  }, [router]);

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  async function handleDelete(id: number) {
    const token = localStorage.getItem("ru_planner_token");
    if (!token) return;
    setDeletingId(id);
    try {
      await fetch(`${apiBase}/schedules/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      setSchedules((prev) => {
        const next = prev.filter((s) => s.id !== id);
        if (selectedId === id) setSelectedId(next[0]?.id ?? null);
        return next;
      });
    } finally {
      setDeletingId(null);
      setConfirmId(null);
    }
  }

  const selected = schedules.find((s) => s.id === selectedId) ?? null;

  return (
    <div className="schedules-shell">
      <header className="schedules-topbar">
        <div className="schedules-topbar-logo">
          <img src="/RUPlanner_logo.png" alt="RU Planner" className="topbar-logo-img" />
          <span className="logo-text" style={{ color: "var(--text)" }}>RU Planner</span>
        </div>
        <button className="topbar-btn" onClick={() => router.push("/")}>
          ← Back to planner
        </button>
      </header>

      {loading ? (
        <div className="empty-state" style={{ minHeight: "calc(100vh - 57px)" }}>
          <p className="muted">Loading…</p>
        </div>
      ) : schedules.length === 0 ? (
        <div className="empty-state" style={{ minHeight: "calc(100vh - 57px)" }}>
          <div className="empty-state-icon">📋</div>
          <p className="empty-state-title">No saved schedules yet</p>
          <p className="empty-state-sub">
            Generate a degree plan and save it to see it here.
          </p>
          <button
            className="primary-button"
            style={{ width: "auto", marginTop: 4 }}
            onClick={() => router.push("/")}
          >
            Generate a plan
          </button>
        </div>
      ) : (
        <div className="schedules-master-detail">
          {/* ── Left: schedule list ── */}
          <div className="schedules-list-panel">
            <div className="schedules-list-header">
              <h1 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>My Schedules</h1>
              <span style={{
                fontSize: 11, fontWeight: 600, background: "var(--scarlet)",
                color: "#fff", borderRadius: 20, padding: "2px 9px",
              }}>
                {schedules.length}
              </span>
            </div>

            <div className="schedules-list">
              {schedules.map((s) => {
                const credits = totalCredits(s.plan_data.terms);
                const isSelected = selectedId === s.id;
                const isConfirming = confirmId === s.id;

                return (
                  <div
                    key={s.id}
                    className={`schedule-list-item${isSelected ? " selected" : ""}`}
                    onClick={() => setSelectedId(s.id)}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="schedule-card-name">{s.name}</div>
                      <div className="schedule-card-meta" style={{ marginTop: 3 }}>
                        {formatDate(s.created_at)}
                        &nbsp;·&nbsp;{s.plan_data.terms.length} terms
                        &nbsp;·&nbsp;{credits} cr
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
                        {s.plan_data.terms.slice(0, 6).map((t) => (
                          <span key={t.term} style={{
                            fontSize: 10, fontWeight: 600, borderRadius: 4,
                            padding: "1px 6px", ...getTermPillStyle(t.term),
                          }}>
                            {t.term}
                          </span>
                        ))}
                        {s.plan_data.terms.length > 6 && (
                          <span style={{
                            fontSize: 10, fontWeight: 600, borderRadius: 4,
                            padding: "1px 6px", background: "#f1f5f9",
                            color: "var(--muted)", border: "1px solid var(--border)",
                          }}>
                            +{s.plan_data.terms.length - 6}
                          </span>
                        )}
                      </div>
                    </div>

                    <div
                      style={{ flexShrink: 0, marginLeft: 8 }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {isConfirming ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "center" }}>
                          <span style={{ fontSize: 10, color: "var(--muted)" }}>Delete?</span>
                          <div style={{ display: "flex", gap: 4 }}>
                            <button
                              onClick={() => handleDelete(s.id)}
                              disabled={deletingId === s.id}
                              style={{ fontSize: 10, fontWeight: 700, padding: "3px 8px", background: "#dc2626", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}
                            >
                              {deletingId === s.id ? "…" : "Yes"}
                            </button>
                            <button
                              onClick={() => setConfirmId(null)}
                              style={{ fontSize: 10, fontWeight: 600, padding: "3px 8px", background: "var(--white)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer" }}
                            >
                              No
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmId(s.id)}
                          title="Delete schedule"
                          style={{ fontSize: 13, padding: "4px 6px", background: "none", border: "1px solid transparent", borderRadius: 5, cursor: "pointer", color: "var(--muted)", lineHeight: 1, transition: "all 0.15s" }}
                          onMouseEnter={(e) => { const b = e.currentTarget as HTMLButtonElement; b.style.background = "#fff1f2"; b.style.borderColor = "#fca5a5"; b.style.color = "#dc2626"; }}
                          onMouseLeave={(e) => { const b = e.currentTarget as HTMLButtonElement; b.style.background = "none"; b.style.borderColor = "transparent"; b.style.color = "var(--muted)"; }}
                        >
                          🗑
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Right: detail panel ── */}
          <div className="schedules-detail-panel">
            {selected ? (
              <>
                <div className="schedules-detail-header">
                  <div>
                    <div style={{ fontSize: 18, fontWeight: 700 }}>{selected.name}</div>
                    <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                      Saved {formatDate(selected.created_at)}
                      &nbsp;·&nbsp;{selected.plan_data.terms.length} terms
                      &nbsp;·&nbsp;{totalCredits(selected.plan_data.terms)} total credits
                      {selected.plan_data.completion_term && (
                        <span style={{ color: "#16a34a", fontWeight: 600 }}>
                          &nbsp;· Completes {selected.plan_data.completion_term}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div style={{ padding: "20px 24px", overflowY: "auto", flex: 1 }}>
                  {selected.plan_data.completion_term && (
                    <div className="plan-completion" style={{ marginBottom: 16 }}>
                      <span>✓</span>
                      <span>All requirements complete by <strong>{selected.plan_data.completion_term}</strong></span>
                    </div>
                  )}
                  <div className="plan-grid">
                    {selected.plan_data.terms.map((term) => (
                      <div key={term.term} className={getTermClass(term.term)}>
                        <div className="plan-term-header">
                          <strong>{term.term}</strong>
                          <span className="credits-badge">{term.total_credits} cr</span>
                        </div>
                        <div className="plan-course-list">
                          {term.courses.map((course) => (
                            <div key={course.code} className={`plan-course${course.is_elective ? " elective" : ""}`}>
                              <div className="plan-course-header">
                                <a
                                  className="plan-course-code"
                                  href={getCoursiclUrl(course.code) ?? undefined}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  title={getRegistrarCode(course.code) ?? course.code}
                                >
                                  {course.code}
                                </a>
                                {course.is_elective && <span className="elective-badge">ELECTIVE</span>}
                              </div>
                              <div className="plan-course-meta">{course.title} · {course.credits} cr</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-state" style={{ flex: 1 }}>
                <p className="muted">Select a schedule to view</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
