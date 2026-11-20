# ECOSCAN

**Document ID:** TRADIX-TOOL-ECOSCAN-001  
**Status:** IMPLEMENTATION IN PROGRESS / REVIEW REQUIRED  
**Owner:** TRADIX (shared engineering tool only)  
**Scope:** All registered portfolio projects and their separately authorized storage records  
**Default mode:** MANUAL  
**Runtime dependency:** None

## 1. Purpose

Provide an optional, removable, low-overhead tool that measures storage and file inventories independently for each project or system, then produces a portfolio-wide summary from the individual results.

The monitor is an engineering/administrative tool. It does not own project data, become a storage provider, or become a runtime dependency of any product.

## 2. Portfolio scope

The project registry is extensible and must not be hard-coded to a fixed list. Initial known entries include:

- TRADIX
- NEXORA
- MegaMarket
- EXVARLI
- AAECN
- Trading Intelligence Platform
- X Financial System
- XENORA AI
- Other projects added through an explicit registry entry

Each project is a separate measurement boundary. A project may contain multiple systems, repositories, document stores, object-storage buckets, local disks, archives, and backup locations. Each source must be separately identified and authorized. Where multiple projects share one repository, path-scoped sources must split the project folders and exclude those same paths from the repository-level source so the same blob is not counted twice.

The registry stores references and measurement rules only. It must not copy project secrets, credentials, private files, financial records, or business data into a shared central store.

## 3. Operating modes

- **DISABLED:** no scans, scheduled jobs, or background work.
- **MANUAL:** run only when explicitly requested.
- **SCHEDULED:** run only on an explicitly enabled schedule.
- **EVENT-SNAPSHOT (optional):** consume existing storage metadata/events when available; must not introduce a continuous scanner.

Default is MANUAL. No scheduled or event-driven operation may be enabled implicitly.

## 4. Independent measurement model

Each project/source scanner runs independently and emits a normalized measurement record containing:

- project_id and source_id
- source/provider type and opaque source reference
- measured_at timestamp and measurement window
- logical bytes and object/file count
- physical bytes, where the provider exposes reliable values
- backup/archive bytes, reported separately
- temporary/incomplete upload bytes, reported separately
- uploaded/deleted bytes during the interval, when available
- coverage status: COMPLETE, PARTIAL, FAILED, or NOT_AUTHORIZED
- measurement method, source timestamp, and confidence/limitations

A failed or inaccessible source is never represented as zero. Partial results must remain visibly partial.

## 5. Aggregation and accuracy

The aggregation engine consumes only validated project/source records. It must:

1. Preserve per-project and per-source detail.
2. Produce a portfolio total without merging project ownership or source records.
3. Separate logical size, physical consumption, backups, archives, and incomplete multipart uploads.
4. Detect shared objects by stable object identity where available. Show project-attributed usage separately from deduplicated physical portfolio usage; never silently deduplicate based only on matching filenames.
5. Avoid double-counting replicas, snapshots, or shared files when provider metadata supports reliable identity.
6. Mark totals as incomplete when any in-scope source is PARTIAL, FAILED, or NOT_AUTHORIZED.
7. Preserve units and distinguish decimal TB from binary TiB.
8. Never infer missing measurements or extrapolate them as observed facts.

## 6. Scheduling and notifications

Scheduling is optional and must be configurable independently of the core tool.

The optional GitHub Actions workflow defines:
- Weekly: independent source inventory and project-level report (Monday, 05:00 UTC).
- Monthly: portfolio inventory review (day 1, 05:00 UTC).
- Manual dispatch: on-demand inventory.

Scheduled runs are enabled in the registry but do not execute until the workflow is merged into the repository default branch. A scheduled run publishes/updates one GitHub issue containing the latest report. ChatGPT's separate weekly review task is intended to inspect that issue and deliver the summary to the user.

Current alert implementation covers incomplete, inaccessible, missing, and unregistered sources/projects. Capacity-percentage alerts are not enabled until an adapter can supply a trustworthy used-bytes/capacity-bytes pair. Growth rates and forecasts are not yet implemented because a durable prior-measurement history has not been established.

Thresholds are configurable per project/source. Initial suggested defaults are 80% warning and 90% critical for a known capacity limit. A percentage alert is suppressed when the provider does not expose a trustworthy capacity denominator.

Every report/alert must include its coverage, timestamp, changed values, failed sources, threshold basis, and whether the result is measured or estimated. Notifications must not claim that an external action was taken when only a report was generated.

The schedule must be disableable with one configuration change. No hourly or continuous polling is required. The tool must not create a paid cloud service or external notification dependency by default.

## 7. Low-overhead requirements

- Prefer provider inventory APIs, repository metadata, filesystem metadata, and recorded upload/delete events.
- Do not download file contents to measure their sizes.
- Do not hash every byte during routine inventory.
- Reserve full content verification and reconciliation for a separately requested maintenance operation.
- Support pagination, checkpoints, bounded concurrency, rate-limit handling, and resumable scans.
- Do not rescan unchanged sources when reliable version markers or provider cursors are available.
- Enforce per-project and per-source time, API-call, and concurrency budgets.
- No background process may run in DISABLED or MANUAL mode.

## 8. Security and isolation

- Read-only access by default.
- Each scanner receives only the minimum access required for its registered project/source.
- No cross-project credential reuse.
- Secrets remain in their owning provider/project secret store and are referenced, never copied into reports or this repository.
- Reports must not expose file contents, secret values, private URLs, or sensitive metadata.
- Access failures must be reported, not worked around by widening permissions.

## 9. Portability and removal

- Keep the tool in its own directory under `tools/ecoscan/`.
- Keep its governing specification in this separate document.
- No imports from this tool may be required by TRADIX Gateway, EventStore, build/release pipelines, or any product runtime.
- Configuration, registry, and reports must use documented exportable formats.
- Support replacing scanners/providers without changing the normalized record or aggregation contract.
- Removing the tool directory, its optional workflow, and its configuration must not modify project files, storage objects, backups, credentials, or core TRADIX behavior.
- Do not delete historical reports automatically when disabling or removing the executable; retention and deletion are separate owner-controlled decisions.

## 10. Required report structure

1. Portfolio overview and total measured bytes.
2. Per-project totals and coverage status.
3. Per-source inventory and measurement method.
4. Logical vs physical vs backup/archive usage.
5. Change since previous comparable measurement.
6. Growth rate and forecast, clearly labelled as estimates.
7. Capacity warnings and source-access failures.
8. Exclusions, unknowns, and measurement limitations.

## 11. Acceptance gates

The tool is not considered operational until all of the following are demonstrated:

- Independent scans for at least two separate project boundaries.
- Aggregation does not merge or expose project-owned data.
- Failed/partial sources are not counted as zero.
- Duplicate/shared-object handling is tested.
- Manual mode performs no scheduled/background work.
- Scheduled mode can be enabled and disabled without code changes.
- Alerts trigger only on verified thresholds and include evidence.
- Rate limits, timeouts, interrupted scans, and restart/resume are tested.
- Export/import of registry and reports is tested.
- Removing the tool leaves core tests and product operations unchanged.
- No paid provider or new infrastructure is required for the default configuration.

Until these gates pass, status must remain PROPOSED or IMPLEMENTATION-IN-PROGRESS. Do not describe the portfolio as fully measured or monitored.

## 12. Current implementation boundary

The first implementation now includes:
- GitHub repository metadata and recursive Git-tree inventory.
- Path-scoped GitHub scans so embedded NEXORA, MegaMarket, and EXVARLI folders are attributed to their own project records and excluded from the TRADIX core subtotal.
- Read-only local-directory metadata scanning for explicitly configured paths.
- Independent per-source results and project-level aggregation.
- COMPLETE, EMPTY, PARTIAL, NOT_CONFIGURED, NOT_AUTHORIZED_OR_NOT_FOUND, RATE_LIMITED, and FAILED source states.
- JSON and Markdown report generation.
- Optional update/create of one GitHub issue for scheduled report delivery.
- A GitHub Actions workflow for weekly/monthly scheduled runs and manual dispatch.
- Automated tests for tree sizing, empty repositories, incomplete coverage, local scans, and report output.

The implementation remains incomplete. It does not yet scan Railway volume contents, local machines not mounted into the runner, B2/R2/S3 buckets, Git LFS payloads, backups, or other external storage. Private GitHub repositories require a fine-grained read-only token stored by the owner as the repository secret `ECOSCAN_GITHUB_TOKEN`; the workflow's built-in token is limited to TRADIX. The scheduled workflow runs only after this PR is merged to the default branch. No report has yet been generated by the scheduled workflow, no ChatGPT notification has been verified, and no capacity forecast is claimed.


## 13. Initial system assessment (2026-11-20)

The connected GitHub account exposed five repositories:

| Repository | Visibility | Tracked tree files | Tracked blob bytes |
|---|---|---:|---:|
| `grinlife4-stack/TRADIX` | Public | 28 | 1,189,726 |
| `grinlife4-stack/NEXORA` | Public | 3 | 1,014,003 |
| `grinlife4-stack/info_engine` | Private | 3 | 6,712 |
| `grinlife4-stack/fluffy-happiness` | Private | 3 | 6,217 |
| `grinlife4-stack/-Green888` | Public | 0 | 0 (empty repository) |

These are current checked-out Git tree blob sizes, not total repository history, LFS payloads, local working copies, backups, or cloud storage. The two private repositories require a scoped read-only token for scheduled Actions access. The empty repository is not an access failure.

The connected Railway account exposed one workspace, one project (`TRADIX Artifact Gateway Staging`), one service (`artifact-gateway`), one 500 MB volume mounted at `/data`, and no buckets. The latest known deployment was SUCCESS. Railway's service-level disk metric reported approximately 0.0322 GB at the latest sample, but this is not verified as volume consumption and must not be used as such. No Railway volume-content inventory adapter is implemented.

The current registry also lists MegaMarket, EXVARLI, AAECN, X Financial System, XENORA AI, and the Trading Intelligence Platform as portfolio projects. Only the sources explicitly mapped in the registry are measured; projects without configured sources remain NOT_REGISTERED, so the portfolio total is deliberately marked INCOMPLETE.


The initial path-level attribution from those same Git trees is:

| Project/source boundary | Files | Logical blob bytes |
|---|---:|---:|
| TRADIX core (project-specific folders excluded) | 16 | 57,192 |
| NEXORA (standalone repository plus its TRADIX dossier/assets) | 9 | 2,055,655 |
| MegaMarket (TRADIX embedded project folder) | 4 | 70,709 |
| EXVARLI (TRADIX embedded project folder and financial dossier) | 2 | 20,173 |
| Trading Intelligence Platform (`info_engine`) | 3 | 6,712 |
| Unclassified archive (`fluffy-happiness`) | 3 | 6,217 |
| **Total measured tracked blobs** | **37** | **2,216,658** |

The total is approximately 2.114 MiB of tracked Git tree content. This is a manual baseline derived from the GitHub tree API using the same path boundaries as the registry; it is not yet a report generated by the monitor executable. The -Green888 repository is empty and contributes zero tracked blobs. AAECN, X Financial System, and XENORA AI have no registered storage source yet and remain unmeasured.


## 14. Implemented project/source controls and manual scope selection

The registry now has independent boolean controls:
- `projects[].enabled`: disables every configured source belonging to that project.
- `sources[].enabled`: disables only that source.
- Omitted values default to enabled for backward compatibility.

A disabled project/source is represented as `DISABLED`, with null measured sizes. It is never represented as zero. Its project coverage is `INCOMPLETE`, and the ecosystem total remains incomplete.

Manual CLI scope selection:
- Whole registry: `python -m tools.ecoscan --scope ecosystem` (default).
- One or more projects: `python -m tools.ecoscan --scope project --project NEXORA` (repeat `--project` for multiple projects).
- One or more sources: `python -m tools.ecoscan --scope source --source nexora-github` (repeat `--source` for multiple sources).

Invalid or unknown selectors fail before any source scan. A project-scope run includes only sources registered to the selected projects. A source-scope run includes only the selected source IDs and their corresponding project attribution, not sibling sources.

These controls and scope-selection behavior have unit-test coverage. They do not yet establish live provider connectivity or operational acceptance. Railway volumes, B2/R2/S3, backup inventories, Git LFS payload sizes, historical growth, and capacity forecasts remain unimplemented.
