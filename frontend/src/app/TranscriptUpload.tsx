"use client";

import { useState, useRef, useEffect } from "react";

type CourseDetail = {
  title_raw: string;
  rutgers_code: string | null;
  grade: string;
  passed: boolean;
  failed: boolean;
  is_transfer: boolean;
  is_in_progress: boolean;
  semester: string;
  credits: number;
  equivalency_note: string;
};

type TranscriptResult = {
  matched: string[];
  in_progress: string[];
  inferred: Record<string, string>;
  courses_detail: CourseDetail[];
  ai_summary: string;
  student_name: string;
};

type Props = {
  onCoursesDetected: (codes: string[]) => void;
  onInProgressDetected?: (codes: string[]) => void;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function StatusBadge({ course }: { course: CourseDetail }) {
  if (course.is_in_progress) {
    return (
      <span style={{
        background: "#fef3c7", color: "#92400e",
        padding: "2px 8px", borderRadius: "999px", fontSize: "11px", fontWeight: 600,
      }}>In Progress</span>
    );
  }
  if (course.is_transfer) {
    return (
      <span style={{
        background: "#dbeafe", color: "#1e40af",
        padding: "2px 8px", borderRadius: "999px", fontSize: "11px", fontWeight: 600,
      }}>Transfer</span>
    );
  }
  if (course.failed) {
    return (
      <span style={{
        background: "#fee2e2", color: "#991b1b",
        padding: "2px 8px", borderRadius: "999px", fontSize: "11px", fontWeight: 600,
      }}>Failed</span>
    );
  }
  if (course.passed) {
    return (
      <span style={{
        background: "#dcfce7", color: "#166534",
        padding: "2px 8px", borderRadius: "999px", fontSize: "11px", fontWeight: 600,
      }}>Passed</span>
    );
  }
  return null;
}

export default function TranscriptUpload({ onCoursesDetected, onInProgressDetected }: Props) {
  const [phase, setPhase] = useState<"idle" | "analyzing" | "done" | "error">("idle");
  const [progress, setProgress] = useState(0);
  const [showResults, setShowResults] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [result, setResult] = useState<TranscriptResult | null>(null);
  const [tableExpanded, setTableExpanded] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function startProgressBar() {
    setProgress(0);
    setShowResults(false);

    // Tick up to ~85% over 8 seconds — simulates Claude processing time
    const totalTicks = 80;
    const targetPct = 85;
    const intervalMs = (8000 / totalTicks);

    intervalRef.current = setInterval(() => {
      setProgress(prev => {
        if (prev >= targetPct) {
          clearInterval(intervalRef.current!);
          return prev;
        }
        // Ease-out: slower as it approaches the target
        const remaining = targetPct - prev;
        const step = Math.max(0.3, remaining * 0.06);
        return Math.min(targetPct, prev + step);
      });
    }, intervalMs);
  }

  function finishProgressBar(onDone: () => void) {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setProgress(100);
    setTimeout(onDone, 600);
  }

  // Cleanup interval on unmount
  useEffect(() => () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
  }, []);

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setPhase("error");
      setErrorMsg("Please upload a PDF file.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setPhase("error");
      setErrorMsg("File is too large. Maximum size is 10 MB.");
      return;
    }

    setPhase("analyzing");
    setErrorMsg("");
    setResult(null);
    startProgressBar();

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(`${apiBase}/parse-transcript`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        finishProgressBar(() => {
          setPhase("error");
          setErrorMsg(err.detail ?? "Failed to parse transcript.");
        });
        return;
      }

      const data: TranscriptResult = await res.json();

      finishProgressBar(() => {
        setResult(data);
        setPhase("done");
        setShowResults(true);
        onCoursesDetected(data.matched);
        if (data.in_progress?.length && onInProgressDetected) {
          onInProgressDetected(data.in_progress);
        }
      });
    } catch {
      finishProgressBar(() => {
        setPhase("error");
        setErrorMsg("Network error — could not reach the server.");
      });
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  // Group courses by semester for the table
  const bySemester: Record<string, CourseDetail[]> = {};
  if (result?.courses_detail) {
    for (const c of result.courses_detail) {
      const key = c.semester || "Unknown";
      if (!bySemester[key]) bySemester[key] = [];
      bySemester[key].push(c);
    }
  }

  const transferCourses = result?.courses_detail.filter(c => c.is_transfer) ?? [];
  const totalCourses = result?.courses_detail.length ?? 0;

  return (
    <div style={{ marginBottom: "12px" }}>
      {/* Drop zone — hide once done */}
      {phase !== "done" && (
        <div
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => phase === "idle" && inputRef.current?.click()}
          style={{
            border: "2px dashed #d1d5db",
            borderRadius: "8px",
            padding: "16px",
            textAlign: "center",
            cursor: phase === "idle" ? "pointer" : "default",
            background: phase === "analyzing" ? "#f9fafb" : "transparent",
            transition: "background 0.15s",
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            style={{ display: "none" }}
            onChange={handleChange}
          />
          <p style={{ margin: 0, fontSize: "13px", color: "#6b7280" }}>
            {phase === "analyzing"
              ? "Analyzing transcript with AI…"
              : "📄 Upload Rutgers transcript PDF (drag & drop or click)"}
          </p>
        </div>
      )}

      {/* Progress bar */}
      {(phase === "analyzing" || (phase === "done" && progress < 100)) && (
        <div style={{ marginTop: "10px" }}>
          <div style={{
            display: "flex", justifyContent: "space-between",
            fontSize: "11px", color: "#6b7280", marginBottom: "4px",
          }}>
            <span>
              {progress < 30 ? "Reading transcript…"
                : progress < 60 ? "Identifying courses…"
                : progress < 85 ? "Matching Rutgers equivalents…"
                : "Finalizing…"}
            </span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div style={{
            height: "6px", background: "#e5e7eb", borderRadius: "999px", overflow: "hidden",
          }}>
            <div style={{
              height: "100%",
              width: `${progress}%`,
              background: "linear-gradient(90deg, #cc0033, #e8003d)",
              borderRadius: "999px",
              transition: "width 0.25s ease-out",
            }} />
          </div>
        </div>
      )}

      {/* Error */}
      {phase === "error" && (
        <p style={{ fontSize: "12px", marginTop: "6px", color: "#b91c1c" }}>
          {errorMsg}
        </p>
      )}

      {/* Results panel */}
      {showResults && result && (
        <div style={{ marginTop: "14px" }}>

          {/* Re-upload link */}
          <div style={{ marginBottom: "10px" }}>
            <button
              onClick={() => {
                setPhase("idle");
                setShowResults(false);
                setResult(null);
                setProgress(0);
              }}
              style={{
                background: "none", border: "none", padding: 0,
                fontSize: "11px", color: "#6b7280", cursor: "pointer",
                textDecoration: "underline",
              }}
            >
              Upload a different transcript
            </button>
          </div>

          {/* AI Summary card */}
          {result.ai_summary && (
            <div style={{
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
              padding: "12px 14px",
              marginBottom: "12px",
            }}>
              <div style={{ fontSize: "10px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
                AI Summary
              </div>
              <p style={{ margin: 0, fontSize: "12px", color: "#374151", lineHeight: 1.6, fontStyle: "italic" }}>
                {result.ai_summary}
              </p>
            </div>
          )}

          {/* Transfer equivalencies */}
          {transferCourses.length > 0 && (
            <div style={{
              background: "#eff6ff",
              border: "1px solid #bfdbfe",
              borderRadius: "8px",
              padding: "12px 14px",
              marginBottom: "12px",
            }}>
              <div style={{ fontSize: "10px", fontWeight: 700, color: "#1e40af", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" }}>
                Transfer Credits ({transferCourses.length})
              </div>
              {transferCourses.map((c, i) => (
                <div key={i} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "flex-start",
                  padding: "6px 0",
                  borderTop: i > 0 ? "1px solid #dbeafe" : "none",
                  gap: "8px",
                }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "12px", fontWeight: 500, color: "#1e3a8a" }}>{c.title_raw}</div>
                    {c.equivalency_note && (
                      <div style={{ fontSize: "11px", color: "#3b82f6", marginTop: "2px" }}>{c.equivalency_note}</div>
                    )}
                  </div>
                  <div style={{ flexShrink: 0, textAlign: "right" }}>
                    {c.rutgers_code
                      ? <span style={{ fontSize: "12px", fontWeight: 700, color: "#1e40af" }}>→ {c.rutgers_code}</span>
                      : <span style={{ fontSize: "11px", color: "#9ca3af" }}>No match found</span>
                    }
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Course table toggle */}
          <div>
            <button
              onClick={() => setTableExpanded(prev => !prev)}
              style={{
                background: "none", border: "1px solid #e5e7eb",
                borderRadius: "6px", padding: "6px 12px",
                fontSize: "12px", color: "#374151", cursor: "pointer",
                width: "100%", textAlign: "left",
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}
            >
              <span>All courses ({totalCourses})</span>
              <span style={{ fontSize: "10px", color: "#9ca3af" }}>{tableExpanded ? "▲ Hide" : "▼ Show"}</span>
            </button>

            {tableExpanded && (
              <div style={{ marginTop: "8px", overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11px" }}>
                  <thead>
                    <tr style={{ background: "#f9fafb", borderBottom: "1px solid #e5e7eb" }}>
                      <th style={{ padding: "6px 8px", textAlign: "left", color: "#6b7280", fontWeight: 600 }}>Semester</th>
                      <th style={{ padding: "6px 8px", textAlign: "left", color: "#6b7280", fontWeight: 600 }}>Course</th>
                      <th style={{ padding: "6px 8px", textAlign: "left", color: "#6b7280", fontWeight: 600 }}>Code</th>
                      <th style={{ padding: "6px 8px", textAlign: "center", color: "#6b7280", fontWeight: 600 }}>Credits</th>
                      <th style={{ padding: "6px 8px", textAlign: "center", color: "#6b7280", fontWeight: 600 }}>Grade</th>
                      <th style={{ padding: "6px 8px", textAlign: "center", color: "#6b7280", fontWeight: 600 }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(bySemester).map(([semester, courses]) =>
                      courses.map((c, idx) => (
                        <tr key={`${semester}-${idx}`} style={{ borderBottom: "1px solid #f3f4f6" }}>
                          <td style={{ padding: "5px 8px", color: "#6b7280" }}>
                            {idx === 0 ? semester : ""}
                          </td>
                          <td style={{ padding: "5px 8px", color: "#111827", fontWeight: 500 }}>{c.title_raw}</td>
                          <td style={{ padding: "5px 8px", color: "#374151" }}>{c.rutgers_code ?? "—"}</td>
                          <td style={{ padding: "5px 8px", textAlign: "center", color: "#374151" }}>{c.credits}</td>
                          <td style={{ padding: "5px 8px", textAlign: "center", color: "#374151", fontWeight: 600 }}>
                            {c.grade || "—"}
                          </td>
                          <td style={{ padding: "5px 8px", textAlign: "center" }}>
                            <StatusBadge course={c} />
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
