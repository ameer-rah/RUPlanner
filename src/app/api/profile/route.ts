import { getServerSession } from "next-auth";
import { authOptions } from "../../../lib/auth";
import { logAudit } from "../../../lib/audit";
import { validateEnv } from "../../../lib/env";
import { prisma } from "../../../lib/prisma";
import { getClientIp, rateLimit } from "../../../lib/rate-limit";

type ProfilePayload = {
  school?: string;
  majors?: string[];
  minors?: string[];
  catalogYear?: string;
  gradTarget?: string;
};

function normalizeList(value: string | undefined): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export async function GET(request: Request) {
  validateEnv();
  const session = await getServerSession(authOptions);
  if (!session?.user?.id) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const user = await prisma.user.findUnique({
    where: { netid: session.user.id },
    include: { profile: true },
  });

  return Response.json({ profile: user?.profile ?? null });
}

export async function POST(request: Request) {
  validateEnv();
  const ip = getClientIp(request);
  const limit = await rateLimit(`profile:${ip}`, { limit: 20, windowMs: 60_000 });
  if (!limit.allowed) {
    return Response.json(
      { error: "Too many requests. Please try again later." },
      { status: 429, headers: { "Retry-After": Math.ceil((limit.resetAt - Date.now()) / 1000).toString() } }
    );
  }

  const session = await getServerSession(authOptions);
  if (!session?.user?.id) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as ProfilePayload;
  const majors = Array.isArray(body.majors) ? body.majors : normalizeList((body as unknown as { majors?: string }).majors);
  const minors = Array.isArray(body.minors) ? body.minors : normalizeList((body as unknown as { minors?: string }).minors);

  const user = await prisma.user.upsert({
    where: { netid: session.user.id },
    update: {},
    create: { netid: session.user.id, email: session.user.email ?? null },
  });

  const profile = await prisma.profile.upsert({
    where: { userId: user.id },
    update: {
      school: body.school ?? "",
      majors,
      minors,
      catalogYear: body.catalogYear ?? "",
      gradTarget: body.gradTarget ?? "",
    },
    create: {
      userId: user.id,
      school: body.school ?? "",
      majors,
      minors,
      catalogYear: body.catalogYear ?? "",
      gradTarget: body.gradTarget ?? "",
    },
  });

  await logAudit({
    action: "profile.update",
    path: "/api/profile",
    ip,
    userAgent: request.headers.get("user-agent") ?? undefined,
    userId: user.id,
    metadata: { majorsCount: majors.length, minorsCount: minors.length },
  });

  return Response.json({ profile });
}
