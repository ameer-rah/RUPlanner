import { validateEnv } from "../../../../lib/env";
import { prisma } from "../../../../lib/prisma";
import { hashPassword } from "../../../../lib/password";
import { getClientIp, rateLimit } from "../../../../lib/rate-limit";

type RegisterPayload = {
  username?: string;
  email?: string;
  password?: string;
};

export async function POST(request: Request) {
  validateEnv();
  const ip = getClientIp(request);
  const limit = await rateLimit(`auth-register:${ip}`, { limit: 5, windowMs: 60_000 });
  if (!limit.allowed) {
    return Response.json(
      { error: "Too many requests. Please try again later." },
      { status: 429, headers: { "Retry-After": Math.ceil((limit.resetAt - Date.now()) / 1000).toString() } }
    );
  }

  const body = (await request.json()) as RegisterPayload;
  const username = body.username?.trim();
  const email = body.email?.trim().toLowerCase();
  const password = body.password ?? "";

  if (!username || !email || password.length < 8) {
    return Response.json({ error: "Invalid input" }, { status: 400 });
  }

  const existing = await prisma.user.findFirst({
    where: {
      OR: [{ email }, { username }],
    },
  });
  if (existing) {
    return Response.json({ error: "User already exists" }, { status: 409 });
  }

  const passwordHash = await hashPassword(password);
  const user = await prisma.user.create({
    data: {
      email,
      username,
      netid: email,
      passwordHash,
    },
  });

  return Response.json({ id: user.id });
}
