# ECOSCAN

Optional, read-only, removable utility for measuring storage independently across registered portfolio projects and aggregating the resulting reports.

**Status: first implementation in progress.** The current code supports GitHub repository tree inventory, configured local directory metadata scans, Railway volume capacity/backup metadata, S3-compatible current-object metadata (B2/R2/S3/Railway-compatible endpoints), normalized JSON/Markdown reports, and optional GitHub issue publication. Provider adapters still require live credential-backed validation. Scheduled execution is defined in a separate GitHub Actions workflow but will not run until that workflow reaches the default branch.

## Run manually

From the TRADIX repository root with Python 3.11 or newer:

```bash
python -m tools.ecoscan
```

Optional arguments:

```bash
python -m tools.ecoscan --config tools/ecoscan/config/ecoscan.json --output artifacts/ecoscan/latest.json
```

Reports are written locally as JSON and Markdown. The tool does not upload, delete, modify, or hash source files.

## GitHub access

- Public repositories can be inventoried through the GitHub REST API.
- Private repositories require a token with read-only metadata and contents access to each registered private repository.
- For scheduled GitHub Actions, configure a repository secret named `ECOSCAN_GITHUB_TOKEN` containing a fine-grained token limited to the required repositories and read-only contents/metadata permissions.
- The workflow's built-in `GITHUB_TOKEN` is restricted to TRADIX; it cannot be assumed to read other private repositories.
- Issue publication uses the workflow's built-in token with `issues: write`; no personal token is needed for publishing the report to TRADIX.

Never commit tokens or private data.

## Current source coverage

The initial registry contains the five repositories visible in the connected GitHub account at implementation time. It intentionally marks other portfolio projects with no registered storage source as NOT_REGISTERED. Railway volume contents, local machines not mounted into the runner, historical object versions, incomplete multipart uploads, Git LFS payload sizes, and unregistered external archives are not yet measured. Current Railway and S3-compatible metadata adapters are not yet live-validated.

## Operating and removal rules

- The registry defaults to MANUAL. No local background process is started.
- The optional GitHub Actions workflow supports manual dispatch and weekly/monthly schedules after it is merged to the default branch.
- The workflow updates one GitHub issue titled `ECOSCAN — Latest Report`; incomplete sources are surfaced as warnings.
- No product runtime, Gateway, EventStore, Railway service, or production infrastructure depends on this tool.
- Disable scheduled runs by disabling the workflow. Remove the tool by removing this directory and its optional workflow/configuration; no source data is modified.


## Manual scan scopes and controls

Set `enabled: false` on a project entry to skip all of its sources, or on an individual source to skip only that source. Disabled entries are reported as `DISABLED` with unknown size, never as zero.

Examples:

```bash
# Entire configured registry
python -m tools.ecoscan --scope ecosystem

# One project
python -m tools.ecoscan --scope project --project NEXORA

# One source only
python -m tools.ecoscan --scope source --source nexora-github
```

Selectors are validated before scanning. Unknown IDs and invalid selector combinations stop the run.


### Railway volume metadata

Set `provider` to `railway_volume` and configure either a verified `volume_instance_id`, or `volume_id` plus `environment_id` for environment-scoped discovery. Prefer a Railway Project Token scoped to the exact environment and expose it to the ECOSCAN runner as `RAILWAY_PROJECT_TOKEN`; the adapter sends it using Railway's `Project-Access-Token` header. Account/workspace tokens can instead be supplied as `RAILWAY_API_TOKEN` and are sent as Bearer tokens. Set these in the local runner environment or GitHub Actions secrets, not in the monitored `artifact-gateway` service. The scheduled workflow reads repository secrets named `RAILWAY_PROJECT_TOKEN` or `RAILWAY_API_TOKEN`. Project Tokens are environment-scoped, but Railway does not document them as read-only permission tokens; the adapter only issues GraphQL queries. Treat the token as a credential with possible broader capabilities inside its environment. Never commit it.

The adapter reports provisioned capacity and backup inventory metadata without reading volume contents. It does not report used filesystem bytes. Environment-level `volumeInstances` discovery is mocked-tested but still requires live schema validation.


### S3-compatible object storage (B2 / R2 / S3 / Railway buckets)

Use `provider: "s3_compatible"` with an explicit `endpoint`, `bucket`, `region`, `url_style`, and names of environment variables holding read-only access and secret keys. The adapter paginates `ListObjectsV2` and sums current object sizes without downloading object bodies. Historical versions, incomplete multipart uploads, and provider billing bytes are outside this measurement.
