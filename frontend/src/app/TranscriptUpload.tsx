"use client";

import { useState, useRef } from "react";

type Props = {
  onCoursesDetected: (codes: string[]) => void;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function TranscriptUpload({ onCoursesDetected }: Props) {
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setStatus("error");
      setMessage("Please upload a PDF file.");
      return;
    }

    setStatus("uploading");
    setMessage("Parsing transcript…");

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

      const codes: string[] = await res.json();
      if (codes.length === 0) {
        setStatus("done");
        setMessage("No course codes detected. You can add them manually below.");
        return;
      }

      onCoursesDetected(codes);
      setStatus("done");
      setMessage(`Detected ${codes.length} course(s) from transcript. Review and remove any errors below.`);
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
        <p
          style={{
            fontSize: "12px",
            marginTop: "6px",
            color: status === "error" ? "#b91c1c" : status === "done" ? "#15803d" : "#6b7280",
          }}
        >
          {message}
        </p>
      )}
    </div>
  );
}
