"use client";

import { useEffect, useState } from "react";
import { signIn } from "next-auth/react";

type ProviderMap = Record<string, { id: string; name: string; signinUrl?: string }>;

export default function SignInCard() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [providers, setProviders] = useState<ProviderMap | null>(null);

  useEffect(() => {
    fetch("/api/auth/providers")
      .then((res) => res.json())
      .then((data) => setProviders(data))
      .catch(() => setProviders(null));
  }, []);

  async function handleCredentialsSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("Signing in...");
    const result = await signIn("local", {
      identifier,
      password,
      callbackUrl: "/",
      redirect: true,
    });

    if (result?.error) {
      setStatus("Sign in failed.");
    }
  }

  async function handleRutgersSignIn() {
    setStatus("Redirecting to Rutgers sign-in...");
    await signIn("auth0", { callbackUrl: "/" });
  }

  async function handleGoogleSignIn() {
    setStatus("Redirecting to Google sign-in...");
    const callbackUrl = `${window.location.origin}/`;
    const result = await signIn("google", { callbackUrl, redirect: true });
    if (result?.error) {
      setStatus("Google sign-in failed.");
    }
  }

  const hasAuth0 = !!providers?.auth0;
  const showGoogle = providers ? !!providers.google : true;
  const showLocal = providers ? !!providers.local : true;

  return (
    <main className="signin-page">
      <div className="signin-card">
        <div className="signin-logo">R</div>
        <h1>Sign in to RUPlanner</h1>
        <p className="muted">Welcome back! Please sign in to continue.</p>

        {hasAuth0 ? (
          <button className="primary-button full-width" type="button" onClick={handleRutgersSignIn}>
            Continue with Rutgers
          </button>
        ) : null}
        {showGoogle ? (
          <button className="secondary-button full-width" type="button" onClick={handleGoogleSignIn}>
            Continue with Google
          </button>
        ) : null}

        <div className="signin-divider">
          <span>or</span>
        </div>

        {showLocal ? (
          <form className="form" onSubmit={handleCredentialsSubmit}>
            <label className="label" htmlFor="identifier">
              Email or username
            </label>
            <input
              id="identifier"
              className="input"
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
              placeholder="you@example.com"
            />
            <label className="label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              className="input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
            />
            <button className="primary-button full-width" type="submit">
              Continue
            </button>
            <a className="link" href="/signup">
              Create an account
            </a>
            {status ? <p className="muted">{status}</p> : null}
          </form>
        ) : null}

        <p className="signin-footnote">Secure sign-in powered by your Rutgers SSO.</p>
      </div>
    </main>
  );
}
