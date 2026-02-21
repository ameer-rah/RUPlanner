import NextAuth from "next-auth";
import { authOptions } from "../../../../lib/auth";
import { logAudit } from "../../../../lib/audit";
import { validateEnv } from "../../../../lib/env";
import { getClientIp, rateLimit } from "../../../../lib/rate-limit";

const authHandler = NextAuth(authOptions);

type RouteContext = { params: { nextauth?: string[] } };

async function rateLimitedHandler(request: Request, context: RouteContext) {
  const path = new URL(request.url).pathname;
  const skipRateLimit = [
    "/api/auth/providers",
    "/api/auth/csrf",
    "/api/auth/_log",
    "/api/auth/callback/google",
    "/api/auth/signin/google",
  ];
  if (skipRateLimit.includes(path)) {
    return authHandler(request, context);
  }
  validateEnv();
  const ip = getClientIp(request);
  const limit = await rateLimit(`auth:${ip}`, { limit: 10, windowMs: 60_000 });
  if (!limit.allowed) {
    return Response.json(
      { error: "Too many requests. Please try again later." },
      { status: 429, headers: { "Retry-After": Math.ceil((limit.resetAt - Date.now()) / 1000).toString() } }
    );
  }
  await logAudit({
    action: "auth.request",
    path: "/api/auth",
    ip,
    userAgent: request.headers.get("user-agent") ?? undefined,
  });
  return authHandler(request, context);
}

export { rateLimitedHandler as GET, rateLimitedHandler as POST };
