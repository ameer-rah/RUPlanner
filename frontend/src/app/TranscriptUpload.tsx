"use client";

import { useState, useRef } from "react";

type TranscriptResult = {
  matched: string[];
  in_progress: string[];
  inferred: Record<string, string>;
};

type Props = {
  onCoursesDetected: (codes: string[]) => void;
  onInProgressDetected?: (codes: string[]) => void;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function TranscriptUpload({ onCoursesDetected, onInProgressDetected }: Props) {
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const [inferred, setInferred] = useState<Record<string, string>>({});
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setStatus("error");
      setMessage("Please upload a PDF file.");
      return;
    }

    const MAX_SIZE_MB = 10;
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setStatus("error");
      setMessage(`File is too large. Maximum size is ${MAX_SIZE_MB} MB.`);
      return;
    }

    setStatus("uploading");
    setMessage("Parsing transcript…");
    setInferred({});

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(`${apiBase}/parse-transcript`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        setStatus("error");
        setMessage(`Error: ${err.detail ?? "Failed to parse transcript."}`);
        return;
      }

      const data: TranscriptResult = await res.json();
      const { matched, in_progress: inProg, inferred: inf } = data;

      if (matched.length === 0 && (inProg ?? []).length === 0) {
        setStatus("done");
        setMessage("No course codes detected. You can add them manually below.");
        return;
      }

      onCoursesDetected(matched);
      if (inProg?.length && onInProgressDetected) onInProgressDetected(inProg);
      setInferred(inf ?? {});
      const inferredCount = Object.keys(inf ?? {}).length;
      const ipCount = inProg?.length ?? 0;
      setStatus("done");
      setMessage(
        `Detected ${matched.length} completed course(s)` +
        (ipCount > 0 ? ` + ${ipCount} in-progress` : "") +
        " from transcript." +
        (inferredCount > 0 ? ` ${inferredCount} transfer credit${inferredCount > 1 ? "s" : ""} auto-matched.` : "") +
        " Review and remove any errors below."
      );
    } catch {
      setStatus("error");
      setMessage("Network error — could not reach the server.");
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

  const inferredEntries = Object.entries(inferred);

  return (
    <div style={{ marginBottom: "12px" }}>
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: "2px dashed #d1d5db",
          borderRadius: "8px",
          padding: "16px",
          textAlign: "center",
          cursor: "pointer",
          background: status === "uploading" ? "#f9fafb" : "transparent",
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
          {status === "uploading"
            ? "⏳ Parsing…"
            : "📄 Upload Rutgers transcript PDF (drag & drop or click)"}
        </p>
      </div>

      {message && (
        <p style={{
          fontSize: "12px",
          marginTop: "6px",
          color: status === "error" ? "#b91c1c" : status === "done" ? "#15803d" : "#6b7280",
        }}>
          {message}
        </p>
      )}

      {inferredEntries.length > 0 && (
        <div style={{
          marginTop: "8px",
          padding: "8px 10px",
          background: "#eff6ff",
          border: "1px solid #bfdbfe",
          borderRadius: "6px",
          fontSize: "11px",
          color: "#1d4ed8",
        }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Transfer credits auto-matched:</div>
          {inferredEntries.map(([rutgersCode, label]) => (
            <div key={rutgersCode} style={{ marginTop: 2 }}>
              {label} → <strong>{rutgersCode}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
