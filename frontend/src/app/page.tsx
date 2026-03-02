"use client";

import { useState, useEffect } from "react";
import CompletedCoursesInput from "./CompletedCoursesInput";

type ProgramInfo = {
  school: string;
  degree_level: string;
  major_name: string;
  catalog_year: string;
  display_name: string;
};

type PlannedCourse = {
  code: string;
  title: string;
  credits: number;
  is_elective: boolean;
  elective_options: string[];
};

type PlanTerm = {
  term: string;
  courses: PlannedCourse[];
  total_credits: number;
};

type PlanResponse = {
  terms: PlanTerm[];
  remaining_courses: string[];
  warnings: string[];
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [degreeLevel, setDegreeLevel] = useState("Bachelor");
  const [majors, setMajors] = useState("Computer Science (BS, SAS)");
  const [minors, setMinors] = useState("");
  const [completedCourses, setCompletedCourses] = useState<string[]>([]);
  const [targetGradTerm, setTargetGradTerm] = useState("Spring 2028");
  const [maxCredits, setMaxCredits] = useState(15);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [status, setStatus] = useState("");
  const [programs, setPrograms] = useState<ProgramInfo[]>([]);

  useEffect(() => {
    fetch(`${apiBase}/programs`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data: ProgramInfo[]) => setPrograms(data))
      .catch(() => {});
  }, []);

  const majorPrograms = programs.filter((p) => p.degree_level !== "minor");
  const minorPrograms = programs.filter((p) => p.degree_level === "minor");

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setStatus("Generating plan...");
    const payload = {
      degree_level: degreeLevel,
      majors: majors.split(",").map((item) => item.trim()).filter(Boolean),
      minors: minors.split(",").map((item) => item.trim()).filter(Boolean),
      completed_courses: completedCourses,
      target_grad_term: targetGradTerm,
      max_credits_per_term: maxCredits,
    };

    const res = await fetch(`${apiBase}/plan`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Unknown error" }));
      setStatus(`Error: ${err.detail ?? "Failed to generate plan."}`);
      return;
    }

    const data = (await res.json()) as PlanResponse;
    setPlan(data);
    setStatus("Plan generated.");
  }

  return (
    <main className="container">
      <h1>RU Planner</h1>
      <p className="muted">Pick your degree, program, and completed courses to generate a plan.</p>
      <form className="form" onSubmit={handleSubmit}>
        <label className="label" htmlFor="degreeLevel">
          Degree level
        </label>
        <select
          id="degreeLevel"
          className="input"
          value={degreeLevel}
          onChange={(event) => setDegreeLevel(event.target.value)}
        >
          <option>Associate</option>
          <option>Bachelor</option>
          <option>Master</option>
        </select>

        <label className="label" htmlFor="majors">
          Major(s) — comma-separate for dual major
        </label>
        <input
          id="majors"
          className="input"
          value={majors}
          onChange={(event) => setMajors(event.target.value)}
          list="majorOptions"
        />
        <datalist id="majorOptions">
          {majorPrograms.map((p) => (
            <option key={p.display_name} value={p.display_name} />
          ))}
        </datalist>

        <label className="label" htmlFor="minors">
          Minor(s) — comma-separate for multiple
        </label>
        <input
          id="minors"
          className="input"
          value={minors}
          onChange={(event) => setMinors(event.target.value)}
          list="minorOptions"
        />
        <datalist id="minorOptions">
          {minorPrograms.map((p) => (
            <option key={p.display_name} value={p.display_name} />
          ))}
        </datalist>

        <label className="label">
          Completed courses
        </label>
        <CompletedCoursesInput value={completedCourses} onChange={setCompletedCourses} />

        <label className="label" htmlFor="targetGradTerm">
          Target graduation term
        </label>
        <input
          id="targetGradTerm"
          className="input"
          value={targetGradTerm}
          onChange={(event) => setTargetGradTerm(event.target.value)}
        />

        <label className="label" htmlFor="maxCredits">
          Max credits per term
        </label>
        <input
          id="maxCredits"
          className="input"
          type="number"
          min={6}
          max={21}
          value={maxCredits}
          onChange={(event) => setMaxCredits(Number(event.target.value))}
        />

        <button className="primary-button" type="submit">
          Generate my plan
        </button>
        {status ? <p className="muted">{status}</p> : null}
      </form>

      {plan ? (
        <section className="plan-grid">
          {completedCourses.length > 0 && (
            <div className="plan-completed">
              <strong>Completed courses applied ({completedCourses.length})</strong>
              <div className="plan-completed-chips">
                {completedCourses.map((code) => (
                  <span key={code} className="plan-completed-chip">{code}</span>
                ))}
              </div>
            </div>
          )}

          {plan.warnings.length > 0 ? (
            <div className="plan-warning">
              <strong>Notes</strong>
              <ul>
                {plan.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {plan.remaining_courses.length > 0 ? (
            <div
              className="plan-warning"
              style={{ borderColor: "#fca5a5", background: "#fff1f2", color: "#991b1b" }}
            >
              <strong>Could not schedule before graduation</strong>
              <ul>
                {plan.remaining_courses.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {plan.terms.map((term) => (
            <div key={term.term} className="plan-term">
              <div className="plan-term-header">
                <strong>{term.term}</strong>
                <span>{term.total_credits} credits</span>
              </div>
              <div className="plan-course-list">
                {term.courses.map((course) => (
                  <div
                    key={course.code}
                    className="plan-course"
                    style={course.is_elective ? { borderLeft: "3px solid #f59e0b" } : undefined}
                  >
                    <div className="plan-course-title" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      {course.code}
                      {course.is_elective && (
                        <span style={{
                          fontSize: "10px",
                          fontWeight: 600,
                          background: "#fef3c7",
                          color: "#92400e",
                          padding: "1px 5px",
                          borderRadius: "4px",
                          letterSpacing: "0.03em",
                        }}>
                          ELECTIVE
                        </span>
                      )}
                    </div>
                    <div className="plan-course-meta">
                      {course.title} · {course.credits} credits
                    </div>
                    {course.is_elective && course.elective_options.length > 0 && (
                      <details style={{ marginTop: "4px" }}>
                        <summary style={{ fontSize: "11px", color: "#6b7280", cursor: "pointer" }}>
                          Swap — {course.elective_options.length} options available
                        </summary>
                        <div style={{ fontSize: "11px", color: "#6b7280", marginTop: "4px", lineHeight: 1.6 }}>
                          {course.elective_options.join(" · ")}
                        </div>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      ) : null}
    </main>
  );
}
