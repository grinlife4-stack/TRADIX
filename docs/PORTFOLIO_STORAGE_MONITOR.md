# Portfolio Storage Monitor

**Document ID:** TRADIX-TOOL-PORTFOLIO-STORAGE-MONITOR-001  
**Status:** PROPOSED / REVIEW REQUIRED  
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
- Other projects added through an explicit registry entry

Each project is a separate measurement boundary. A project may contain multiple systems, repositories, document stores, object-storage buckets, local disks, archives, and backup locations. Each source must be separately identified and authorized.

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

Proposed initial schedule, subject to owner approval and successful implementation:
- Weekly: independent source inventory and project-level report.
- Monthly: portfolio summary, growth comparison, and capacity forecast.
- Immediate alert: only when a completed measurement crosses a configured threshold or a previously available source becomes inaccessible.

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

- Keep the tool in its own directory under `tools/portfolio_storage_monitor/`.
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

This document establishes the design contract only. It does not claim that scanners, schedules, notifications, integrations, or live portfolio measurements have been implemented or tested. The first implementation should be a local/manual read-only inventory runner with a small registry and normalized JSON reports. Scheduling and alerts are a later, separately verifiable stage.
