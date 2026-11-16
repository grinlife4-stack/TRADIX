import assert from "node:assert/strict";

const base = process.env.MEMORY_GATEWAY_URL || "http://127.0.0.1:8787";
const key = process.env.MEMORY_GATEWAY_API_KEY;
assert.ok(key && key.length >= 64, "test API key must be at least 64 characters");

const health = await fetch(`${base}/health`);
assert.equal(health.status, 200);
assert.deepEqual(await health.json(), { ok: true, service: "memory-gateway", version: "1.0.2" });

const unauthorized = await fetch(`${base}/v1/context?project=missing`);
assert.equal(unauthorized.status, 401);

const missing = await fetch(`${base}/v1/context?project=missing`, {
  headers: { authorization: `Bearer ${key}` }
});
assert.equal(missing.status, 404);
assert.deepEqual(await missing.json(), { error: "project_not_found" });

const invalid = await fetch(`${base}/v1/context?project=BAD%20KEY`, {
  headers: { authorization: `Bearer ${key}` }
});
assert.equal(invalid.status, 400);

const valid = await fetch(`${base}/v1/context?project=tradix`, {
  headers: { authorization: `Bearer ${key}` }
});
assert.equal(valid.status, 200);
const context = await valid.json();
assert.equal(context.schema_version, "1.0");
assert.equal(context.project.project_key, "tradix");
assert.equal(context.project.name, "TRADIX");
assert.ok(Array.isArray(context.active_missions));
assert.ok(Array.isArray(context.approved_decisions));
assert.ok(Array.isArray(context.recent_events));
assert.equal(context.recent_events[0].event_type, "CI_INTEGRATION_TEST");

console.log("memory gateway integration checks passed");
