import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const readJson = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const nodeSchema = readJson("../../schemas/hardware-node-v1.schema.json");
const requestSchema = readJson("../../schemas/hardware-resource-request-v1.schema.json");
const ajv = new Ajv2020({ allErrors: true, strict: true, allowUnionTypes: true });
addFormats(ajv);

const validateNode = ajv.compile(nodeSchema);
const validateRequest = ajv.compile(requestSchema);

const node = {
  schema_version: 1,
  node_id: "lab-node-unverified",
  status: "quarantined",
  observed_at: "2026-11-17T12:00:00Z",
  source: { agent_version: "inventory-contract-fixture", inventory_sha256: "a".repeat(64) },
  host: { os: "unknown", architecture: "unknown", kernel: null },
  cpu: { model: null, physical_cores: null, logical_threads: null, allocatable_millicores: 0, features: [] },
  memory: { total_bytes: null, available_bytes: null, reserved_bytes: 0, allocatable_bytes: 0, technology: null, ecc: null },
  accelerators: [{
    device_id: "gpu-0",
    kind: "gpu",
    vendor: null,
    model: null,
    memory_total_bytes: null,
    memory_free_bytes: null,
    memory_reserved_bytes: 0,
    supported_apis: [],
    health: "unknown"
  }],
  storage: [],
  network: [],
  runtime: { container_runtime: null, sandbox_profiles: [], os_kernel_compatible: false },
  health: { overall: "unknown", last_heartbeat_at: null, checks: [] },
  notes: "Fixture only. No real host or hardware has been inspected."
};

const request = {
  schema_version: 1,
  request_id: "task-123:stage-test",
  task_id: "task-123",
  runtime_profile: "gvisor",
  cpu: { min_millicores: 1000, max_millicores: 2000, architecture: ["x86_64"] },
  memory: { ram_bytes: 1073741824, hard_limit: true },
  accelerators: [{ kind: "gpu", count: 1, min_memory_bytes: 8589934592, required_api: "rocm" }],
  storage: { scratch_bytes: 1073741824, persistent_bytes: 0 },
  network: { profile: "none" },
  limits: { wall_time_seconds: 300, max_processes: 64, max_output_bytes: 1048576, lease_ttl_seconds: 60 },
  security: { untrusted_code: true, require_read_only_source: true, secrets_profile: "none" }
};

assert.equal(validateNode(node), true, ajv.errorsText(validateNode.errors));
assert.equal(validateRequest(request), true, ajv.errorsText(validateRequest.errors));
console.log("PASS: quarantined mixed/unknown node inventory and portable resource request validate");

const invalidNodes = [
  { ...node, node_id: "Upper Case Not Allowed" },
  { ...node, cpu: { ...node.cpu, logical_threads: 0 } },
  { ...node, accelerators: [{ ...node.accelerators[0], memory_reserved_bytes: -1 }] },
  { ...node, unexpected_vendor_lock: true }
];
for (const invalid of invalidNodes) assert.equal(validateNode(invalid), false, "invalid node inventory unexpectedly passed");

const invalidRequests = [
  { ...request, runtime_profile: "provider-specific-host" },
  { ...request, memory: { ram_bytes: 0, hard_limit: true } },
  { ...request, network: { profile: "unrestricted" } },
  { ...request, accelerators: [{ ...request.accelerators[0], count: 0 }] },
  { ...request, secrets: { production_token: "must-not-exist" } }
];
for (const invalid of invalidRequests) assert.equal(validateRequest(invalid), false, "invalid resource request unexpectedly passed");

console.log("PASS: malformed, unsafe, and provider-pinned inventory/resource requests are rejected");
