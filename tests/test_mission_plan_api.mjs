import assert from "node:assert/strict";

const base = process.env.MISSION_PLAN_API_URL || "http://127.0.0.1:8789";
const key = process.env.MISSION_PLAN_API_KEY;
assert.ok(key && key.length >= 64, "test API key must contain at least 64 characters");

const health = await fetch(`${base}/health`);
assert.equal(health.status, 200);
assert.deepEqual(await health.json(), { ok: true, service: "mission-plan-api", version: "0.1.0" });

assert.equal((await fetch(`${base}/v1/product`)).status, 401);
const productResponse = await fetch(`${base}/v1/product`, { headers: { authorization: `Bearer ${key}` } });
assert.equal(productResponse.status, 200);
const product = (await productResponse.json()).product;
assert.equal(product.project_key, "tradix");

const missionId = "mission-plan-api-ci";
const mission = {
  mission_id: missionId,
  project_key: product.project_key,
  version: 1,
  title: "Mission plan API integration",
  objective: "Verify durable mission and plan access through the isolated product API.",
  acceptance_criteria: ["Mission versions persist", "Task plan versions persist"],
  constraints: ["Do not dispatch tasks"],
  risk_class: "low",
  approval_required: false
};
const missionKey = "mission-plan-api-ci-mission-v1";
const postMission = () => fetch(`${base}/v1/missions`, {
  method: "POST",
  headers: { authorization: `Bearer ${key}`, "content-type": "application/json", "idempotency-key": missionKey },
  body: JSON.stringify(mission)
});
const createdMission = await postMission();
assert.equal(createdMission.status, 200);
const createdMissionBody = await createdMission.json();
assert.equal(createdMissionBody.mission.version_no, 1);
assert.equal(createdMissionBody.mission.mission.mission_id, missionId);
const retriedMission = await postMission();
assert.equal(retriedMission.status, 200);
assert.equal((await retriedMission.json()).mission.version_no, 1);

const changedMission = { ...mission, title: "Changed payload under same idempotency key" };
const conflict = await fetch(`${base}/v1/missions`, {
  method: "POST",
  headers: { authorization: `Bearer ${key}`, "content-type": "application/json", "idempotency-key": missionKey },
  body: JSON.stringify(changedMission)
});
assert.equal(conflict.status, 409);
assert.deepEqual(await conflict.json(), { error: "idempotency_conflict" });

const forged = await fetch(`${base}/v1/missions`, {
  method: "POST",
  headers: { authorization: `Bearer ${key}`, "content-type": "application/json", "idempotency-key": "mission-plan-api-forged" },
  body: JSON.stringify({ ...mission, project_id: "22222222-2222-4222-8222-222222222222" })
});
assert.equal(forged.status, 400);

const latestMission = await fetch(`${base}/v1/missions/${missionId}`, { headers: { authorization: `Bearer ${key}` } });
assert.equal(latestMission.status, 200);
assert.equal((await latestMission.json()).versions[0].version_no, 1);

const plan = {
  mission_id: missionId,
  mission_version: 1,
  plan_version: 1,
  project_key: product.project_key,
  tasks: [
    {
      task_id: "define-api-contract",
      project_key: product.project_key,
      title: "Define API contract",
      request: "Record the API contract as a plan task.",
      acceptance_criteria: ["Contract recorded"],
      risk_class: "low",
      approval_required: false
    },
    {
      task_id: "verify-api-contract",
      project_key: product.project_key,
      title: "Verify API contract",
      request: "Verify the recorded API contract.",
      acceptance_criteria: ["Verification recorded"],
      risk_class: "low",
      approval_required: false
    }
  ],
  dependencies: [{ depends_on: "define-api-contract", task_id: "verify-api-contract" }]
};
const planKey = "mission-plan-api-ci-plan-v1";
const postPlan = () => fetch(`${base}/v1/missions/${missionId}/plans`, {
  method: "POST",
  headers: { authorization: `Bearer ${key}`, "content-type": "application/json", "idempotency-key": planKey },
  body: JSON.stringify(plan)
});
const createdPlan = await postPlan();
assert.equal(createdPlan.status, 200);
const createdPlanBody = await createdPlan.json();
assert.equal(createdPlanBody.task_plan.plan_version_no, 1);
assert.equal(createdPlanBody.task_plan.task_plan.dependencies.length, 1);
const retriedPlan = await postPlan();
assert.equal(retriedPlan.status, 200);
assert.equal((await retriedPlan.json()).task_plan.plan_version_no, 1);

const planHistory = await fetch(`${base}/v1/missions/${missionId}/plans?limit=10`, {
  headers: { authorization: `Bearer ${key}` }
});
assert.equal(planHistory.status, 200);
assert.ok((await planHistory.json()).versions.some(row => row.plan_version_no === 1));

const pathMismatch = await fetch(`${base}/v1/missions/another-mission/plans`, {
  method: "POST",
  headers: { authorization: `Bearer ${key}`, "content-type": "application/json", "idempotency-key": "mission-plan-api-path-mismatch" },
  body: JSON.stringify(plan)
});
assert.equal(pathMismatch.status, 400);

console.log("mission plan API integration checks passed");
