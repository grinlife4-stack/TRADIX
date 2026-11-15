# Backblaze B2 Object Storage Integration

**Status:** Adapter implemented on `factory/phase-0-blueprint`; live credentials and runtime connection are not yet configured or verified.

## Target bucket

- Bucket: `tradix-factory-storage`
- Endpoint: `https://s3.us-east-005.backblazeb2.com`
- Region: `us-east-005`
- Access: private
- Encryption: enabled in the Backblaze bucket configuration
- Bucket ID (console reference only): `8779123cd223daf6a1120218`

The S3 API uses the bucket name, not the Backblaze bucket ID.

## Runtime environment variables

Set these as encrypted runtime secrets/variables. Do not commit a `.env` file or paste either credential into chat, GitHub, issue comments, logs, or build output.

```dotenv
B2_ENDPOINT=https://s3.us-east-005.backblazeb2.com
B2_REGION=us-east-005
B2_BUCKET_NAME=tradix-factory-storage
B2_APPLICATION_KEY_ID=<application-key-id>
B2_APPLICATION_KEY=<application-key-secret>
```

Use a manually created, non-master application key restricted to this bucket. For the adapter's verification path, it needs permission to list files, read files, and write files. Do not grant account-wide access. If the key is restricted to one bucket and the provider requires it for bucket-level listing, enable `listAllBucketNames` only if the chosen operation actually requires listing all buckets; the verification script lists objects within the named bucket, not all buckets.

## Install and verify

```bash
python -m pip install -e '.[storage,dev]'
python -m pytest -q
python scripts/verify_backblaze_b2.py
```

The default verification checks authenticated access and lists at most one object. After runtime secrets are configured, run the write/read-back test explicitly:

```bash
python scripts/verify_backblaze_b2.py --write-test
```

The write test creates a tiny uniquely named object under `healthchecks/` and reads it back. It intentionally leaves the object in place. Backblaze B2 buckets are versioned, and a normal delete creates a delete marker while older versions remain, so automatic cleanup would falsely suggest that the test data was erased.

## Failure handling

- `AccessDenied`: verify the key is a non-master application key, is scoped to this bucket, and has the required list/read/write capabilities.
- Signature/authentication errors: verify that the key ID and application key have not been swapped and that there are no whitespace characters in either secret.
- Endpoint/region errors: the endpoint host must match `B2_REGION` exactly.
- Network errors: verify outbound HTTPS access from the actual runtime environment.

The adapter uses AWS Signature Version 4 and path-style addressing. It does not make the bucket public, alter lifecycle settings, or create/delete buckets.

## Current blocker

No Railway project or service exists in the connected workspace. The GitHub adapter can be reviewed and tested in CI, but a live B2 test must run from an approved runtime after its secret store is configured. No cloud project/service should be created until the user reviews the runtime cost and explicitly approves creation/deployment.
