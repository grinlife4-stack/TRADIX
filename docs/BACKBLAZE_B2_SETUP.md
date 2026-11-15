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

## Configure a no-server verification run with GitHub Actions

A manually triggered GitHub Actions workflow is included at `.github/workflows/verify-backblaze-b2.yml`. It runs on a temporary GitHub-hosted runner and does not create a Railway project or persistent service.

In the repository, open **Settings → Secrets and variables → Actions → New repository secret** and add these five secrets:

- `B2_ENDPOINT` = `https://s3.us-east-005.backblazeb2.com`
- `B2_REGION` = `us-east-005`
- `B2_BUCKET_NAME` = `tradix-factory-storage`
- `B2_APPLICATION_KEY_ID` = your application key ID
- `B2_APPLICATION_KEY` = your application key secret

Do not put the key values in GitHub files, issue comments, or chat. Because GitHub requires a `workflow_dispatch` workflow to exist on the default branch, this workflow becomes runnable only after PR #1 is reviewed and merged into `main`. The job also checks that the selected ref is exactly `main` and checks out `main`; a manual dispatch from any other branch is skipped before secrets are exposed. Do not merge it automatically. After the merge, open **Actions → Verify Backblaze B2 → Run workflow**. First run with `write_test=false` to verify authenticated bucket listing. After that succeeds, run again with `write_test=true` to verify upload and read-back. The second run leaves one tiny object under `healthchecks/` because the bucket retains object versions.

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

## Current blocker

No Railway project or service exists in the connected workspace. A live B2 test can run on GitHub's temporary hosted runner after the five repository secrets are configured; this does not create a persistent service or Railway project. No cloud project/service should be created until the user reviews the runtime cost and explicitly approves creation/deployment.
