import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("./index.mjs", import.meta.url), "utf8");
assert.match(source, /^console\.log\("Hello from TRADIX"\);?\s*$/);
assert.doesNotMatch(source, /\b(fetch|https?:|child_process|process\.env)\b/);
console.log(JSON.stringify({
  review: "passed",
  checks: ["exact-output-source", "no-network-or-child-process-dependency"]
}));
