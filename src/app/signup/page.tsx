"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";

export default function SignUpPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("Creating account...");

    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username, email, password }),
    });

    if (!res.ok) {
      const message = res.status === 409 ? "Account already exists." : "Sign up failed.";
      setStatus(message);
      return;
    }

    await signIn("local", {
      identifier: email,
      password,
      callbackUrl: "/",
      redirect: true,
    });
  }

  return (
    <main className="signin-page">
      <div className="signin-card">
        <div className="signin-logo">R</div>
        <h1>Create your account</h1>
        <p className="muted">Sign up with email and a password.</p>
        <form className="form" onSubmit={handleSubmit}>
          <label className="label" htmlFor="username">
            Username
          </label>
          <input
            id="username"
            className="input"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="ruplanner_user"
          />
          <label className="label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            className="input"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
          />
          <label className="label" htmlFor="password">
            Password (min 8 chars)
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
            Create account
          </button>
          <a className="link" href="/signin">
            Back to sign in
          </a>
          {status ? <p className="muted">{status}</p> : null}
        </form>
      </div>
    </main>
  );
}
