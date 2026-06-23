"use client";

import { Suspense } from "react";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getRegistrarCode } from "../registrar";
import CourseDetailModal from "../CourseDetailModal";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://api.ruplanner.com";

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

function termToSocCode(termName: string): { year: string; term: string } | null {
  const match = termName.match(/^(Fall|Spring|Summer|Winter)\s+(\d{4})$/);
  if (!match) return null;
  const codes: Record<string, string> = { Fall: "9", Spring: "1", Summer: "7", Winter: "0" };
  return { year: match[2], term: codes[match[1]] };
}

function getSeasonColors(term: string): { bg: string; text: string; border: string } {
  if (term.includes("Fall"))   return { bg: "rgba(200,80,30,0.08)",   text: "#fb923c", border: "rgba(200,80,30,0.2)" };
  if (term.includes("Spring")) return { bg: "rgba(3,105,161,0.08)",   text: "#38bdf8", border: "rgba(3,105,161,0.2)" };
  if (term.includes("Summer")) return { bg: "rgba(22,163,74,0.08)",   text: "#4ade80", border: "rgba(22,163,74,0.2)" };
  return                               { bg: "rgba(91,33,182,0.08)",   text: "#a78bfa", border: "rgba(91,33,182,0.2)" };
}

function totalCredits(terms: PlanTerm[]) {
  return terms.reduce((sum, t) => sum + t.total_credits, 0);
}

function formatSavedDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function getUserInitials(email: string | null): string {
  if (!email) return "?";
  return email.charAt(0).toUpperCase();
}

function UserMenu({ email, onSignOut }: { email: string | null; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <button className="topbar-avatar" onClick={() => setOpen((v) => !v)} title={email ?? ""}>
        {getUserInitials(email)}
      </button>
      {open && (
        <>
          <div style={{ position: "fixed", inset: 0, zIndex: 199 }} onClick={() => setOpen(false)} />
          <div style={{
            position: "absolute", top: "calc(100% + 8px)", right: 0,
            background: "var(--surface)", border: "1.5px solid var(--border-2)",
            borderRadius: 12, boxShadow: "var(--shadow-lg)", minWidth: 200, zIndex: 200, overflow: "hidden",
          }}>
            <div style={{ padding: "12px 16px 10px", borderBottom: "1px solid var(--border)" }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text)" }}>{email ?? ""}</div>
              <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>Signed in</div>
            </div>
            <button
              onClick={() => { setOpen(false); onSignOut(); }}
              style={{
                width: "100%", padding: "10px 16px", background: "none", border: "none",
                textAlign: "left", fontSize: 13, color: "var(--ru-red)", cursor: "pointer",
                fontFamily: "inherit", fontWeight: 500,
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

// ── Main Page ─────────────────────────────────────────────────────────────────

function SchedulesPageContent() {
  const router = useRouter();
  const [schedules, setSchedules] = useState<SavedSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  const [detailModal, setDetailModal] = useState<{
    courseCode: string;
    courseTitle: string;
    credits: number;
    isElective: boolean;
    termName: string;
    socYear: string;
    socTerm: string;
  } | null>(null);

  useEffect(() => {
    router.prefetch("/planner");
    fetch(`${apiBase}/auth/me`, { credentials: "include" })
      .then((r) => { if (!r.ok) { router.push("/"); return null; } return r.json(); })
      .then((user) => {
        if (!user) return;
        setUserEmail(user.email);
        return fetch(`${apiBase}/schedules`, { credentials: "include" });
      })
      .then((r) => {
        if (!r) return [];
        if (r.status === 401) { router.push("/"); return []; }
        return r.ok ? r.json() : [];
      })
      .then((data: SavedSchedule[]) => {
        setSchedules(data ?? []);
        if (data?.length > 0) setSelectedId(data[0].id);
      })
      .finally(() => setLoading(false));
  }, [router]);

  function handleSignOut() {
    fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" }).catch(() => {});
    router.push("/");
  }

  async function handleDelete(id: number) {
    setDeletingId(id);
    try {
      await fetch(`${apiBase}/schedules/${id}`, { method: "DELETE", credentials: "include" });
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

  const Topbar = (
    <header className="schedules-topbar" style={{ position: "fixed", top: 0, left: 0, right: 0, zIndex: 100 }}>
      <div className="schedules-topbar-logo">
        <img src="/RUPlanner Logo.svg" alt="RU Planner" style={{ height: 36, width: "auto" }} />
      </div>
      <nav className="topbar-nav">
        <Link href="/planner" className="topbar-nav-item" prefetch>My Planner</Link>
        <span className="topbar-nav-item active">Schedules</span>
        <Link href="/sniper" className="topbar-nav-item">Course Sniper</Link>
      </nav>
      <div className="topbar-right">
        <UserMenu email={userEmail} onSignOut={handleSignOut} />
      </div>
    </header>
  );

  // Empty state
  if (!loading && schedules.length === 0) {
    return (
      <div style={{ background: "var(--surface)", minHeight: "100vh" }}>
        {Topbar}
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          minHeight: "100vh", gap: 16, textAlign: "center", padding: 32,
        }}>
          <div style={{ fontSize: 40 }}>📋</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text)", letterSpacing: "-0.03em" }}>
            No saved schedules yet
          </div>
          <div style={{ fontSize: 14, color: "var(--text-3)", maxWidth: 280 }}>
            Generate a degree plan and save it to see it here.
          </div>
          <button
            onClick={() => router.push("/planner")}
            style={{
              marginTop: 8, padding: "12px 28px", background: "var(--ru-red)", color: "#fff",
              border: "none", borderRadius: 10, fontSize: 14, fontWeight: 700,
              cursor: "pointer", fontFamily: "inherit",
            }}
          >
            Generate a plan
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--surface)" }}>
      {Topbar}

      {/* ── Sidebar: schedule list ── */}
      <div style={{
        width: 260, minWidth: 200, maxWidth: 260, flexShrink: 0,
        height: "100vh", overflowY: "auto",
        paddingTop: "var(--topbar-height)",
        borderRight: "1px solid var(--border)",
        background: "var(--surface-2)",
        display: "flex", flexDirection: "column",
      }}>
        {/* Sidebar header */}
        <div style={{
          padding: "20px 16px 12px",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", color: "var(--text-3)", textTransform: "uppercase" }}>
            My Schedules
          </div>
        </div>

        {/* Schedule list */}
        <div style={{ flex: 1, overflowY: "auto", padding: "10px 10px" }}>
          {loading ? (
            <div style={{ padding: 16, fontSize: 13, color: "var(--text-3)" }}>Loading…</div>
          ) : (
            schedules.map((s) => {
              const credits = totalCredits(s.plan_data.terms);
              const isSelected = selectedId === s.id;
              const isConfirming = confirmId === s.id;
              // Show first 3 unique season colors as dots
              const termDots = s.plan_data.terms.slice(0, 4).map((t) => getSeasonColors(t.term));

              return (
                <div
                  key={s.id}
                  onClick={() => { setSelectedId(s.id); setConfirmId(null); }}
                  style={{
                    padding: "12px 12px",
                    borderRadius: 10,
                    marginBottom: 4,
                    cursor: "pointer",
                    background: isSelected ? "var(--surface-3)" : "transparent",
                    border: `1.5px solid ${isSelected ? "var(--border-2)" : "transparent"}`,
                    transition: "all 0.12s",
                  }}
                  onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = "var(--surface-2)"; }}
                  onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}
                >
                  {/* Term dots */}
                  <div style={{ display: "flex", gap: 4, marginBottom: 7 }}>
                    {termDots.map((c, i) => (
                      <div key={i} style={{ width: 7, height: 7, borderRadius: "50%", background: c.text, opacity: 0.7 }} />
                    ))}
                    {s.plan_data.terms.length > 4 && (
                      <div style={{ fontSize: 9, color: "var(--text-3)", alignSelf: "center" }}>+{s.plan_data.terms.length - 4}</div>
                    )}
                  </div>

                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", lineHeight: 1.3, marginBottom: 3 }}>
                    {s.name}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-3)" }}>
                    {s.plan_data.terms.length} terms · {credits} cr
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-3)", marginTop: 2 }}>
                    Saved {formatSavedDate(s.created_at)}
                  </div>

                  {/* Delete controls */}
                  <div style={{ marginTop: 8 }} onClick={(e) => e.stopPropagation()}>
                    {isConfirming ? (
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <span style={{ fontSize: 10, color: "var(--text-3)" }}>Delete?</span>
                        <button
                          onClick={() => handleDelete(s.id)}
                          disabled={deletingId === s.id}
                          style={{
                            fontSize: 10, fontWeight: 600, padding: "3px 8px",
                            background: "var(--ru-red)", color: "#fff",
                            border: "none", borderRadius: 6, cursor: "pointer", fontFamily: "inherit",
                          }}
                        >
                          {deletingId === s.id ? "…" : "Yes"}
                        </button>
                        <button
                          onClick={() => setConfirmId(null)}
                          style={{
                            fontSize: 10, fontWeight: 500, padding: "3px 8px",
                            background: "var(--surface-2)", color: "var(--text-2)",
                            border: "1.5px solid var(--border-2)", borderRadius: 6, cursor: "pointer", fontFamily: "inherit",
                          }}
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmId(s.id)}
                        style={{
                          fontSize: 11, padding: "2px 0",
                          background: "none", border: "none",
                          cursor: "pointer", color: "var(--text-3)",
                          borderRadius: 4, transition: "color 0.12s", fontFamily: "inherit",
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--ru-red)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-3)"; }}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}

          {/* New schedule */}
          <div style={{ padding: "4px 0 8px" }}>
            <button
              onClick={() => router.push("/planner")}
              style={{
                width: "100%", padding: "9px 12px", fontSize: 12, fontWeight: 600,
                background: "none", border: "1.5px dashed var(--border-2)",
                borderRadius: 10, color: "var(--text-3)", cursor: "pointer",
                fontFamily: "inherit", transition: "all 0.15s", textAlign: "left",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--ru-red)"; e.currentTarget.style.color = "var(--ru-red)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-2)"; e.currentTarget.style.color = "var(--text-3)"; }}
            >
              + New schedule
            </button>
          </div>
        </div>
      </div>

      {/* ── Detail panel ── */}
      <div style={{
        flex: 1, minWidth: 0,
        height: "100vh", overflowY: "auto",
        paddingTop: "var(--topbar-height)",
        background: "var(--surface-2)",
      }}>
        {selected ? (
          <>
            {/* Detail header */}
            <div style={{
              padding: "28px 32px 24px",
              borderBottom: "1px solid var(--border)",
              background: "var(--surface)",
              position: "sticky", top: 0, zIndex: 10,
            }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: "var(--text)", letterSpacing: "-0.03em", marginBottom: 4 }}>
                {selected.name}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                Saved {formatSavedDate(selected.created_at)} · {selected.plan_data.terms.length} semesters · {totalCredits(selected.plan_data.terms)} total credits
              </div>

              {/* Progress bar */}
              {(() => {
                const credits = totalCredits(selected.plan_data.terms);
                const earnedCr = selected.plan_data.completed_credits ?? 0;
                const totalCr = selected.plan_data.total_credits ?? credits;
                const pct = totalCr > 0 ? Math.round((earnedCr / totalCr) * 100) : 0;
                return (
                  <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 16 }}>
                    <div style={{ flex: 1, height: 5, background: "var(--surface-3)", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${pct}%`, background: "var(--ru-red)", borderRadius: 3, transition: "width 0.4s" }} />
                    </div>
                    <span style={{ fontSize: 11, color: "var(--text-3)", whiteSpace: "nowrap" }}>
                      {earnedCr} / {totalCr} cr completed
                    </span>
                  </div>
                );
              })()}
            </div>

            {/* Semester grid */}
            <div style={{ padding: "28px 32px 40px" }}>
              {selected.plan_data.completion_term && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "10px 16px", marginBottom: 20,
                  background: "rgba(34,197,94,0.06)", border: "1px solid rgba(34,197,94,0.15)",
                  borderRadius: 10, fontSize: 13, color: "#4ade80",
                }}>
                  <span>✓</span>
                  <span>All requirements complete by <strong>{selected.plan_data.completion_term}</strong></span>
                </div>
              )}

              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
                gap: 16,
              }}>
                {selected.plan_data.terms.map((term) => {
                  const soc = termToSocCode(term.term);
                  const colors = getSeasonColors(term.term);
                  return (
                    <div key={term.term} style={{
                      background: "var(--surface)",
                      border: "1.5px solid var(--border)",
                      borderRadius: 14,
                      overflow: "hidden",
                    }}>
                      {/* Term header */}
                      <div style={{
                        padding: "10px 16px",
                        background: colors.bg,
                        borderBottom: `1px solid ${colors.border}`,
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                      }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: colors.text }}>
                          {term.term.toUpperCase()}
                        </span>
                        <span style={{
                          fontSize: 10, fontWeight: 700, padding: "2px 8px",
                          background: colors.bg, color: colors.text,
                          border: `1px solid ${colors.border}`, borderRadius: 20,
                        }}>
                          {term.total_credits} cr
                        </span>
                      </div>

                      {/* Courses */}
                      <div style={{ padding: "10px 0" }}>
                        {term.courses.map((course) => {
                          const hasRegistrar = !!getRegistrarCode(course.code);
                          const clickable = !!(soc && hasRegistrar);
                          return (
                            <div
                              key={course.code}
                              onClick={() => {
                                if (!clickable) return;
                                setDetailModal({
                                  courseCode: course.code,
                                  courseTitle: course.title,
                                  credits: course.credits,
                                  isElective: course.is_elective,
                                  termName: term.term,
                                  socYear: soc!.year,
                                  socTerm: soc!.term,
                                });
                              }}
                              style={{
                                padding: "8px 16px",
                                cursor: clickable ? "pointer" : "default",
                                transition: "background 0.1s",
                                display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
                              }}
                              onMouseEnter={(e) => { if (clickable) e.currentTarget.style.background = "var(--surface-2)"; }}
                              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                            >
                              <div style={{ minWidth: 0 }}>
                                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text)", flexShrink: 0 }}>
                                    {course.code}
                                  </span>
                                  {course.is_elective && (
                                    <span style={{
                                      fontSize: 9, fontWeight: 700, padding: "1px 5px",
                                      background: "rgba(251,191,36,0.1)", color: "#fbbf24",
                                      border: "1px solid rgba(251,191,36,0.2)", borderRadius: 4,
                                    }}>
                                      ELEC
                                    </span>
                                  )}
                                </div>
                                <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                                  {course.title}
                                </div>
                              </div>
                              <span style={{ fontSize: 11, color: "var(--text-3)", flexShrink: 0 }}>
                                {course.credits}cr
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        ) : loading ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-3)", fontSize: 13 }}>
            Loading…
          </div>
        ) : (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-3)", fontSize: 13 }}>
            Select a schedule to view
          </div>
        )}
      </div>

      {/* Course Detail Modal */}
      {detailModal && (
        <CourseDetailModal
          courseCode={detailModal.courseCode}
          courseTitle={detailModal.courseTitle}
          credits={detailModal.credits}
          isElective={detailModal.isElective}
          termName={detailModal.termName}
          socYear={detailModal.socYear}
          socTerm={detailModal.socTerm}
          canSnipe={false}
          onClose={() => setDetailModal(null)}
          onSnipe={() => {}}
        />
      )}
    </div>
  );
}

export default function SchedulesPage() {
  return (
    <Suspense>
      <SchedulesPageContent />
    </Suspense>
  );
}
