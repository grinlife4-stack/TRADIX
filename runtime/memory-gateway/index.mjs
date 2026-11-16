import pg from "pg";
import { timingSafeEqual, createHash } from "node:crypto";

const { Pool } = pg;
const databaseUrl = process.env.DATABASE_URL;
const apiKey = process.env.MEMORY_GATEWAY_API_KEY;
if (!databaseUrl) throw new Error("DATABASE_URL is required");
if (!apiKey || apiKey.length < 32) throw new Error("MEMORY_GATEWAY_API_KEY must be at least 32 characters");

const pool = new Pool({ connectionString: databaseUrl, max: 3, idleTimeoutMillis: 30000, connectionTimeoutMillis: 5000 });
const expected = createHash("sha256").update(apiKey).digest();

function authorized(request) {
  const header = request.headers.get("authorization") || "";
  if (!header.startsWith("Bearer ")) return false;
  const provided = createHash("sha256").update(header.slice(7)).digest();
  return provided.length === expected.length && timingSafeEqual(provided, expected);
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff"
    }
  });
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return json({ ok: true, service: "memory-gateway", version: "1.0" });
    }
    if (!authorized(request)) return json({ error: "unauthorized" }, 401);
    if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
    if (url.pathname !== "/v1/context") return json({ error: "not_found" }, 404);
    const projectKey = url.searchParams.get("project");
    if (!projectKey || !/^[a-z0-9][a-z0-9._-]{1,79}$/.test(projectKey)) {
      return json({ error: "invalid_project_key" }, 400);
    }
    try {
      const result = await pool.query("SELECT memory_bootstrap_context($1) AS context", [projectKey]);
      if (!result.rows.length || result.rows[0].context === null) {
        return json({ error: "project_not_found" }, 404);
      }
      return json(result.rows[0].context);
    } catch (error) {
      console.error("memory gateway query failed", { message: error?.message, code: error?.code });
      return json({ error: "memory_backend_unavailable" }, 503);
    }
  }
};
