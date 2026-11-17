import assert from "node:assert/strict";

const base = process.env.MEMORY_GATEWAY_URL || "http://127.0.0.1:8787";
const tradixToken = process.env.MEMORY_GATEWAY_TRADIX_TOKEN;
const otherToken = process.env.MEMORY_GATEWAY_OTHER_TOKEN;
assert.ok(tradixToken && tradixToken.length >= 40, "TRADIX project token required");
assert.ok(otherToken && otherToken.length >= 40, "second project token required");

const health = await fetch(`${base}/health`);
assert.equal(health.status, 200);
assert.deepEqual(await health.json(), { ok: true, service: "memory-gateway", version: "1.1.0" });

const unauthorized = await fetch(`${base}/v1/context`);
assert.equal(unauthorized.status, 401);

const legacySelector = await fetch(`${base}/v1/context?project=tradix`, {
  headers: { authorization: `Bearer ${tradixToken}` }
});
assert.equal(legacySelector.status, 400);
assert.deepEqual(await legacySelector.json(), { error: "project_selector_not_supported" });

const tradix = await fetch(`${base}/v1/context`, {
  headers: { authorization: `Bearer ${tradixToken}` }
});
assert.equal(tradix.status, 200);
const tradixContext = await tradix.json();
assert.equal(tradixContext.project.project_key, "tradix");
assert.equal(tradixContext.project.name, "TRADIX");

const other = await fetch(`${base}/v1/context`, {
  headers: { authorization: `Bearer ${otherToken}` }
});
assert.equal(other.status, 200);
const otherContext = await other.json();
assert.equal(otherContext.project.project_key, "other-project");
assert.equal(otherContext.project.name, "Other Project");
assert.notEqual(tradixContext.project.project_id, otherContext.project.project_id);

const revoked = await fetch(`${base}/v1/context`, {
  headers: { authorization: "Bearer revoked-project-token-ci-0123456789abcdef0123456789abcdef" }
});
assert.equal(revoked.status, 401);

console.log("memory gateway project isolation and authentication checks passed");
