import { createServer } from "node:http";
import { timingSafeEqual, createHash } from "node:crypto";
import { Pool } from "pg";

const port = Number(process.env.PORT || 8789);
const databaseUrl = process.env.DATABASE_URL;
const apiKey = process.env.MISSION_PLAN_API_KEY;
const nodeEnv = process.env.NODE_ENV || "development";

if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("PORT must be a valid TCP port");
if (!databaseUrl) throw new Error("DATABASE_URL is required");
if (!apiKey || apiKey.length < 64) throw new Error("MISSION_PLAN_API_KEY must contain at least 64 characters");

const parsedDatabaseUrl = new URL(databaseUrl);
const localHosts = new Set(["localhost", "127.0.0.1", "::1"]);
const sslmode = parsedDatabaseUrl.searchParams.get("sslmode");
if (sslmode === "disable" && nodeEnv !== "test") throw new Error("sslmode=disable is permitted only in NODE_ENV=test");
if (!localHosts.has(parsedDatabaseUrl.hostname) && !["verify-full", "verify-ca"].includes(sslmode)) {
  throw new Error("remote PostgreSQL connections require sslmode=verify-full or verify-ca");
}

const pool = new Pool({ connectionString: databaseUrl, max: 5, idleTimeoutMillis: 10000, connectionTimeoutMillis: 5000 });
let productIdentity;

function authorized(request) {
  const header = request.headers.authorization || "";
  const supplied = header.startsWith("Bearer ") ? header.slice(7) : "";
  const expectedBytes = Buffer.from(apiKey);
  const suppliedBytes = Buffer.from(supplied);
  return suppliedBytes.length === expectedBytes.length && timingSafeEqual(suppliedBytes, expectedBytes);
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
  try { value = JSON.parse(Buffer.concat(chunks).toString("utf8")); }
  catch {
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

function idempotencyKey(request, response) {
  const value = request.headers["idempotency-key"];
  if (typeof value !== "string" || value.trim().length < 1 || value.length > 255) {
    send(response, 400, { error: "idempotency_key_required" });
    return null;
  }
  return value;
}

function mapDatabaseError(error) {
  const message = String(error?.message || "");
  if (message.includes("not authorized for this product mission") ||
      message.includes("not authorized for this product task plan") ||
      message.includes("session identity is not an isolated product runtime")) return [403, "product_scope_denied"];
  if (message.includes("idempotency key reused with different content") ||
      message.includes("task plan idempotency key reused with different content")) return [409, "idempotency_conflict"];
  if (message.includes("version must equal the next stored version") ||
      message.includes("plan_version must equal the next stored version")) return [409, "version_conflict"];
  if (message.includes("mission version not found for this product runtime")) return [404, "mission_version_not_found"];
  if (message.includes("invalid mission snapshot")) return [422, "invalid_mission"];
  if (message.includes("invalid task plan snapshot") ||
      message.includes("task plan contains") ||
      message.includes("task plan project or mission identity mismatch")) return [422, "invalid_task_plan"];
  return [503, "database_unavailable"];
}


function nonEmptyString(value, max) {
  return typeof value === "string" && value.trim().length > 0 && value.length <= max;
}

function validateIntake(input) {
  if (!input || typeof input !== "object" || Array.isArray(input) ||
      Object.keys(input).some(key => !["dossier", "mission", "task_plan"].includes(key)) ||
      !input.dossier || !input.mission || !input.task_plan) {
    return "intake must contain exactly dossier, mission, and task_plan objects";
  }
  const { dossier, mission, task_plan: plan } = input;
  if ([dossier, mission, plan].some(x => !x || typeof x !== "object" || Array.isArray(x) || Object.hasOwn(x, "project_id"))) {
    return "intake snapshots must be objects and cannot supply project_id";
  }
  if (dossier.schema_version !== 1 || dossier.product_type !== productIdentity.product_type ||
      !nonEmptyString(dossier.mission, 12000) || !Array.isArray(dossier.requirements) || dossier.requirements.length < 1 ||
      !Array.isArray(dossier.acceptance_criteria) || dossier.acceptance_criteria.length < 1 ||
      !dossier.lifecycle || dossier.lifecycle.state !== "pending_approval") {
    return "invalid dossier or dossier lifecycle must be pending_approval";
  }
  const missionKeys = new Set(["mission_id","project_key","version","title","objective","acceptance_criteria","constraints","risk_class","approval_required","budget_currency","budget_limit_minor"]);
  if (Object.keys(mission).some(k => !missionKeys.has(k)) ||
      mission.project_key !== productIdentity.project_key ||
      !nonEmptyString(mission.mission_id, 80) || !Number.isInteger(mission.version) || mission.version < 1 ||
      !nonEmptyString(mission.title,160) || !nonEmptyString(mission.objective,12000) ||
      !Array.isArray(mission.acceptance_criteria) || mission.acceptance_criteria.length < 1 || mission.acceptance_criteria.length > 30 ||
      !Array.isArray(mission.constraints || []) || (mission.constraints || []).length > 30 ||
      !["low","medium","high","critical"].includes(mission.risk_class || "low") ||
      mission.approval_required !== true ||
      (["high","critical"].includes(mission.risk_class) && !mission.approval_required) ||
      ((mission.budget_currency === undefined) !== (mission.budget_limit_minor === undefined)) ||
      (mission.budget_currency !== undefined && !/^[A-Z]{3}$/.test(mission.budget_currency)) ||
      (mission.budget_limit_minor !== undefined && (!Number.isSafeInteger(mission.budget_limit_minor) || mission.budget_limit_minor < 0))) {
    return "invalid mission; approval_required must be true for intake";
  }
  const planKeys = new Set(["mission_id","mission_version","plan_version","project_key","tasks","dependencies"]);
  if (Object.keys(plan).some(k => !planKeys.has(k)) ||
      plan.mission_id !== mission.mission_id || plan.mission_version !== mission.version ||
      plan.project_key !== productIdentity.project_key || !Number.isInteger(plan.plan_version) || plan.plan_version < 1 ||
      !Array.isArray(plan.tasks) || plan.tasks.length < 1 || plan.tasks.length > 100 ||
      !Array.isArray(plan.dependencies) || plan.dependencies.length > 500) {
    return "invalid task plan identity or shape";
  }
  const ids = new Set();
  for (const task of plan.tasks) {
    if (!task || typeof task !== "object" || Array.isArray(task) ||
        !nonEmptyString(task.task_id,80) || ids.has(task.task_id) ||
        task.project_key !== productIdentity.project_key ||
        !nonEmptyString(task.title,160) || !nonEmptyString(task.request,12000) ||
        !Array.isArray(task.acceptance_criteria) || task.acceptance_criteria.length < 1 || task.acceptance_criteria.length > 30 ||
        !["low","medium","high","critical"].includes(task.risk_class || "low") ||
        typeof (task.approval_required ?? false) !== "boolean" ||
        (["high","critical"].includes(task.risk_class) && task.approval_required !== true) ||
        ((task.repository === undefined) !== (task.base_ref === undefined))) {
      return "invalid task envelope in plan";
    }
    ids.add(task.task_id);
  }
  const edges = new Set();
  const outgoing = new Map([...ids].map(id => [id, []]));
  const indegree = new Map([...ids].map(id => [id, 0]));
  for (const edge of plan.dependencies) {
    if (!edge || typeof edge !== "object" || Object.keys(edge).length !== 2 ||
        !ids.has(edge.depends_on) || !ids.has(edge.task_id) || edge.depends_on === edge.task_id) {
      return "invalid task dependency";
    }
    const key = edge.depends_on + "\\u0000" + edge.task_id;
    if (edges.has(key)) return "duplicate task dependency";
    edges.add(key);
    outgoing.get(edge.depends_on).push(edge.task_id);
    indegree.set(edge.task_id, indegree.get(edge.task_id) + 1);
  }
  const ready = [...ids].filter(id => indegree.get(id) === 0);
  let visited = 0;
  while (ready.length) {
    const id = ready.pop();
    visited++;
    for (const next of outgoing.get(id)) {
      indegree.set(next, indegree.get(next) - 1);
      if (indegree.get(next) === 0) ready.push(next);
    }
  }
  if (visited !== ids.size) return "task plan dependency graph contains a cycle";
  return null;
}

function intakeKey(root, kind) {
  const digest = createHash("sha256").update(root).digest("hex").slice(0, 48);
  return `intake:${digest}:${kind}`;
}

async function recordIntake(input, rootKey) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const dossierVersion = await client.query(
      "SELECT factory.record_product_dossier($1::uuid, $2::jsonb, $3::text) AS version_no",
      [productIdentity.project_id, JSON.stringify(input.dossier), intakeKey(rootKey, "dossier")]
    );
    const missionVersion = await client.query(
      "SELECT factory.record_mission_version($1::uuid, $2::jsonb, $3::text) AS version_no",
      [productIdentity.project_id, JSON.stringify(input.mission), intakeKey(rootKey, "mission")]
    );
    const planVersion = await client.query(
      "SELECT factory.record_task_plan_version($1::uuid, $2::text, $3::integer, $4::jsonb, $5::text) AS plan_version_no",
      [productIdentity.project_id, input.mission.mission_id, input.mission.version, JSON.stringify(input.task_plan), intakeKey(rootKey, "plan")]
    );
    await client.query("COMMIT");
    return {
      dossier_version: dossierVersion.rows[0].version_no,
      mission_version: missionVersion.rows[0].version_no,
      plan_version: planVersion.rows[0].plan_version_no
    };
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}

async function verifyDatabaseIdentity() {
  const identityResult = await pool.query(`
    SELECT session_user::text AS login,
      pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER') AS is_runtime,
      pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER') AS is_approver,
      pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') AS is_executor,
      (SELECT count(*)::int FROM factory.project_identities WHERE role_name = session_user) AS identity_count,
      (SELECT project_id::text FROM factory.project_identities WHERE role_name = session_user LIMIT 1) AS project_id
  `);
  const identity = identityResult.rows[0];
  if (!identity || !identity.is_runtime || identity.is_approver || identity.is_executor ||
      identity.identity_count !== 1 || !identity.project_id) {
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
  const url = new URL(request.url || "/", "http://127.0.0.1");
  if (request.method === "GET" && url.pathname === "/health") {
    return send(response, 200, { ok: true, service: "mission-plan-api", version: "0.1.0" });
  }
  if (!authorized(request)) return send(response, 401, { error: "unauthorized" });
  if (request.method === "GET" && url.pathname === "/v1/product") {
    return send(response, 200, { product: productIdentity });
  }


  if (request.method === "POST" && url.pathname === "/v1/intake") {
    const key = idempotencyKey(request, response);
    if (!key) return;
    const input = await readJson(request);
    const invalid = validateIntake(input);
    if (invalid) return send(response, 422, { error: "invalid_intake", detail: invalid });
    const versions = await recordIntake(input, key);
    return send(response, 200, {
      product: productIdentity,
      intake_status: "pending_human_approval",
      dispatch_authorized: false,
      task_creation: "not_performed",
      resource_reservation: "not_performed",
      versions,
      mission_id: input.mission.mission_id
    });
  }

  if (request.method === "POST" && url.pathname === "/v1/missions") {
    const key = idempotencyKey(request, response);
    if (!key) return;
    const mission = await readJson(request);
    if (Object.hasOwn(mission, "project_id")) return send(response, 400, { error: "project_identity_is_server_bound" });
    if (mission.project_key !== productIdentity.project_key) return send(response, 422, { error: "mission_product_mismatch" });
    const result = await pool.query(
      "SELECT factory.record_mission_version($1::uuid, $2::jsonb, $3::text) AS version_no",
      [productIdentity.project_id, JSON.stringify(mission), key]
    );
    const saved = await pool.query(`
      SELECT version_no, mission, created_by_login::text, created_at
      FROM factory.mission_versions WHERE mission_id = $1 AND version_no = $2 LIMIT 1
    `, [mission.mission_id, result.rows[0].version_no]);
    if (saved.rowCount !== 1) throw new Error("committed mission version could not be read back");
    return send(response, 200, { product: productIdentity, mission: saved.rows[0] });
  }

  const missionRoute = url.pathname.match(/^\/v1\/missions\/([^/]+)(?:\/(versions|plans))?$/);
  if (missionRoute) {
    let missionId;
    try { missionId = decodeURIComponent(missionRoute[1]); }
    catch { return send(response, 400, { error: "invalid_mission_id" }); }
    if (!missionId || missionId.length > 80) return send(response, 400, { error: "invalid_mission_id" });
    const suffix = missionRoute[2] || "";
    if (request.method === "GET" && (suffix === "" || suffix === "versions")) {
      const rawLimit = url.searchParams.get("limit") || (suffix === "" ? "1" : "20");
      const limit = Number(rawLimit);
      if (!Number.isInteger(limit) || limit < 1 || limit > 100) return send(response, 400, { error: "invalid_limit" });
      const result = await pool.query(`
        SELECT version_no, mission, created_by_login::text, created_at
        FROM factory.mission_versions WHERE mission_id = $1
        ORDER BY version_no DESC LIMIT $2
      `, [missionId, limit]);
      if (result.rowCount === 0) return send(response, 404, { error: "mission_not_found" });
      return send(response, 200, { product: productIdentity, mission_id: missionId, versions: result.rows });
    }
    if (suffix === "plans" && request.method === "POST") {
      const key = idempotencyKey(request, response);
      if (!key) return;
      const plan = await readJson(request);
      if (Object.hasOwn(plan, "project_id")) return send(response, 400, { error: "project_identity_is_server_bound" });
      if (plan.mission_id !== missionId) return send(response, 400, { error: "mission_path_body_mismatch" });
      if (plan.project_key !== productIdentity.project_key) return send(response, 422, { error: "task_plan_product_mismatch" });
      const result = await pool.query(
        "SELECT factory.record_task_plan_version($1::uuid, $2::text, $3::integer, $4::jsonb, $5::text) AS plan_version_no",
        [productIdentity.project_id, missionId, plan.mission_version, JSON.stringify(plan), key]
      );
      const saved = await pool.query(`
        SELECT mission_id, mission_version_no, plan_version_no, task_plan, created_by_login::text, created_at
        FROM factory.task_plan_versions
        WHERE mission_id = $1 AND plan_version_no = $2 LIMIT 1
      `, [missionId, result.rows[0].plan_version_no]);
      if (saved.rowCount !== 1) throw new Error("committed task plan version could not be read back");
      return send(response, 200, { product: productIdentity, task_plan: saved.rows[0] });
    }
    if (suffix === "plans" && request.method === "GET") {
      const rawLimit = url.searchParams.get("limit") || "20";
      const limit = Number(rawLimit);
      if (!Number.isInteger(limit) || limit < 1 || limit > 100) return send(response, 400, { error: "invalid_limit" });
      const result = await pool.query(`
        SELECT mission_id, mission_version_no, plan_version_no, task_plan, created_by_login::text, created_at
        FROM factory.task_plan_versions WHERE mission_id = $1
        ORDER BY plan_version_no DESC LIMIT $2
      `, [missionId, limit]);
      return send(response, 200, { product: productIdentity, mission_id: missionId, versions: result.rows });
    }
  }
  return send(response, 404, { error: "not_found" });
}

const server = createServer(async (request, response) => {
  try { await handle(request, response); }
  catch (error) {
    if (error?.statusCode) return send(response, error.statusCode, { error: error.message });
    const [status, code] = mapDatabaseError(error);
    console.error("mission plan request failed", { code, message: error?.message });
    return send(response, status, { error: code });
  }
});

await verifyDatabaseIdentity();
server.listen(port, "0.0.0.0", () => {
  console.log("mission-plan-api listening", { port, project_key: productIdentity.project_key, database_login: productIdentity.login });
});

async function shutdown() {
  server.close(async () => { await pool.end(); process.exit(0); });
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
