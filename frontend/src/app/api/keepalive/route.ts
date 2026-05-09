export async function GET() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (apiBase) {
    try {
      await fetch(`${apiBase}/health`, { signal: AbortSignal.timeout(5000) });
    } catch {}
  }
  return new Response("ok");
}
