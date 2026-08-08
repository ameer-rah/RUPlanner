"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://api.ruplanner.com";
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

const FEATURES = [
  "6,500+ Rutgers courses with prerequisites",
  "AI-built, prereq-aware semester schedule",
  "Course seat sniper with SMS alerts",
  "RateMyProfessors ratings built in",
  "Transcript upload to auto-detect completed courses",
];

async function fetchWithRetry(url: string, options: RequestInit, retries = 2): Promise<Response> {
  for (let i = 0; i <= retries; i++) {
    try {
      const res = await fetch(url, { ...options, credentials: 'include', signal: AbortSignal.timeout(8000) });
      if (res.ok || res.status < 500) return res;
    } catch (e) {
      if (i === retries) throw e;
      await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
  throw new Error("Request failed after retries");
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: object) => void;
          renderButton: (element: HTMLElement, config: object) => void;
        };
      };
    };
  }
}

export default function AuthPage() {
  const router = useRouter();
  const [showAuth, setShowAuth] = useState(false);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);

  useEffect(() => {
    const requestedMode = new URLSearchParams(window.location.search).get("auth");
    if (requestedMode === "signin" || requestedMode === "signup") {
      setMode(requestedMode);
      setAuthChecked(false);
      setShowAuth(true);
    }
  }, []);

  async function finishAuth() {
    let headers: HeadersInit = {};
    try {
      const stored = localStorage.getItem("ru_planner_token");
      if (stored) headers = { Authorization: `Bearer ${stored}` };
    } catch {}
    const res = await fetch(`${apiBase}/auth/me`, { credentials: "include", headers });
    if (!res.ok) {
      router.push("/planner");
      return;
    }
    router.push("/planner");
  }

  useEffect(() => {
    if (!showAuth) {
      setAuthChecked(true);
      return;
    }

    async function checkAuth() {
      try {
        let headers: HeadersInit = {};
        try {
          const stored = localStorage.getItem("ru_planner_token");
          if (stored) headers = { Authorization: `Bearer ${stored}` };
        } catch {}
        const res = await fetch(`${apiBase}/auth/me`, { credentials: 'include', headers });
        if (res.ok) {
          router.push("/planner");
          return;
        }
        try { localStorage.removeItem("ru_planner_token"); } catch {}
      } catch {
        // Not authenticated
      }
      setAuthChecked(true);
    }
    checkAuth();
  }, [router, showAuth]);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    if (window.google) { setGoogleReady(true); return; }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => setGoogleReady(true);
    document.body.appendChild(script);
  }, []);

  useEffect(() => {
    if (!authChecked || !googleReady || !GOOGLE_CLIENT_ID) return;

    window.google?.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async (response: { credential: string }) => {
        setError("");
        setLoading(true);
        try {
          const res = await fetchWithRetry(`${apiBase}/auth/google`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ credential: response.credential }),
          });
          if (!res.ok) {
            const data = await res.json().catch(() => ({ detail: "Google sign-in failed." }));
            setError(data.detail ?? "Google sign-in failed.");
            return;
          }
          const gdata = await res.json().catch(() => ({}));
          if (gdata.access_token) {
            try { localStorage.setItem("ru_planner_token", gdata.access_token); } catch {}
          }
          await finishAuth();
        } catch {
          setError("Could not connect to server.");
        } finally {
          setLoading(false);
        }
      },
    });

    const btn = document.getElementById("google-signin-btn");
    if (btn) {
      window.google?.accounts.id.renderButton(btn, {
        theme: "white",
        size: "large",
        width: btn.offsetWidth || 308,
        text: "continue_with",
      });
    }
  }, [authChecked, googleReady]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const endpoint = mode === "signin" ? "/auth/login" : "/auth/register";

    try {
      const res = await fetchWithRetry(`${apiBase}${endpoint}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Something went wrong." }));
        setError(data.detail ?? "Something went wrong.");
        return;
      }

      const data = await res.json().catch(() => ({}));
      if (data.access_token) {
        try { localStorage.setItem("ru_planner_token", data.access_token); } catch {}
      }
      await finishAuth();
    } catch {
      setError("Could not connect to server.");
    } finally {
      setLoading(false);
    }
  }

  function openAuth(nextMode: "signin" | "signup") {
    setMode(nextMode);
    setError("");
    setAuthChecked(false);
    setShowAuth(true);
  }

  if (!showAuth) {
    return (
      <main className="landing-shell">
        <div className="landing-opening">
          <div className="landing-art" aria-hidden="true" />
          <div className="landing-shade" aria-hidden="true" />

          <header className="landing-nav" aria-label="Main navigation">
            <a className="landing-wordmark" href="#top" aria-label="RUPlanner home">
              <span>RU</span>Planner
            </a>

            <nav className="landing-links" aria-label="Product">
              <a href="#planner">Planner</a>
              <a href="#requirements">Explore</a>
              <a href="#sniper">Sniper</a>
            </nav>

            <button className="landing-nav-cta" type="button" onClick={() => openAuth("signup")}>Build my plan</button>
          </header>

          <section className="landing-hero" id="top">
            <div className="landing-copy">
              <h1>Four years.<br />One clear path.</h1>
              <p>See every requirement, prerequisite, and semester before registration opens.</p>
              <div className="landing-actions">
                <button className="landing-primary" type="button" onClick={() => openAuth("signup")}>
                  Build my plan <span aria-hidden="true">→</span>
                </button>
                <button className="landing-signin" type="button" onClick={() => openAuth("signin")}>Sign in</button>
              </div>
            </div>

            <div className="landing-proof">
              <span>Built for Rutgers–New Brunswick</span>
              <span>Prerequisite-aware</span>
              <span>Free for students</span>
            </div>
          </section>
        </div>

        <section className="story-section story-requirements" id="requirements">
          <div className="story-art" aria-hidden="true" />
          <div className="story-copy">
            <span className="story-eyebrow">Degree requirements</span>
            <h2>Know what<br />counts<span>.</span></h2>
            <p>Your major, core, completed courses, and prerequisites—mapped before you choose a semester.</p>
            <ul className="story-key" aria-label="What RUPlanner maps">
              <li><i className="key-diamond" />Requirements</li>
              <li><i className="key-triangle" />Prerequisites</li>
              <li><i className="key-clover" />Transfer credit</li>
            </ul>
          </div>
        </section>

        <section className="story-section story-planner" id="planner">
          <div className="story-art" aria-hidden="true" />
          <div className="story-copy">
            <span className="story-eyebrow">Semester planning</span>
            <h2>Build the<br />semester<span>.</span></h2>
            <p>Move courses. Check prerequisites. See the whole degree change with you.</p>
            <small>Every move is checked before it becomes a problem.</small>
          </div>
        </section>

        <section className="story-section story-sniper" id="sniper">
          <div className="story-art" aria-hidden="true" />
          <div className="story-copy">
            <span className="story-eyebrow">Course sniper</span>
            <h2>Catch the seat<span>.</span></h2>
            <p>Track a closed section. Get the alert when it opens.</p>
            <small>No refreshing. No guessing.</small>
          </div>
        </section>

        <section className="landing-final">
          <div className="landing-final-art" aria-hidden="true" />
          <div className="landing-final-copy">
            <h2>Your route starts here<span>.</span></h2>
            <p>Bring your degree into focus before the next semester begins.</p>
            <button className="landing-primary" type="button" onClick={() => openAuth("signup")}>
              Build my plan <span aria-hidden="true">→</span>
            </button>
          </div>

          <footer className="landing-footer">
            <a className="landing-wordmark" href="#top"><span>RU</span>Planner</a>
            <nav aria-label="Footer navigation">
              <a href="#planner">Planner</a>
              <a href="#sniper">Course Sniper</a>
              <a href="#requirements">Explore</a>
            </nav>
            <p>Made for Rutgers students.</p>
          </footer>
        </section>
      </main>
    );
  }

  if (!authChecked) return <div className="landing-loading" aria-label="Loading" />;

  return (
    <div className="auth-split">
      <button className="auth-back-home" type="button" onClick={() => setShowAuth(false)}>← Back home</button>
      {/* ── Left: brand panel ── */}
      <div className="auth-split-left">
        <img src="/RUPlanner Logo.svg" alt="RU Planner" className="auth-split-logo" />

        <h1 className="auth-split-heading">
          Plan your Rutgers<br />degree in minutes.
        </h1>

        <p className="auth-split-sub">
          Prerequisite-aware semester plans, course sniping,
          and professor ratings — all in one place.
        </p>

        <ul className="auth-split-features">
          {FEATURES.map(f => (
            <li key={f} className="auth-split-feature">{f}</li>
          ))}
        </ul>

        <p className="auth-split-footer">Free for all Rutgers students.</p>
      </div>

      {/* ── Right: auth form ── */}
      <div className="auth-split-right">
        <div className="auth-card">
          <h1 className="auth-heading">
            {mode === "signin" ? "Sign in" : "Create account"}
          </h1>
          <p className="auth-sub" style={{ marginBottom: 24 }}>
            {mode === "signin"
              ? "Welcome back."
              : "Start planning your degree."}
          </p>

          {GOOGLE_CLIENT_ID && (
            <>
              <div id="google-signin-btn" style={{ width: "100%", minHeight: 44, marginBottom: 16 }} />
              <div className="auth-divider"><span>or</span></div>
            </>
          )}

          <form onSubmit={handleSubmit}>
            <div className="auth-field">
              <label className="auth-field-label" htmlFor="email">Email</label>
              <input
                id="email"
                className="input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="youremail@rutgers.edu"
                required
                autoComplete="email"
              />
            </div>

            <div className="auth-field">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
                <label className="auth-field-label" htmlFor="password" style={{ margin: 0 }}>Password</label>
                {mode === "signin" && (
                  <a href="/forgot-password" style={{ fontSize: 12, color: "var(--text-3)", textDecoration: "none" }}
                    onMouseOver={e => (e.currentTarget.style.textDecoration = "underline")}
                    onMouseOut={e => (e.currentTarget.style.textDecoration = "none")}
                  >
                    Forgot?
                  </a>
                )}
              </div>
              <input
                id="password"
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "signup" ? "Min 12 characters" : "Your password"}
                required
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
                minLength={mode === "signup" ? 12 : undefined}
              />
              {mode === "signup" && (
                <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4 }}>
                  Must include uppercase, lowercase, number, and special character
                </div>
              )}
            </div>

            {error && (
              <p className="auth-error" style={{ marginBottom: 14 }}>{error}</p>
            )}

            <button
              className="primary-button"
              type="submit"
              disabled={loading}
              style={{ width: "100%" }}
            >
              {loading
                ? "Please wait…"
                : mode === "signin"
                ? "Continue →"
                : "Create account →"}
            </button>
          </form>

          <p className="auth-switch">
            {mode === "signin" ? "Don't have an account? " : "Already have an account? "}
            <button
              className="auth-switch-btn"
              type="button"
              onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); }}
            >
              {mode === "signin" ? "Sign up" : "Sign in"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
