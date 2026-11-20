# ECOSCAN — Ecosystem Resource and Infrastructure Monitor

**Document ID:** ECOSCAN-SPEC-001  
**Status:** ARCHITECTURE BASELINE / IMPLEMENTATION NOT YET VERIFIED  
**System identity:** ECOSCAN  
**System type:** Independent portfolio-wide monitoring tool built by TRADIX  
**Canonical location:** `grinlife4-stack/TRADIX/docs/tools/ECOSCAN_SPEC.md`
**Ready-made capability audit:** [ECOSCAN Ready-Made Capability Audit](ECOSCAN_READY_MADE_CAPABILITY_AUDIT.md) (2026-11-20)
**Implementation plan:** [ECOSCAN Implementation Plan and MVP Boundary](ECOSCAN_IMPLEMENTATION_PLAN.md) (proposed; no implementation or runtime authorization implied)
**Threat model and acceptance matrix:** [ECOSCAN Threat Model and Acceptance-Test Matrix](ECOSCAN_THREAT_MODEL_AND_ACCEPTANCE_MATRIX.md) (draft)

## 1. Purpose and identity

ECOSCAN is an independent system for measuring, tracking, and reporting the technical resources and infrastructure used by all registered projects and tools in the ecosystem.

It is built and documented through TRADIX, which remains the permanent factory and toolbox. Once delivered, ECOSCAN has its own identity, configuration, data, operating lifecycle, and runtime. It must be usable without TRADIX running or being reachable.

ECOSCAN is not a storage provider, infrastructure owner, deployment controller, or project operator. Its default role is read-only measurement, analysis, and reporting.

## 2. Operating principle: scan only what is needed

ECOSCAN must not continuously scan the entire ecosystem by default. The requested scope determines the work performed.

Supported scopes:

1. **Ecosystem-wide:** scan all registered and enabled projects and sources.
2. **Project:** scan one or more selected projects.
3. **Subsystem/category:** scan a selected class of resources, such as repositories, object storage, local servers, backups, or deployment volumes.
4. **Individual source:** scan one selected repository, bucket, volume, server path, archive, or other registered source.
5. **Comparison/recheck:** revisit only sources selected for verification or comparison with an earlier measurement.

A request for a narrow scan must not silently expand into a full-ecosystem scan. The report must state exactly what was in scope and what was excluded.

## 3. Independent controls

Controls are hierarchical and persistent:

- **Global system switch:** ENABLED / DISABLED. DISABLED stops all new manual scans, scheduled scans, background jobs, and report/alert publication. It does not delete historical data or configuration.
- **Automatic schedule switch:** ENABLED / DISABLED. When disabled, no scheduled scan runs. Manual scans remain available if the global switch is enabled.
- **Manual execution:** an authorized user selects the scope and starts a one-time scan. Manual execution does not enable future schedules.
- **Project switch:** ENABLED / DISABLED for each registered project.
- **Subsystem switch:** ENABLED / DISABLED for each category or subsystem.
- **Source switch:** ENABLED / DISABLED for each individual source.

The global switch overrides every lower-level switch. A disabled project, subsystem, or source is excluded from execution. Its absence must be shown in coverage reporting and must never be represented as zero consumption.

The system must expose current state, last state-change time, actor/source of the change, reason, last successful scan, last report, and next scheduled run where applicable.

## 4. Registry and project isolation

The registry is extensible. It must not assume a fixed project list or hard-code the current portfolio.

Each registered project has a stable project_id and separately registered source_id values. Each source record defines:

- project_id and source_id;
- source/provider type and opaque locator;
- measurement adapter and measurement type;
- authorized credential reference (never the secret value);
- enabled/disabled state;
- expected measurement fields and units;
- scan budget, pagination/checkpoint rules, and optional schedule;
- data-retention and reporting policy.

The registry stores only the references and rules required to measure resources. It must not copy project secrets, private files, financial records, business content, or unrelated metadata into a shared store. Credentials remain in the owning project's/provider's secret store and are accessed only through least-privilege authorization.

## 5. Measurement model and accuracy

Each measurement must be attributable to a specific project and source and must include:

- measured_at and source_timestamp where available;
- logical bytes and object/file count, where exposed;
- physical bytes or provider-reported consumption, where reliable;
- capacity bytes only when the provider exposes a trustworthy denominator;
- backup, archive, replica, snapshot, and incomplete-upload sizes as separate categories where available;
- measurement method, adapter version, evidence/reference, and confidence/limitations;
- coverage state: COMPLETE, PARTIAL, FAILED, NOT_CONFIGURED, NOT_AUTHORIZED, or DISABLED.

Never combine unlike quantities into one unexplained total. In particular, logical repository blob size, repository history, Git LFS, local disk use, deployment volume use, object storage, backups, archives, and deduplicated physical storage must remain distinguishable.

A missing, disabled, inaccessible, stale, or failed source is not zero. Portfolio totals must be marked PARTIAL/INCOMPLETE whenever an in-scope source has no valid measurement. Every report must distinguish measured values from estimates.

## 6. Reports, history, and alerts

Every report includes:

1. requested scope and timestamp;
2. coverage status and excluded/disabled sources;
3. per-project and per-source measurements;
4. portfolio total only for comparable measurements, with the exact aggregation basis;
5. logical versus physical, backup, archive, and other separate usage categories;
6. changes from the previous comparable measurement;
7. growth rate or forecast only after sufficient comparable history exists, clearly labelled as an estimate;
8. capacity alerts only where both used and capacity values are trustworthy;
9. failed, inaccessible, stale, and unregistered sources;
10. evidence, method, confidence, and limitations.

Reports and alerts are separate outputs. A report may be generated without sending an immediate alert. Alert channels are optional and must not be required for core operation.

History must be durable, exportable, and attributable to the relevant project/source. Retention and deletion are explicit owner-controlled policies.

## 7. Low-overhead execution

- Default mode is MANUAL; automatic scheduling is opt-in and independently switchable.
- No continuous polling or always-on scanner is required.
- Prefer provider inventory APIs, filesystem metadata, repository metadata, and recorded upload/delete events.
- Do not download file contents to measure their sizes.
- Do not hash every byte during routine inventory.
- Support pagination, checkpoints, bounded concurrency, rate-limit handling, timeouts, and resumable scans.
- Skip unchanged sources when reliable provider version markers or cursors prove that a rescan is unnecessary.
- Apply per-project and per-source time, API-call, and concurrency budgets.
- A global DISABLED state must prevent both manual and scheduled execution and prevent publication of new reports/alerts.

## 8. Security and read-only boundaries

- Read-only access by default; no write, delete, deploy, resize, billing, or configuration changes to monitored resources.
- Each adapter receives only the minimum access required for its registered source.
- No cross-project credential reuse.
- Secrets are referenced, never copied into ECOSCAN reports or source control.
- Reports must not expose secret values, private file contents, or sensitive locators.
- Permission failures are reported; ECOSCAN must not widen permissions or try alternate credentials automatically.
- Project owners retain authority over their resources and access grants.

## 9. Portability and replacement

ECOSCAN must be deployable independently of TRADIX and use provider-neutral adapters and exportable configuration/report formats.

Its design must support local execution, user-owned servers, and replaceable compatible storage/inventory providers without making a paid cloud service mandatory. A provider adapter must not become the only representation of the source registry or measurement history.

ECOSCAN can be stopped, moved, upgraded, replaced, or removed without changing monitored project resources. Removing ECOSCAN must not delete source data, backups, credentials, or project records. Historical reports are retained or deleted only according to explicit policy.

## 10. Acceptance gates

ECOSCAN is not operationally complete until evidence demonstrates:

- whole-ecosystem, project-only, subsystem-only, and single-source scan scopes;
- no accidental scope expansion;
- global, schedule, project, subsystem, and source switches, including persistence and precedence;
- DISABLED state blocks all new execution and report/alert publication;
- disabled and failed sources remain visible as coverage gaps, never zero;
- separate measurement types and no double counting;
- read-only access and least-privilege credential handling;
- bounded, resumable scans and correct rate-limit/timeout handling;
- durable history, export/import, and report attribution;
- independent operation without TRADIX runtime availability;
- safe stop, replacement, and removal without effects on monitored projects;
- default configuration requires no paid provider or always-on service.

Until these gates are tested and accepted, ECOSCAN must be described as specified or under implementation, not as a fully operational ecosystem monitor.
