# TRADIX S3-Compatible Artifact Store v0.1

**Status:** Implemented adapter; verified against ephemeral RustFS in CI  
**Production status:** Not connected to Backblaze B2 or any production bucket  
**Scope:** Content-addressed artifact upload, read-back verification, and safe restore

## 1. Object identity

Artifacts are stored under a deterministic content-addressed key:

\`projects/{project_key}/runs/{run_id}/attempts/{attempt_id}/sha256/{sha256}/{file_name}\`

The object metadata repeats the SHA-256 digest, project key, run ID, and attempt ID. A key is rejected unless all identity segments are safe and the digest is a full lowercase SHA-256 value.

## 2. Upload contract

For each file, the adapter:

1. Requires a regular, non-symbolic-link source file.
2. Reads the bytes and checks that the source file did not change while being read.
3. Calculates SHA-256 locally.
4. Checks whether the content-addressed object already exists.
5. If it exists, downloads and verifies the existing bytes before treating the upload as an idempotent retry.
6. Otherwise uploads with content type, byte size, and identity metadata.
7. Reads the object metadata back with HEAD.
8. Downloads the object with GET and recomputes SHA-256 and byte size before returning success.

The adapter does not trust ETag as a SHA-256 digest. It does not expose delete, overwrite, bucket creation, or public ACL operations.

## 3. Restore contract

Restore requires an expected SHA-256 and byte size. It downloads and verifies the complete object before writing anything to the destination.

The destination path must be relative to a caller-selected restore root. Traversal segments, absolute paths, symbolic-link directories, and existing destination files are rejected. The verified bytes are written to a private temporary file, fsynced, then linked into place without replacing an existing file.

## 4. Configuration

The adapter reads these environment variables:

- \`TRADIX_ARTIFACT_S3_ENDPOINT\`
- \`TRADIX_ARTIFACT_S3_REGION\`
- \`TRADIX_ARTIFACT_S3_BUCKET\`
- \`TRADIX_ARTIFACT_S3_ACCESS_KEY_ID\`
- \`TRADIX_ARTIFACT_S3_SECRET_ACCESS_KEY\`

Remote endpoints must use HTTPS. HTTP is allowed only when the explicit local-test flag \`TRADIX_ARTIFACT_S3_ALLOW_LOCAL_HTTP=true\` is set and the endpoint host is loopback.

Use path-style addressing. Do not put credentials in endpoint URLs, command arguments, manifests, logs, or product-script environments.

## 5. Backblaze B2 configuration target

For a future B2 connection:

- Use the bucket's exact endpoint: \`https://s3.<region>.backblazeb2.com\`.
- Set the region to the same region shown in the B2 bucket details.
- Use a bucket-scoped B2 application key, not the account master key.
- Keep the bucket private.
- Do not configure per-object ACLs; the adapter does not set them.
- Keep delete permissions out of the runtime key.
- Add credentials only to a protected secret store after a human owner has verified the bucket and key scope.

Backblaze's S3-compatible API uses AWS Signature Version 4 and requires HTTPS. B2 supports path-style addressing. The adapter uses the AWS SDK v3 with path-style addressing.

Official references:
- https://www.backblaze.com/docs/cloud-storage-use-the-aws-sdk-for-javascript-v3-with-backblaze-b2
- https://www.backblaze.com/docs/cloud-storage-call-the-s3-compatible-api
- https://www.backblaze.com/docs/cloud-storage-present-a-branded-s3-endpoint

## 6. Validation and limitations

CI uses a disposable RustFS 1.0.3 container with test-only credentials. It validates upload, HEAD/GET read-back, idempotent retry, restore, path traversal rejection, symlink rejection, no-overwrite behavior, and same-size content tampering detection.

RustFS is a test service only. Its successful CI integration does not prove B2 compatibility or B2 availability. No B2 credentials, bucket, retention policy, Object Lock, lifecycle rule, or restore from B2 has been configured or tested.

This adapter is not yet called by the factory executor. The next integration step must upload evidence before its database receipt is committed, record the exact object key and digest, and refuse verification if object read-back fails. The worker must never receive storage credentials.

## 7. Executor receipt integration

When S3 configuration is present, the trusted executor uploads each evidence file and completes HEAD/GET verification before calling the fenced database evidence function. The receipt stores an `s3://bucket/key` URI plus the digest, byte size, and object key in metadata. The final task verification requires all three evidence receipts to point to remote objects.

Set `TRADIX_REQUIRE_REMOTE_ARTIFACTS=true` on a worker that must fail closed without remote storage. The S3 credentials stay in the executor process; the product child process receives only its explicit runtime allowlist and never receives the storage key or secret. If an upload succeeds but the subsequent database receipt fails, an orphaned content-addressed object may remain. There is no delete API; a future reconciliation process must identify such objects without automatically deleting them.

CI now exercises this full path against the disposable RustFS service. This validates the executor-to-S3-compatible-store-to-database receipt ordering, not Backblaze B2 production connectivity.
