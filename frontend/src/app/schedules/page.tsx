"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

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
  return "plan-term";
}

function getTermPillStyle(term: string): React.CSSProperties {
  if (term.includes("Fall"))
    return { background: "#422006", color: "#fbbf24", border: "1px solid #d97706" };
  if (term.includes("Spring"))
    return { background: "#1e1b4b", color: "#93c5fd", border: "1px solid #2563eb" };
  return { background: "#022c22", color: "#6ee7b7", border: "1px solid #059669" };
}

function totalCredits(terms: PlanTerm[]) {
  return terms.reduce((sum, t) => sum + t.total_credits, 0);
}

export default function SchedulesPage() {
  const router = useRouter();
  const [schedules, setSchedules] = useState<SavedSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
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
      .then((data) => setSchedules(data ?? []))
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
      setSchedules((prev) => prev.filter((s) => s.id !== id));
      if (expanded === id) setExpanded(null);
    } finally {
      setDeletingId(null);
      setConfirmId(null);
    }
  }

  return (
    <div className="schedules-shell">
      <header className="schedules-topbar">
        <div className="schedules-topbar-logo">
          <span className="logo-mark">RU</span>
          <span className="logo-text" style={{ color: "var(--text)" }}>Planner</span>
        </div>
        <button className="topbar-btn" onClick={() => router.push("/")}>
          ← Back to planner
        </button>
      </header>

      <div className="schedules-content">
        {/* Page heading */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", margin: 0 }}>
            My Schedules
          </h1>
          {!loading && schedules.length > 0 && (
            <span style={{
              fontSize: 12, fontWeight: 600, background: "var(--scarlet)",
              color: "#fff", borderRadius: 20, padding: "2px 10px",
            }}>
              {schedules.length}
            </span>
          )}
        </div>

        {loading ? (
          <p className="muted">Loading…</p>
        ) : schedules.length === 0 ? (
          <div className="empty-state" style={{ minHeight: 280 }}>
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
          <div style={{ display: "grid", gap: 14 }}>
            {schedules.map((s) => {
              const credits = totalCredits(s.plan_data.terms);
              const isExpanded = expanded === s.id;
              const isConfirming = confirmId === s.id;

              return (
                <div key={s.id} className="schedule-card">
                  {/* Card header row */}
                  <div style={{ display: "flex", alignItems: "stretch" }}>
                    <button
                      className="schedule-card-header"
                      style={{ flex: 1 }}
                      onClick={() => setExpanded(isExpanded ? null : s.id)}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="schedule-card-name">{s.name}</div>
                        <div className="schedule-card-meta" style={{ marginTop: 4 }}>
                          Saved {formatDate(s.created_at)}
                          &nbsp;·&nbsp;{s.plan_data.terms.length} terms
                          &nbsp;·&nbsp;{credits} total credits
                          {s.plan_data.completion_term && (
                            <span style={{ color: "#16a34a", fontWeight: 600 }}>
                              &nbsp;· Completes {s.plan_data.completion_term}
                            </span>
                          )}
                        </div>

                        {/* Term preview pills */}
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 10 }}>
                          {s.plan_data.terms.slice(0, 8).map((t) => (
                            <span
                              key={t.term}
                              style={{
                                fontSize: 11, fontWeight: 600, borderRadius: 5,
                                padding: "2px 8px", ...getTermPillStyle(t.term),
                              }}
                            >
                              {t.term}
                            </span>
                          ))}
                          {s.plan_data.terms.length > 8 && (
                            <span style={{
                              fontSize: 11, fontWeight: 600, borderRadius: 5,
                              padding: "2px 8px", background: "#f1f5f9",
                              color: "var(--muted)", border: "1px solid var(--border)",
                            }}>
                              +{s.plan_data.terms.length - 8} more
                            </span>
                          )}
                        </div>
                      </div>

                      <span className="schedule-expand-icon" style={{ marginLeft: 16 }}>
                        {isExpanded ? "▲" : "▼"}
                      </span>
                    </button>

                    {/* Delete button area */}
                    <div style={{
                      display: "flex", alignItems: "center", padding: "0 16px",
                      borderLeft: "1px solid var(--border)", background: "var(--subtle)",
                    }}>
                      {isConfirming ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "center" }}>
                          <span style={{ fontSize: 11, color: "var(--muted)", whiteSpace: "nowrap" }}>
                            Delete?
                          </span>
                          <div style={{ display: "flex", gap: 6 }}>
                            <button
                              onClick={() => handleDelete(s.id)}
                              disabled={deletingId === s.id}
                              style={{
                                fontSize: 11, fontWeight: 700, padding: "4px 10px",
                                background: "#dc2626", color: "#fff", border: "none",
                                borderRadius: 5, cursor: "pointer",
                              }}
                            >
                              {deletingId === s.id ? "…" : "Yes"}
                            </button>
                            <button
                              onClick={() => setConfirmId(null)}
                              style={{
                                fontSize: 11, fontWeight: 600, padding: "4px 10px",
                                background: "var(--white)", color: "var(--text)",
                                border: "1px solid var(--border)", borderRadius: 5, cursor: "pointer",
                              }}
                            >
                              No
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmId(s.id)}
                          title="Delete schedule"
                          style={{
                            fontSize: 14, padding: "6px 8px", background: "none",
                            border: "1px solid var(--border)", borderRadius: 6,
                            cursor: "pointer", color: "var(--muted)", lineHeight: 1,
                            transition: "all 0.15s",
                          }}
                          onMouseEnter={(e) => {
                            (e.currentTarget as HTMLButtonElement).style.background = "#fff1f2";
                            (e.currentTarget as HTMLButtonElement).style.borderColor = "#fca5a5";
                            (e.currentTarget as HTMLButtonElement).style.color = "#dc2626";
                          }}
                          onMouseLeave={(e) => {
                            (e.currentTarget as HTMLButtonElement).style.background = "none";
                            (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)";
                            (e.currentTarget as HTMLButtonElement).style.color = "var(--muted)";
                          }}
                        >
                          🗑
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Expanded plan */}
                  {isExpanded && (
                    <div className="schedule-card-body">
                      {s.plan_data.completion_term && (
                        <div className="plan-completion" style={{ marginBottom: 16 }}>
                          <span>✓</span>
                          <span>
                            All requirements complete by <strong>{s.plan_data.completion_term}</strong>
                          </span>
                        </div>
                      )}

                      <div className="plan-grid">
                        {s.plan_data.terms.map((term) => (
                          <div key={term.term} className={getTermClass(term.term)}>
                            <div className="plan-term-header">
                              <strong>{term.term}</strong>
                              <span className="credits-badge">{term.total_credits} cr</span>
                            </div>
                            <div className="plan-course-list">
                              {term.courses.map((course) => (
                                <div
                                  key={course.code}
                                  className={`plan-course${course.is_elective ? " elective" : ""}`}
                                >
                                  <div className="plan-course-header">
                                    <span className="plan-course-code">{course.code}</span>
                                    {course.is_elective && (
                                      <span className="elective-badge">ELECTIVE</span>
                                    )}
                                  </div>
                                  <div className="plan-course-meta">
                                    {course.title} · {course.credits} cr
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
