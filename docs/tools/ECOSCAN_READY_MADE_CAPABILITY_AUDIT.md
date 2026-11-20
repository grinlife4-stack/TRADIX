# ECOSCAN — Ready-Made Capability Audit

**Document ID:** ECOSCAN-AUDIT-001  
**Audit date:** 2026-11-20  
**Status:** Initial evidence-based architecture audit; revalidate versions, licenses, and provider terms before adoption  
**Scope:** Ready-made tools and interfaces relevant to ECOSCAN's resource/infrastructure inventory, measurement, history, reporting, and alerting requirements  
**Decision authority:** Project owner

## 1. Executive decision

**Do not build a new general-purpose monitoring stack.** ECOSCAN's distinctive requirement is not another CPU dashboard. It is a scope-controlled, project-isolated, read-only inventory and measurement orchestrator that can combine heterogeneous sources while preserving provenance, coverage gaps, measurement types, cost limits, and exportability.

Use existing systems directly where they already provide the needed measurement:

- Use provider-native read-only inventory/metadata APIs for cloud and object-storage sources, subject to a separate provider-specific cost, permission, and availability check.
- Use operating-system and filesystem metadata interfaces for local paths and volumes.
- Use GitHub's repository metadata and dedicated Git LFS usage interfaces separately; do not treat a repository-size field as a complete account of LFS, artifacts, packages, or external backups.
- If host telemetry is required, prefer a small existing self-hosted option such as Beszel for selected hosts, or Zabbix/Prometheus where their operational footprint is justified.
- Treat OpenTelemetry Collector as an optional telemetry pipeline, not as an inventory database or scanner.
- Do not make Grafana, Zabbix, Beszel, Netdata, Prometheus, or any cloud service a mandatory ECOSCAN runtime dependency.

Custom development is justified only for the thin ECOSCAN layer that existing products do not supply as one portable, owner-controlled capability: source registry, scan-scope enforcement, project boundaries, normalized measurement/evidence model, coverage-state semantics, budget enforcement, resumability, comparable reports, and export/import.

## 2. Requirements tested against existing options

| Required capability | Existing option | Reuse decision | Gap / limitation |
|---|---|---|---|
| Host CPU, memory, disk, network, GPU, SMART and container metrics | Beszel; Zabbix; Prometheus exporters | Use directly when host telemetry is needed; Beszel is the lightest initial candidate for selected Linux/host sources | These are monitoring agents/hubs, not portfolio-wide source inventories. They may require persistent agents, services, or a server. |
| Numeric time-series collection and alert rules | Prometheus | Reuse directly for continuous metrics where justified | Prometheus explicitly targets numeric time series; it is not a complete per-object inventory or exact billing ledger. |
| Dashboards across metrics sources | Grafana OSS | Optional presentation layer only | AGPL-3.0-only default license and operational/UI scope; not needed for a minimal manual inventory MVP. |
| Enterprise network/server/service discovery and monitoring | Zabbix | Consider for environments already using it or requiring its breadth | AGPLv3 from 7.0 onward; server/database/frontend/proxy architecture is heavier than a manual, bounded inventory tool. Not an object-store or project-accounting source of truth. |
| Vendor-neutral telemetry receive/process/export | OpenTelemetry Collector | Optional adapter/pipeline if telemetry already exists | It is a telemetry pipeline, not an inventory registry, durable portfolio measurement model, or complete report engine. Component maturity varies. |
| Lightweight host monitoring | Beszel | Preferred optional candidate for a small self-hosted host-monitoring pilot | Hub + agents; metrics focus is hosts/containers/disks/ZFS. It does not cover GitHub repositories, object-storage inventory, or cross-provider source semantics. MIT license. |
| Full-stack host/application monitoring | Netdata | Do not select as the default core | Agent is GPLv3+, but the Netdata UI and Cloud have closed-source components; Cloud has free and paid tiers. This creates a mixed licensing and optional cloud dependency that is unnecessary for ECOSCAN's core. |
| Repository metadata and LFS accounting | GitHub REST API + Git LFS usage interfaces | Use provider-native interfaces directly | Repository metadata is not a complete measurement of all storage classes. Git LFS stores actual objects separately from pointer files and has separate quotas/billing. Actions artifacts, packages, releases, and backups need separate measurement paths. |
| Object storage and provider capacity/usage | Provider-native APIs and inventory features | Use per-provider adapters only after separate review | No universal API or universal zero-cost guarantee. API request charges, inventory generation, egress, account eligibility, permissions, retention, and regional restrictions must be checked per provider. |
| Local filesystems, volumes, and backup directories | Native OS/filesystem metadata tools | Use directly through narrow read-only adapters | Logical size, allocated blocks, snapshots, deduplication, sparse files, hard links, and filesystem-level physical usage are not interchangeable. |

## 3. Candidate assessment

### 3.1 Beszel — preferred optional host telemetry candidate

- **Capability:** Lightweight self-hosted host monitoring with a hub and agents; published metrics include CPU, memory, disk usage/I/O, network, temperature, GPU, containers, SMART, and ZFS.
- **License:** MIT, according to its project repository.
- **Cost:** Software can be self-hosted without a required paid monitoring subscription. Hardware, power, network, and maintenance remain real costs. Do not assume that every optional integration or hosted service is free.
- **Security/operations:** Requires a hub and agent communication. Only install agents on explicitly registered systems, restrict network exposure, use per-system credentials, and retain a read-only monitoring role. Do not expose the hub publicly by default.
- **Portability:** Self-hosted deployment and API support are useful; export/restore must be tested before relying on it as a historical record.
- **Decision:** Suitable as an optional source adapter for host telemetry, not as ECOSCAN's core registry or report authority.
- **Evidence:** [Beszel repository and feature/license description](https://github.com/henrygd/beszel); [release history](https://github.com/henrygd/beszel/releases).

### 3.2 Prometheus — proven time-series engine, not inventory core

- **Capability:** Scrapes and stores numeric time-series metrics, supports exporters, rules, and alerting. Its standalone server is designed to remain useful without remote storage.
- **License:** Apache-2.0.
- **Cost:** Self-hosted software has no license fee; compute, storage, backups, and maintenance are not free.
- **Security/operations:** Scrape targets and exporters expand the network and credential surface. Keep targets allowlisted, endpoints private, and retention bounded.
- **Portability:** Local time-series storage and open query interfaces reduce dependence on a hosted vendor.
- **Limitation:** Prometheus documentation explicitly warns against using it for 100%-accurate per-request billing. It also does not solve project/source ownership, object inventory, LFS accounting, or coverage completeness.
- **Decision:** Reuse for optional continuous numeric metrics only. Do not make it mandatory for manual source inventory.
- **Evidence:** [Prometheus overview and design fit/limitations](https://prometheus.io/docs/introduction/overview/); [Prometheus Apache-2.0 license](https://github.com/prometheus/prometheus/blob/main/LICENSE).

### 3.3 Zabbix — broad monitoring suite, operationally heavier

- **Capability:** Distributed monitoring of networks, servers, VMs, applications, databases, cloud resources, discovery, alerts, and capacity planning.
- **License:** AGPLv3 from version 7.0 onward.
- **Cost:** Software is available at no license cost. Hosting, database operations, support, and maintenance remain costs. Commercial support is optional.
- **Security/operations:** Its server/database/frontend/proxy architecture and agent or agentless collection are more operational machinery than the initial ECOSCAN manual-scan model needs.
- **Portability:** Self-hosted, but migration/export and retention behavior must be tested for the chosen deployment.
- **Decision:** Do not deploy a separate Zabbix stack just for ECOSCAN. Reuse an existing Zabbix installation through a read-only adapter if a project already operates one or a later requirement justifies it.
- **Evidence:** [Zabbix product overview](https://www.zabbix.com/documentation/current/en/manual/introduction); [Zabbix licensing](https://www.zabbix.com/license).

### 3.4 OpenTelemetry Collector — optional data pipeline

- **Capability:** Vendor-neutral receivers, processors, exporters, connectors, and extensions for metrics, logs, and traces.
- **License:** OpenTelemetry Collector project is Apache-2.0; verify individual third-party components and distributions before bundling them.
- **Cost:** Self-hosted collector software is free to use; backend, storage, compute, and operations may cost money.
- **Security/operations:** Can support batching, retries, encryption, and sensitive-data filtering, but a collector also creates a data movement and egress boundary that must be explicitly configured.
- **Limitation:** It is a pipeline, not the authoritative source registry, inventory database, coverage model, or measurement report engine. Component stability varies.
- **Decision:** Optional only when a source already emits telemetry and a pipeline is useful. Do not introduce it for a one-off metadata scan.
- **Evidence:** [Collector architecture, objectives, and security guidance](https://opentelemetry.io/docs/collector/); [component types and registry](https://opentelemetry.io/docs/collector/components/).

### 3.5 Grafana OSS — optional visualization

- **Capability:** Dashboards and analysis across supported data sources, including Prometheus.
- **License:** Default repository license is AGPL-3.0-only, with explicitly listed Apache-2.0 exceptions for selected paths.
- **Cost:** Self-hosted OSS avoids a mandatory cloud subscription; compute, storage, upgrades, and operations remain costs. Hosted Grafana offerings are not part of the zero-cost baseline.
- **Limitation:** Visualization does not establish measurement accuracy, source completeness, authorization, or data ownership.
- **Decision:** Do not add it to the first ECOSCAN release. Export reports in portable formats first; add Grafana only if real operator demand justifies the additional service.
- **Evidence:** [Grafana licensing details](https://github.com/grafana/grafana/blob/main/LICENSING.md); [Prometheus data source](https://grafana.com/docs/grafana/latest/datasources/prometheus/).

### 3.6 Netdata — not selected as the default

- **Capability:** Broad host and application observability with metrics, logs, traces, alerts, and integrations.
- **License boundary:** Netdata Agent is GPLv3+; Netdata UI and Netdata Cloud are closed-source, with free and paid Cloud tiers.
- **Cost/lock-in:** A self-hosted agent can be used, but a workflow that relies on the proprietary UI or hosted Cloud is not a fully open-source, fully self-contained baseline.
- **Decision:** Do not make Netdata the ECOSCAN core. An existing agent may be considered as a source only if the exact API/export and licensing boundary is acceptable.
- **Evidence:** [Netdata repository and component licensing](https://github.com/netdata/netdata).

## 4. Source-specific measurement rules

### GitHub repositories

Use GitHub's API for repository metadata, but do not infer complete storage consumption from one repository-size value. Git LFS stores object content separately from pointer files; LFS storage and bandwidth have separate quotas and billing behavior. Treat at least these as distinct source classes: Git repository data, Git LFS, Actions artifacts, Packages, Releases, and external backups. Each requires its own API or provider measurement and its own coverage state.

Evidence: [Git LFS storage model](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage); [Git LFS billing and free quotas](https://docs.github.com/en/billing/concepts/product-billing/git-lfs).

### Object storage and backups

Do not select Backblaze B2, S3, R2, or another provider as a mandatory dependency. Implement provider-specific adapters only after documenting the provider's current API, authentication scope, inventory/listing behavior, pagination, request pricing, minimum retention or lifecycle fees, egress, regional eligibility, and account access. Provider-native inventories may be preferred for large buckets when their generation and storage costs are known. A missing credential or unavailable provider is NOT_AUTHORIZED/FAILED, never zero.

### Local filesystems and disks

Use native metadata/statistics APIs with explicit semantics. Preserve logical bytes, allocated bytes, filesystem capacity, snapshots, replicas, and deduplicated physical consumption as separate measurements. Avoid reading or hashing file contents during routine inventory. A filesystem scan must have explicit path allowlists, mount boundaries, symlink policy, and time/concurrency limits.

## 5. Cost, eligibility, and operating constraints

1. No paid hosted dashboard, cloud database, always-on SaaS, or paid agent is required by the core architecture.
2. Self-hosted open-source software is not literally cost-free: hardware, electricity, backups, bandwidth, API calls, and maintenance remain.
3. Provider API pricing and access eligibility must be checked before enabling an adapter. No adapter is enabled merely because its API exists.
4. Do not assume a provider, SaaS dashboard, payment method, or account feature is available from Iran or any other jurisdiction. Verify the specific account and provider terms before connection.
5. Start with manual execution and existing user-owned infrastructure. Scheduling and continuous monitoring remain opt-in.
6. Do not download file contents, perform full content hashing, or create a permanent agent footprint unless a specific source requires it and the owner approves it.

## 6. Recommended implementation boundary

### Reuse

- Native provider APIs and inventory features for cloud/object-storage sources.
- Native OS/filesystem metadata for local storage.
- GitHub API plus separate Git LFS and artifact/package measurements.
- Beszel as an optional host-metrics adapter where its hub/agent model is acceptable.
- Existing Prometheus/Zabbix/OpenTelemetry installations only through documented read-only interfaces when already justified by the source owner.

### Build only the missing ECOSCAN layer

- Portable source/project registry and explicit owner/operator assignment.
- Per-source adapter contract and capability declaration.
- Scope planner that cannot silently widen a requested scan.
- Persistent global/schedule/project/subsystem/source switches.
- Per-source API/time/concurrency budgets and resumable checkpoints.
- Normalized measurement envelope with units, timestamps, provenance, confidence, and coverage states.
- Strict distinction between logical/physical/capacity/backup/LFS/artifact metrics.
- Durable, attributable, exportable reports and history.
- Read-only security boundary, credential references, and negative tests proving no write operations.
- Optional alert routing separated from report generation.

Do not build a new metrics time-series database, dashboard, alerting platform, remote agent fleet, or general-purpose deployment manager unless a later evidence-based requirement proves that an existing tool cannot meet it.

## 7. Audit outcome and gates before implementation

**Decision:** Selective reuse plus a thin custom orchestration layer. No full monitoring platform is to be rebuilt.

Before implementing any adapter, record a provider/source-specific mini-audit containing:
- exact source owner and operator;
- supported API and data fields;
- credential scope and revocation path;
- request pricing, quotas, pagination, and rate limits;
- regional/account eligibility and any payment-method requirement;
- measurement semantics and known omissions;
- export format and replacement path;
- test fixture and expected coverage-state behavior.

Before any pilot is enabled, the source owner must explicitly authorize read-only access. Until the adapter passes these gates, report it as NOT_CONFIGURED or NOT_AUTHORIZED, not operational.

## 8. Revalidation

This audit is a dated decision record, not a permanent endorsement of third-party products. Recheck project activity, license, supported versions, security advisories, API terms, costs, and regional availability immediately before adoption and at each major upgrade.
