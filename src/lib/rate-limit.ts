import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

type RateLimitOptions = {
  limit: number;
  windowMs: number;
};

type RateLimitResult = {
  allowed: boolean;
  remaining: number;
  resetAt: number;
};

const memoryStore = new Map<string, number[]>();

const redis =
  process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN
    ? new Redis({
        url: process.env.UPSTASH_REDIS_REST_URL,
        token: process.env.UPSTASH_REDIS_REST_TOKEN,
      })
    : null;

const redisLimiters = new Map<string, Ratelimit>();

export async function rateLimit(key: string, options: RateLimitOptions): Promise<RateLimitResult> {
  if (redis) {
    const seconds = Math.max(1, Math.ceil(options.windowMs / 1000));
    const limiterKey = `${options.limit}:${seconds}`;
    if (!redisLimiters.has(limiterKey)) {
      redisLimiters.set(
        limiterKey,
        new Ratelimit({
          redis,
          limiter: Ratelimit.slidingWindow(options.limit, `${seconds} s`),
        })
      );
    }
    const limiter = redisLimiters.get(limiterKey)!;
    const result = await limiter.limit(key);
    return {
      allowed: result.success,
      remaining: result.remaining,
      resetAt: result.reset,
    };
  }

  const now = Date.now();
  const windowStart = now - options.windowMs;
  const timestamps = (memoryStore.get(key) ?? []).filter((ts) => ts > windowStart);
  const allowed = timestamps.length < options.limit;

  if (allowed) {
    timestamps.push(now);
  }

  memoryStore.set(key, timestamps);

  const resetAt = timestamps.length === 0 ? now + options.windowMs : timestamps[0] + options.windowMs;
  return {
    allowed,
    remaining: Math.max(0, options.limit - timestamps.length),
    resetAt,
  };
}

export function getClientIp(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) {
    return forwarded.split(",")[0]?.trim() || "unknown";
  }
  return request.headers.get("x-real-ip") ?? "unknown";
}
