"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://api.ruplanner.com";

// ── Types ─────────────────────────────────────────────────────────────────────

type MeetingTime = {
  day: string;
  startTime: string;
  endTime: string;
  buildingCode: string;
  roomNumber: string;
};

type SectionInfo = {
  course_code: string;
  course_title: string;
  section_number: string;
  section_index: string;
  open_status: boolean;
  instructors: string[];
  meeting_times: MeetingTime[];
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

// ── Term helpers ──────────────────────────────────────────────────────────────

const TERM_NAMES: Record<string, string> = {
  "1": "Spring", "7": "Summer", "9": "Fall", "0": "Winter",
};
const TERM_ORDER = ["1", "7", "9"];

function getUpcomingTerms(): { label: string; year: string; term: string }[] {
  const now = new Date();
  const month = now.getMonth() + 1;
  const year = now.getFullYear();
  let currentTermCode: string;
  if (month <= 5) currentTermCode = "1";
  else if (month <= 8) currentTermCode = "7";
  else currentTermCode = "9";
  const results: { label: string; year: string; term: string }[] = [];
  let searchYear = year;
  let idx = TERM_ORDER.indexOf(currentTermCode);
  while (results.length < 2) {
    idx = (idx + 1) % TERM_ORDER.length;
    if (idx === 0) searchYear++;
    const termCode = TERM_ORDER[idx];
    results.push({ label: `${TERM_NAMES[termCode]} ${searchYear}`, year: String(searchYear), term: termCode });
  }
  return results;
}

// ── Formatters ────────────────────────────────────────────────────────────────

const DAY_LABELS: Record<string, string> = {
  M: "Mon", T: "Tue", W: "Wed", TH: "Thu", F: "Fri", S: "Sat", SU: "Sun",
};

function formatTime(t: string): string {
  if (!t) return "";
  const h = parseInt(t.slice(0, -2), 10);
  const m = t.slice(-2);
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${m} ${ampm}`;
}

function formatMeetingTimes(times: MeetingTime[]): string {
  return times
    .map((mt) => {
      const day = DAY_LABELS[mt.day] ?? mt.day;
      const loc = mt.buildingCode && mt.roomNumber ? ` · ${mt.buildingCode}-${mt.roomNumber}` : "";
      return `${day} ${formatTime(mt.startTime)}–${formatTime(mt.endTime)}${loc}`;
    })
    .join(" / ") || "TBA";
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function getUserInitials(email: string | null): string {
  if (!email) return "?";
  return email.charAt(0).toUpperCase();
}

// ── User menu ─────────────────────────────────────────────────────────────────

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

// ── Snipe card ────────────────────────────────────────────────────────────────

function SnipeCard({ snipe, onDelete }: { snipe: Snipe; onDelete: (id: number) => void }) {
  const [deleting, setDeleting] = useState(false);
  const termName = `${TERM_NAMES[snipe.term] ?? snipe.term} ${snipe.year}`;
  const notified = !!snipe.notified_at;

  async function handleDelete() {
    setDeleting(true);
    try {
      await fetch(`${apiBase}/snipes/${snipe.id}`, { method: "DELETE", credentials: "include" });
      onDelete(snipe.id);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div style={{
      background: "var(--surface-3)",
      border: `1.5px solid ${notified ? "var(--border)" : "var(--border-2)"}`,
      borderRadius: 16,
      padding: "18px 20px",
      opacity: notified ? 0.55 : 1,
      transition: "opacity 0.2s",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
        {/* Status dot */}
        <div style={{ paddingTop: 3, flexShrink: 0 }}>
          {notified ? (
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--text-3)" }} />
          ) : (
            <div style={{
              width: 10, height: 10, borderRadius: "50%",
              background: "var(--ru-red)",
              boxShadow: "0 0 0 3px rgba(204,17,51,0.2)",
              animation: "snipe-pulse 2s ease-in-out infinite",
            }} />
          )}
        </div>

        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 15, fontWeight: 700, color: "var(--text)" }}>{snipe.course_code}</span>
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>
              Section {snipe.section_number} · Index {snipe.section_index}
            </span>
          </div>
          <div style={{ fontSize: 13, color: "var(--text-2)", marginTop: 3 }}>
            {snipe.course_title} · {termName}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4 }}>
            {notified
              ? `Notified ${formatDate(snipe.notified_at!)} · ${snipe.phone_number}`
              : `Watching · ${snipe.phone_number} · Added ${formatDate(snipe.created_at)}`}
          </div>
        </div>

        {/* Delete */}
        <button
          onClick={handleDelete}
          disabled={deleting}
          style={{
            flexShrink: 0,
            padding: "5px 13px", fontSize: 12, fontWeight: 500,
            background: "none", border: "1.5px solid var(--border-2)",
            borderRadius: 8, cursor: deleting ? "not-allowed" : "pointer",
            color: "var(--text-3)", transition: "all 0.12s", fontFamily: "inherit",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--ru-red)"; e.currentTarget.style.color = "var(--ru-red)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-2)"; e.currentTarget.style.color = "var(--text-3)"; }}
        >
          {deleting ? "…" : "Delete"}
        </button>
      </div>
    </div>
  );
}

// ── Input style shared ─────────────────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  width: "100%", boxSizing: "border-box",
  padding: "11px 14px", fontSize: 14,
  background: "var(--surface-2)",
  border: "1.5px solid var(--border-2)", borderRadius: 10,
  color: "var(--text)", outline: "none", fontFamily: "inherit",
  transition: "border-color 0.15s",
};

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SniperPage() {
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [snipes, setSnipes] = useState<Snipe[]>([]);

  const upcomingTerms = getUpcomingTerms();
  const [selectedTerm, setSelectedTerm] = useState(upcomingTerms[0]);

  const [indexInput, setIndexInput] = useState("");
  const [looking, setLooking] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [sectionInfo, setSectionInfo] = useState<SectionInfo | null>(null);

  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${apiBase}/auth/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((user) => {
        if (!user) { router.push("/"); return; }
        setUserEmail(user.email);
        return fetch(`${apiBase}/snipes`, { credentials: "include" });
      })
      .then((r) => (r && r.ok ? r.json() : []))
      .then((data: Snipe[]) => setSnipes(data ?? []))
      .catch(() => {});
  }, [router]);

  function handleSignOut() {
    fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" }).catch(() => {});
    router.push("/");
  }

  async function handleLookup() {
    const idx = indexInput.trim();
    if (!idx) return;
    setLooking(true);
    setLookupError(null);
    setSectionInfo(null);
    try {
      const r = await fetch(
        `${apiBase}/soc/section-by-index?index=${encodeURIComponent(idx)}&year=${selectedTerm.year}&term=${selectedTerm.term}`,
        { credentials: "include" }
      );
      if (r.status === 404) { setLookupError("Section not found — check the index and selected term."); return; }
      if (!r.ok) throw new Error();
      setSectionInfo(await r.json());
    } catch {
      setLookupError("Could not reach the Rutgers SOC. Try again.");
    } finally {
      setLooking(false);
    }
  }

  async function handleSnipe() {
    if (!sectionInfo) return;
    const phoneClean = phone.trim();
    if (!phoneClean.match(/^\+1\d{10}$|^\d{10}$/)) {
      setSubmitError("Enter a valid US phone number (10 digits or +1XXXXXXXXXX).");
      return;
    }
    const e164 = phoneClean.startsWith("+") ? phoneClean : `+1${phoneClean}`;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const r = await fetch(`${apiBase}/snipes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          course_code: sectionInfo.course_code,
          course_title: sectionInfo.course_title,
          section_index: indexInput.trim(),
          section_number: sectionInfo.section_number,
          year: selectedTerm.year,
          term: selectedTerm.term,
          campus: "NB",
          phone_number: e164,
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail ?? "Failed to create snipe.");
      }
      const newSnipe: Snipe = await r.json();
      setSnipes((prev) => [newSnipe, ...prev]);
      setIndexInput("");
      setSectionInfo(null);
      setPhone("");
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  const activeSnipes = snipes.filter((s) => s.active && !s.notified_at);
  const inactiveSnipes = snipes.filter((s) => s.notified_at);

  return (
    <>
      <style>{`
        @keyframes snipe-pulse {
          0%, 100% { box-shadow: 0 0 0 3px rgba(204,17,51,0.2); }
          50%       { box-shadow: 0 0 0 6px rgba(204,17,51,0.08); }
        }
        .sniper-input:focus { border-color: var(--border-2) !important; box-shadow: 0 0 0 3px rgba(255,255,255,0.04); }
      `}</style>

      {/* Full-width topbar — same as all other pages */}
      <header className="schedules-topbar">
        <div className="schedules-topbar-logo">
          <img src="/RUPlanner Logo.svg" alt="RU Planner" style={{ height: 36, width: "auto" }} />
        </div>
        <nav className="topbar-nav">
          <Link href="/planner" className="topbar-nav-item" prefetch>My Planner</Link>
          <Link href="/schedules" className="topbar-nav-item" prefetch>Schedules</Link>
          <span className="topbar-nav-item active">Course Sniper</span>
        </nav>
        <div className="topbar-right">
          <UserMenu email={userEmail} onSignOut={handleSignOut} />
        </div>
      </header>

      <div style={{ display: "flex", height: "calc(100vh - var(--topbar-height))", marginTop: "var(--topbar-height)", background: "var(--surface)" }}>
        {/* ── Left panel: form ── */}
        <div style={{
          width: 420, minWidth: 340, maxWidth: 420, flexShrink: 0,
          height: "100%", overflowY: "auto",
          padding: "0 0 40px",
          borderRight: "1px solid var(--border)",
          display: "flex", flexDirection: "column",
        }}>
          <div style={{ padding: "40px 36px 0", flex: 1 }}>
            {/* Header */}
            <div style={{ marginBottom: 32 }}>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", color: "var(--ru-red)", marginBottom: 10, textTransform: "uppercase" }}>
                Course Sniper
              </div>
              <h1 style={{ fontSize: 26, fontWeight: 800, color: "var(--text)", margin: "0 0 8px", lineHeight: 1.2, letterSpacing: "-0.03em" }}>
                Get notified the moment a seat opens.
              </h1>
              <p style={{ fontSize: 13, color: "var(--text-3)", margin: 0, lineHeight: 1.6 }}>
                Enter a section index and we'll text you instantly when a closed section opens up.
              </p>
            </div>

            {/* Term selector */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 10 }}>
                Term
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                {upcomingTerms.map((t) => {
                  const active = selectedTerm.label === t.label;
                  return (
                    <button
                      key={t.label}
                      type="button"
                      onClick={() => { setSelectedTerm(t); setSectionInfo(null); setLookupError(null); }}
                      style={{
                        padding: "8px 18px", fontSize: 13, fontWeight: 600,
                        borderRadius: 20, cursor: "pointer", transition: "all 0.15s",
                        border: "1.5px solid",
                        borderColor: active ? "var(--ru-red)" : "var(--border-2)",
                        background: active ? "var(--ru-red)" : "var(--surface-2)",
                        color: active ? "#fff" : "var(--text-2)",
                        fontFamily: "inherit",
                        boxShadow: active ? "0 2px 12px rgba(204,17,51,0.25)" : "none",
                      }}
                    >
                      {t.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Phone */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-3)", letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 8 }}>
                Phone Number
              </label>
              <input
                className="sniper-input"
                type="tel"
                placeholder="e.g. 7325551234 or +17325551234"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                style={inputStyle}
              />
              <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 5 }}>
                Msg & data rates may apply.
              </div>
            </div>

            {/* Section index */}
            <div style={{ marginBottom: 8 }}>
              <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-3)", letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 8 }}>
                Section Index
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  className="sniper-input"
                  type="text"
                  placeholder="5-digit index"
                  value={indexInput}
                  onChange={(e) => { setIndexInput(e.target.value); setSectionInfo(null); setLookupError(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter") handleLookup(); }}
                  style={{ ...inputStyle, flex: 1 }}
                />
                <button
                  type="button"
                  onClick={handleLookup}
                  disabled={looking || !indexInput.trim()}
                  style={{
                    padding: "11px 20px", fontSize: 13, fontWeight: 700,
                    background: "var(--ru-red)", color: "#fff",
                    border: "none", borderRadius: 10,
                    cursor: looking || !indexInput.trim() ? "not-allowed" : "pointer",
                    opacity: looking || !indexInput.trim() ? 0.6 : 1,
                    transition: "opacity 0.15s", whiteSpace: "nowrap", fontFamily: "inherit",
                    flexShrink: 0,
                  }}
                >
                  {looking ? "…" : "Look up"}
                </button>
              </div>
            </div>

            {/* Lookup error */}
            {lookupError && (
              <div style={{
                padding: "10px 14px", marginTop: 10,
                background: "rgba(204,17,51,0.08)", border: "1.5px solid rgba(204,17,51,0.25)",
                borderRadius: 10, fontSize: 13, color: "#f87171",
              }}>
                {lookupError}
              </div>
            )}

            {/* Section preview card */}
            {sectionInfo && (
              <div className="wizard-step-anim" style={{
                marginTop: 16,
                background: "var(--surface-2)",
                border: "1.5px solid var(--border-2)",
                borderRadius: 14,
                padding: "18px 20px",
                display: "flex", flexDirection: "column", gap: 14,
              }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                  <span style={{
                    flexShrink: 0, fontSize: 10, fontWeight: 700, borderRadius: 20,
                    padding: "3px 10px", marginTop: 2,
                    background: sectionInfo.open_status ? "rgba(34,197,94,0.12)" : "rgba(204,17,51,0.12)",
                    color: sectionInfo.open_status ? "#4ade80" : "#f87171",
                    border: `1px solid ${sectionInfo.open_status ? "rgba(34,197,94,0.3)" : "rgba(204,17,51,0.3)"}`,
                  }}>
                    {sectionInfo.open_status ? "OPEN" : "CLOSED"}
                  </span>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text)" }}>
                      {sectionInfo.course_code} · Section {sectionInfo.section_number}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3 }}>
                      {sectionInfo.course_title}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4 }}>
                      {sectionInfo.instructors[0] ?? "Staff"} · {formatMeetingTimes(sectionInfo.meeting_times)}
                    </div>
                  </div>
                </div>

                {!sectionInfo.open_status && (
                  <div style={{
                    padding: "8px 12px", fontSize: 12, color: "#fbbf24",
                    background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.2)",
                    borderRadius: 8,
                  }}>
                    Section is closed — you'll be texted the moment a seat opens.
                  </div>
                )}
                {!phone.trim() && (
                  <div style={{
                    padding: "8px 12px", fontSize: 12, color: "#f87171",
                    background: "rgba(204,17,51,0.08)", border: "1px solid rgba(204,17,51,0.2)",
                    borderRadius: 8,
                  }}>
                    Enter your phone number above before sniping.
                  </div>
                )}
                {submitError && (
                  <div style={{ fontSize: 12, color: "#f87171" }}>{submitError}</div>
                )}
                <button
                  type="button"
                  onClick={handleSnipe}
                  disabled={submitting || !phone.trim()}
                  style={{
                    padding: "12px 0", background: "var(--ru-red)", color: "#fff",
                    fontWeight: 700, fontSize: 14, border: "none", borderRadius: 10,
                    cursor: submitting || !phone.trim() ? "not-allowed" : "pointer",
                    opacity: submitting || !phone.trim() ? 0.6 : 1,
                    transition: "opacity 0.15s", fontFamily: "inherit",
                  }}
                >
                  {submitting ? "Setting up snipe…" : "🎯 Snipe this section"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ── Right panel: active snipes ── */}
        <div style={{
          flex: 1, minWidth: 0,
          height: "100%", overflowY: "auto",
          background: "var(--surface-2)",
          padding: "36px 40px 40px",
        }}>
          {/* Active snipes */}
          <div style={{ marginBottom: 40 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", color: "var(--ru-red)", textTransform: "uppercase" }}>
                Active Snipes
              </div>
              {activeSnipes.length > 0 && (
                <div style={{
                  fontSize: 11, fontWeight: 700, padding: "2px 8px",
                  background: "rgba(204,17,51,0.12)", color: "var(--ru-red)",
                  border: "1px solid rgba(204,17,51,0.2)", borderRadius: 20,
                }}>
                  {activeSnipes.length}
                </div>
              )}
            </div>

            {activeSnipes.length === 0 ? (
              <div style={{
                padding: "40px 32px",
                background: "var(--surface-3)",
                border: "1.5px dashed var(--border-2)",
                borderRadius: 16,
                textAlign: "center",
              }}>
                <div style={{ fontSize: 28, marginBottom: 12 }}>🎯</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-2)", marginBottom: 4 }}>
                  No active snipes
                </div>
                <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                  Look up a section index on the left to get started.
                </div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {activeSnipes.map((s) => (
                  <SnipeCard key={s.id} snipe={s} onDelete={(id) => setSnipes((prev) => prev.filter((x) => x.id !== id))} />
                ))}
              </div>
            )}
          </div>

          {/* Inactive snipes */}
          {inactiveSnipes.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", color: "var(--text-3)", textTransform: "uppercase", marginBottom: 16 }}>
                Past Snipes
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {inactiveSnipes.map((s) => (
                  <SnipeCard key={s.id} snipe={s} onDelete={(id) => setSnipes((prev) => prev.filter((x) => x.id !== id))} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
