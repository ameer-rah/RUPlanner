import { prisma } from "./prisma";

type AuditEvent = {
  action: string;
  path: string;
  ip?: string;
  userAgent?: string;
  userId?: string;
  metadata?: Record<string, unknown>;
};

export async function logAudit(event: AuditEvent) {
  try {
    await prisma.auditLog.create({
      data: {
        action: event.action,
        path: event.path,
        ip: event.ip,
        userAgent: event.userAgent,
        userId: event.userId,
        metadata: event.metadata ?? {},
      },
    });
  } catch (error) {
    console.warn("audit_log_failed", error);
  }
}
