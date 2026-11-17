# Backblaze B2 Object Storage Integration

**Status:** Adapter and GitHub Actions verification workflow are on `main`. GitHub-hosted runner verification passed on 2026-11-15 (run `43745900128`). This proves B2 connectivity from that ephemeral runner only; no persistent runtime connection or full artifact lifecycle is implemented.

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

## Configure a no-server verification run with GitHub Actions

A manually triggered GitHub Actions workflow is included at `.github/workflows/verify-backblaze-b2.yml`. It runs on a temporary GitHub-hosted runner and does not create a Railway project or persistent service.

In the repository, open **Settings → Secrets and variables → Actions → New repository secret** and add these five secrets:

- `B2_ENDPOINT` = `https://s3.us-east-005.backblazeb2.com`
- `B2_REGION` = `us-east-005`
- `B2_BUCKET_NAME` = `tradix-factory-storage`
- `B2_APPLICATION_KEY_ID` = your application key ID
- `B2_APPLICATION_KEY` = your application key secret

Do not put the key values in GitHub files, issue comments, or chat. The workflow is already present on `main` and was manually dispatched successfully. Run `43745900128` completed with `write_test=true`; logs confirmed authenticated bucket listing and upload/read-back. The unique object under `healthchecks/` is intentionally retained because the bucket keeps object versions. The GitHub connector currently has no direct workflow-dispatch operation, so a future manual run may require the GitHub Actions UI unless a dispatch capability is added.

## Local install and verification

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

## Current verified state and limitations

- GitHub Actions has successfully authenticated to the private bucket, listed objects, uploaded a uniquely named health-check object, and read it back.
- The five repository secrets were injected into the runner as masked environment values. Their underlying values are not readable through the GitHub connector and must remain secret.
- No Railway project or service exists in the connected workspace. The successful test ran on a temporary GitHub-hosted runner and does not prove a persistent application runtime.
- The adapter has not yet been integrated into a factory artifact lifecycle (upload, content hash, metadata record, retrieval, retention, integrity check).
- No backup/restore test has been performed. Do not describe B2 as a verified backup system until a restore test passes.
- No cloud project/service should be created until the user reviews runtime cost and explicitly approves creation/deployment.
