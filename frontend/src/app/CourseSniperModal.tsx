"use client";

import { useState, useEffect } from "react";
import { getRegistrarCode } from "./registrar";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ────────────────────────────────────────────────────────────────────

type MeetingTime = {
  day: string;
  start: string;
  end: string;
  building: string;
  room: string;
};

type Section = {
  index: string;
  sectionNumber: string;
  openStatus: boolean;
  instructors: string[];
  meetingTimes: MeetingTime[];
  courseNumber: string;
  courseTitle: string;
};

type Props = {
  courseCode: string;      // e.g. "CS111"
  courseTitle: string;
  year: string;
  term: string;            // "9"=Fall, "1"=Spring, "7"=Summer, "0"=Winter
  campus?: string;
  token: string;
  onClose: () => void;
  onSniped: () => void;    // refresh snipes list
};

const TERM_LABELS: Record<string, string> = {
  "9": "Fall", "1": "Spring", "7": "Summer", "0": "Winter",
};

const DAY_LABELS: Record<string, string> = {
  M: "Mon", T: "Tue", W: "Wed", TH: "Thu", F: "Fri", S: "Sat", SU: "Sun",
};

function formatTime(t: string): string {
  if (!t) return "";
  // SOC returns times like "1040" or "1230"
  const h = parseInt(t.slice(0, -2), 10);
  const m = t.slice(-2);
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${m} ${ampm}`;
}

// ── Modal ────────────────────────────────────────────────────────────────────

export default function CourseSniperModal({
  courseCode, courseTitle, year, term, campus = "NB", token, onClose, onSniped,
}: Props) {
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedIndex, setSelectedIndex] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Parse subject from registrar code  e.g. "01:198:111" → "198", courseNum → "111"
  const registrar = getRegistrarCode(courseCode);
  const [, subject, courseNumber] = registrar?.split(":") ?? [null, null, null];

  useEffect(() => {
    if (!subject) {
      setError("Unknown course prefix — cannot look up sections.");
      setLoading(false);
      return;
    }
    fetch(`${apiBase}/soc/sections?subject=${subject}&year=${year}&term=${term}&campus=${campus}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject("SOC fetch failed")))
      .then((data: Section[]) => {
        // Filter to this specific course number
        const filtered = data.filter(
          (s) => s.courseNumber === courseNumber
        );
        setSections(filtered);
      })
      .catch(() => setError("Could not load sections. The SOC may be unavailable."))
      .finally(() => setLoading(false));
  }, [subject, courseNumber, year, term, campus, token]);

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleSnipe() {
    if (!selectedIndex) return;
    const phoneClean = phone.trim();
    if (!phoneClean.match(/^\+1\d{10}$|^\d{10}$/)) {
      setSubmitError("Enter a valid US phone number (10 digits or +1XXXXXXXXXX).");
      return;
    }
    const e164 = phoneClean.startsWith("+") ? phoneClean : `+1${phoneClean}`;
    const sec = sections.find((s) => s.index === selectedIndex)!;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const resp = await fetch(`${apiBase}/snipes`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          course_code: courseCode,
          course_title: courseTitle,
          section_index: sec.index,
          section_number: sec.sectionNumber,
          year,
          term,
          campus,
          phone_number: e164,
        }),
      });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        throw new Error(d.detail ?? "Failed to create snipe.");
      }
      onSniped();
      onClose();
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  const selected = sections.find((s) => s.index === selectedIndex) ?? null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="elective-modal" style={{ maxWidth: 600, width: "95vw" }} onClick={(e) => e.stopPropagation()}>

        {/* Header */}
        <div className="elective-modal-header">
          <div>
            <div className="elective-modal-title">
              Course Sniper — {courseCode}
            </div>
            <div className="elective-modal-sub">
              {courseTitle} · {TERM_LABELS[term] ?? term} {year}
            </div>
          </div>
          <button className="elective-modal-close" onClick={onClose}>✕</button>
        </div>

        {/* Body */}
        <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>

          {loading && (
            <div style={{ textAlign: "center", color: "var(--muted)", padding: 24, fontSize: 13 }}>
              Loading sections…
            </div>
          )}

          {error && (
            <div style={{ color: "#dc2626", fontSize: 13, padding: "10px 0" }}>{error}</div>
          )}

          {!loading && !error && sections.length === 0 && (
            <div style={{ color: "var(--muted)", fontSize: 13, padding: "10px 0" }}>
              No sections found for {courseCode} in {TERM_LABELS[term] ?? term} {year}.
            </div>
          )}

          {/* Section list */}
          {!loading && sections.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", marginBottom: 2 }}>
                Pick a closed section to watch — you&apos;ll get a text the moment it opens.
              </div>
              <div style={{ maxHeight: 280, overflowY: "auto", display: "flex", flexDirection: "column", gap: 6 }}>
                {sections.map((sec) => {
                  const isSelected = selectedIndex === sec.index;
                  const instructor = sec.instructors[0] ?? "Staff";
                  const times = sec.meetingTimes
                    .map((mt) => `${DAY_LABELS[mt.day] ?? mt.day} ${formatTime(mt.start)}–${formatTime(mt.end)}`)
                    .join(", ");
                  return (
                    <button
                      key={sec.index}
                      onClick={() => setSelectedIndex(isSelected ? null : sec.index)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 12,
                        padding: "10px 14px",
                        background: isSelected ? "#fef2f2" : "var(--white)",
                        border: `1.5px solid ${isSelected ? "var(--scarlet)" : "var(--border)"}`,
                        borderRadius: 8,
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "all 0.15s",
                      }}
                    >
                      {/* Open/closed pill */}
                      <span style={{
                        flexShrink: 0,
                        fontSize: 10,
                        fontWeight: 700,
                        borderRadius: 20,
                        padding: "2px 8px",
                        background: sec.openStatus ? "#dcfce7" : "#fee2e2",
                        color: sec.openStatus ? "#166534" : "#991b1b",
                        border: `1px solid ${sec.openStatus ? "#86efac" : "#fca5a5"}`,
                      }}>
                        {sec.openStatus ? "OPEN" : "CLOSED"}
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                          Section {sec.sectionNumber}
                          <span style={{ fontWeight: 400, color: "var(--muted)", marginLeft: 6, fontSize: 12 }}>
                            Index: {sec.index}
                          </span>
                        </div>
                        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                          {instructor}{times ? ` · ${times}` : ""}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Phone number input — only shown after a section is selected */}
          {selectedIndex && selected && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, paddingTop: 4 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)" }}>
                Your phone number (US)
              </div>
              <div style={{ fontSize: 12, color: "var(--muted)" }}>
                We&apos;ll text you the instant section {selected.sectionNumber} (index {selected.index}) opens.
              </div>
              <input
                type="tel"
                placeholder="e.g. 7325551234 or +17325551234"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                style={{
                  padding: "9px 12px",
                  fontSize: 14,
                  border: "1.5px solid var(--border)",
                  borderRadius: 8,
                  outline: "none",
                  fontFamily: "inherit",
                }}
              />
              {submitError && (
                <div style={{ color: "#dc2626", fontSize: 12 }}>{submitError}</div>
              )}
              <button
                onClick={handleSnipe}
                disabled={submitting || !phone.trim()}
                style={{
                  padding: "10px 0",
                  background: "var(--scarlet)",
                  color: "#fff",
                  fontWeight: 700,
                  fontSize: 14,
                  border: "none",
                  borderRadius: 8,
                  cursor: submitting ? "not-allowed" : "pointer",
                  opacity: submitting ? 0.7 : 1,
                  transition: "opacity 0.15s",
                }}
              >
                {submitting ? "Setting up snipe…" : "🎯 Snipe this section"}
              </button>
              <div style={{ fontSize: 11, color: "var(--muted)", textAlign: "center" }}>
                Msg &amp; data rates may apply. One text per seat opening. Unsubscribe anytime by deleting the snipe.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
