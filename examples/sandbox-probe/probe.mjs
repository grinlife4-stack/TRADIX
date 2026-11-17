import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";

assert.equal(typeof process.getuid, "function", "Linux UID inspection must be available");
assert.notEqual(process.getuid(), 0, "sandbox must not run as root");

for (const key of [
  "DATABASE_URL",
  "GITHUB_TOKEN",
  "MISSION_PLAN_API_KEY",
  "MEMORY_GATEWAY_API_KEY",
  "PRODUCT_DOSSIER_API_KEY"
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

const routeLines = readFileSync("/proc/net/route", "utf8").trim().split("\n").slice(1);
const hasDefaultRoute = routeLines.some(line => line.trim().split(/\s+/)[1] === "00000000");
assert.equal(hasDefaultRoute, false, "sandbox must not have a default IPv4 route");

console.log("PASS non-root execution");
console.log("PASS no injected application secrets");
console.log("PASS read-only product workspace");
console.log("PASS bounded temporary storage");
console.log("PASS no default IPv4 route");
