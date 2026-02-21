"use client";

import { useEffect, useState } from "react";

type ProfileFormState = {
  school: string;
  majors: string;
  minors: string;
  catalogYear: string;
  gradTarget: string;
};

const initialState: ProfileFormState = {
  school: "",
  majors: "",
  minors: "",
  catalogYear: "",
  gradTarget: "",
};

export default function ProfilePage() {
  const [form, setForm] = useState<ProfileFormState>(initialState);
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let active = true;
    fetch("/api/profile")
      .then(async (res) => {
        if (!res.ok) {
          throw new Error("Unauthorized");
        }
        return res.json();
      })
      .then((data) => {
        if (!active) return;
        if (data.profile) {
          setForm({
            school: data.profile.school ?? "",
            majors: (data.profile.majors ?? []).join(", "),
            minors: (data.profile.minors ?? []).join(", "),
            catalogYear: data.profile.catalogYear ?? "",
            gradTarget: data.profile.gradTarget ?? "",
          });
        }
      })
      .catch(() => {
        if (active) {
          setStatus("Please sign in to edit your profile.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("Saving...");
    const payload = {
      school: form.school,
      majors: form.majors.split(",").map((item) => item.trim()).filter(Boolean),
      minors: form.minors.split(",").map((item) => item.trim()).filter(Boolean),
      catalogYear: form.catalogYear,
      gradTarget: form.gradTarget,
    };

    const res = await fetch("/api/profile", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      setStatus("Saved.");
    } else if (res.status === 401) {
      setStatus("Please sign in to edit your profile.");
    } else {
      setStatus("Save failed. Try again.");
    }
  }

  return (
    <main className="container">
      <h1>Profile</h1>
      <p className="muted">
        Add your school, majors, minors, catalog year, and target graduation term.
      </p>
      {loading ? (
        <p className="muted">Loading...</p>
      ) : (
        <form onSubmit={handleSubmit} className="form">
          <label className="label" htmlFor="school">
            School
          </label>
          <input
            id="school"
            className="input"
            value={form.school}
            onChange={(event) => setForm({ ...form, school: event.target.value })}
            placeholder="SAS, SoE, etc."
          />

          <label className="label" htmlFor="majors">
            Majors (comma-separated)
          </label>
          <input
            id="majors"
            className="input"
            value={form.majors}
            onChange={(event) => setForm({ ...form, majors: event.target.value })}
            placeholder="Computer Science, Mathematics"
          />

          <label className="label" htmlFor="minors">
            Minors (comma-separated)
          </label>
          <input
            id="minors"
            className="input"
            value={form.minors}
            onChange={(event) => setForm({ ...form, minors: event.target.value })}
            placeholder="Economics"
          />

          <label className="label" htmlFor="catalogYear">
            Catalog year
          </label>
          <input
            id="catalogYear"
            className="input"
            value={form.catalogYear}
            onChange={(event) => setForm({ ...form, catalogYear: event.target.value })}
            placeholder="2025-2026"
          />

          <label className="label" htmlFor="gradTarget">
            Target graduation term
          </label>
          <input
            id="gradTarget"
            className="input"
            value={form.gradTarget}
            onChange={(event) => setForm({ ...form, gradTarget: event.target.value })}
            placeholder="Spring 2028"
          />

          <button className="primary-button" type="submit">
            Save profile
          </button>
          {status ? <p className="muted">{status}</p> : null}
        </form>
      )}
    </main>
  );
}
