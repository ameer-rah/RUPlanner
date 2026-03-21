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

type RmpData = {
  name: string;
  rating: number | null;
  num_ratings: number;
  difficulty: number | null;
  would_take_again: number | null;
  legacy_id: number | null;
};

type Props = {
  courseCode: string;
  courseTitle: string;
  credits: number;
  isElective: boolean;
  termName: string;   // e.g. "Fall 2026"
  socYear: string;    // e.g. "2026"
  socTerm: string;    // e.g. "9"
  token: string;
  canSnipe: boolean;
  onSnipe: () => void;
  onClose: () => void;
};

const TERM_LABELS: Record<string, string> = {
  "9": "Fall", "1": "Spring", "7": "Summer", "0": "Winter",
};

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
  if (!times.length) return "TBA";
  const days = times.map((mt) => DAY_LABELS[mt.day] ?? mt.day).join("");
  const first = times[0];
  return `${days} ${formatTime(first.start)}–${formatTime(first.end)}`;
}

function StarRating({ rating }: { rating: number }) {
  return (
    <span style={{ display: "inline-flex", gap: 2 }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          style={{ color: i <= Math.round(rating) ? "#f59e0b" : "var(--surface-3)", fontSize: 16 }}
        >
          ★
        </span>
      ))}
    </span>
  );
}

function RatingBar({ value, max, color }: { value: number; max: number; color: string }) {
  return (
    <div style={{ flex: 1, height: 6, background: "var(--surface-3)", borderRadius: 3, overflow: "hidden" }}>
      <div
        style={{
          height: "100%",
          width: `${Math.min(100, (value / max) * 100)}%`,
          background: color,
          borderRadius: 3,
        }}
      />
    </div>
  );
}

// ── Modal ────────────────────────────────────────────────────────────────────

export default function CourseDetailModal({
  courseCode, courseTitle, credits, isElective, termName,
  socYear, socTerm, token, canSnipe, onSnipe, onClose,
}: Props) {
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rmp, setRmp] = useState<RmpData | null>(null);

  const registrar = getRegistrarCode(courseCode);
  const [, subject, courseNumber] = registrar?.split(":") ?? [null, null, null];

  // Fetch sections
  useEffect(() => {
    if (!subject) {
      setError("No registrar mapping — section data unavailable.");
      setLoading(false);
      return;
    }
    fetch(`${apiBase}/soc/sections?subject=${subject}&year=${socYear}&term=${socTerm}&campus=NB`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: Section[]) => setSections(data.filter((s) => s.courseNumber === courseNumber)))
      .catch(() => setError("Could not load sections."))
      .finally(() => setLoading(false));
  }, [subject, courseNumber, socYear, socTerm, token]);

  // Fetch RMP for the first instructor once sections load
  useEffect(() => {
    if (!sections.length) return;
    const instructor = sections[0]?.instructors[0];
    if (!instructor || instructor === "Staff") return;
    fetch(`${apiBase}/rmp/rating?name=${encodeURIComponent(instructor)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setRmp(d ?? null))
      .catch(() => null);
  }, [sections]);

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const openCount = sections.filter((s) => s.openStatus).length;
  const displayTerm = `${TERM_LABELS[socTerm] ?? socTerm} ${socYear}`;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="elective-modal"
        style={{ maxWidth: 620, width: "95vw", padding: 0, overflow: "hidden" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div style={{ padding: "24px 24px 20px", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
            <div>
              <span style={{
                display: "inline-block",
                background: "var(--ru-red-light)", color: "var(--ru-red)",
                border: "1px solid rgba(200,16,46,0.3)",
                borderRadius: 20, padding: "3px 12px",
                fontSize: 13, fontWeight: 700, marginBottom: 8,
              }}>
                {courseCode}
              </span>
              <div style={{ fontSize: 22, fontWeight: 700, color: "var(--text)", lineHeight: 1.2 }}>
                {courseTitle}
              </div>
            </div>
            <button
              onClick={onClose}
              style={{
                background: "none", border: "none", color: "var(--text-3)",
                fontSize: 18, cursor: "pointer", padding: 4, flexShrink: 0,
              }}
            >
              ✕
            </button>
          </div>

          {/* ── Stat cards ── */}
          <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
            {[
              { label: "CREDITS", value: `${credits} cr` },
              { label: "TERM", value: termName },
              { label: "TYPE", value: isElective ? "Elective" : "Required", color: isElective ? "var(--amber)" : "var(--green)" },
              {
                label: "OPEN SEATS",
                value: loading ? "…" : error ? "N/A" : `${openCount} / ${sections.length}`,
                color: openCount > 0 ? "var(--green)" : "var(--ru-red)",
              },
            ].map(({ label, value, color }) => (
              <div key={label} style={{
                background: "var(--surface-2)", borderRadius: 10, padding: "10px 14px",
                flex: "1 1 100px",
              }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-3)", letterSpacing: "0.08em", marginBottom: 4 }}>
                  {label}
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, color: color ?? "var(--text)" }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Body ── */}
        <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 20, maxHeight: "55vh", overflowY: "auto" }}>

          {/* RMP block */}
          {rmp && rmp.rating !== null && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--purple)", letterSpacing: "0.08em", marginBottom: 10 }}>
                RATE MY PROFESSOR
              </div>
              <div style={{
                background: "var(--surface-2)", borderRadius: 12, padding: "14px 16px",
                display: "flex", gap: 20, alignItems: "center",
              }}>
                {/* Score */}
                <div style={{ textAlign: "center", flexShrink: 0 }}>
                  <div style={{ fontSize: 32, fontWeight: 800, color: "var(--text)", lineHeight: 1 }}>
                    {rmp.rating.toFixed(1)}
                  </div>
                  <StarRating rating={rmp.rating} />
                  <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4 }}>
                    {rmp.num_ratings} ratings
                  </div>
                </div>
                {/* Bars */}
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
                  {rmp.difficulty !== null && (
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 12, color: "var(--text-2)", width: 80 }}>Difficulty</span>
                      <RatingBar value={rmp.difficulty} max={5} color="#ef4444" />
                      <span style={{ fontSize: 12, color: "var(--text-3)", width: 28, textAlign: "right" }}>
                        {rmp.difficulty.toFixed(1)}
                      </span>
                    </div>
                  )}
                  {rmp.would_take_again !== null && (
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 12, color: "var(--text-2)", width: 80 }}>Would retake</span>
                      <RatingBar value={rmp.would_take_again} max={100} color="#22c55e" />
                      <span style={{ fontSize: 12, color: "var(--text-3)", width: 28, textAlign: "right" }}>
                        {Math.round(rmp.would_take_again)}%
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Sections table */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--purple)", letterSpacing: "0.08em", marginBottom: 10 }}>
              AVAILABLE SECTIONS
            </div>

            {loading && (
              <div style={{ color: "var(--text-3)", fontSize: 13, padding: "12px 0" }}>Loading sections…</div>
            )}
            {error && (
              <div style={{ color: "var(--text-3)", fontSize: 13, padding: "12px 0" }}>{error}</div>
            )}
            {!loading && !error && sections.length === 0 && (
              <div style={{ color: "var(--text-3)", fontSize: 13, padding: "12px 0" }}>
                No sections found for {displayTerm}.
              </div>
            )}

            {!loading && sections.length > 0 && (
              <div style={{ borderRadius: 10, overflow: "hidden", border: "1px solid var(--border)" }}>
                {/* Table header */}
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "60px 1fr 1fr 90px",
                  gap: 0,
                  padding: "8px 14px",
                  background: "var(--surface-2)",
                  borderBottom: "1px solid var(--border)",
                }}>
                  {["SECTION", "INSTRUCTOR", "TIME", "SEATS"].map((h) => (
                    <div key={h} style={{ fontSize: 10, fontWeight: 700, color: "var(--text-3)", letterSpacing: "0.06em" }}>
                      {h}
                    </div>
                  ))}
                </div>

                {/* Rows */}
                {sections.map((sec, i) => {
                  const instructor = sec.instructors[0] ?? "Staff";
                  const time = formatMeetingTimes(sec.meetingTimes);
                  return (
                    <div
                      key={sec.index}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "60px 1fr 1fr 90px",
                        gap: 0,
                        padding: "11px 14px",
                        background: "var(--surface)",
                        borderBottom: i < sections.length - 1 ? "1px solid var(--border)" : "none",
                        alignItems: "center",
                      }}
                    >
                      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>
                        {sec.sectionNumber}
                      </div>
                      <div style={{ fontSize: 13, color: "var(--text-2)", paddingRight: 8 }}>
                        {instructor}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                        {time}
                      </div>
                      <div>
                        <span style={{
                          display: "inline-block",
                          fontSize: 11, fontWeight: 700,
                          padding: "3px 10px", borderRadius: 20,
                          background: sec.openStatus ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                          color: sec.openStatus ? "#4ade80" : "#f87171",
                          border: `1px solid ${sec.openStatus ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
                        }}>
                          {sec.openStatus ? "Open" : "Closed"}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* ── Footer ── */}
        <div style={{
          padding: "16px 24px",
          borderTop: "1px solid var(--border)",
          display: "flex", gap: 10, justifyContent: "flex-end",
        }}>
          <button
            onClick={onClose}
            style={{
              padding: "10px 20px", background: "var(--surface-2)",
              border: "1px solid var(--border-2)", borderRadius: 10,
              color: "var(--text)", fontSize: 14, fontWeight: 600,
              cursor: "pointer", fontFamily: "inherit",
            }}
          >
            Close
          </button>
          {canSnipe && (
            <button
              onClick={() => { onClose(); onSnipe(); }}
              style={{
                padding: "10px 20px", background: "var(--surface-2)",
                border: "1px solid var(--border-2)", borderRadius: 10,
                color: "var(--text)", fontSize: 14, fontWeight: 600,
                cursor: "pointer", fontFamily: "inherit",
                display: "flex", alignItems: "center", gap: 8,
              }}
            >
              🎯 Snipe closed sections
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
