import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const result = spawnSync(process.execPath, [join(here, "index.mjs")], {
  encoding: "utf8",
  timeout: 5000,
  env: { PATH: process.env.PATH ?? "", NODE_ENV: "test" }
});
assert.equal(result.status, 0, result.stderr || "health execution failed");
assert.equal(result.stdout.trim(), "Hello from TRADIX");
console.log(JSON.stringify({ health: "ok", service: "hello-world-demo" }));
