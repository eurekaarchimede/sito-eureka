import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const allowedOrigins = new Set([
  "https://eurekaarchimede.it",
  "https://www.eurekaarchimede.it",
  "https://eurekaarchimede.github.io",
]);

const attempts = new Map<string, { count: number; resetAt: number }>();
const attemptLimit = 5;
const attemptWindowMs = 15 * 60 * 1000;

function response(body: Record<string, unknown>, status: number, origin: string | null) {
  const headers = new Headers({
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Vary": "Origin",
  });
  if (origin && allowedOrigins.has(origin)) {
    headers.set("Access-Control-Allow-Origin", origin);
    headers.set("Access-Control-Allow-Methods", "POST, OPTIONS");
    headers.set("Access-Control-Allow-Headers", "content-type");
    headers.set("Access-Control-Max-Age", "86400");
  }
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers });
}

async function sameSecret(candidate: string, expected: string): Promise<boolean> {
  const encoder = new TextEncoder();
  const [candidateHash, expectedHash] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(candidate)),
    crypto.subtle.digest("SHA-256", encoder.encode(expected)),
  ]);
  const left = new Uint8Array(candidateHash);
  const right = new Uint8Array(expectedHash);
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) difference |= left[index] ^ right[index];
  return difference === 0;
}

Deno.serve(async (request: Request) => {
  const origin = request.headers.get("origin");
  if (!origin || !allowedOrigins.has(origin)) return response({ error: "Origin non autorizzata" }, 403, origin);
  if (request.method === "OPTIONS") return response({}, 204, origin);
  if (request.method !== "POST") return response({ error: "Metodo non consentito" }, 405, origin);

  const expected = Deno.env.get("TEACHER_EMAIL_PASSWORD");
  if (!expected || expected.length < 12) {
    return response({ error: "Servizio non configurato" }, 503, origin);
  }

  const now = Date.now();
  const address = request.headers.get("cf-connecting-ip")
    || request.headers.get("x-real-ip")
    || "unknown";
  let attempt = address === "unknown" ? undefined : attempts.get(address);
  if (address !== "unknown") {
    if (!attempt || attempt.resetAt <= now) {
      attempt = { count: 0, resetAt: now + attemptWindowMs };
      attempts.set(address, attempt);
    }
    if (attempt.count >= attemptLimit) return response({ error: "Troppi tentativi" }, 429, origin);
    attempt.count += 1;
  }

  try {
    const rawBody = await request.text();
    if (rawBody.length > 1024) return response({ error: "Richiesta non valida" }, 400, origin);
    const body = JSON.parse(rawBody);
    const candidate = typeof body.password === "string" ? body.password : "";
    if (candidate.length < 12 || candidate.length > 128) {
      return response({ error: "Codice non valido" }, 401, origin);
    }
    if (!(await sameSecret(candidate, expected))) {
      return response({ error: "Codice non valido" }, 401, origin);
    }
    if (address !== "unknown") attempts.delete(address);
    return response({ verified: true }, 200, origin);
  } catch {
    return response({ error: "Richiesta non valida" }, 400, origin);
  }
});
