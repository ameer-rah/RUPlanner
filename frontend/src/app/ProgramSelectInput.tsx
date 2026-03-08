"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";

type ProgramInfo = {
  school: string;
  degree_level: string;
  major_name: string;
  catalog_year: string;
  display_name: string;
};

type Props = {
  programs: ProgramInfo[];
  value: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
};

export default function ProgramSelectInput({ programs, value, onChange, placeholder }: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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

  const filtered = programs.filter(
    (p) =>
      !value.includes(p.display_name) &&
      (query === "" ||
        p.major_name.toLowerCase().includes(query.toLowerCase()) ||
        p.school.toLowerCase().includes(query.toLowerCase()) ||
        p.display_name.toLowerCase().includes(query.toLowerCase()))
  );

  const grouped: Record<string, ProgramInfo[]> = {};
  for (const p of filtered) {
    if (!grouped[p.school]) grouped[p.school] = [];
    grouped[p.school].push(p);
  }

  const flatFiltered = filtered;

  function select(displayName: string) {
    onChange([...value, displayName]);
    setQuery("");
    setActiveIdx(-1);
    inputRef.current?.focus();
  }

  function remove(displayName: string) {
    onChange(value.filter((v) => v !== displayName));
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, flatFiltered.length - 1));
      setOpen(true);
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
    if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && flatFiltered[activeIdx]) {
        select(flatFiltered[activeIdx].display_name);
      }
      return;
    }
    if (e.key === "Backspace" && query === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div
      ref={wrapperRef}
      className="chip-input-wrapper"
      style={{ position: "relative" }}
      onClick={() => inputRef.current?.focus()}
    >
      {value.map((dn) => (
        <span key={dn} className="chip" title={dn}>
          <span className="chip-label">{dn}</span>
          <button
            type="button"
            className="chip-remove"
            onClick={(e) => {
              e.stopPropagation();
              remove(dn);
            }}
            aria-label={`Remove ${dn}`}
          >
            ×
          </button>
        </span>
      ))}

      <input
        ref={inputRef}
        className="chip-text-input"
        type="text"
        placeholder={value.length === 0 ? (placeholder ?? "Search programs…") : "Add another…"}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActiveIdx(-1);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        autoComplete="off"
        spellCheck={false}
      />

      {open && (
        <div className="chip-suggestions">
          {flatFiltered.length === 0 ? (
            <div className="program-select-empty">
              {query ? "No programs match your search." : "All programs selected."}
            </div>
          ) : (
            Object.entries(grouped).map(([school, schoolPrograms]) => {
              return (
                <div key={school}>
                  <div className="program-select-group-header">{school}</div>
                  {schoolPrograms.map((p) => {
                    const idx = flatFiltered.indexOf(p);
                    return (
                      <div
                        key={p.display_name}
                        className={`chip-suggestion-item${idx === activeIdx ? " chip-suggestion-active" : ""}`}
                        onMouseDown={(e) => {
                          e.preventDefault();
                          select(p.display_name);
                        }}
                        onMouseEnter={() => setActiveIdx(idx)}
                      >
                        <span className="chip-suggestion-code">{p.major_name}</span>
                        <span className="chip-suggestion-title">
                          {p.degree_level} · {p.catalog_year}
                        </span>
                      </div>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
