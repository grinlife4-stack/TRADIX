# TRADIX Execution & Delivery Engine

**Status:** Architecture proposal / implementation not started  
**Date:** 2026-11-17  
**Scope:** TRADIX factory control plane and execution adapters

## 1. Decision

TRADIX should not reimplement mature tools for routine software production. It should discover, register, connect, orchestrate, verify, and replace existing tools through stable adapters.

The factory owns orchestration, policy, provenance, evidence, lifecycle, and interfaces. Specialized tools own the work they are designed to perform: source compilation, tests, packaging, signing, distribution, deployment, and monitoring.

This is a generic factory capability, not a MegaMarket, trading, AAECN, or other product subsystem.

## 2. Target capability chain

`Request → Project specification → Plan → Tool selection → Execution → Verification → Artifact → Approval → Delivery → Monitoring`

Every stage must emit structured evidence and a durable run record. A successful command is not automatically a successful delivery.

### Core responsibilities

1. **Tool Catalog**
   - Register tool identity, category, version, license, source, supported platforms, capabilities, inputs/outputs, resource needs, and operational constraints.
   - Track whether the tool is installed, reachable, authenticated, healthy, permitted, and currently usable.
   - Distinguish free/open-source software from hosted services with free tiers or usage limits.

2. **Adapter Contract**
   - Give every integration a versioned, vendor-neutral interface.
   - Keep provider-specific details inside adapters.
   - Support health checks, capability discovery, execution, cancellation, logs, artifact references, and error normalization.
   - Permit replacement only when the candidate satisfies the same declared contract and acceptance tests.

3. **Execution Orchestrator**
   - Build a dependency graph for each delivery workflow.
   - Dispatch steps to local, hosted, or self-hosted runners according to platform, cost, privacy, and resource policies.
   - Use isolated, least-privilege execution environments.
   - Make jobs resumable/idempotent where possible; record retries and timeouts.
   - Never expose secrets to untrusted project code or general-purpose agents.

4. **Verification and Evidence**
   - Bind test results, source commit, tool versions, build inputs, artifact digest, signer identity, and approval to one immutable run context.
   - Reject stale, missing, mismatched, or unverifiable evidence.
   - Separate technical verification from human release authorization.
   - Keep a run failed or blocked when a required verifier is unavailable.

5. **Artifact and Release Registry**
   - Store artifact metadata, checksums, provenance, build recipe, compatibility, retention, and release state.
   - Keep binaries and large artifacts in suitable artifact/object storage; do not put them in the capability metadata registry.
   - Support version pinning, promotion between environments, rollback references, and reproducible rebuild metadata.

6. **Delivery Connectors**
   - Integrate destination-specific publication APIs through separate adapters.
   - Require explicit project-owner approval for external publication, store submissions, payments, purchases, DNS changes, or production deployments.
   - Record submission IDs, review state, rejection reasons, and resulting release URLs where available.

## 3. Initial tool portfolio candidates

These are candidates to evaluate, not claims that they are already connected or installed.

| Workflow | Candidate tools | Notes / constraints |
|---|---|---|
| Cross-platform mobile UI | Flutter | Open-source framework; Android and iOS from shared code |
| Android build | Gradle + Android SDK | Build/signing environment and SDK licenses must be managed |
| iOS build/sign | Xcode on macOS | Apple platform requirement; cannot be replaced by a Linux-only runner |
| Mobile release automation | Fastlane | Automates parts of signing and store delivery; store accounts and credentials remain external |
| CI orchestration | GitHub Actions; self-hosted runners | Hosted quotas and platform limits must be visible; self-hosting is an option, not a prerequisite |
| Web UI testing | Playwright | Browser automation and test evidence |
| Python testing | pytest | Test runner, not a complete quality/security gate |
| Containerized builds | Docker or compatible OCI tooling | Optional execution isolation; assess daemon/security model before adoption |
| Dependency/security checks | OSV-Scanner, Trivy, Semgrep, Ruff | Evaluate license, maintenance, false-positive handling, and policy fit separately |

Tool selection must be based on current upstream maintenance, license, platform coverage, security posture, reproducibility, cost, and an executable proof of compatibility. Popularity alone is not acceptance evidence.

## 4. Mobile-app vertical slice

Use a deliberately small, non-commercial sample application to validate the complete chain before generalizing it.

### Android path
1. Generate or import a minimal Flutter sample in a separate product repository.
2. Resolve and pin Flutter, Gradle, Android SDK, and dependency versions.
3. Run static checks and automated tests.
4. Build a release AAB in a controlled runner.
5. Verify package identity, manifest permissions, version, signing configuration, and artifact digest.
6. Keep signing keys outside Git and outside ordinary agent context.
7. Produce a release evidence bundle.
8. Submit to a testing track only after explicit owner approval and valid Play Console access.

### iOS path
1. Reuse the same Flutter source where appropriate.
2. Dispatch build/sign steps to a macOS runner with a compatible Xcode version.
3. Verify bundle identifier, entitlements, provisioning profile, certificates, and artifact digest.
4. Keep Apple credentials and signing material in a protected secret store.
5. Produce a release evidence bundle.
6. Submit to TestFlight/App Store Connect only after explicit owner approval and valid Apple Developer access.

A successful build does not mean the store has accepted the app. Store review, developer enrollment, privacy declarations, age ratings, export compliance, screenshots, and policy compliance remain separate gates.

## 5. Security and authority boundaries

- Agents may propose plans and inspect outputs; they do not receive signing keys or unrestricted deployment credentials.
- Tool adapters run with scoped identities and least privilege.
- Secrets are injected only into the specific trusted execution step that needs them; logs must redact them.
- External side effects are disabled by default.
- Build and test jobs operate on pinned source commits and dependencies.
- Untrusted project code must not run inside the control-plane process.
- Every release requires evidence bound to the exact source SHA and artifact digest.
- A failed or missing verification gate blocks delivery.
- Human approval is required for store submission and production release until a separately reviewed policy authorizes a narrower automation scope.

## 6. Relationship to the Project Capability Registry

The Tool Catalog and Capability Registry are different records:

- **Tool Catalog:** external/local tools and adapters TRADIX can invoke.
- **Capability Registry:** reusable TRADIX-owned capabilities that have passed promotion review.

A tool being registered does not make it a trusted factory capability. An adapter becomes a shared TRADIX capability only after security, license, cost, test, compatibility, ownership, and evidence gates pass.

Do not add executable code, credentials, binaries, or project-specific business logic to capability descriptors.

## 7. Replaceability and resilience

- Define interfaces before selecting providers.
- Maintain at least one viable alternative for critical categories where practical.
- Record provider lock-in, data portability, rate limits, quotas, pricing triggers, and exit procedure.
- Keep workflow definitions independent of provider-specific syntax where feasible.
- Run adapter contract tests against every replacement candidate.
- Do not claim seamless replacement where formats, signing systems, proprietary APIs, or platform rules make it impossible; record the migration cost and manual steps.

## 8. Phased implementation

### Phase 0 — Inventory and policy
- Inspect the existing TRADIX repository and CI.
- Inventory tools already available in GitHub-hosted runners and connected services.
- Create a machine-readable tool descriptor schema and adapter contract.
- Define trust levels: discovered, evaluated, approved, connected, suspended, retired.
- No credentials, external publication, or new paid infrastructure.

### Phase 1 — Read-only catalog
- Implement tool descriptors and catalog queries.
- Record version, license, source, platform, status, capabilities, and evidence references.
- Add validation tests and documentation.
- No arbitrary command execution.

### Phase 2 — Safe execution adapters
- Add a narrow runner interface and allowlisted job types.
- Start with existing GitHub Actions workflows and local test commands.
- Add isolated execution, bounded resources, logs, cancellation, and run receipts.
- Do not allow agents to invent arbitrary shell commands or access secrets.

### Phase 3 — Artifact and evidence
- Add artifact digest/provenance records and evidence verification.
- Bind source SHA, dependency lock state, toolchain versions, test results, and output digests.
- Add retention and recovery policy.

### Phase 4 — Mobile vertical slice
- Build and verify the sample Android app.
- Add macOS/Xcode path for iOS only when a macOS runner and Apple developer access are available.
- Test distribution to internal testing tracks with owner approval.
- Do not submit a public store release as part of the prototype.

### Phase 5 — Generalize
- Extract only proven, reusable components into TRADIX.
- Publish stable interfaces and versioned adapters.
- Validate adoption by a second independent project before declaring the capability generally reusable.

## 9. Acceptance criteria

The engine is not considered operational until all are demonstrated:

1. A tool can be discovered, evaluated, registered, health-checked, and suspended.
2. An adapter passes a vendor-neutral contract test suite.
3. A workflow runs against a pinned source commit in an isolated runner.
4. Run evidence binds the source SHA, toolchain, tests, and artifact digest.
5. Missing or mismatched evidence blocks release.
6. Secrets are not exposed in logs, agent context, or repository contents.
7. A failed step can be diagnosed and retried without corrupting prior run evidence.
8. A replacement adapter passes the same contract tests.
9. The Android sample produces a verifiable AAB and internal testing submission record.
10. The iOS sample produces a verifiable signed artifact on macOS when that platform path is provisioned.
11. No product is forced to depend on a live TRADIX control plane to run a previously adopted artifact.
12. The complete flow is documented and independently reproducible.

## 10. Current status and explicit non-claims

This document is an architecture proposal only. It does not assert that Flutter, Gradle, Fastlane, Xcode, Android SDK, Play Console, App Store Connect, signing credentials, or any new runner are currently connected or provisioned.

No mobile app has been built, signed, submitted, or published by this proposal. No paid service, developer account, external credential, store submission, or production deployment is authorized.

The existing Project Capability Registry remains a prototype. Its authenticated reviewer identity, cryptographic approval receipts, externally anchored audit evidence, and package distribution gates remain separate prerequisites. This proposal does not authorize bypassing those gates.
