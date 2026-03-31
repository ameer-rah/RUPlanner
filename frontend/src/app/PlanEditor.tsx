"use client";

import { useState, useRef, useMemo, useEffect } from "react";
import { getRegistrarCode, getCoursiclUrl } from "./registrar";

export type ElectiveOption = {
  code: string;
  title: string;
  credits: number;
  prerequisites: string[];
};

export type PlannedCourse = {
  code: string;
  title: string;
  credits: number;
  is_elective: boolean;
  prerequisites: string[];
  elective_options: ElectiveOption[];
};

export type PlanTerm = {
  term: string;
  courses: PlannedCourse[];
  total_credits: number;
};

type Props = {
  initialTerms: PlanTerm[];
  completedCourses: string[];
  onTermsChange: (terms: PlanTerm[]) => void;
};

function getTermClass(term: string) {
  if (term.includes("Fall")) return "plan-term term-fall";
  if (term.includes("Spring")) return "plan-term term-spring";
  if (term.includes("Summer")) return "plan-term term-summer";
  if (term.includes("Winter")) return "plan-term term-winter";
  return "plan-term";
}

// ── Elective Picker Modal ───────────────────────────────────────────────────

function ElectivePicker({
  course,
  onSelect,
  onClose,
}: {
  course: PlannedCourse;
  onSelect: (opt: ElectiveOption) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return course.elective_options.filter(
      (o) =>
        o.code.toLowerCase().includes(q) || o.title.toLowerCase().includes(q)
    );
  }, [course.elective_options, query]);

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="elective-modal" onClick={(e) => e.stopPropagation()}>
        <div className="elective-modal-header">
          <div>
            <div className="elective-modal-title">Choose an Elective</div>
            <div className="elective-modal-sub">
              Currently: <strong>{course.code}</strong> — {course.title}
            </div>
          </div>
          <button className="elective-modal-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="elective-modal-search">
          <input
            autoFocus
            placeholder="Search by code or title…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="elective-options-list">
          {filtered.length === 0 ? (
            <div style={{ padding: "20px", textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
              No courses match your search.
            </div>
          ) : (
            filtered.map((opt) => (
              <button
                key={opt.code}
                className="elective-option-row"
                onClick={() => onSelect(opt)}
              >
                <div className="elective-option-code">{opt.code}</div>
                <div className="elective-option-meta">
                  {opt.title} · {opt.credits} cr
                  {opt.prerequisites.length > 0 && (
                    <span style={{ marginLeft: 6, color: "#b45309" }}>
                      · prereqs: {opt.prerequisites.join(", ")}
                    </span>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// ── Add Course Form ──────────────────────────────────────────────────────────

function AddCourseForm({
  onAdd,
  onClose,
}: {
  onAdd: (course: PlannedCourse) => void;
  onClose: () => void;
}) {
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [credits, setCredits] = useState("3");
  const [error, setError] = useState("");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = code.trim().toUpperCase();
    if (!trimmed) { setError("Course code is required."); return; }
    const cr = parseFloat(credits);
    if (isNaN(cr) || cr <= 0) { setError("Credits must be a positive number."); return; }
    onAdd({
      code: trimmed,
      title: title.trim() || trimmed,
      credits: cr,
      is_elective: false,
      prerequisites: [],
      elective_options: [],
    });
  }

  return (
    <div className="add-course-form">
      <form onSubmit={handleSubmit}>
        <div className="add-course-row">
          <input
            autoFocus
            className="add-course-input add-course-code"
            placeholder="Code (e.g. CS 111)"
            value={code}
            onChange={(e) => { setCode(e.target.value); setError(""); }}
          />
          <input
            className="add-course-input add-course-title"
            placeholder="Title (optional)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <input
            className="add-course-input add-course-credits"
            placeholder="Cr"
            value={credits}
            type="number"
            min="0.5"
            max="6"
            step="0.5"
            onChange={(e) => setCredits(e.target.value)}
          />
          <button type="submit" className="add-course-confirm-btn">Add</button>
          <button type="button" className="add-course-cancel-btn" onClick={onClose}>✕</button>
        </div>
        {error && <div className="add-course-error">{error}</div>}
      </form>
    </div>
  );
}

// ── Main PlanEditor ─────────────────────────────────────────────────────────

export default function PlanEditor({ initialTerms, completedCourses, onTermsChange }: Props) {
  const [terms, setTerms] = useState<PlanTerm[]>(initialTerms);

  // drag state
  const draggingRef = useRef<{
    course: PlannedCourse;
    fromTermIdx: number;
    fromCourseIdx: number;
  } | null>(null);
  const [dragOverTermIdx, setDragOverTermIdx] = useState<number | null>(null);
  const [dropValid, setDropValid] = useState(true);
  const [dragError, setDragError] = useState<string | null>(null);

  // elective picker
  const [picker, setPicker] = useState<{
    termIdx: number;
    courseIdx: number;
    course: PlannedCourse;
  } | null>(null);

  // add-course form — which term is open
  const [addingToTerm, setAddingToTerm] = useState<number | null>(null);

  const completedSet = useMemo(
    () => new Set(completedCourses.map((c) => c.toUpperCase())),
    [completedCourses]
  );

  // Notify parent whenever terms change
  useEffect(() => {
    onTermsChange(terms);
  }, [terms, onTermsChange]);

  // ── Prerequisite validation ─────────────────────────────────────────────

  const TERM_CREDIT_LIMITS: Record<string, number> = {
    Fall: 20, Spring: 20, Summer: 12, Winter: 4,
  };

  function validateDrop(
    course: PlannedCourse,
    toTermIdx: number,
    currentTerms: PlanTerm[],
    fromTermIdx: number
  ): string | null {
    if (fromTermIdx === toTermIdx) return null; // same term, just reorder — always fine

    // Rule 0: credit limit for destination term
    const toTerm = currentTerms[toTermIdx];
    const season = toTerm.term.split(" ")[0];
    const limit = TERM_CREDIT_LIMITS[season];
    if (limit !== undefined) {
      const newTotal = toTerm.total_credits + course.credits;
      if (newTotal > limit) {
        return `${toTerm.term} would reach ${newTotal} cr — the ${season} semester limit is ${limit} credits.`;
      }
    }

    // Rule 1: every prereq of `course` must be completed or in a term BEFORE toTermIdx
    for (const prereq of course.prerequisites) {
      if (completedSet.has(prereq)) continue;
      const prereqTermIdx = currentTerms.findIndex((t) =>
        t.courses.some((c) => c.code === prereq)
      );
      if (prereqTermIdx === -1 || prereqTermIdx >= toTermIdx) {
        return `Cannot place here — ${prereq} (prerequisite) must be in an earlier term.`;
      }
    }

    // Rule 2: no course in terms[0..toTermIdx] should list `course` as a prereq
    for (let i = 0; i <= toTermIdx; i++) {
      if (i === fromTermIdx) continue; // source term will lose this course
      for (const c of currentTerms[i].courses) {
        if (c.code === course.code) continue;
        if (c.prerequisites.includes(course.code)) {
          return `Cannot place here — ${c.code} in ${currentTerms[i].term} requires ${course.code} as a prerequisite.`;
        }
      }
    }

    return null;
  }

  // ── Drag handlers ───────────────────────────────────────────────────────

  function handleDragStart(
    course: PlannedCourse,
    termIdx: number,
    courseIdx: number
  ) {
    draggingRef.current = { course, fromTermIdx: termIdx, fromCourseIdx: courseIdx };
  }

  function handleDragEnter(toTermIdx: number) {
    if (!draggingRef.current) return;
    const { course, fromTermIdx } = draggingRef.current;
    const error = validateDrop(course, toTermIdx, terms, fromTermIdx);
    setDragOverTermIdx(toTermIdx);
    setDropValid(!error);
    setDragError(error);
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
  }

  function handleDragLeave(e: React.DragEvent, termIdx: number) {
    if ((e.currentTarget as HTMLElement).contains(e.relatedTarget as Node)) return;
    if (dragOverTermIdx === termIdx) {
      setDragOverTermIdx(null);
      setDragError(null);
    }
  }

  function handleDrop(e: React.DragEvent, toTermIdx: number) {
    e.preventDefault();
    setDragOverTermIdx(null);

    if (!draggingRef.current) return;
    const { course, fromTermIdx, fromCourseIdx } = draggingRef.current;
    draggingRef.current = null;

    const error = validateDrop(course, toTermIdx, terms, fromTermIdx);
    if (error) {
      setDragError(error);
      setTimeout(() => setDragError(null), 4000);
      return;
    }

    setTerms((prev) => {
      const next = prev.map((t) => ({ ...t, courses: [...t.courses] }));
      // Remove from source
      next[fromTermIdx].courses.splice(fromCourseIdx, 1);
      next[fromTermIdx].total_credits -= course.credits;
      // Append to destination
      next[toTermIdx].courses.push(course);
      next[toTermIdx].total_credits += course.credits;
      return next;
    });
    setDragError(null);
  }

  function handleDragEnd() {
    draggingRef.current = null;
    setDragOverTermIdx(null);
    setDropValid(true);
    setDragError(null);
  }

  // ── Elective swap ───────────────────────────────────────────────────────

  function handleElectiveSelect(termIdx: number, courseIdx: number, opt: ElectiveOption) {
    setTerms((prev) => {
      const next = prev.map((t) => ({ ...t, courses: [...t.courses] }));
      const old = next[termIdx].courses[courseIdx];

      // Build updated options: remove chosen, add back the old course
      const updatedOptions: ElectiveOption[] = [
        ...old.elective_options.filter((o) => o.code !== opt.code),
        { code: old.code, title: old.title, credits: old.credits, prerequisites: old.prerequisites },
      ];

      const newCourse: PlannedCourse = {
        code: opt.code,
        title: opt.title,
        credits: opt.credits,
        is_elective: true,
        prerequisites: opt.prerequisites,
        elective_options: updatedOptions,
      };

      next[termIdx].courses[courseIdx] = newCourse;
      next[termIdx].total_credits =
        next[termIdx].total_credits - old.credits + newCourse.credits;
      return next;
    });
    setPicker(null);
  }

  // ── Delete / Add course ─────────────────────────────────────────────────

  function handleDeleteCourse(termIdx: number, courseIdx: number) {
    setTerms((prev) => {
      const next = prev.map((t) => ({ ...t, courses: [...t.courses] }));
      const removed = next[termIdx].courses.splice(courseIdx, 1)[0];
      next[termIdx].total_credits -= removed.credits;
      return next;
    });
  }

  function handleAddCourse(termIdx: number, course: PlannedCourse) {
    setTerms((prev) => {
      const next = prev.map((t) => ({ ...t, courses: [...t.courses] }));
      next[termIdx].courses.push(course);
      next[termIdx].total_credits += course.credits;
      return next;
    });
    setAddingToTerm(null);
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <>
      {dragError && <div className="drag-error-toast">⚠ {dragError}</div>}

      <div className="plan-grid">
        {terms.map((term, termIdx) => {
          const isDragOver = dragOverTermIdx === termIdx;
          const dropClass = isDragOver
            ? dropValid
              ? " drop-valid"
              : " drop-invalid"
            : "";

          return (
            <div
              key={term.term}
              className={getTermClass(term.term) + dropClass}
              onDragOver={handleDragOver}
              onDragEnter={() => handleDragEnter(termIdx)}
              onDragLeave={(e) => handleDragLeave(e, termIdx)}
              onDrop={(e) => handleDrop(e, termIdx)}
            >
              <div className="plan-term-header">
                <strong>{term.term}</strong>
                <span className="credits-badge">{term.total_credits} cr</span>
              </div>

              <div className="plan-course-list">
                {term.courses.map((course, courseIdx) => (
                  <div
                    key={course.code}
                    className={`plan-course${course.is_elective ? " elective" : ""} draggable-course`}
                    draggable
                    onDragStart={() => handleDragStart(course, termIdx, courseIdx)}
                    onDragEnd={handleDragEnd}
                  >
                    <div className="plan-course-header">
                      <span className="drag-handle" title="Drag to move">⠿</span>
                      <a
                        className="plan-course-code"
                        href={getCoursiclUrl(course.code) ?? undefined}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        title={getRegistrarCode(course.code) ?? course.code}
                      >
                        {course.code}
                      </a>
                      {course.is_elective && (
                        <span className="elective-badge">ELECTIVE</span>
                      )}
                      <button
                        className="course-delete-btn"
                        title="Remove course"
                        onClick={() => handleDeleteCourse(termIdx, courseIdx)}
                      >
                        ×
                      </button>
                    </div>
                    <div className="plan-course-meta">
                      {course.title} · {course.credits} cr
                    </div>
                    {course.prerequisites.length > 0 && (
                      <div className="plan-course-prereqs">
                        Prereqs: {course.prerequisites.join(", ")}
                      </div>
                    )}
                    {course.is_elective && course.elective_options.length > 0 && (
                      <button
                        className="elective-swap-btn"
                        onClick={() => setPicker({ termIdx, courseIdx, course })}
                      >
                        Swap · {course.elective_options.length} options
                      </button>
                    )}
                  </div>
                ))}

                {term.courses.length === 0 && addingToTerm !== termIdx && (
                  <div className="empty-term-hint">Drop a course here</div>
                )}

                {addingToTerm === termIdx ? (
                  <AddCourseForm
                    onAdd={(course) => handleAddCourse(termIdx, course)}
                    onClose={() => setAddingToTerm(null)}
                  />
                ) : (
                  <button
                    className="add-course-btn"
                    onClick={() => setAddingToTerm(termIdx)}
                  >
                    + Add course
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {picker && (
        <ElectivePicker
          course={picker.course}
          onSelect={(opt) => handleElectiveSelect(picker.termIdx, picker.courseIdx, opt)}
          onClose={() => setPicker(null)}
        />
      )}
    </>
  );
}