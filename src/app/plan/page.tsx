"use client";

import { useEffect, useMemo, useState } from "react";

type PlanTerm = {
  term: { year: number; season: string };
  courses: string[];
  credits: number;
};

type PlanResult = {
  terms: PlanTerm[];
  remainingCourses: string[];
  warnings: string[];
};

type PlanPayload = {
  plan: PlanResult;
  programId?: string;
};

type PlanResponse = {
  planId: string | null;
  plan: PlanPayload | null;
  programId?: string;
  courseCredits?: Record<string, number>;
};

type DragPayload = {
  courseId: string;
  fromIndex: number;
};

export default function PlanEditorPage() {
  const [planId, setPlanId] = useState<string | null>(null);
  const [plan, setPlan] = useState<PlanPayload | null>(null);
  const [courseCredits, setCourseCredits] = useState<Record<string, number>>({});
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetch("/api/plan")
      .then(async (res) => {
        if (!res.ok) {
          throw new Error("Unauthorized");
        }
        return res.json();
      })
      .then((data: PlanResponse) => {
        if (!active) return;
        setPlanId(data.planId ?? null);
        setPlan(data.plan ?? null);
        setCourseCredits(data.courseCredits ?? {});
      })
      .catch(() => {
        if (active) {
          setStatus("Please sign in to view your plan.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const terms = useMemo(() => plan?.plan.terms ?? [], [plan]);

  function handleDragStart(event: React.DragEvent<HTMLDivElement>, courseId: string, fromIndex: number) {
    const payload: DragPayload = { courseId, fromIndex };
    event.dataTransfer.setData("application/json", JSON.stringify(payload));
    event.dataTransfer.effectAllowed = "move";
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>, toIndex: number) {
    event.preventDefault();
    const raw = event.dataTransfer.getData("application/json");
    if (!raw || !plan) {
      return;
    }
    const payload = JSON.parse(raw) as DragPayload;
    if (payload.fromIndex === toIndex) {
      return;
    }

    const nextTerms = plan.plan.terms.map((term) => ({ ...term, courses: [...term.courses] }));
    const from = nextTerms[payload.fromIndex];
    const to = nextTerms[toIndex];
    if (!from || !to) {
      return;
    }

    from.courses = from.courses.filter((course) => course !== payload.courseId);
    to.courses.push(payload.courseId);

    recalcCredits(nextTerms);
    setPlan({ ...plan, plan: { ...plan.plan, terms: nextTerms } });
  }

  function recalcCredits(nextTerms: PlanTerm[]) {
    for (const term of nextTerms) {
      term.credits = term.courses.reduce((sum, courseId) => sum + (courseCredits[courseId] ?? 0), 0);
    }
  }

  async function handleSave() {
    if (!plan) {
      return;
    }
    setStatus("Saving...");
    const res = await fetch("/api/plan", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ planId, plan }),
    });

    if (res.ok) {
      const data = (await res.json()) as { planId: string };
      setPlanId(data.planId);
      setStatus("Saved.");
    } else if (res.status === 401) {
      setStatus("Please sign in to save your plan.");
    } else {
      setStatus("Save failed. Try again.");
    }
  }

  if (loading) {
    return (
      <main className="container">
        <p className="muted">Loading...</p>
      </main>
    );
  }

  if (!plan) {
    return (
      <main className="container">
        <h1>Plan editor</h1>
        <p className="muted">Generate a plan first, then return here to edit it.</p>
        {status ? <p className="muted">{status}</p> : null}
      </main>
    );
  }

  return (
    <main className="container">
      <div className="plan-header">
        <div>
          <h1>Plan editor</h1>
          <p className="muted">Drag courses between terms and save your edits.</p>
        </div>
        <button className="primary-button" type="button" onClick={handleSave}>
          Save plan
        </button>
      </div>
      <div className="plan-grid">
        {terms.map((term, index) => (
          <div
            key={`${term.term.season}-${term.term.year}-${index}`}
            className="plan-term"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => handleDrop(event, index)}
          >
            <div className="plan-term-header">
              <strong>
                {term.term.season} {term.term.year}
              </strong>
              <span>{term.credits} credits</span>
            </div>
            <div className="plan-course-list">
              {term.courses.length === 0 ? (
                <div className="plan-empty">Drop a course here</div>
              ) : (
                term.courses.map((courseId) => (
                  <div
                    key={`${courseId}-${index}`}
                    className="plan-course"
                    draggable
                    onDragStart={(event) => handleDragStart(event, courseId, index)}
                  >
                    {courseId}
                  </div>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
      {status ? <p className="muted">{status}</p> : null}
    </main>
  );
}
