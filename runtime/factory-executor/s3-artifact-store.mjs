import { createHash, randomUUID } from "node:crypto";
import { lstat, mkdir, open, readFile, realpath, link, unlink } from "node:fs/promises";
import { basename, isAbsolute, relative, resolve, sep } from "node:path";
import {
  GetObjectCommand,
  HeadObjectCommand,
  PutObjectCommand,
  S3Client
} from "@aws-sdk/client-s3";

const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const BUCKET = /^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/;
const MAX_ARTIFACT_BYTES = 128 * 1024 * 1024;

export class ArtifactStoreError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "ArtifactStoreError";
    this.code = code;
  }
}

function requireString(value, label, max = 255) {
  if (typeof value !== "string" || !value.trim() || value.length > max) {
    throw new ArtifactStoreError("INVALID_ARGUMENT", label + " is invalid");
  }
  return value;
}

function validateId(value, label) {
  requireString(value, label, 128);
  if (!SAFE_ID.test(value)) throw new ArtifactStoreError("INVALID_ARGUMENT", label + " has an unsafe format");
  return value;
}

function validateHash(value) {
  if (typeof value !== "string" || !SHA256.test(value)) {
    throw new ArtifactStoreError("INVALID_ARGUMENT", "expected_sha256 must be a lowercase SHA-256 digest");
  }
  return value;
}

function validateFileName(value) {
  requireString(value, "file_name", 128);
  const name = basename(value);
  if (name !== value || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(name) || name === "." || name === "..") {
    throw new ArtifactStoreError("INVALID_ARGUMENT", "file_name must be a simple safe file name");
  }
  return name;
}

function validateBucket(value) {
  requireString(value, "bucket", 63);
  if (!BUCKET.test(value) || value.includes("..")) {
    throw new ArtifactStoreError("INVALID_CONFIGURATION", "S3 bucket name is invalid");
  }
  return value;
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function isNotFound(error) {
  return error && (error.$metadata?.httpStatusCode === 404 ||
    ["NotFound", "NoSuchKey", "NoSuchObject"].includes(error.name));
}

async function bodyToBuffer(body) {
  if (body && typeof body.transformToByteArray === "function") {
    return Buffer.from(await body.transformToByteArray());
  }
  if (body && Symbol.asyncIterator in Object(body)) {
    const chunks = [];
    for await (const chunk of body) chunks.push(Buffer.from(chunk));
    return Buffer.concat(chunks);
  }
  throw new ArtifactStoreError("INVALID_RESPONSE", "object storage returned an unreadable response body");
}

function validateObjectKey(key, expectedSha256) {
  requireString(key, "object_key", 1024);
  const parts = key.split("/");
  if (parts.length !== 9 ||
      parts[0] !== "projects" ||
      parts[2] !== "runs" ||
      parts[4] !== "attempts" ||
      parts[6] !== "sha256" ||
      parts[7] !== expectedSha256) {
    throw new ArtifactStoreError("INVALID_ARGUMENT", "object key does not match the expected content-addressed layout");
  }
  validateId(parts[1], "project_key");
  validateId(parts[3], "run_id");
  validateId(parts[5], "attempt_id");
  validateFileName(parts[8]);
  return parts;
}

export function createS3CompatibleClient(env = process.env) {
  const endpointText = requireString(env.TRADIX_ARTIFACT_S3_ENDPOINT, "TRADIX_ARTIFACT_S3_ENDPOINT", 512);
  let endpoint;
  try {
    endpoint = new URL(endpointText);
  } catch {
    throw new ArtifactStoreError("INVALID_CONFIGURATION", "S3 endpoint must be a valid URL");
  }
  const allowLocalHttp = env.TRADIX_ARTIFACT_S3_ALLOW_LOCAL_HTTP === "true";
  const localHost = ["127.0.0.1", "localhost", "::1"].includes(endpoint.hostname);
  if (endpoint.protocol !== "https:" && !(allowLocalHttp && localHost && endpoint.protocol === "http:")) {
    throw new ArtifactStoreError("INVALID_CONFIGURATION", "S3 endpoint must use HTTPS; HTTP is allowed only for explicit loopback tests");
  }
  if (endpoint.username || endpoint.password || endpoint.search || endpoint.hash || (endpoint.pathname !== "/" && endpoint.pathname !== "")) {
    throw new ArtifactStoreError("INVALID_CONFIGURATION", "S3 endpoint must not embed credentials, query, or fragment");
  }
  const region = requireString(env.TRADIX_ARTIFACT_S3_REGION, "TRADIX_ARTIFACT_S3_REGION", 64);
  const accessKeyId = requireString(env.TRADIX_ARTIFACT_S3_ACCESS_KEY_ID, "TRADIX_ARTIFACT_S3_ACCESS_KEY_ID", 256);
  const secretAccessKey = requireString(env.TRADIX_ARTIFACT_S3_SECRET_ACCESS_KEY, "TRADIX_ARTIFACT_S3_SECRET_ACCESS_KEY", 512);
  return new S3Client({
    endpoint: endpoint.toString().replace(/\/$/, ""),
    region,
    forcePathStyle: true,
    maxAttempts: 3,
    credentials: { accessKeyId, secretAccessKey }
  });
}

export class S3ArtifactStore {
  constructor({ client, bucket }) {
    if (!client || typeof client.send !== "function") {
      throw new ArtifactStoreError("INVALID_CONFIGURATION", "an S3-compatible client is required");
    }
    this.client = client;
    this.bucket = validateBucket(bucket);
  }

  static fromEnv(env = process.env) {
    return new S3ArtifactStore({
      client: createS3CompatibleClient(env),
      bucket: env.TRADIX_ARTIFACT_S3_BUCKET
    });
  }

  objectKey({ projectKey, runId, attemptId, sha256: digest, fileName }) {
    return [
      "projects",
      validateId(projectKey, "project_key"),
      "runs",
      validateId(runId, "run_id"),
      "attempts",
      validateId(attemptId, "attempt_id"),
      "sha256",
      validateHash(digest),
      validateFileName(fileName)
    ].join("/");
  }

  async inspect({ key, expectedSha256, expectedByteSize }) {
    const digest = validateHash(expectedSha256);
    const parts = validateObjectKey(key, digest);
    if (!Number.isSafeInteger(expectedByteSize) || expectedByteSize < 0 || expectedByteSize > MAX_ARTIFACT_BYTES) {
      throw new ArtifactStoreError("INVALID_ARGUMENT", "expected_byte_size must be a non-negative safe integer");
    }
    let head;
    try {
      head = await this.client.send(new HeadObjectCommand({ Bucket: this.bucket, Key: key }));
    } catch (error) {
      if (isNotFound(error)) throw new ArtifactStoreError("NOT_FOUND", "artifact object was not found");
      throw new ArtifactStoreError("STORAGE_UNAVAILABLE", "artifact metadata could not be read");
    }
    if (head.ContentLength !== expectedByteSize || head.Metadata?.sha256 !== digest ||
        head.Metadata?.project_key !== parts[1] || head.Metadata?.run_id !== parts[3] ||
        head.Metadata?.attempt_id !== parts[5]) {
      throw new ArtifactStoreError("INTEGRITY_MISMATCH", "stored artifact metadata does not match its expected digest or size");
    }
    return { key, byteSize: head.ContentLength, sha256: digest, contentType: head.ContentType || "application/octet-stream" };
  }

  async readVerified({ key, expectedSha256, expectedByteSize }) {
    const metadata = await this.inspect({ key, expectedSha256, expectedByteSize });
    let response;
    try {
      response = await this.client.send(new GetObjectCommand({ Bucket: this.bucket, Key: key }));
    } catch {
      throw new ArtifactStoreError("STORAGE_UNAVAILABLE", "artifact bytes could not be downloaded");
    }
    const bytes = await bodyToBuffer(response.Body);
    if (bytes.byteLength !== metadata.byteSize || sha256(bytes) !== metadata.sha256) {
      throw new ArtifactStoreError("INTEGRITY_MISMATCH", "downloaded artifact failed SHA-256 or size verification");
    }
    return { ...metadata, bytes };
  }

  async uploadFile({ sourcePath, projectKey, runId, attemptId, contentType = "application/octet-stream" }) {
    const source = resolve(requireString(sourcePath, "source_path", 2048));
    const before = await lstat(source);
    if (!before.isFile() || before.isSymbolicLink()) {
      throw new ArtifactStoreError("INVALID_ARGUMENT", "source_path must be a regular non-symlink file");
    }
    if (before.size > MAX_ARTIFACT_BYTES) {
      throw new ArtifactStoreError("ARTIFACT_TOO_LARGE", "artifact exceeds the 128 MiB in-memory adapter limit");
    }
    const bytes = await readFile(source);
    const after = await lstat(source);
    if (before.size !== after.size || before.mtimeMs !== after.mtimeMs || before.ino !== after.ino) {
      throw new ArtifactStoreError("SOURCE_CHANGED", "source file changed while being read");
    }
    const digest = sha256(bytes);
    const fileName = validateFileName(basename(source));
    const key = this.objectKey({ projectKey, runId, attemptId, sha256: digest, fileName });
    requireString(contentType, "content_type", 160);
    if (/[\r\n]/.test(contentType)) throw new ArtifactStoreError("INVALID_ARGUMENT", "content_type contains invalid characters");

    try {
      const existing = await this.inspect({ key, expectedSha256: digest, expectedByteSize: bytes.byteLength });
      await this.readVerified({ key, expectedSha256: digest, expectedByteSize: bytes.byteLength });
      return { ...existing, reused: true };
    } catch (error) {
      if (!(error instanceof ArtifactStoreError) || error.code !== "NOT_FOUND") throw error;
    }

    try {
      await this.client.send(new PutObjectCommand({
        Bucket: this.bucket,
        Key: key,
        Body: bytes,
        ContentLength: bytes.byteLength,
        ContentType: contentType,
        Metadata: {
          sha256: digest,
          project_key: projectKey,
          run_id: runId,
          attempt_id: attemptId
        }
      }));
    } catch {
      throw new ArtifactStoreError("STORAGE_UNAVAILABLE", "artifact upload failed");
    }

    const verified = await this.readVerified({ key, expectedSha256: digest, expectedByteSize: bytes.byteLength });
    return {
      key,
      sha256: digest,
      byteSize: bytes.byteLength,
      contentType: verified.contentType,
      reused: false
    };
  }

  async restore({ key, expectedSha256, expectedByteSize, restoreRoot, relativePath }) {
    const verified = await this.readVerified({ key, expectedSha256, expectedByteSize });
    const rootText = resolve(requireString(restoreRoot, "restore_root", 2048));
    await mkdir(rootText, { recursive: true });
    const rootInfo = await lstat(rootText);
    if (!rootInfo.isDirectory() || rootInfo.isSymbolicLink()) {
      throw new ArtifactStoreError("INVALID_DESTINATION", "restore root must be a real directory, not a symbolic link");
    }
    const root = await realpath(rootText);
    requireString(relativePath, "relative_path", 1024);
    if (relativePath.includes("\\") || isAbsolute(relativePath)) {
      throw new ArtifactStoreError("INVALID_DESTINATION", "restore path must be relative and use forward slashes");
    }
    const segments = relativePath.split("/");
    if (segments.some(part => !part || part === "." || part === "..")) {
      throw new ArtifactStoreError("INVALID_DESTINATION", "restore path contains an unsafe segment");
    }
    const fileName = validateFileName(segments.pop());
    let parent = root;
    for (const segment of segments) {
      validateFileName(segment);
      parent = resolve(parent, segment);
      try {
        const info = await lstat(parent);
        if (!info.isDirectory() || info.isSymbolicLink()) {
          throw new ArtifactStoreError("INVALID_DESTINATION", "restore path contains a non-directory or symbolic link");
        }
      } catch (error) {
        if (error?.code !== "ENOENT") throw error;
        await mkdir(parent);
      }
    }
    const destination = resolve(parent, fileName);
    const rel = relative(root, destination);
    if (!rel || rel.startsWith(".." + sep) || rel === ".." || isAbsolute(rel)) {
      throw new ArtifactStoreError("INVALID_DESTINATION", "restore destination escaped the restore root");
    }
    try {
      await lstat(destination);
      throw new ArtifactStoreError("DESTINATION_EXISTS", "restore destination already exists");
    } catch (error) {
      if (error instanceof ArtifactStoreError) throw error;
      if (error?.code !== "ENOENT") throw error;
    }

    const temporary = resolve(parent, "." + fileName + "." + randomUUID() + ".part");
    const handle = await open(temporary, "wx", 0o600);
    try {
      await handle.writeFile(verified.bytes);
      await handle.sync();
    } finally {
      await handle.close();
    }
    try {
      await link(temporary, destination);
    } catch (error) {
      await unlink(temporary).catch(() => {});
      if (error?.code === "EEXIST") {
        throw new ArtifactStoreError("DESTINATION_EXISTS", "restore destination already exists");
      }
      throw new ArtifactStoreError("RESTORE_FAILED", "verified artifact could not be committed to the restore path");
    }
    await unlink(temporary);
    return { path: destination, byteSize: verified.byteSize, sha256: verified.sha256 };
  }
}
