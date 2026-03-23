"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!token) setError("Missing or invalid reset link.");
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/auth/reset-password`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Something went wrong." }));
        setError(data.detail ?? "Something went wrong.");
        return;
      }

      setSuccess(true);
      setTimeout(() => router.push("/"), 2500);
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

        {success ? (
          <>
            <h1 className="auth-heading">Password updated!</h1>
            <p className="auth-sub">
              Your password has been reset. Redirecting you to sign in…
            </p>
          </>
        ) : (
          <>
            <h1 className="auth-heading">Set a new password</h1>
            <p className="auth-sub">Choose a new password for your RU Planner account.</p>

            <form onSubmit={handleSubmit} style={{ textAlign: "left" }}>
              <div className="auth-field">
                <label className="auth-field-label" htmlFor="password">New password</label>
                <input
                  id="password"
                  className="input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 6 characters"
                  required
                  minLength={6}
                  autoComplete="new-password"
                  disabled={!token}
                />
              </div>

              <div className="auth-field">
                <label className="auth-field-label" htmlFor="confirm">Confirm password</label>
                <input
                  id="confirm"
                  className="input"
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Repeat your new password"
                  required
                  autoComplete="new-password"
                  disabled={!token}
                />
              </div>

              {error && (
                <p className="auth-error" style={{ marginBottom: 14 }}>{error}</p>
              )}

              <button
                className="primary-button"
                type="submit"
                disabled={loading || !token}
                style={{ width: "100%" }}
              >
                {loading ? "Saving…" : "Reset password →"}
              </button>
            </form>

            <p className="auth-switch">
              <Link href="/" className="auth-switch-btn">Back to sign in</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
