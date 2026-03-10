"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getRegistrarCode, getCoursiclUrl } from "../registrar";
import CourseSniperModal from "../CourseSniperModal";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function safeGetStorage(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function safeRemoveStorage(key: string) {
  try { localStorage.removeItem(key); } catch { /* ignore */ }
}

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

type Snipe = {
  id: number;
  course_code: string;
  course_title: string;
  section_index: string;
  section_number: string;
  year: string;
  term: string;
  campus: string;
  phone_number: string;
  active: boolean;
  notified_at: string | null;
  created_at: string;
};

const TERM_LABELS: Record<string, string> = {
  "9": "Fall", "1": "Spring", "7": "Summer", "0": "Winter",
};

function termToSocCode(termName: string): { year: string; term: string } | null {
  const match = termName.match(/^(Fall|Spring|Summer|Winter)\s+(\d{4})$/);
  if (!match) return null;
  const codes: Record<string, string> = { Fall: "9", Spring: "1", Summer: "7", Winter: "0" };
  return { year: match[2], term: codes[match[1]] };
}

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

// ── Snipes Panel ─────────────────────────────────────────────────────────────

function SnipesPanel({
  open, token, snipes, onDelete, onClose,
}: {
  open: boolean;
  token: string;
  snipes: Snipe[];
  onDelete: (id: number) => void;
  onClose: () => void;
}) {
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function handleDelete(id: number) {
    setDeletingId(id);
    try {
      await fetch(`${apiBase}/snipes/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      onDelete(id);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <>
      {/* Invisible backdrop — click to close */}
      {open && <div className="snipes-backdrop" onClick={onClose} />}

      <div className={`snipes-panel${open ? " open" : ""}`}>
        {/* Header */}
        <div className="snipes-panel-header">
          <div>
            <div className="snipes-panel-title">🎯 Course Sniper</div>
            <div className="snipes-panel-sub">
              Get a text the moment a seat opens
            </div>
          </div>
          <button className="snipes-panel-close" onClick={onClose}>✕</button>
        </div>

        {/* Body */}
        <div className="snipes-panel-body">
          {snipes.length === 0 ? (
            <div className="snipes-empty">
              <div className="snipes-empty-icon">🎯</div>
              <div className="snipes-empty-text">
                No active snipes yet.<br />
                Click the 🎯 on any course to watch a section.
              </div>
            </div>
          ) : (
            snipes.map((s) => {
              const termLabel = `${TERM_LABELS[s.term] ?? s.term} ${s.year}`;
              const wasNotified = !!s.notified_at;
              return (
                <div key={s.id} className={`snipe-card${wasNotified ? " notified" : ""}`}>
                  <div className="snipe-card-icon">{wasNotified ? "✅" : "🎯"}</div>
                  <div className="snipe-card-body">
                    <div className="snipe-card-title">
                      {s.course_code} · Sec {s.section_number}
                      <span className="snipe-card-index">#{s.section_index}</span>
                    </div>
                    <div className="snipe-card-meta">
                      {termLabel} · {s.phone_number}
                    </div>
                    {wasNotified && (
                      <div className="snipe-card-notified">
                        ✓ Notified {new Date(s.notified_at!).toLocaleString()}
                      </div>
                    )}
                  </div>
                  <button
                    className="snipe-delete-btn"
                    onClick={() => handleDelete(s.id)}
                    disabled={deletingId === s.id}
                    title="Remove snipe"
                  >
                    {deletingId === s.id ? "…" : "🗑"}
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SchedulesPage() {
  const router = useRouter();
  const [schedules, setSchedules] = useState<SavedSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [token, setToken] = useState<string | null>(null);

  const [snipes, setSnipes] = useState<Snipe[]>([]);
  const [snipeModal, setSnipeModal] = useState<{
    courseCode: string;
    courseTitle: string;
    year: string;
    term: string;
  } | null>(null);
  const [showSnipes, setShowSnipes] = useState(false);

  const fetchSnipes = useCallback((tok: string) => {
    fetch(`${apiBase}/snipes`, { headers: { Authorization: `Bearer ${tok}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then((data: Snipe[]) => setSnipes(data ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const tok = safeGetStorage("ru_planner_token");
    if (!tok) { router.push("/auth"); return; }
    setToken(tok);

    fetch(`${apiBase}/schedules`, { headers: { Authorization: `Bearer ${tok}` } })
      .then((r) => {
        if (r.status === 401) {
          safeRemoveStorage("ru_planner_token");
          safeRemoveStorage("ru_planner_email");
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

    fetchSnipes(tok);
  }, [router, fetchSnipes]);

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric",
    });
  }

  async function handleDelete(id: number) {
    const tok = safeGetStorage("ru_planner_token");
    if (!tok) return;
    setDeletingId(id);
    try {
      await fetch(`${apiBase}/schedules/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${tok}` },
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
  const activeSnipes = snipes.filter((s) => s.active && !s.notified_at).length;

  return (
    <div className="schedules-shell">
      <header className="schedules-topbar">
        <div className="schedules-topbar-logo">
          <img src="/RUPlanner_logo.png" alt="RU Planner" className="topbar-logo-img" />
          <span className="logo-text" style={{ color: "var(--text)" }}>RU Planner</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="topbar-btn"
            onClick={() => setShowSnipes((v) => !v)}
            style={{ position: "relative" }}
          >
            🎯 My Snipes
            {activeSnipes > 0 && (
              <span className="snipe-topbar-badge">{activeSnipes}</span>
            )}
          </button>
          <button className="topbar-btn" onClick={() => router.push("/")}>
            ← Back to planner
          </button>
        </div>
      </header>

      {/* Always-mounted slide-in panel */}
      {token && (
        <SnipesPanel
          open={showSnipes}
          token={token}
          snipes={snipes}
          onDelete={(id) => setSnipes((prev) => prev.filter((s) => s.id !== id))}
          onClose={() => setShowSnipes(false)}
        />
      )}

      {loading ? (
        <div className="empty-state" style={{ minHeight: "calc(100vh - 57px)" }}>
          <p className="muted">Loading…</p>
        </div>
      ) : schedules.length === 0 ? (
        <div className="empty-state" style={{ minHeight: "calc(100vh - 57px)" }}>
          <div className="empty-state-icon">📋</div>
          <p className="empty-state-title">No saved schedules yet</p>
          <p className="empty-state-sub">Generate a degree plan and save it to see it here.</p>
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

                    <div style={{ flexShrink: 0, marginLeft: 8 }} onClick={(e) => e.stopPropagation()}>
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
                          onMouseEnter={(e) => { const b = e.currentTarget; b.style.background = "#fff1f2"; b.style.borderColor = "#fca5a5"; b.style.color = "#dc2626"; }}
                          onMouseLeave={(e) => { const b = e.currentTarget; b.style.background = "none"; b.style.borderColor = "transparent"; b.style.color = "var(--muted)"; }}
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
                          {term.courses.map((course) => {
                            const soc = termToSocCode(term.term);
                            const hasRegistrar = !!getRegistrarCode(course.code);
                            return (
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

                                  {soc && hasRegistrar && token && (
                                    <button
                                      title="Snipe a section — get texted when a seat opens"
                                      onClick={() => setSnipeModal({
                                        courseCode: course.code,
                                        courseTitle: course.title,
                                        year: soc.year,
                                        term: soc.term,
                                      })}
                                      style={{
                                        marginLeft: "auto",
                                        background: "none",
                                        border: "none",
                                        cursor: "pointer",
                                        fontSize: 14,
                                        padding: "1px 4px",
                                        borderRadius: 4,
                                        color: "var(--muted)",
                                        lineHeight: 1,
                                        transition: "color 0.15s",
                                      }}
                                      onMouseEnter={(e) => { e.currentTarget.style.color = "var(--scarlet)"; }}
                                      onMouseLeave={(e) => { e.currentTarget.style.color = "var(--muted)"; }}
                                    >
                                      🎯
                                    </button>
                                  )}
                                </div>
                                <div className="plan-course-meta">{course.title} · {course.credits} cr</div>
                              </div>
                            );
                          })}
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

      {snipeModal && token && (
        <CourseSniperModal
          courseCode={snipeModal.courseCode}
          courseTitle={snipeModal.courseTitle}
          year={snipeModal.year}
          term={snipeModal.term}
          token={token}
          onClose={() => setSnipeModal(null)}
          onSniped={() => fetchSnipes(token)}
        />
      )}
    </div>
  );
}
