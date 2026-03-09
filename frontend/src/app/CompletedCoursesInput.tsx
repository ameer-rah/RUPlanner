"use client";

import { useState, useEffect, useRef, useCallback, KeyboardEvent } from "react";
import { registrarToShortCode } from "./registrar";

type CourseSearchResult = {
  code: string;
  title: string;
  credits: number;
};

type Props = {
  value: string[];
  onChange: (codes: string[]) => void;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function CompletedCoursesInput({ value, onChange }: Props) {
  const [inputValue, setInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<CourseSearchResult[]>([]);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
        setActiveIdx(-1);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const fetchSuggestions = useCallback((q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setSuggestions([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `${apiBase}/courses?q=${encodeURIComponent(q.trim())}&limit=12`
        );
        if (res.ok) {
          const data: CourseSearchResult[] = await res.json();
          // Filter out already-added courses
          setSuggestions(data.filter((c) => !value.includes(c.code)));
          setActiveIdx(-1);
        }
      } catch {
        setSuggestions([]);
      } finally {
        setLoading(false);
      }
    }, 200);
  }, [value]);

  useEffect(() => {
    fetchSuggestions(inputValue);
  }, [inputValue, fetchSuggestions]);

  function addCode(code: string) {
    const raw = code.trim().toUpperCase();
    // If the user typed a registrar code like "01:198:111", convert it to "CS111"
    const upper = registrarToShortCode(raw) ?? raw;
    if (!upper || value.includes(upper)) {
      setInputValue("");
      setSuggestions([]);
      setOpen(false);
      return;
    }
    onChange([...value, upper]);
    setInputValue("");
    setSuggestions([]);
    setActiveIdx(-1);
    setOpen(false);
    inputRef.current?.focus();
  }

  function removeCode(code: string) {
    onChange(value.filter((c) => c !== code));
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, -1));
      return;
    }
    if (e.key === "Escape") {
      setOpen(false);
      setActiveIdx(-1);
      return;
    }
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      if (activeIdx >= 0 && suggestions[activeIdx]) {
        addCode(suggestions[activeIdx].code);
      } else if (inputValue.trim()) {
        addCode(inputValue);
      }
      return;
    }
    if (e.key === "Backspace" && inputValue === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  const showDropdown = open && inputValue.trim().length > 0;

  return (
    <div
      ref={wrapperRef}
      className="chip-input-wrapper"
      style={{ position: "relative" }}
      onClick={() => inputRef.current?.focus()}
    >
      {value.map((code) => (
        <span key={code} className="chip">
          {code}
          <button
            type="button"
            className="chip-remove"
            onClick={(e) => {
              e.stopPropagation();
              removeCode(code);
            }}
            aria-label={`Remove ${code}`}
          >
            ×
          </button>
        </span>
      ))}

      <input
        ref={inputRef}
        className="chip-text-input"
        type="text"
        placeholder={value.length === 0 ? "Search by code or name…" : "Add another…"}
        value={inputValue}
        onChange={(e) => {
          setInputValue(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        autoComplete="off"
        spellCheck={false}
      />

      {showDropdown && (
        <div className="chip-suggestions">
          {loading ? (
            <div className="program-select-empty">Searching…</div>
          ) : suggestions.length === 0 ? (
            <div className="program-select-empty">
              No courses found — press Enter to add &ldquo;{inputValue.trim().toUpperCase()}&rdquo; manually.
            </div>
          ) : (
            suggestions.map((s, idx) => (
              <div
                key={s.code}
                className={`chip-suggestion-item${idx === activeIdx ? " chip-suggestion-active" : ""}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  addCode(s.code);
                }}
                onMouseEnter={() => setActiveIdx(idx)}
              >
                <span className="chip-suggestion-code">{s.code}</span>
                <span className="chip-suggestion-title">
                  {s.title} · {s.credits} cr
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
