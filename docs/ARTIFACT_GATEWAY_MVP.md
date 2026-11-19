# TRADIX Artifact Gateway — MVP Record

**Status:** Implemented on an isolated feature branch; CI verified. Not deployed.
**Scope:** Reusable engineering capability owned by TRADIX. It is not a product runtime dependency and does not centralize product files.

## Purpose

Provide a simple, auditable path to receive a file, verify it, extract supported content, and transfer the original binary to a destination explicitly configured for the owning project.

## Current flow

1. A project-specific gateway instance receives a multipart upload over HTTPS.
2. Bearer authentication is checked using a runtime secret.
3. The gateway streams the upload to temporary storage while enforcing a byte limit and computing SHA-256.
4. An optional caller-supplied SHA-256 is compared with the computed digest.
5. ZIP files are integrity-checked and inventoried; PDF, DOCX and XLSX are parsed with bounded readers; supported text formats are decoded as UTF-8.
6. The original binary is written to the configured backend.
7. The remote S3 object or GitHub binary is read/checked for integrity; a local receipt records the artifact ID, project, hash, size, destination and extraction result.

## Destination adapters

- **Local:** content-addressed storage below a configured persistent volume.
- **S3-compatible:** upload, HEAD metadata/size verification, and GET read-back with byte-count plus SHA-256 verification. This can target a project-owned Backblaze B2 bucket.
- **GitHub Contents API:** upload to a content-addressed path in a project-owned repository and an explicitly configured existing non-production branch; read back and verify SHA-256. The adapter's upload limit is 20 MiB.

No live B2 bucket or GitHub project token is configured by this code change. Unit tests use mocked remote services; they do not claim live connectivity.

## Isolation rules

- One gateway instance is bound to one immutable `TRADIX_PROJECT_ID`.
- Each instance has its own API key, persistent metadata volume and destination credentials.
- The client cannot select or override the project namespace.
- S3 credentials must be limited to the selected project's bucket/prefix. GitHub tokens must be limited to the selected project repository.
- The gateway never writes to TRADIX source files or stores project artifacts in this repository.
- A product may decline or replace the gateway without losing ownership of its records or destination.

## Security boundaries

- Upload size is bounded by `TRADIX_MAX_UPLOAD_BYTES`; configure a matching request-body cap and rate limit at the ingress/reverse proxy because multipart parsing occurs before the endpoint handler.\n- DOCX/XLSX ZIP containers are preflighted before parser invocation: at most 4,096 members, a 4 MiB central directory, 64 MiB total uncompressed data, 32 MiB per member, and a 100:1 per-member compression ratio. ZIP64 and encrypted/duplicate members are rejected. XLSX extraction is additionally capped at 100,000 cells and 2 million characters.
- The service must run behind HTTPS. The built-in listener defaults to loopback.
- Credentials are environment/runtime secrets only and are excluded from receipts.
- Remote operations are append-only; no delete or overwrite endpoint exists.
- ZIP extraction is not automatic in the HTTP gateway.
- No macros, scripts or uploaded executable content are run.
- OCR, legacy DOC, arbitrary URL fetching, general-purpose cloud connectors and remote content download are not part of this MVP.

## Runtime configuration

See [Artifact Intake README](../tools/artifact_intake/README.md) for exact environment variable names, CLI usage, upload examples and backend setup.

A deployment is not authorized by this implementation alone. Before deployment, choose the owning project, its destination, a persistent volume, runtime secrets, HTTPS ingress, request limits, monitoring and backup/restore behavior. Test a real upload and read-back using non-sensitive sample data.

## Verification

GitHub Actions run 665 completed successfully with 27 tests passing. This includes authentication, hash mismatch, size limits, ZIP rejection, local content-addressed storage, mocked S3 verification, mocked GitHub upload/read-back and idempotent retry behavior.
