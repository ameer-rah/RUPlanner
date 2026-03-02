"use client";

import { useState, useEffect, useRef, useCallback, KeyboardEvent } from "react";

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

// Matches patterns like CS111, MATH151, PHYS203, COMPLIT201
const COURSE_CODE_RE = /^[A-Z]{2,8}\d{2,4}[A-Z]?$/i;

export default function CompletedCoursesInput({ value, onChange }: Props) {
  const [inputValue, setInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<CourseSearchResult[]>([]);
  const [activeIdx, setActiveIdx] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch suggestions with 250ms debounce
  const fetchSuggestions = useCallback((q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `${apiBase}/courses?q=${encodeURIComponent(q.trim())}&limit=10`
        );
        if (res.ok) {
          const data: CourseSearchResult[] = await res.json();
          setSuggestions(data);
          setActiveIdx(-1);
        }
      } catch {
        setSuggestions([]);
      }
    }, 250);
  }, []);

  useEffect(() => {
    fetchSuggestions(inputValue);
  }, [inputValue, fetchSuggestions]);

  function addCode(raw: string) {
    const code = raw.trim().toUpperCase();
    if (!code) return;
    if (value.includes(code)) {
      setInputValue("");
      setSuggestions([]);
      return;
    }
    onChange([...value, code]);
    setInputValue("");
    setSuggestions([]);
    setActiveIdx(-1);
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
      setSuggestions([]);
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

  const showDropdown = suggestions.length > 0;

  return (
    <div
      className="chip-input-wrapper"
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
        placeholder={value.length === 0 ? "Type a course code, e.g. CS111…" : ""}
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        autoComplete="off"
        spellCheck={false}
      />

      {showDropdown && (
        <div className="chip-suggestions">
          {suggestions.map((s, idx) => (
            <div
              key={s.code}
              className={`chip-suggestion-item${idx === activeIdx ? " chip-suggestion-active" : ""}`}
              onMouseDown={(e) => {
                e.preventDefault(); // keep focus in input
                addCode(s.code);
              }}
              onMouseEnter={() => setActiveIdx(idx)}
            >
              <span className="chip-suggestion-code">{s.code}</span>
              <span className="chip-suggestion-title">
                {s.title} · {s.credits} cr
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
