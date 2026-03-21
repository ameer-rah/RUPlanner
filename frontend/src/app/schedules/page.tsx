"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getRegistrarCode, getCoursiclUrl } from "../registrar";
import CourseSniperModal from "../CourseSniperModal";
import CourseDetailModal from "../CourseDetailModal";

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
    completed_credits?: number;
    total_credits?: number;
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

// Returns the single next upcoming term name from a list of term names.
// "Upcoming" = closest future term that hasn't started yet.
// Approximate semester start months: Spring=Jan, Summer=May, Fall=Sep, Winter=Dec.
function getNextUpcomingTerm(termNames: string[]): string | null {
  const startMonth: Record<string, number> = { Spring: 1, Summer: 5, Fall: 9, Winter: 12 };
  const now = new Date();
  const future = termNames
    .map((name) => {
      const m = name.match(/^(Fall|Spring|Summer|Winter)\s+(\d{4})$/);
      if (!m) return null;
      const start = new Date(parseInt(m[2], 10), startMonth[m[1]] - 1, 1);
      return start > now ? { name, start } : null;
    })
    .filter(Boolean) as { name: string; start: Date }[];
  if (future.length === 0) return null;
  future.sort((a, b) => a.start.getTime() - b.start.getTime());
  return future[0].name;
}

function getTermClass(term: string) {
  if (term.includes("Fall")) return "plan-term term-fall";
  if (term.includes("Spring")) return "plan-term term-spring";
  if (term.includes("Summer")) return "plan-term term-summer";
  if (term.includes("Winter")) return "plan-term term-winter";
  return "plan-term";
}

function getSeason(term: string): string {
  if (term.includes("Fall")) return "fall";
  if (term.includes("Spring")) return "spring";
  if (term.includes("Summer")) return "summer";
  return "winter";
}

function totalCredits(terms: PlanTerm[]) {
  return terms.reduce((sum, t) => sum + t.total_credits, 0);
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

function formatSavedDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

// ── Schedule sidebar item chips ───────────────────────────────────────────────

function ScheduleChips({ terms }: { terms: PlanTerm[] }) {
  const shown = terms.slice(0, 3);
  const extra = terms.length - shown.length;
  return (
    <div className="schedule-item-chips">
      {shown.map((t) => {
        const season = getSeason(t.term);
        const label = t.term.replace("Spring", "Spr").replace("Summer", "Sum").replace("Winter", "Win");
        const style: React.CSSProperties =
          season === "fall" ? { background: "var(--season-fall-bg)", color: "var(--season-fall-text)" } :
          season === "spring" ? { background: "var(--season-spring-bg)", color: "var(--season-spring-text)" } :
          season === "summer" ? { background: "var(--season-summer-bg)", color: "var(--season-summer-text)" } :
          { background: "var(--season-winter-bg)", color: "var(--season-winter-text)" };
        return (
          <span key={t.term} className="schedule-item-chip" style={style}>
            {label}
          </span>
        );
      })}
      {extra > 0 && (
        <span className="schedule-item-chip">+{extra}</span>
      )}
    </div>
  );
}

// ── Sniper Panel ─────────────────────────────────────────────────────────────

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

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

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

  const activeSnipes = snipes.filter((s) => s.active && !s.notified_at);
  const notifiedSnipes = snipes.filter((s) => s.notified_at);
  const phoneNumbers = [...new Set(snipes.map((s) => s.phone_number).filter(Boolean))];

  return (
    <>
      {open && <div className="snipes-backdrop" onClick={onClose} />}

      <div className={`snipes-panel${open ? " open" : ""}`}>
        {/* Header */}
        <div className="snipes-panel-header">
          <div className="snipes-panel-icon">🎯</div>
          <div className="snipes-panel-info">
            <div className="snipes-panel-title">Course sniper</div>
            <div className="snipes-panel-sub">Get a text the moment a seat opens</div>
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
                Click 🎯 on any course to watch a section.
              </div>
            </div>
          ) : (
            <>
              {/* Active snipes section */}
              {activeSnipes.length > 0 && (
                <>
                  <div className="snipes-section-label">{activeSnipes.length} active snipe{activeSnipes.length !== 1 ? "s" : ""}</div>
                  {activeSnipes.map((s) => {
                    const termLabel = `${TERM_LABELS[s.term] ?? s.term} ${s.year}`;
                    const timeStr = s.created_at
                      ? new Date(s.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })
                      : "";
                    return (
                      <div key={s.id} className="snipe-card">
                        <div className="snipe-dot watching" />
                        <div className="snipe-card-body">
                          <div className="snipe-card-title">
                            {s.course_code} — Section {s.section_number}
                          </div>
                          <div className="snipe-card-meta">{termLabel} · {timeStr}</div>
                        </div>
                        <span className="snipe-status-badge watching">Watching</span>
                        <button
                          className="snipe-delete-btn"
                          onClick={() => handleDelete(s.id)}
                          disabled={deletingId === s.id}
                          title="Remove snipe"
                        >
                          {deletingId === s.id ? "…" : "✕"}
                        </button>
                      </div>
                    );
                  })}
                </>
              )}

              {/* Phone number block */}
              {phoneNumbers.length > 0 && (
                <>
                  <div className="snipes-section-label" style={{ marginTop: 8 }}>Notify via</div>
                  <div className="snipe-phone-block">
                    <div className="snipe-phone-icon">📱</div>
                    <div>
                      <div className="snipe-phone-number">{phoneNumbers[0]}</div>
                      <div className="snipe-phone-label">SMS alerts enabled</div>
                    </div>
                  </div>
                </>
              )}

              {/* Alert history */}
              {notifiedSnipes.length > 0 && (
                <>
                  <div className="snipes-section-label" style={{ marginTop: 8 }}>Recent alerts</div>
                  {notifiedSnipes.map((s) => {
                    const termLabel = `${TERM_LABELS[s.term] ?? s.term} ${s.year}`;
                    const timeAgo = s.notified_at
                      ? new Date(s.notified_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })
                      : "";
                    return (
                      <div key={s.id} className="snipe-history-row">
                        <div className="snipe-history-dot" style={{ background: "#16a34a" }} />
                        <span className="snipe-history-text">
                          {s.course_code} §{s.section_number} opened — {termLabel}
                        </span>
                        <span className="snipe-history-time">{timeAgo}</span>
                      </div>
                    );
                  })}
                </>
              )}
            </>
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
  const [userEmail, setUserEmail] = useState<string | null>(null);

  const [snipes, setSnipes] = useState<Snipe[]>([]);
  const [snipeModal, setSnipeModal] = useState<{
    courseCode: string;
    courseTitle: string;
    year: string;
    term: string;
  } | null>(null);
  const [detailModal, setDetailModal] = useState<{
    courseCode: string;
    courseTitle: string;
    credits: number;
    isElective: boolean;
    termName: string;
    socYear: string;
    socTerm: string;
    canSnipe: boolean;
  } | null>(null);
  const [showSnipes, setShowSnipes] = useState(false);

  const fetchSnipes = useCallback((tok: string) => {
    fetch(`${apiBase}/snipes`, { headers: { Authorization: `Bearer ${tok}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then((data: Snipe[]) => setSnipes(data ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    router.prefetch("/planner");
    const tok = safeGetStorage("ru_planner_token");
    const email = safeGetStorage("ru_planner_email");
    if (!tok) { router.push("/"); return; }
    setToken(tok);
    setUserEmail(email);

    fetch(`${apiBase}/schedules`, { headers: { Authorization: `Bearer ${tok}` } })
      .then((r) => {
        if (r.status === 401) {
          safeRemoveStorage("ru_planner_token");
          safeRemoveStorage("ru_planner_email");
          router.push("/");
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

  function handleSignOut() {
    safeRemoveStorage("ru_planner_token");
    safeRemoveStorage("ru_planner_email");
    router.push("/");
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
  const activeSnipeCount = snipes.filter((s) => s.active && !s.notified_at).length;

  // Parse plan name for title display
  function parsePlanTitle(name: string): { main: string; grad: string | null } {
    const dashIdx = name.lastIndexOf("—");
    if (dashIdx === -1) return { main: name, grad: null };
    return {
      main: name.slice(0, dashIdx).trim(),
      grad: name.slice(dashIdx + 1).trim(),
    };
  }

  return (
    <div className="schedules-shell">
      {/* ── Topbar ── */}
      <header className="schedules-topbar">
        <div className="schedules-topbar-logo">
          <img src="/RUPlanner Logo.svg" alt="RU Planner" style={{ height: 36, width: "auto" }} />
        </div>
        <nav className="topbar-nav">
          <Link href="/planner" className="topbar-nav-item" prefetch>My Planner</Link>
          <span className="topbar-nav-item active">Schedules</span>
          <button
            className="topbar-nav-item"
            style={{ border: "none", cursor: "pointer" }}
            onClick={() => setShowSnipes((v) => !v)}
          >
            Course Sniper
          </button>
        </nav>
        <div className="topbar-right">
          <UserMenu email={userEmail} onSignOut={handleSignOut} />
        </div>
      </header>

      {/* Always-mounted slide-in sniper panel */}
      {token && (
        <SnipesPanel
          open={showSnipes}
          token={token}
          snipes={snipes}
          onDelete={(id) => setSnipes((prev) => prev.filter((s) => s.id !== id))}
          onClose={() => setShowSnipes(false)}
        />
      )}

      {/* ── Master / detail layout ── */}
      {!loading && schedules.length === 0 ? (
        <div
          className="empty-state"
          style={{ minHeight: "calc(100vh - var(--topbar-height))", marginTop: "var(--topbar-height)" }}
        >
          <div className="empty-state-icon">📋</div>
          <p className="empty-state-title">No saved schedules yet</p>
          <p className="empty-state-sub">Generate a degree plan and save it to see it here.</p>
          <button
            className="primary-button"
            style={{ width: "auto", marginTop: 4 }}
            onClick={() => router.push("/planner")}
          >
            Generate a plan
          </button>
        </div>
      ) : (
        <div className="schedules-master-detail">
          {/* ── Sidebar: schedule list ── */}
          <div className="schedules-list-panel">
            <div className="schedules-list-header">
              <span style={{ fontSize: 11, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--lavender-600)" }}>
                My Schedules
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
                    onClick={() => { setSelectedId(s.id); setConfirmId(null); }}
                  >
                    <div className="schedule-card-name">{s.name}</div>
                    <div className="schedule-card-meta">
                      {s.plan_data.terms.length} terms · {credits} cr
                    </div>
                    <ScheduleChips terms={s.plan_data.terms} />

                    {/* Delete controls */}
                    <div style={{ marginTop: 8 }} onClick={(e) => e.stopPropagation()}>
                      {isConfirming ? (
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <span style={{ fontSize: 10, color: "var(--lavender-600)" }}>Delete?</span>
                          <button
                            onClick={() => handleDelete(s.id)}
                            disabled={deletingId === s.id}
                            style={{
                              fontSize: 10, fontWeight: 600, padding: "3px 8px",
                              background: "var(--ru-red)", color: "#fff",
                              border: "none", borderRadius: 6, cursor: "pointer",
                            }}
                          >
                            {deletingId === s.id ? "…" : "Yes"}
                          </button>
                          <button
                            onClick={() => setConfirmId(null)}
                            style={{
                              fontSize: 10, fontWeight: 500, padding: "3px 8px",
                              background: "#fff", color: "var(--lavender-700)",
                              border: "1.5px solid var(--lavender-200)", borderRadius: 6, cursor: "pointer",
                            }}
                          >
                            No
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmId(s.id)}
                          style={{
                            fontSize: 11, padding: "2px 6px",
                            background: "none", border: "none",
                            cursor: "pointer", color: "var(--lavender-600)",
                            borderRadius: 4, transition: "color 0.12s",
                          }}
                          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--ru-red)"; }}
                          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--lavender-600)"; }}
                          title="Delete schedule"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* New schedule button */}
              <div style={{ padding: "4px 0 8px" }}>
                <button className="new-schedule-btn" onClick={() => router.push("/planner")}>
                  + New schedule
                </button>
              </div>
            </div>
          </div>

          {/* ── Detail panel ── */}
          <div className="schedules-detail-panel">
            {selected ? (
              <>
                {/* Detail header */}
                <div className="schedules-detail-header">
                  {(() => {
                    const { main, grad } = parsePlanTitle(selected.name);
                    const credits = totalCredits(selected.plan_data.terms);
                    return (
                      <>
                        <div className="planner-title">
                          {main}
                          {grad && <span className="planner-title-grad">— {grad}</span>}
                        </div>
                        <div className="planner-subtitle">
                          Saved {formatSavedDate(selected.created_at)} · {selected.plan_data.terms.length} terms · {credits} total credits
                        </div>

                        {/* Stats bar */}
                        <div className="stats-bar" style={{ marginTop: 14 }}>
                          <div className="stats-bar-item" style={{ paddingLeft: 4 }}>
                            <span className="stats-bar-number">{credits}</span>
                            <span className="stats-bar-label">total credits</span>
                          </div>
                          <div className="stats-bar-item">
                            <span className="stats-bar-number">{selected.plan_data.terms.length}</span>
                            <span className="stats-bar-label">semesters</span>
                          </div>
                          <div className="stats-bar-item">
                            <span className="stats-bar-number">{activeSnipeCount}</span>
                            <span className="stats-bar-label">active snipes</span>
                          </div>
                          {(() => {
                            const earnedCr = selected.plan_data.completed_credits ?? 0;
                            const totalCr = selected.plan_data.total_credits ?? credits;
                            const pct = totalCr > 0 ? Math.round((earnedCr / totalCr) * 100) : 0;
                            return (
                              <div className="stats-bar-progress">
                                <div className="stats-bar-progress-labels">
                                  <span className="stats-bar-progress-title">Degree progress</span>
                                  <span className="stats-bar-progress-value">{earnedCr} / {totalCr} cr ({pct}%)</span>
                                </div>
                                <div className="stats-bar-progress-track">
                                  <div className="stats-bar-progress-fill" style={{ width: `${pct}%` }} />
                                </div>
                              </div>
                            );
                          })()}
                        </div>
                      </>
                    );
                  })()}
                </div>

                {/* Semester grid */}
                <div className="schedules-detail-content">
                  {selected.plan_data.completion_term && (
                    <div className="plan-completion" style={{ marginBottom: 12 }}>
                      <span>✓</span>
                      <span>All requirements complete by <strong>{selected.plan_data.completion_term}</strong></span>
                    </div>
                  )}

                  <div className="plan-grid">
                    {(() => {
                      const nextTerm = getNextUpcomingTerm(selected.plan_data.terms.map((t) => t.term));
                      return selected.plan_data.terms.map((term) => {
                      const soc = termToSocCode(term.term);
                      return (
                        <div key={term.term} className={getTermClass(term.term)}>
                          {/* Card header */}
                          <div className="plan-term-header">
                            <strong>{term.term}</strong>
                            <span className="credits-badge">{term.total_credits} cr</span>
                          </div>

                          {/* Course rows */}
                          <div className="plan-course-list">
                            {term.courses.map((course) => {
                              const hasRegistrar = !!getRegistrarCode(course.code);
                              const snipeActive = snipes.some(
                                (sn) => sn.course_code === course.code && sn.active && !sn.notified_at
                              );
                              return (
                                <div
                                  key={course.code}
                                  className="plan-course"
                                  style={{ cursor: soc && hasRegistrar ? "pointer" : "default" }}
                                  onClick={() => {
                                    if (!soc || !hasRegistrar || !token) return;
                                    setDetailModal({
                                      courseCode: course.code,
                                      courseTitle: course.title,
                                      credits: course.credits,
                                      isElective: course.is_elective,
                                      termName: term.term,
                                      socYear: soc.year,
                                      socTerm: soc.term,
                                      canSnipe: term.term === nextTerm,
                                    });
                                  }}
                                >
                                  <div className="plan-course-header">
                                    <span className="plan-course-code">
                                      {course.code}
                                    </span>
                                    {course.is_elective && (
                                      <span className="elective-badge">ELEC</span>
                                    )}
                                    <span className="plan-course-name">{course.title}</span>
                                    <span className="plan-course-credits">{course.credits}</span>
                                    {soc && hasRegistrar && token && term.term === nextTerm && (
                                      <button
                                        title="Snipe — get texted when a seat opens"
                                        className={`course-snipe-btn${snipeActive ? " sniped" : ""}`}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setSnipeModal({
                                            courseCode: course.code,
                                            courseTitle: course.title,
                                            year: soc.year,
                                            term: soc.term,
                                          });
                                        }}
                                      >
                                        🎯
                                      </button>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    });
                    })()}
                  </div>
                </div>
              </>
            ) : loading ? (
              <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <p className="muted" style={{ fontSize: 13 }}>Loading…</p>
              </div>
            ) : (
              <div className="empty-state" style={{ flex: 1 }}>
                <p className="muted">Select a schedule to view</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Course Detail Modal */}
      {detailModal && token && (
        <CourseDetailModal
          courseCode={detailModal.courseCode}
          courseTitle={detailModal.courseTitle}
          credits={detailModal.credits}
          isElective={detailModal.isElective}
          termName={detailModal.termName}
          socYear={detailModal.socYear}
          socTerm={detailModal.socTerm}
          token={token}
          canSnipe={detailModal.canSnipe}
          onClose={() => setDetailModal(null)}
          onSnipe={() => {
            setDetailModal(null);
            setSnipeModal({
              courseCode: detailModal.courseCode,
              courseTitle: detailModal.courseTitle,
              year: detailModal.socYear,
              term: detailModal.socTerm,
            });
          }}
        />
      )}

      {/* Course Sniper Modal */}
      {snipeModal && token && (
        <CourseSniperModal
          courseCode={snipeModal.courseCode}
          courseTitle={snipeModal.courseTitle}
          year={snipeModal.year}
          term={snipeModal.term}
          token={token}
          onClose={() => setSnipeModal(null)}
          onSniped={() => {
            const tok = safeGetStorage("ru_planner_token");
            if (tok) fetchSnipes(tok);
          }}
        />
      )}
    </div>
  );
}
