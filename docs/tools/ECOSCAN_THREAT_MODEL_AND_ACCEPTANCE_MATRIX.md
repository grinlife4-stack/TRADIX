# ECOSCAN — Threat Model and Acceptance-Test Matrix

**Document ID:** ECOSCAN-SEC-001  
**Status:** Draft threat model and test baseline  
**Applies to:** ECOSCAN 0.1 contracts and planned MVP  
**Related:** `docs/tools/ECOSCAN_SPEC.md`, `docs/tools/ECOSCAN_IMPLEMENTATION_PLAN.md`, `standards/ecoscan/0.1/`

## 1. Security objective

ECOSCAN is a read-only, scope-limited measurement tool. It must not change monitored resources, cross project boundaries, widen a requested scan, expose credentials, or misrepresent missing/partial data as zero or complete.

The default decision is deny. A scan runs only for an explicitly registered and enabled source, within the selected scope, using owner-authorized least-privilege access and bounded resources.

## 2. Assets

1. Project-owned source data and metadata.
2. Source credentials and credential references.
3. Project registries, scan history, checkpoints, evidence, and exports.
4. Project identity, owner/operator assignments, and authorization records.
5. Global/project/subsystem/source control states.
6. Scan budgets, provider quotas, and API request capacity.
7. Measurement integrity, timestamps, provenance, coverage, and limitations.
8. ECOSCAN package, schemas, dependencies, and release artifacts.

## 3. Trust boundaries

- **Project boundary:** each project's registry, history, evidence, and credentials remain independently controlled.
- **Source boundary:** GitHub, Backblaze B2, local filesystems, hosts, and other providers are untrusted external or local sources. A successful API response is not proof of complete physical usage.
- **Credential boundary:** secrets remain in owner-controlled secret storage. ECOSCAN receives only a narrowly scoped credential at execution time.
- **Adapter boundary:** adapters are replaceable, separately versioned components and must obey the typed read-only contract.
- **Filesystem boundary:** configured local paths are untrusted inputs. Path traversal, symlink escape, mount crossing, special files, and race conditions must be considered.
- **Export boundary:** exported registries, reports, and evidence may reveal sensitive infrastructure metadata. Exports are project-owned data, not public documents.
- **TRADIX boundary:** TRADIX is a development factory. No runtime call to TRADIX is required for a released ECOSCAN installation.

## 4. Threat actors and failure sources

- Malicious or compromised source/provider responses.
- Malicious or malformed registry/configuration inputs.
- A project operator with access to one project attempting to read another project's data.
- A compromised adapter, dependency, or build pipeline.
- Accidental credential disclosure through exceptions, logs, exports, or debug output.
- Untrusted local files, symlinks, mount points, or filesystem races.
- Network attacker attempting SSRF, endpoint substitution, replay, or credential interception.
- Resource exhaustion caused by huge listings, pagination loops, slow endpoints, or unbounded traversal.
- Operator error: wrong project/source selection, stale credential, broad scope, or misinterpreted measurement.

## 5. Threat register

| ID | Threat | Required control | Required negative test |
|---|---|---|---|
| EC-01 | Cross-project data disclosure | Separate per-project databases/directories; project ID checked on every read/write/export; no shared credential store | Project A identity cannot query, export, or import Project B data |
| EC-02 | Secret leakage | Opaque credential refs; secret values excluded from models, repr, logs, errors, SQLite, and exports | Inject canary secret and assert it is absent from every serialized/logged output |
| EC-03 | Unauthorized source scan | Owner/operator authorization and explicit source registration; fail closed | Missing, revoked, or mismatched authorization makes zero adapter calls |
| EC-04 | Scope expansion | Immutable requested scope; planner emits only selected source IDs | Single-source request never invokes any other registered adapter |
| EC-05 | Disabled-state bypass | Recheck global/project/subsystem/source switches before each page and publication | Disable mid-scan; next page and report publication are blocked |
| EC-06 | Read-only violation | Adapter contract exposes only list/metadata/read operations; use provider keys without write/delete | Fake client raises if put/delete/update/create operations are invoked |
| EC-07 | Path traversal/symlink escape | Canonical path containment, no-follow policy, mount boundary controls, safe file-type filtering | `../`, absolute path substitution, symlink escape, FIFO/device and mount crossing rejected |
| EC-08 | SSRF/metadata endpoint access | Strict provider endpoint allowlist; HTTPS; reject userinfo, unexpected ports, redirects to private/link-local/metadata IPs | Redirect/private IP/metadata endpoint and DNS rebinding simulations rejected |
| EC-09 | Unbounded scan / cost exhaustion | Max pages/items/time/concurrency, deadline, rate-limit backoff, checkpoint and cancellation | Huge listing, repeated continuation token, slow server, and rate-limit storm stop within budget |
| EC-10 | False zero or false completeness | Explicit coverage states; no measurement when source unavailable; measurement semantics/limitations mandatory | Failed/disabled/unconfigured source never yields a zero measurement or COMPLETE coverage |
| EC-11 | Misstated storage totals | Distinguish logical, allocated, physical, capacity, provider-reported, versions, and artifacts | Incomparable kinds/scopes/time windows cannot be aggregated |
| EC-12 | Checkpoint tampering/replay | Checkpoint bound to project/source/adapter/schema and scan ID; validate continuation tokens; integrity-protect local state where required | Reuse checkpoint across source/project or alter cursor is rejected |
| EC-13 | Export path traversal or tampering | Safe relative paths, manifest hashes, no symlink entries, import into a fresh isolated directory | `../` paths, duplicate paths, hash mismatch, symlink entries rejected |
| EC-14 | Dependency/supply-chain compromise | Minimal optional dependencies, pinned/reviewed versions, license inventory, reproducible release evidence | Dependency inventory and lockfile checks fail on unreviewed package/license |
| EC-15 | Audit/history alteration | Append-only scan events or tamper-evident history; backups and retention explicit | Mutated measurement/history is detected or clearly marked as unverified |
| EC-16 | Race between authorization and action | Revalidate authorization and control state immediately before each bounded request | Revocation between pages prevents subsequent provider call |
| EC-17 | Confused deputy | Adapter bound to one source descriptor and one credential reference; no arbitrary caller-supplied credential/URL | A request cannot substitute another source's credential or endpoint |
| EC-18 | Data retention/ownership violation | Project owner sets retention; ECOSCAN removal does not delete source data; export/import preserves ownership | Removing ECOSCAN leaves monitored source unchanged and project export intact |

## 6. Measurement integrity rules

1. Every measurement is bound to one project, one source, one adapter version, and one observation time.
2. Logical object bytes from S3 listing are not provider-billed bytes, physical bytes, or all-version bytes.
3. Missing, disabled, failed, stale, or unauthorized sources produce coverage records, not zero-valued measurements.
4. Partial pagination produces PARTIAL coverage even if some measurements were obtained.
5. Repeated continuation tokens, missing cursors, or truncated listings must stop safely and record the gap.
6. Aggregation requires equal measurement kind, unit, source semantics, compatible scope, and an explicitly defined time window.
7. Estimates are stored and displayed as estimates, never silently mixed with measured values.
8. Provider timestamps and local observation timestamps remain separate.

## 7. Required acceptance matrix

| ID | Test | Expected result | Gate |
|---|---|---|---|
| AT-01 | Registry schema valid/invalid fixtures | Valid documents pass; unknown fields and invalid IDs fail | Phase 1 |
| AT-02 | Measurement schema fixtures | Wrong units, negative values, unknown kinds, invalid timestamps fail | Phase 1 |
| AT-03 | Coverage schema fixtures | All six coverage states accepted; malformed records rejected | Phase 1 |
| AT-04 | Export manifest fixtures | Missing hashes, unsafe paths, unknown versions rejected | Phase 1 |
| AT-05 | Global switch disabled | No adapter call, no report/alert publication | Phase 1 |
| AT-06 | Project/subsystem/source disabled | Disabled source excluded and shown as DISABLED | Phase 1 |
| AT-07 | Exact scope | Single-source scan touches only that source | Phase 1 |
| AT-08 | Mid-scan disable/revocation | Next bounded operation is cancelled/blocked | Phase 1 |
| AT-09 | Read-only contract | No write/delete methods are exposed or called | Phase 1 |
| AT-10 | Local path containment | Traversal, symlink escape, forbidden file types, and mount escape rejected | Phase 1 |
| AT-11 | Budget/checkpoint | Page/item/time caps enforced; resume preserves source identity and scope | Phase 1 |
| AT-12 | Failure is not zero | Failed/disabled/unconfigured source yields coverage only | Phase 1 |
| AT-13 | Project isolation | Cross-project reads/import/export fail | Phase 1 |
| AT-14 | Export/import portability | Clean environment restores registry/history/evidence references without TRADIX | Phase 1 |
| AT-15 | GitHub pagination/rate limit | Bounded, resumable, read-only, correct partial coverage | Phase 2 |
| AT-16 | B2 pagination | Every current-object page accounted for within budget; repeated token rejected | Phase 3 |
| AT-17 | B2 semantics | Report current logical object bytes only; versions/multipart omissions explicit | Phase 3 |
| AT-18 | Live read-only source test | Only after owner authorization and credential scope review | Phase 2/3 |
| AT-19 | No TRADIX runtime | Installed package runs with TRADIX unavailable and no `tradix.*` import | Phase 5 |
| AT-20 | Remove/replace ECOSCAN | Source resources and owner data remain unchanged | Phase 5 |

## 8. Open security decisions

These are intentionally unresolved and must be settled before the relevant implementation phase:

1. Owner/operator identity source and authorization evidence format.
2. Local filesystem allowed-root and mount-boundary configuration model.
3. Whether local SQLite history needs application-level encryption for the selected deployment.
4. Checkpoint integrity mechanism and retention.
5. Export signing/authenticity requirements and key ownership.
6. Audit-log tamper evidence versus a simpler append-only local event log.
7. Exact GitHub API endpoints/scopes and whether private repository metadata is in MVP.
8. Exact B2 read-only application-key capabilities and treatment of versions, multipart uploads, and provider billing data.
9. Threat response and security update policy for optional dependencies.

## 9. Release decision

No ECOSCAN runtime, provider credential, persistent service, or deployment is approved by this document. Phase 1 may begin only after the schema and security review is accepted. Network adapters require separate source-owner authorization and provider-specific cost/permission review. Production use requires all relevant acceptance gates to pass.
