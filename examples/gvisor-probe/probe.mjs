import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";

assert.equal(typeof process.getuid, "function", "Linux UID inspection must be available");
assert.notEqual(process.getuid(), 0, "sandbox must not run as root");

const status = readFileSync("/proc/self/status", "utf8");
const effectiveCapabilities = status.match(/^CapEff:\s+([0-9a-f]+)$/m)?.[1];
const noNewPrivileges = status.match(/^NoNewPrivs:\s+(\d+)$/m)?.[1];
assert.ok(effectiveCapabilities, "effective Linux capabilities must be inspectable");
assert.match(effectiveCapabilities, /^0+$/, "sandbox must have zero effective Linux capabilities");
assert.equal(noNewPrivileges, "1", "no-new-privileges must be enforced");

for (const key of [
  "DATABASE_URL",
  "GITHUB_TOKEN",
  "MISSION_PLAN_API_KEY",
  "MEMORY_GATEWAY_API_KEY",
  "PRODUCT_DOSSIER_API_KEY",
  "TRADIX_ARTIFACT_S3_ACCESS_KEY_ID",
  "TRADIX_ARTIFACT_S3_SECRET_ACCESS_KEY"
]) {
  assert.equal(process.env[key], undefined, "secret environment variable leaked: " + key);
}

assert.throws(
  () => writeFileSync("/workspace/.tradix-sandbox-write-probe", "must-not-write"),
  error => error && ["EROFS", "EACCES"].includes(error.code),
  "product workspace must be read-only"
);

writeFileSync("/tmp/tradix-sandbox-probe", "temporary-write-ok");
assert.equal(readFileSync("/tmp/tradix-sandbox-probe", "utf8"), "temporary-write-ok");
writeFileSync("/dev/shm/tradix-sandbox-probe", "bounded-shm-write-ok");
assert.equal(readFileSync("/dev/shm/tradix-sandbox-probe", "utf8"), "bounded-shm-write-ok");

const routeLines = readFileSync("/proc/net/route", "utf8").trim().split("\n").slice(1);
const hasDefaultRoute = routeLines.some(line => line.trim().split(/\s+/)[1] === "00000000");
assert.equal(hasDefaultRoute, false, "sandbox must not have a default IPv4 route");
const ipv6Routes = readFileSync("/proc/net/ipv6_route", "utf8").trim().split("\n");
const hasDefaultIPv6EgressRoute = ipv6Routes.some(line => {
  const fields = line.trim().split(/\s+/);
  if (fields.length < 10) return false;
  const isDefault = fields[0] === "0".repeat(32) && fields[1] === "00";
  const routeIsUp = (Number.parseInt(fields[8], 16) & 0x1) === 0x1;
  const isNonLoopback = fields[9] !== "lo";
  return isDefault && routeIsUp && isNonLoopback;
});
assert.equal(
  hasDefaultIPv6EgressRoute,
  false,
  "sandbox must not have an active non-loopback default IPv6 egress route"
);

console.log("PASS non-root execution");
console.log("PASS zero effective Linux capabilities");
console.log("PASS no-new-privileges enforced");
console.log("PASS no injected application secrets");
console.log("PASS read-only product workspace");
console.log("PASS bounded /tmp and shared-memory storage");
console.log("PASS no default IPv4 or IPv6 route");
