import { prisma } from "../../../lib/prisma";
import { validateEnv } from "../../../lib/env";

export async function GET() {
  validateEnv();
  if (process.env.NODE_ENV === "production") {
    return Response.json({ error: "Not found" }, { status: 404 });
  }

  const logs = await prisma.auditLog.findMany({
    orderBy: { createdAt: "desc" },
    take: 20,
  });

  return Response.json({ logs });
}
