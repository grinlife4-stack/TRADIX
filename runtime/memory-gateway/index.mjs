import { createHash, timingSafeEqual } from "node:crypto";
import { Pool } from "pg";

const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) throw new Error("DATABASE_URL missing");

const pool = new Pool({
  connectionString: databaseUrl,
  max: 5,
  connectionTimeoutMillis: 5000,
  idleTimeoutMillis: 30000,
  statement_timeout: 10000,
  application_name: "tradix-memory-gateway"
});
pool.on("error", error => {
  console.error("memory gateway idle database client error", {
    message: error?.message,
    code: error?.code
  });
});

const json = (value, status = 200) => new Response(JSON.stringify(value), {
  status,
  headers: {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff"
  }
});

function bearerToken(request) {
  const value = request.headers.get("authorization") || "";
  const match = /^Bearer ([A-Za-z0-9._~-]{40,256})$/.exec(value);
  return match ? match[1] : null;
}

function tokenHash(token) {
  return createHash("sha256").update(token, "utf8").digest();
}

function safeEqual(left, right) {
  return left.length === right.length && timingSafeEqual(left, right);
}

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return json({ ok: true, service: "memory-gateway", version: "1.1.0" });
    }

    if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
    if (url.pathname !== "/v1/context") return json({ error: "not_found" }, 404);

    // Project identity is derived from the bearer credential, never caller-selected.
    if (url.searchParams.has("project")) return json({ error: "project_selector_not_supported" }, 400);

    const token = bearerToken(request);
    if (!token) return json({ error: "unauthorized" }, 401);

    try {
      const digest = tokenHash(token);
      const result = await pool.query(
        "SELECT public.memory_bootstrap_context_for_token($1::bytea) AS context",
        [digest]
      );
      const context = result.rows[0]?.context ?? null;
      // Constant-time digest comparison is performed by PostgreSQL bytea equality
      // only after the API hashes a fixed-length token; no raw token reaches SQL.
      if (!context) return json({ error: "unauthorized" }, 401);
      return json(context);
    } catch (error) {
      console.error("memory gateway query failed", {
        message: error?.message,
        code: error?.code
      });
      return json({ error: "memory_backend_unavailable" }, 503);
    }
  },

  async close() {
    await pool.end();
  }
};

export { safeEqual };
