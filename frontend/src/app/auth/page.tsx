"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

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

  async function finishAuth(token: string, userEmail: string) {
    localStorage.setItem("ru_planner_token", token);
    localStorage.setItem("ru_planner_email", userEmail);
    router.push("/");
  }

  useEffect(() => {
    const token = localStorage.getItem("ru_planner_token");
    if (token) {
      router.push("/");
      return;
    }
    setAuthChecked(true);
  }, [router]);

  useEffect(() => {
    if (!authChecked || !GOOGLE_CLIENT_ID) return;

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => {
      window.google?.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (response: { credential: string }) => {
          setError("");
          setLoading(true);
          try {
            const res = await fetch(`${apiBase}/auth/google`, {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({ credential: response.credential }),
            });
            if (!res.ok) {
              const data = await res.json().catch(() => ({ detail: "Google sign-in failed." }));
              setError(data.detail ?? "Google sign-in failed.");
              return;
            }
            const { access_token } = await res.json();
            const meRes = await fetch(`${apiBase}/auth/me`, {
              headers: { Authorization: `Bearer ${access_token}` },
            });
            const me = meRes.ok ? await meRes.json() : { email: "user" };
            await finishAuth(access_token, me.email);
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
    };
    document.body.appendChild(script);
    return () => { document.body.removeChild(script); };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const endpoint = mode === "signin" ? "/auth/login" : "/auth/register";

    try {
      const res = await fetch(`${apiBase}${endpoint}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Something went wrong." }));
        setError(data.detail ?? "Something went wrong.");
        return;
      }

      const { access_token } = await res.json();
      await finishAuth(access_token, email);
    } catch {
      setError("Could not connect to server.");
    } finally {
      setLoading(false);
    }
  }

  if (!authChecked) return null;

  return (
    <div className="auth-shell">
      <div className="auth-card">
        {/* Logo mark */}
        <img src="/RUPlanner_logo.png" alt="RU Planner" className="auth-logo-img" />

        {/* Heading */}
        <h1 className="auth-heading">
          {mode === "signin" ? "Sign in to RU Planner" : "Create your account"}
        </h1>
        <p className="auth-sub">
          {mode === "signin"
            ? "Welcome back! Please sign in to continue."
            : "Sign up to save and manage your degree plans."}
        </p>

        {/* Google button */}
        {GOOGLE_CLIENT_ID && (
          <>
            <div id="google-signin-btn" style={{ width: "100%", minHeight: 44, marginBottom: 16 }} />
            <div className="auth-divider"><span>or</span></div>
          </>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ textAlign: "left" }}>
          <div className="auth-field">
            <label className="auth-field-label" htmlFor="email">Email address</label>
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
            <label className="auth-field-label" htmlFor="password">Password</label>
            <input
              id="password"
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "signup" ? "Create a password (min 6 chars)" : "Your password"}
              required
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              minLength={mode === "signup" ? 6 : undefined}
            />
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

        {/* Switch mode */}
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
  );
}
