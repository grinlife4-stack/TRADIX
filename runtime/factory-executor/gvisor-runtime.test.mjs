import test from "node:test";
import assert from "node:assert/strict";
import {
  GVISOR_RUNTIME,
  GvisorPreflightError,
  assertGvisorRuntimeRegistered,
  assertImmutableImageId,
  buildGvisorRuntimeArgs,
  parseDockerRuntimes,
  preflightGvisorSandbox
} from "./gvisor-runtime.mjs";

const image = `sha256:${"a".repeat(64)}`;

test("requires Docker to register runsc", () => {
  assert.equal(assertGvisorRuntimeRegistered('{"runc":{"path":"runc"},"runsc":{"path":"runsc"}}').path, "runsc");
  assert.throws(
    () => assertGvisorRuntimeRegistered('{"runc":{"path":"runc"}}'),
    error => error instanceof GvisorPreflightError && error.code === "BACKEND_UNAVAILABLE"
  );
});

test("rejects malformed runtime inventory and mutable image references", () => {
  assert.throws(() => parseDockerRuntimes("not-json"), /invalid runtime metadata/);
  assert.throws(() => assertImmutableImageId("node:latest"), /immutable sha256 image ID/);
});

test("selects only the fixed runsc runtime", () => {
  assert.deepEqual(buildGvisorRuntimeArgs(), ["--runtime=runsc"]);
});

test("preflight fails closed before running commands on unsupported hosts", async () => {
  let calls = 0;
  await assert.rejects(
    preflightGvisorSandbox({ image, platform: "win32", arch: "x64", runCommand: async () => { calls++; } }),
    error => error.code === "BACKEND_UNAVAILABLE"
  );
  assert.equal(calls, 0);
});

test("preflight verifies runtime, exact image identity, then smoke-runs under runsc", async () => {
  const calls = [];
  const result = await preflightGvisorSandbox({
    image, platform: "linux", arch: "x64",
    runCommand: async args => {
      calls.push(args);
      if (args[0] === "info") return { stdout: '{"runsc":{"path":"runsc"}}' };
      if (args[0] === "image") return { stdout: image };
      return { stdout: "v24.22.3" };
    }
  });
  assert.equal(result.runtime, GVISOR_RUNTIME);
  assert.equal(result.imageId, image);
  assert.equal(calls.length, 3);
  assert.ok(calls[2].includes("--runtime=runsc"));
  assert.ok(calls[2].includes("--network"));
  assert.ok(calls[2].includes("none"));
});

test("preflight refuses image mismatch and does not smoke-run", async () => {
  let calls = 0;
  await assert.rejects(
    preflightGvisorSandbox({
      image, platform: "linux", arch: "x64",
      runCommand: async args => {
        calls++;
        if (args[0] === "info") return { stdout: '{"runsc":{"path":"runsc"}}' };
        return { stdout: `sha256:${"b".repeat(64)}` };
      }
    }),
    error => error.code === "BACKEND_MISCONFIGURED"
  );
  assert.equal(calls, 2);
});
