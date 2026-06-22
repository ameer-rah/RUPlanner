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
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);

  async function finishAuth() {
    router.push("/planner");
  }

  useEffect(() => {
    async function checkAuth() {
      try {
        const res = await fetch(`${apiBase}/auth/me`, { credentials: 'include' });
        if (res.ok) {
          router.push("/planner");
          return;
        }
      } catch (e) {
        // Not authenticated
      }
      setAuthChecked(true);
    }
    checkAuth();
  }, [router]);

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

      await finishAuth();
    } catch {
      setError("Could not connect to server.");
    } finally {
      setLoading(false);
    }
  }

  if (!authChecked) return null;

  return (
    <div className="auth-split">
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
