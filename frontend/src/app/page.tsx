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
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);

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
          <h1 className="auth-heading">Continue to RU Planner</h1>
          <p className="auth-sub" style={{ marginBottom: 24 }}>
            Sign in or create your account with Google.
          </p>

          {GOOGLE_CLIENT_ID ? (
            <div id="google-signin-btn" aria-label="Continue with Google" style={{ width: "100%", minHeight: 44 }} />
          ) : (
            <p className="auth-error">Google sign-in is not configured.</p>
          )}
          {loading && <p className="auth-sub" style={{ marginTop: 14 }}>Signing you in…</p>}
          {error && <p className="auth-error" style={{ marginTop: 14 }}>{error}</p>}
          <p className="auth-switch" style={{ marginTop: 22 }}>
            RU Planner uses Google for secure account access. No separate password is stored.
          </p>
        </div>
      </div>
    </div>
  );
}
