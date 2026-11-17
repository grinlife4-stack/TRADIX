import assert from "node:assert/strict";

const base = process.env.PRODUCT_DOSSIER_API_URL || "http://127.0.0.1:8788";
const key = process.env.PRODUCT_DOSSIER_API_KEY;
assert.ok(key && key.length >= 64, "test API key must contain at least 64 characters");

const health = await fetch(`${base}/health`);
assert.equal(health.status, 200);
assert.deepEqual(await health.json(), { ok: true, service: "product-dossier-api", version: "0.1.0" });

const unauthorized = await fetch(`${base}/v1/product`);
assert.equal(unauthorized.status, 401);

const productResponse = await fetch(`${base}/v1/product`, {
  headers: { authorization: `Bearer ${key}` }
});
assert.equal(productResponse.status, 200);
const product = await productResponse.json();
assert.equal(product.product.project_key, "tradix");
assert.equal(product.product.product_type, "software");

const dossier = {
  schema_version: 1,
  product_type: "software",
  mission: "API integration dossier fixture",
  requirements: ["persist through the controlled dossier writer"],
  acceptance_criteria: ["same idempotency key returns the same version"],
  lifecycle: { state: "active" },
  resource_plan: { execution: "isolated" },
  portability: { manifest: "portability.json", status: "planned" }
};
const idempotencyKey = `dossier-api-ci-${Date.now()}`;
const create = () => fetch(`${base}/v1/dossier`, {
  method: "POST",
  headers: {
    authorization: `Bearer ${key}`,
    "content-type": "application/json",
    "idempotency-key": idempotencyKey
  },
  body: JSON.stringify(dossier)
});
const first = await create();
assert.equal(first.status, 200);
const firstBody = await first.json();
assert.equal(firstBody.dossier.dossier.mission, dossier.mission);
assert.deepEqual(firstBody.dossier.dossier.portability, dossier.portability);
const retry = await create();
assert.equal(retry.status, 200);
const retryBody = await retry.json();
assert.equal(retryBody.dossier.version_no, firstBody.dossier.version_no);

const latest = await fetch(`${base}/v1/dossier`, {
  headers: { authorization: `Bearer ${key}` }
});
assert.equal(latest.status, 200);
assert.equal((await latest.json()).dossier.version_no, firstBody.dossier.version_no);

const versions = await fetch(`${base}/v1/dossier/versions?limit=10`, {
  headers: { authorization: `Bearer ${key}` }
});
assert.equal(versions.status, 200);
assert.ok((await versions.json()).versions.some(row => row.version_no === firstBody.dossier.version_no));

const forgedProject = await fetch(`${base}/v1/dossier`, {
  method: "POST",
  headers: {
    authorization: `Bearer ${key}`,
    "content-type": "application/json",
    "idempotency-key": `${idempotencyKey}-forged`
  },
  body: JSON.stringify({ ...dossier, project_id: "22222222-2222-4222-8222-222222222222" })
});
assert.equal(forgedProject.status, 400);

const wrongProductType = await fetch(`${base}/v1/dossier`, {
  method: "POST",
  headers: {
    authorization: `Bearer ${key}`,
    "content-type": "application/json",
    "idempotency-key": `${idempotencyKey}-wrong-type`
  },
  body: JSON.stringify({ ...dossier, product_type: "physical" })
});
assert.equal(wrongProductType.status, 422);
assert.deepEqual(await wrongProductType.json(), { error: "invalid_product_dossier" });

console.log("product dossier API integration checks passed");
