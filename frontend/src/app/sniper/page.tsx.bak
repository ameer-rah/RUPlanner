"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function safeGetStorage(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function safeRemoveStorage(key: string) {
  try { localStorage.removeItem(key); } catch { }
}

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
const TERM_ORDER = ["1", "7", "9"]; // Spring → Summer → Fall (skip Winter for display)

function getUpcomingTerms(): { label: string; year: string; term: string }[] {
  const now = new Date();
  const month = now.getMonth() + 1; // 1–12
  const year = now.getFullYear();

  // Determine current term code
  let currentTermCode: string;
  if (month <= 5) currentTermCode = "1";       // Jan–May = Spring
  else if (month <= 8) currentTermCode = "7";  // Jun–Aug = Summer
  else currentTermCode = "9";                  // Sep–Dec = Fall

  const results: { label: string; year: string; term: string }[] = [];
  let searchYear = year;
  let idx = TERM_ORDER.indexOf(currentTermCode);

  // Collect the next 2 terms after the current one
  while (results.length < 2) {
    idx = (idx + 1) % TERM_ORDER.length;
    if (idx === 0) searchYear++; // wrapped back to Spring → new year
    const termCode = TERM_ORDER[idx];
    results.push({
      label: `${TERM_NAMES[termCode]} ${searchYear}`,
      year: String(searchYear),
      term: termCode,
    });
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
      const loc = mt.buildingCode && mt.roomNumber
        ? ` · ${mt.buildingCode}-${mt.roomNumber}`
        : mt.buildingCode ? ` · ${mt.buildingCode}` : "";
      return `${day} ${formatTime(mt.startTime)}–${formatTime(mt.endTime)}${loc}`;
    })
    .join(" / ") || "TBA";
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

// ── User menu ─────────────────────────────────────────────────────────────────

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

// ── Snipe card ────────────────────────────────────────────────────────────────

function SnipeCard({ snipe, onDelete }: { snipe: Snipe; onDelete: (id: number) => void }) {
  const [deleting, setDeleting] = useState(false);
  const token = safeGetStorage("ru_planner_token");
  const termName = `${({ "1": "Spring", "7": "Summer", "9": "Fall", "0": "Winter" } as Record<string, string>)[snipe.term] ?? snipe.term} ${snipe.year}`;
  const inactive = !!snipe.notified_at;

  async function handleDelete() {
    setDeleting(true);
    try {
      await fetch(`${apiBase}/snipes/${snipe.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      onDelete(snipe.id);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 14,
      padding: "14px 18px",
      background: inactive ? "var(--surface)" : "var(--white)",
      border: `1.5px solid ${inactive ? "var(--border)" : "var(--border-2)"}`,
      borderRadius: 12, opacity: inactive ? 0.6 : 1,
    }}>
      <div style={{
        width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
        background: inactive ? "var(--muted)" : "var(--scarlet)",
        boxShadow: inactive ? "none" : "0 0 0 3px rgba(204,0,0,0.15)",
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: "#111" }}>
          {snipe.course_code}
          <span style={{ fontWeight: 400, color: "var(--muted)", marginLeft: 8, fontSize: 12 }}>
            Section {snipe.section_number} · Index {snipe.section_index}
          </span>
        </div>
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
          {snipe.course_title} · {termName}
        </div>
        <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>
          {inactive
            ? `Notified ${formatDate(snipe.notified_at!)} · ${snipe.phone_number}`
            : `Watching · ${snipe.phone_number} · Added ${formatDate(snipe.created_at)}`}
        </div>
      </div>
      <button
        onClick={handleDelete}
        disabled={deleting}
        style={{
          padding: "5px 12px", fontSize: 12, fontWeight: 500,
          background: "none", border: "1.5px solid var(--border)",
          borderRadius: 8, cursor: deleting ? "not-allowed" : "pointer",
          color: "var(--muted)", transition: "all 0.12s",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--scarlet)"; e.currentTarget.style.color = "var(--scarlet)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--muted)"; }}
      >
        {deleting ? "…" : "Delete"}
      </button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SniperPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
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
    const tok = safeGetStorage("ru_planner_token");
    const email = safeGetStorage("ru_planner_email");
    if (!tok) { router.push("/"); return; }
    setToken(tok);
    setUserEmail(email);
    fetch(`${apiBase}/snipes`, { headers: { Authorization: `Bearer ${tok}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then((data: Snipe[]) => setSnipes(data ?? []))
      .catch(() => {});
  }, [router]);

  function handleSignOut() {
    safeRemoveStorage("ru_planner_token");
    safeRemoveStorage("ru_planner_email");
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
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (r.status === 404) {
        setLookupError("Section not found — check the index and selected term.");
        return;
      }
      if (!r.ok) throw new Error();
      setSectionInfo(await r.json());
    } catch {
      setLookupError("Could not reach the Rutgers SOC. Try again.");
    } finally {
      setLooking(false);
    }
  }

  async function handleSnipe() {
    if (!sectionInfo || !token) return;
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
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
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
    <div className="schedules-shell">
      {/* Topbar */}
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

      {/* Page content */}
      <div style={{
        width: "100%",
        maxWidth: 720,
        margin: "var(--topbar-height) auto 0",
        padding: "36px 24px 60px",
        boxSizing: "border-box",
      }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: "var(--text)", margin: 0 }}>
            Course Sniper 🎯
          </h1>
          <p style={{ fontSize: 14, color: "var(--muted)", marginTop: 6 }}>
            Enter a section index and we'll text you the moment a seat opens.
          </p>
        </div>

        {/* Term tabs */}
        <div style={{ display: "flex", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
          {upcomingTerms.map((t) => {
            const active = selectedTerm.label === t.label;
            return (
              <button
                key={t.label}
                onClick={() => { setSelectedTerm(t); setSectionInfo(null); setLookupError(null); }}
                style={{
                  padding: "7px 18px", fontSize: 13, fontWeight: 600,
                  borderRadius: 20, cursor: "pointer", transition: "all 0.15s",
                  border: "1.5px solid",
                  borderColor: active ? "var(--scarlet)" : "var(--border-2)",
                  background: active ? "var(--scarlet)" : "var(--surface)",
                  color: active ? "#fff" : "var(--text)",
                  boxShadow: active ? "0 2px 8px rgba(204,0,0,0.18)" : "none",
                }}
              >
                {t.label}
              </button>
            );
          })}
        </div>
        <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 20 }}>
          Showing upcoming terms — updates automatically each semester.
        </div>

        {/* Phone number — collected upfront so users know it's required */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text)", marginBottom: 6 }}>
            Your phone number
          </label>
          <input
            type="tel"
            placeholder="e.g. 7325551234 or +17325551234"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            style={{
              width: "100%", boxSizing: "border-box",
              padding: "10px 14px", fontSize: 14,
              border: "1.5px solid var(--border)", borderRadius: 10,
              outline: "none", fontFamily: "inherit",
            }}
          />
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
            We'll text this number the moment a seat opens. Msg & data rates may apply.
          </div>
        </div>

        {/* Section index input with inline Look up button */}
        <div style={{ position: "relative", marginBottom: 20 }}>
          <input
            type="text"
            placeholder="Enter 5-digit section index"
            value={indexInput}
            onChange={(e) => { setIndexInput(e.target.value); setSectionInfo(null); setLookupError(null); }}
            onKeyDown={(e) => { if (e.key === "Enter") handleLookup(); }}
            style={{
              width: "100%", boxSizing: "border-box",
              padding: "10px 110px 10px 14px", fontSize: 14,
              border: "1.5px solid var(--border)", borderRadius: 10,
              outline: "none", fontFamily: "inherit",
            }}
          />
          <button
            onClick={handleLookup}
            disabled={looking || !indexInput.trim()}
            style={{
              position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)",
              padding: "6px 16px", fontSize: 13, fontWeight: 700,
              background: "var(--scarlet)", color: "#fff",
              border: "none", borderRadius: 7,
              cursor: looking || !indexInput.trim() ? "not-allowed" : "pointer",
              opacity: looking || !indexInput.trim() ? 0.7 : 1,
              transition: "opacity 0.15s", whiteSpace: "nowrap",
            }}
          >
            {looking ? "Looking up…" : "Look up"}
          </button>
        </div>

        {/* Lookup error */}
        {lookupError && (
          <div style={{
            padding: "10px 14px", background: "#fef2f2", border: "1.5px solid #fca5a5",
            borderRadius: 10, fontSize: 13, color: "#991b1b", marginBottom: 16,
          }}>
            {lookupError}
          </div>
        )}

        {/* Section confirmation card */}
        {sectionInfo && (
          <div style={{
            padding: 20, background: "var(--white)",
            border: "1.5px solid var(--border-2)", borderRadius: 14,
            marginBottom: 24, display: "flex", flexDirection: "column", gap: 14,
          }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <span style={{
                flexShrink: 0, fontSize: 10, fontWeight: 700, borderRadius: 20,
                padding: "3px 10px",
                background: sectionInfo.open_status ? "#dcfce7" : "#fee2e2",
                color: sectionInfo.open_status ? "#166534" : "#991b1b",
                border: `1px solid ${sectionInfo.open_status ? "#86efac" : "#fca5a5"}`,
                marginTop: 2,
              }}>
                {sectionInfo.open_status ? "OPEN" : "CLOSED"}
              </span>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#111" }}>
                  {sectionInfo.course_code} — Section {sectionInfo.section_number}
                </div>
                <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 2 }}>
                  {sectionInfo.course_title}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4 }}>
                  {sectionInfo.instructors[0] ?? "Staff"} · {formatMeetingTimes(sectionInfo.meeting_times)}
                </div>
              </div>
            </div>

            {/* Status-aware action area */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {!sectionInfo.open_status && (
                <div style={{
                  padding: "8px 12px", background: "#fef9ec",
                  border: "1px solid #fcd34d", borderRadius: 8,
                  fontSize: 12, color: "#92400e",
                }}>
                  This section is <strong>closed</strong> — you'll be texted the moment a seat opens.
                </div>
              )}
              {!phone.trim() && (
                <div style={{
                  padding: "8px 12px", background: "#fef2f2",
                  border: "1px solid #fca5a5", borderRadius: 8,
                  fontSize: 12, color: "#991b1b",
                }}>
                  Enter your phone number above before sniping.
                </div>
              )}
              {submitError && (
                <div style={{ fontSize: 12, color: "#dc2626" }}>{submitError}</div>
              )}
              <button
                onClick={handleSnipe}
                disabled={submitting || !phone.trim()}
                style={{
                  padding: "11px 0", background: "var(--scarlet)", color: "#fff",
                  fontWeight: 700, fontSize: 14, border: "none", borderRadius: 10,
                  cursor: submitting || !phone.trim() ? "not-allowed" : "pointer",
                  opacity: submitting || !phone.trim() ? 0.6 : 1, transition: "opacity 0.15s",
                }}
              >
                {submitting ? "Setting up snipe…" : "🎯 Snipe this section"}
              </button>
            </div>
          </div>
        )}

        {/* Active snipes */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase", color: "var(--scarlet)", marginBottom: 12 }}>
            Active Snipes
          </div>
          {activeSnipes.length === 0 ? (
            <div style={{ fontSize: 13, color: "var(--muted)", padding: "16px 0" }}>
              No active snipes. Enter a section index above to get started.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {activeSnipes.map((s) => (
                <SnipeCard key={s.id} snipe={s} onDelete={(id) => setSnipes((prev) => prev.filter((x) => x.id !== id))} />
              ))}
            </div>
          )}
        </div>

        {/* Inactive snipes */}
        {inactiveSnipes.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase", color: "var(--muted)", marginBottom: 12 }}>
              Inactive Snipes
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {inactiveSnipes.map((s) => (
                <SnipeCard key={s.id} snipe={s} onDelete={(id) => setSnipes((prev) => prev.filter((x) => x.id !== id))} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
