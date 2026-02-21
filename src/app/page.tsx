import { getServerSession } from "next-auth";
import { authOptions } from "../lib/auth";
import SignInCard from "./signin/SignInCard";

const defaultCourses = ["01:198:111"];

export default async function HomePage() {
  const session = await getServerSession(authOptions);
  const signedIn = !!(session?.user as { id?: string } | null)?.id;
  if (!signedIn) {
    return <SignInCard />;
  }

  return (
    <main className="container">
      <h1>RUPlanner Demo</h1>
      <p>
        This is a minimal Next.js wrapper around the planner engine. Enter completed course IDs to
        generate a plan.
      </p>
      <form action="/api/plan" method="post">
        <label htmlFor="completedCourses">Completed courses (comma-separated)</label>
        <textarea
          id="completedCourses"
          name="completedCourses"
          defaultValue={defaultCourses.join(", ")}
          rows={4}
          className="text-area"
        />
        <button className="primary-button" type="submit">
          Generate plan
        </button>
      </form>
      <div className="link-row">
        <a className="link" href="/profile">
          Edit profile
        </a>
        <span> · </span>
        <a className="link" href="/plan">
          Edit plan
        </a>
        <span> · </span>
        <a className="link" href="/api/auth/signout">
          Sign out
        </a>
      </div>
      <p className="muted">
        Rutgers SSO + Postgres wiring is scaffolded; replace the auth flow with Rutgers SSO and
        store profiles + plans in Postgres.
      </p>
    </main>
  );
}
