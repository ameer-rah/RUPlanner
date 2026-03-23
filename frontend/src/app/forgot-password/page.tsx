"use client";

import { useState } from "react";
import Link from "next/link";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/auth/forgot-password`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Something went wrong." }));
        setError(data.detail ?? "Something went wrong.");
        return;
      }
      setSubmitted(true);
    } catch {
      setError("Could not connect to server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <img src="/RUPlanner Logo.svg" alt="RU Planner" className="auth-logo-img" />

        {submitted ? (
          <>
            <h1 className="auth-heading">Check your email</h1>
            <p className="auth-sub" style={{ marginBottom: 28 }}>
              If <strong>{email}</strong> is registered, you&apos;ll receive a password reset link
              shortly. Check your spam folder if you don&apos;t see it.
            </p>
            <Link href="/" className="primary-button" style={{ display: "block", textAlign: "center", textDecoration: "none" }}>
              Back to sign in
            </Link>
          </>
        ) : (
          <>
            <h1 className="auth-heading">Forgot your password?</h1>
            <p className="auth-sub">
              Enter your email and we&apos;ll send you a link to reset your password.
            </p>

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

              {error && (
                <p className="auth-error" style={{ marginBottom: 14 }}>{error}</p>
              )}

              <button
                className="primary-button"
                type="submit"
                disabled={loading}
                style={{ width: "100%" }}
              >
                {loading ? "Sending…" : "Send reset link →"}
              </button>
            </form>

            <p className="auth-switch">
              Remember your password?{" "}
              <Link href="/" className="auth-switch-btn">Sign in</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
