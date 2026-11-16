import { createServer } from "node:http";
import { timingSafeEqual } from "node:crypto";
import { Pool } from "pg";

const port = Number(process.env.PORT || 8788);
const databaseUrl = process.env.DATABASE_URL;
const apiKey = process.env.PRODUCT_DOSSIER_API_KEY;
const nodeEnv = process.env.NODE_ENV || "development";

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("PORT must be a valid TCP port");
}
if (!databaseUrl) throw new Error("DATABASE_URL is required");
if (!apiKey || apiKey.length < 64) {
  throw new Error("PRODUCT_DOSSIER_API_KEY must contain at least 64 characters");
}

const parsedDatabaseUrl = new URL(databaseUrl);
const localHosts = new Set(["localhost", "127.0.0.1", "::1"]);
const sslmode = parsedDatabaseUrl.searchParams.get("sslmode");
if (sslmode === "disable" && nodeEnv !== "test") {
  throw new Error("sslmode=disable is permitted only in NODE_ENV=test");
}
if (!localHosts.has(parsedDatabaseUrl.hostname) && !["verify-full", "verify-ca"].includes(sslmode)) {
  throw new Error("remote PostgreSQL connections require sslmode=verify-full or verify-ca");
}

const pool = new Pool({
  connectionString: databaseUrl,
  max: 5,
  idleTimeoutMillis: 10000,
  connectionTimeoutMillis: 5000
});

let productIdentity;

function authorized(request) {
  const header = request.headers.authorization || "";
  const supplied = header.startsWith("Bearer ") ? header.slice(7) : "";
  const expectedBytes = Buffer.from(apiKey);
  const suppliedBytes = Buffer.from(supplied);
  return suppliedBytes.length === expectedBytes.length &&
    timingSafeEqual(suppliedBytes, expectedBytes);
}

function send(response, status, payload) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff"
  });
  response.end(JSON.stringify(payload));
}

async function readJson(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > 1024 * 1024) {
      const error = new Error("request body too large");
      error.statusCode = 413;
      throw error;
    }
    chunks.push(chunk);
  }
  let value;
  try {
    value = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    const error = new Error("invalid JSON");
    error.statusCode = 400;
    throw error;
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    const error = new Error("JSON body must be an object");
    error.statusCode = 400;
    throw error;
  }
  return value;
}

function mapDatabaseError(error) {
  const message = String(error?.message || "");
  if (message.includes("not authorized for this product dossier")) return [403, "product_scope_denied"];
  if (message.includes("idempotency key reused with different content")) return [409, "idempotency_conflict"];
  if (
    message.includes("minimum schema") ||
    message.includes("product_type does not match") ||
    message.includes("invalid product dossier arguments")
  ) return [422, "invalid_product_dossier"];
  return [503, "database_unavailable"];
}

async function verifyDatabaseIdentity() {
  const identityResult = await pool.query(`
    SELECT
      session_user::text AS login,
      pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER') AS is_runtime,
      pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER') AS is_approver,
      pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') AS is_executor,
      (SELECT count(*)::int FROM factory.project_identities WHERE role_name = session_user) AS identity_count,
      (SELECT project_id::text FROM factory.project_identities WHERE role_name = session_user LIMIT 1) AS project_id
  `);
  const identity = identityResult.rows[0];
  if (
    !identity ||
    !identity.is_runtime ||
    identity.is_approver ||
    identity.is_executor ||
    identity.identity_count !== 1 ||
    !identity.project_id
  ) {
    throw new Error("database login is not an isolated single-product runtime identity");
  }

  const productResult = await pool.query(
    "SELECT project_id::text, project_key, display_name, product_type FROM factory.projects"
  );
  if (productResult.rowCount !== 1 || productResult.rows[0].project_id !== identity.project_id) {
    throw new Error("database RLS did not resolve exactly one matching product");
  }
  productIdentity = { login: identity.login, ...productResult.rows[0] };
}

async function handle(request, response) {
  const host = request.headers.host || "127.0.0.1";
  const url = new URL(request.url || "/", `http://${host}`);

  if (request.method === "GET" && url.pathname === "/health") {
    return send(response, 200, { ok: true, service: "product-dossier-api", version: "0.1.0" });
  }

  if (!authorized(request)) return send(response, 401, { error: "unauthorized" });

  if (request.method === "GET" && url.pathname === "/v1/product") {
    return send(response, 200, { product: productIdentity });
  }

  if (request.method === "GET" && url.pathname === "/v1/dossier") {
    const result = await pool.query(`
      SELECT version_no, dossier, created_by_login::text, created_at
      FROM factory.product_dossier_versions
      ORDER BY version_no DESC
      LIMIT 1
    `);
    if (result.rowCount === 0) return send(response, 404, { error: "dossier_not_found" });
    return send(response, 200, { product: productIdentity, dossier: result.rows[0] });
  }

  if (request.method === "GET" && url.pathname === "/v1/dossier/versions") {
    const rawLimit = url.searchParams.get("limit") || "20";
    const limit = Number(rawLimit);
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      return send(response, 400, { error: "invalid_limit" });
    }
    const result = await pool.query(`
      SELECT version_no, dossier, created_by_login::text, created_at
      FROM factory.product_dossier_versions
      ORDER BY version_no DESC
      LIMIT $1
    `, [limit]);
    return send(response, 200, { product: productIdentity, versions: result.rows });
  }

  if (request.method === "POST" && url.pathname === "/v1/dossier") {
    const idempotencyKey = request.headers["idempotency-key"];
    if (typeof idempotencyKey !== "string" || idempotencyKey.trim().length < 1 || idempotencyKey.length > 255) {
      return send(response, 400, { error: "idempotency_key_required" });
    }
    const dossier = await readJson(request);
    if (Object.hasOwn(dossier, "project_id")) {
      return send(response, 400, { error: "project_identity_is_server_bound" });
    }
    const result = await pool.query(
      "SELECT factory.record_product_dossier($1::uuid, $2::jsonb, $3::text) AS version_no",
      [productIdentity.project_id, JSON.stringify(dossier), idempotencyKey]
    );
    const version = await pool.query(`
      SELECT version_no, dossier, created_by_login::text, created_at
      FROM factory.product_dossier_versions
      WHERE version_no = $1
      LIMIT 1
    `, [result.rows[0].version_no]);
    if (version.rowCount !== 1) throw new Error("committed dossier version could not be read back");
    return send(response, 200, { product: productIdentity, dossier: version.rows[0] });
  }

  return send(response, 404, { error: "not_found" });
}

const server = createServer(async (request, response) => {
  try {
    await handle(request, response);
  } catch (error) {
    if (error?.statusCode) return send(response, error.statusCode, { error: error.message });
    const [status, code] = mapDatabaseError(error);
    console.error("product dossier request failed", { code, message: error?.message });
    return send(response, status, { error: code });
  }
});

await verifyDatabaseIdentity();
server.listen(port, "0.0.0.0", () => {
  console.log("product-dossier-api listening", {
    port,
    project_key: productIdentity.project_key,
    database_login: productIdentity.login
  });
});

async function shutdown() {
  server.close(async () => {
    await pool.end();
    process.exit(0);
  });
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
