import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { buildEvidenceManifest } from "./build-evidence-manifest.mjs";

const env = {
  GITHUB_REPOSITORY: "grinlife4-stack/TRADIX",
  GITHUB_SHA: "a".repeat(40),
  GITHUB_REF: "refs/pull/22/merge",
  GITHUB_WORKFLOW: "factory-ledger-sql",
  GITHUB_RUN_ID: "123456789",
  GITHUB_RUN_ATTEMPT: "2",
  GITHUB_EVENT_NAME: "pull_request",
  GITHUB_ACTOR: "grinlife4-stack",
  GITHUB_JOB: "postgres-schema",
  GITHUB_SERVER_URL: "https://github.com"
};

test("writes a deterministic manifest with per-file hashes and PR metadata", async () => {
  const root = await mkdtemp(join(tmpdir(), "tradix-evidence-"));
  try {
    await mkdir(join(root, "nested"));
    await writeFile(join(root, "nested", "test.txt"), "verified-output\n");
    const eventPath = join(root, "event.json");
    await writeFile(eventPath, JSON.stringify({ pull_request: { number: 22 } }));
    const result = await buildEvidenceManifest({
      directory: join(root, "evidence"),
      env: { ...env, GITHUB_EVENT_PATH: eventPath },
      now: new Date("2026-11-17T10:00:00.000Z")
    });
    assert.equal(result.manifest.source.pull_request_number, 22);
    assert.equal(result.manifest.source.run_url, "https://github.com/grinlife4-stack/TRADIX/actions/runs/123456789");
    assert.deepEqual(result.manifest.files, [{
      path: "nested/test.txt",
      sha256: "eb0246c196d6fc94451aa210219e026788f9dae97c561676aa095ae57f0c7cc0",
      byte_size: 16
    }]);
    const saved = JSON.parse(await readFile(result.output, "utf8"));
    assert.deepEqual(saved, result.manifest);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("rejects missing or malformed GitHub identity instead of emitting anonymous evidence", async () => {
  const root = await mkdtemp(join(tmpdir(), "tradix-evidence-"));
  try {
    await assert.rejects(
      buildEvidenceManifest({ directory: root, env: { ...env, GITHUB_SHA: "latest" } }),
      /GITHUB_SHA/
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("rejects symbolic links in the evidence directory", async () => {
  const root = await mkdtemp(join(tmpdir(), "tradix-evidence-"));
  try {
    const evidence = join(root, "evidence");
    await mkdir(evidence);
    const target = join(root, "outside.txt");
    await writeFile(target, "outside");
    await symlink(target, join(evidence, "linked.txt"));
    await assert.rejects(
      buildEvidenceManifest({ directory: evidence, env }),
      /symbolic links/
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
