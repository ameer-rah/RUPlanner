import { getServerSession } from "next-auth";
import { authOptions } from "../../../lib/auth";
import { logAudit } from "../../../lib/audit";
import { validateEnv } from "../../../lib/env";
import { prisma } from "../../../lib/prisma";
import { getClientIp, rateLimit } from "../../../lib/rate-limit";
import { buildPlan } from "../../../lib/planner";
import { resolveProgramData } from "../../../lib/programs";

function normalizeCourseIds(raw: string): string[] {
  return raw
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

export async function POST(request: Request) {
  validateEnv();
  const ip = getClientIp(request);
  const limit = await rateLimit(`plan:${ip}`, { limit: 20, windowMs: 60_000 });
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

  let completedCourses: string[] = [];

  const contentType = request.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const body = (await request.json()) as { completedCourses?: string[] };
    completedCourses = body.completedCourses ?? [];
  } else {
    const formData = await request.formData();
    const raw = String(formData.get("completedCourses") ?? "");
    completedCourses = normalizeCourseIds(raw);
  }

  const user = await prisma.user.upsert({
    where: { netid: session.user.id },
    update: {},
    create: { netid: session.user.id, email: session.user.email ?? null },
  });
  const profile = await prisma.profile.findUnique({ where: { userId: user.id } });
  const result = buildPlan(completedCourses, profile ?? undefined);

  await prisma.completedCourse.deleteMany({ where: { userId: user.id } });
  if (completedCourses.length > 0) {
    await prisma.completedCourse.createMany({
      data: completedCourses.map((courseId) => ({
        userId: user.id,
        courseId,
      })),
    });
  }
  await prisma.plan.create({
    data: {
      userId: user.id,
      planJson: {
        plan: result.plan,
        programId: result.programId,
      },
    },
  });
  await logAudit({
    action: "plan.generate",
    path: "/api/plan",
    ip,
    userAgent: request.headers.get("user-agent") ?? undefined,
    userId: user.id,
    metadata: { completedCount: completedCourses.length, programId: result.programId },
  });
  return Response.json({
    completedCourses,
    remainingRequirements: Array.from(result.requirementEval.remainingCourses),
    choices: result.requirementEval.choices,
    notes: result.requirementEval.notes,
    plan: result.plan,
    programId: result.programId,
    programWarnings: result.programWarnings,
  });
}

export async function GET(request: Request) {
  validateEnv();
  const session = await getServerSession(authOptions);
  if (!session?.user?.id) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const user = await prisma.user.findUnique({ where: { netid: session.user.id } });
  if (!user) {
    return Response.json({ plan: null });
  }

  const latestPlan = await prisma.plan.findFirst({
    where: { userId: user.id },
    orderBy: { generatedAt: "desc" },
  });
  const profile = await prisma.profile.findUnique({ where: { userId: user.id } });
  const program = resolveProgramData(profile ?? undefined);
  const courseCredits = Object.fromEntries(program.courses.map((course) => [course.id, course.credits]));

  return Response.json({
    planId: latestPlan?.id ?? null,
    plan: latestPlan?.planJson ?? null,
    programId: program.id,
    courseCredits,
  });
}

export async function PUT(request: Request) {
  validateEnv();
  const ip = getClientIp(request);
  const limit = await rateLimit(`plan-save:${ip}`, { limit: 20, windowMs: 60_000 });
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

  const body = (await request.json()) as { planId?: string; plan: unknown };
  const user = await prisma.user.findUnique({ where: { netid: session.user.id } });
  if (!user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  let saved;
  if (body.planId) {
    const existing = await prisma.plan.findFirst({
      where: { id: body.planId, userId: user.id },
    });
    if (!existing) {
      return Response.json({ error: "Plan not found" }, { status: 404 });
    }
    saved = await prisma.plan.update({
      where: { id: body.planId },
      data: { planJson: body.plan },
    });
  } else {
    saved = await prisma.plan.create({
      data: { userId: user.id, planJson: body.plan },
    });
  }

  await logAudit({
    action: "plan.save",
    path: "/api/plan",
    ip,
    userAgent: request.headers.get("user-agent") ?? undefined,
    userId: user.id,
  });

  return Response.json({ planId: saved.id });
}
