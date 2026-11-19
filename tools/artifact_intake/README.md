# TRADIX Artifact Intake and Gateway

TRADIX's reusable artifact tooling accepts files, validates their integrity, extracts supported document content, and transfers artifacts to a configured project-owned destination.

## 1. Local inspection CLI

Requirements: Python 3.11+.

Install document readers:

```bash
python -m pip install -e '.[documents]'
```

Examples:

```bash
python tools/artifact_intake/artifact_intake.py hash path/to/file.zip
python tools/artifact_intake/artifact_intake.py inspect-zip path/to/file.zip
python tools/artifact_intake/artifact_intake.py extract-zip path/to/file.zip /tmp/extracted
python tools/artifact_intake/artifact_intake.py read-text path/to/README.md
python tools/artifact_intake/artifact_intake.py read-document path/to/report.pdf
python tools/artifact_intake/artifact_intake.py read-document path/to/report.docx
python tools/artifact_intake/artifact_intake.py read-document path/to/report.xlsx
```

ZIP extraction rejects traversal paths, symlinks, duplicate names, oversized entries and overwrites. PDF/DOCX/XLSX extraction is read-only. Before DOCX/XLSX parsing, the reader bounds ZIP member count (4,096), central-directory size (4 MiB), total uncompressed size (64 MiB), per-member size (32 MiB), and per-member compression ratio (100:1). ZIP64, encrypted members and duplicate member names are rejected. XLSX output is capped at 100,000 cells and 2 million extracted characters. Scanned-PDF OCR and legacy DOC are not supported.

## 2. Authenticated upload gateway

Install and run:

```bash
python -m pip install -e '.[gateway,documents]'
export TRADIX_PROJECT_ID='nexora'
export TRADIX_API_KEY='<at-least-32-random-characters>'
export TRADIX_ARTIFACT_ROOT='/mnt/persistent/tradix-artifacts'
export TRADIX_STORAGE_BACKEND='local'
python -m tools.artifact_gateway
```

The project ID is fixed when the gateway instance starts. There is no client-supplied project namespace. Deploy a separate instance, API key, persistent volume and destination credentials for each project.

### Upload

```bash
curl --fail-with-body \
  -H "Authorization: Bearer $TRADIX_API_KEY" \
  -F "file=@./report.pdf" \
  http://127.0.0.1:8080/v1/artifacts
```

Optional integrity check:

```bash
-H "X-Content-SHA256: <expected-lowercase-sha256>"
```

The response includes an immutable artifact ID, project namespace, sanitized filename, byte count, SHA-256, storage reference and extracted content/manifest. Retrieve the saved receipt with:

```bash
curl -H "Authorization: Bearer $TRADIX_API_KEY" \
  http://127.0.0.1:8080/v1/artifacts/<artifact-id>
```

Health check: `GET /health`. Interactive API documentation is disabled in this MVP.

### Storage backends

**Local (default):** content-addressed files and JSON receipts are written below `TRADIX_ARTIFACT_ROOT/<project-id>/`. The configured root must be a persistent volume outside the source repository.

**S3-compatible / Backblaze B2:** set `TRADIX_STORAGE_BACKEND=s3` and provide these runtime-only environment variables:

- `TRADIX_S3_ENDPOINT_URL`
- `TRADIX_S3_REGION`
- `TRADIX_S3_BUCKET`
- `TRADIX_S3_ACCESS_KEY_ID`
- `TRADIX_S3_SECRET_ACCESS_KEY`

Install `.[storage]` in addition to the gateway extra. The gateway uploads to a project-prefixed object key and verifies the object with a HEAD request. Use a dedicated bucket or credentials restricted by IAM to that project's prefix. Do not reuse the factory bucket for unrelated product records without an explicit ownership decision.

**GitHub binary transfer:** set `TRADIX_STORAGE_BACKEND=github` and provide:

- `TRADIX_GITHUB_REPOSITORY` as the project-owned `owner/repository`
- `TRADIX_GITHUB_BRANCH` as an existing, dedicated non-production branch
- `TRADIX_GITHUB_PATH_PREFIX` as a non-empty path prefix
- `TRADIX_GITHUB_TOKEN` as a runtime secret with the minimum required repository contents permission

The adapter stores the binary under a SHA-256 content-addressed path, then reads it back and verifies byte count and SHA-256. This gateway caps GitHub transfers at 20 MiB. It does not create branches, write to `main`, or delete remote objects. Use a token restricted to the target project repository.

### Security and operational boundaries

- Every deployment is bound to one project ID and one project-specific API key.
- Use HTTPS through a trusted reverse proxy or platform ingress; do not expose the local HTTP listener directly to the public internet.
- Keep API keys and storage credentials in the deployment platform's secret manager, never in Git, source files, logs, chat or receipts.
- Configure platform-level request limits, rate limits, monitoring and backups.
- The default upload limit is 50 MiB. Set a lower limit when the deployment does not need large files.
- ZIP archives are inspected, not automatically extracted by the gateway.
- The gateway does not execute uploaded content, macros or scripts.
- Local receipts and metadata require persistent storage even when objects are sent to a remote backend.
- Remote uploads are append-only in this MVP; no overwrite or delete endpoint exists.
- This is an engineering utility, not a mandatory runtime dependency for any product.

## 3. Tests

```bash
python -m pip install -e '.[dev,documents,gateway]'
python -m pytest -q
```

CI runs the same test suite. A passing test suite verifies the code paths with local and mocked remote storage; it does not prove that a production B2 bucket, GitHub token, TLS ingress or deployment has been configured.
