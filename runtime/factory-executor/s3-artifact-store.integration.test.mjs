import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  CreateBucketCommand,
  PutObjectCommand
} from "@aws-sdk/client-s3";
import {
  ArtifactStoreError,
  S3ArtifactStore,
  createS3CompatibleClient
} from "./s3-artifact-store.mjs";

const env = process.env;
const bucket = env.TRADIX_ARTIFACT_S3_BUCKET;
const rawClient = createS3CompatibleClient(env);
const store = new S3ArtifactStore({ client: rawClient, bucket });

before(async () => {
  try {
    await rawClient.send(new CreateBucketCommand({ Bucket: bucket }));
  } catch (error) {
    if (!["BucketAlreadyOwnedByYou", "BucketAlreadyExists"].includes(error.name)) throw error;
  }
});

after(async () => {
  rawClient.destroy();
});

function identity() {
  const id = randomUUID().replaceAll("-", "");
  return {
    projectKey: "ci-project",
    runId: "run-" + id,
    attemptId: "attempt-" + id
  };
}

test("uploads content-addressed objects, reads back exact bytes, and retries idempotently", async () => {
  const root = await mkdtemp(join(tmpdir(), "tradix-s3-store-"));
  try {
    const source = join(root, "test-report.txt");
    const bytes = Buffer.from("TRADIX evidence: verified output\n", "utf8");
    await writeFile(source, bytes);
    const ids = identity();
    const first = await store.uploadFile({ sourcePath: source, ...ids, contentType: "text/plain" });
    assert.equal(first.reused, false);
    assert.equal(first.byteSize, bytes.byteLength);
    assert.match(first.sha256, /^[a-f0-9]{64}$/);
    assert.match(first.key, new RegExp("^projects/" + ids.projectKey + "/runs/" + ids.runId + "/attempts/" + ids.attemptId + "/sha256/"));

    const verified = await store.readVerified({
      key: first.key,
      expectedSha256: first.sha256,
      expectedByteSize: first.byteSize
    });
    assert.deepEqual(verified.bytes, bytes);

    const retry = await store.uploadFile({ sourcePath: source, ...ids, contentType: "text/plain" });
    assert.equal(retry.reused, true);
    assert.equal(retry.key, first.key);

    const restoreRoot = join(root, "restore");
    const restored = await store.restore({
      key: first.key,
      expectedSha256: first.sha256,
      expectedByteSize: first.byteSize,
      restoreRoot,
      relativePath: "run-001/reports/test-report.txt"
    });
    assert.equal(restored.sha256, first.sha256);
    assert.deepEqual(await readFile(restored.path), bytes);
    await assert.rejects(
      store.restore({
        key: first.key,
        expectedSha256: first.sha256,
        expectedByteSize: first.byteSize,
        restoreRoot,
        relativePath: "run-001/reports/test-report.txt"
      }),
      error => error instanceof ArtifactStoreError && error.code === "DESTINATION_EXISTS"
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("rejects path traversal and symbolic-link source files", async () => {
  const root = await mkdtemp(join(tmpdir(), "tradix-s3-paths-"));
  try {
    const source = join(root, "evidence.txt");
    await writeFile(source, "path guard");
    const ids = identity();
    const uploaded = await store.uploadFile({ sourcePath: source, ...ids });
    await assert.rejects(
      store.restore({
        key: uploaded.key,
        expectedSha256: uploaded.sha256,
        expectedByteSize: uploaded.byteSize,
        restoreRoot: join(root, "restore"),
        relativePath: "../outside.txt"
      }),
      error => error instanceof ArtifactStoreError && error.code === "INVALID_DESTINATION"
    );

    const linked = join(root, "linked.txt");
    await symlink(source, linked);
    await assert.rejects(
      store.uploadFile({ sourcePath: linked, ...identity() }),
      error => error instanceof ArtifactStoreError && error.code === "INVALID_ARGUMENT"
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("rejects same-size object tampering during restore", async () => {
  const root = await mkdtemp(join(tmpdir(), "tradix-s3-tamper-"));
  try {
    const source = join(root, "immutable.txt");
    const original = Buffer.from("original evidence payload");
    const tampered = Buffer.from("tampered evidence payload");
    assert.equal(original.byteLength, tampered.byteLength);
    await writeFile(source, original);
    const ids = identity();
    const uploaded = await store.uploadFile({ sourcePath: source, ...ids, contentType: "text/plain" });

    await rawClient.send(new PutObjectCommand({
      Bucket: bucket,
      Key: uploaded.key,
      Body: original,
      ContentLength: original.byteLength,
      ContentType: "text/plain",
      Metadata: {
        sha256: uploaded.sha256,
        project_key: "wrong-project",
        run_id: ids.runId,
        attempt_id: ids.attemptId
      }
    }));
    await assert.rejects(
      store.inspect({
        key: uploaded.key,
        expectedSha256: uploaded.sha256,
        expectedByteSize: uploaded.byteSize
      }),
      error => error instanceof ArtifactStoreError && error.code === "INTEGRITY_MISMATCH"
    );

    await rawClient.send(new PutObjectCommand({
      Bucket: bucket,
      Key: uploaded.key,
      Body: tampered,
      ContentLength: tampered.byteLength,
      ContentType: "text/plain",
      Metadata: {
        sha256: uploaded.sha256,
        project_key: ids.projectKey,
        run_id: ids.runId,
        attempt_id: ids.attemptId
      }
    }));

    await assert.rejects(
      store.restore({
        key: uploaded.key,
        expectedSha256: uploaded.sha256,
        expectedByteSize: uploaded.byteSize,
        restoreRoot: join(root, "restore"),
        relativePath: "tampered.txt"
      }),
      error => error instanceof ArtifactStoreError && error.code === "INTEGRITY_MISMATCH"
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("requires HTTPS for remote S3 endpoints and rejects unsafe object identifiers", () => {
  assert.throws(
    () => createS3CompatibleClient({
      ...env,
      TRADIX_ARTIFACT_S3_ENDPOINT: "http://objects.example.com",
      TRADIX_ARTIFACT_S3_ALLOW_LOCAL_HTTP: "true"
    }),
    error => error instanceof ArtifactStoreError && error.code === "INVALID_CONFIGURATION"
  );
  assert.throws(
    () => store.objectKey({
      projectKey: "../other-project",
      runId: "run-1",
      attemptId: "attempt-1",
      sha256: "a".repeat(64),
      fileName: "report.txt"
    }),
    error => error instanceof ArtifactStoreError && error.code === "INVALID_ARGUMENT"
  );
});
