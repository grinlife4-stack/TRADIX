import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const result = spawnSync(process.execPath, [join(here, "index.mjs")], {
  encoding: "utf8",
  timeout: 5000
});

assert.equal(result.status, 0, result.stderr || "hello-world process failed");
assert.equal(result.stdout.trim(), "Hello from TRADIX");
assert.equal(result.stderr, "");
console.log("PASS: hello-world program executed and produced the expected output");
