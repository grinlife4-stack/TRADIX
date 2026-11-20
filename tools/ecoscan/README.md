# ECOSCAN

Optional, read-only, removable utility for measuring storage independently across registered portfolio projects and aggregating the resulting reports.

**Status: first implementation in progress.** The current code supports GitHub repository tree inventory, configured local directory metadata scans, normalized JSON/Markdown reports, and optional GitHub issue publication. Scheduled execution is defined in a separate GitHub Actions workflow but will not run until that workflow reaches the default branch.

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

The initial registry contains the five repositories visible in the connected GitHub account at implementation time. It intentionally marks other portfolio projects with no registered storage source as NOT_REGISTERED. Railway volume contents, local machines, object-storage buckets, backups, Git LFS payloads, and external archives are not yet measured.

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
