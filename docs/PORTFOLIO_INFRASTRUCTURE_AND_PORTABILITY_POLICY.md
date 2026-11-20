# Portfolio Infrastructure, Portability, and Cost Independence Policy

**Document ID:** TRADIX-PORTFOLIO-INFRA-001  
**Status:** GOVERNING PORTFOLIO POLICY  
**Scope:** TRADIX and every current or future portfolio product and system  
**Authority:** Project owner  
**Effective date:** 2026-11-20  
**Change policy:** Amendments require explicit project-owner approval and must preserve the policy's non-negotiable constraints.

## 1. Purpose

The portfolio must grow on infrastructure that is proportionate to actual demand, economically sustainable, and portable between execution environments. Portability is a property of the architecture from the beginning; purchasing or renting larger infrastructure is a later operational decision.

The portfolio must not become dependent on a particular physical machine, host operating system, cloud vendor, VPS provider, storage provider, or paid platform feature.

## 2. Infrastructure growth sequence

The approved growth sequence is:

1. **Existing owned hardware (current stage):** Run and develop systems on available hardware already owned and in use. Use its genuinely available capacity before purchasing or renting additional compute.
2. **Virtual private servers (growth stage):** When measured resource demand, reliability requirements, connectivity, or operational needs justify it, move the relevant workloads to VPS infrastructure. VPS adoption must not require material application rewrites or surrender of data ownership.
3. **Owner-controlled physical server (mature stage):** When scale and economics justify it, move workloads to physical hardware owned and controlled by the portfolio owner.

These stages are capacity and operations choices, not architectural generations. Application contracts, data formats, project boundaries, and operational interfaces must remain compatible across all stages.

No stage transition is automatic. It requires measured need, a cost and risk assessment, a migration plan, and verification.

## 3. Current-stage resource rule

The first priority is to use the existing hardware. As a planning guideline, begin a capacity review when sustained use approaches approximately 50% of the usable capacity of the relevant resource on the systems actually assigned to the workloads.

The 50% figure is a review threshold, not an instruction to migrate immediately and not a simple average across resources. CPU, memory, storage capacity, storage I/O, network throughput, thermal limits, power, and service availability must be evaluated separately. A bottleneck or reliability constraint in one resource cannot be hidden by spare capacity in another.

Capacity decisions must use observed workload measurements and reasonable growth forecasts. Do not buy or rent infrastructure merely because a product might grow in the future.

## 4. Free and time-unlimited execution constraint

**Current execution must prioritize solutions that are genuinely free to continue using and do not stop merely because a trial, promotional credit, or time-limited allowance expires.**

A service or tool must not be treated as an approved operational dependency merely because it advertises a free tier.

Before any external service, platform, API, storage system, build service, domain, hosting product, or development tool is adopted as an execution dependency, document and verify all of the following:

1. **Actual free status:** Is it permanently available at no charge, or is it only a trial, promotional credit, or limited introductory offer?
2. **Time continuity:** Does it continue operating without payment after a defined period or credit expires? Are there inactivity shutdowns, expiry dates, forced renewals, or time-limited access?
3. **Payment and eligibility:** Does registration or continued use require a payment card, foreign payment method, paid account, or a country/identity status unavailable to the project owner?
4. **Complete cost exposure:** Identify direct and indirect charges, including compute, storage, storage operations, bandwidth, egress, API calls, build minutes, backups, snapshots, domains, IP addresses, support, taxes, overages, and required add-ons.
5. **Exit and replacement:** Can the project export its code, data, records, files, configuration, and identifiers in usable formats and continue elsewhere without the provider's continuing cooperation?

If any answer is unknown, the service is **not approved as a required production dependency** until the uncertainty is resolved. It may be used for a bounded evaluation only if expiry, cost, data custody, and exit risks are understood and it cannot become a single point of failure.

Open-source software may satisfy the licensing-cost requirement, but it does not make electricity, hardware, connectivity, maintenance, or backup free. Those operating costs must be considered separately.

## 5. Portability and project independence requirements

Every project must be independently deployable, migratable, recoverable, and replaceable. At minimum:

- No application may rely on a specific host path, machine identity, provider-only feature, or host operating system unless isolated behind a documented adapter and replaceable configuration.
- Runtime configuration and secrets must be separated from source code and handled through environment-specific configuration or an equivalent portable mechanism.
- Build and runtime dependencies must be declared and reproducible.
- Prefer portable packaging and interfaces, including containers where they reduce complexity and improve reproducibility. Do not introduce containers or orchestration where they add needless operational burden.
- Project data must remain within that project's ownership and access boundary.
- Each project must be exportable and restorable independently of other projects.
- Shared services must have documented interfaces, versioning, ownership, and replacement procedures. Shared use must not merge project data, credentials, accounts, finances, or authority.
- No paid provider, TRADIX service, VPS, or physical host may become an unapproved mandatory runtime dependency for an independent product.

## 6. Data integrity and migration requirements

A migration is not complete merely because an application starts on the destination.

The migration design must cover, where applicable:

- Application source, build instructions, dependency versions, and runtime configuration.
- Databases, schemas, migrations, and transactionally consistent backups.
- EventStore streams, event ordering, integrity metadata, and recovery state.
- Files and objects, receipts, manifests, identifiers, metadata, and access-control mappings.
- Logs and audit records that are required for continuity or compliance.
- Scheduled jobs, queues, integrations, webhook configuration, and service-to-service contracts.
- Secret transfer and rotation through a secure, separately controlled process; secrets must never be committed to source control or copied into public documentation.

Every data migration must provide an export/import procedure, integrity verification (including cryptographic checksums where applicable), a restore test, and a rollback or recovery plan. Stable identifiers and project attribution must be preserved.

A provider snapshot alone is not a portable backup. The project must retain an independently usable export of its essential data.

## 7. Migration acceptance tests

Before declaring a project portable, perform a practical test in a separate destination environment. The test must demonstrate:

1. The project can be built and started using its documented instructions.
2. Required configuration can be recreated without provider-specific hidden state.
3. Data, files, records, receipts, and identifiers can be exported and imported.
4. Checksums and application-level consistency checks pass.
5. Critical workflows operate on the destination.
6. Backup restoration works independently of the original host.
7. The project can be rolled back or the original environment retained safely until acceptance.
8. The project can be migrated without materially rewriting its application logic.

Tests must be recorded with date, source and destination environment types, versions, results, and unresolved limitations. Documentation alone does not prove portability.

## 8. Avoid premature complexity

Portability must be achieved through simple, explicit boundaries and replaceable adapters, not through speculative infrastructure.

- Do not introduce Kubernetes, complex service meshes, distributed databases, multi-cloud layers, or elaborate orchestration solely in anticipation of future scale.
- Prefer the smallest architecture that meets current requirements while preserving a credible exit path.
- Add abstraction only where a real provider boundary, portability requirement, security boundary, or tested operational need justifies it.
- Do not duplicate data or services across machines without a defined availability, backup, or recovery requirement.
- Do not purchase hardware or subscribe to a VPS before measured demand and total cost justify the move.

## 9. Provider and infrastructure decision record

Before adopting an external dependency, record:

- Service/provider and exact product/plan.
- Intended project(s) and purpose.
- Free-tier or license terms, including whether access is time-unlimited.
- Geographic, identity, account, and payment eligibility.
- Resource quotas, inactivity policies, and service suspension conditions.
- Direct and indirect costs, including egress and backup.
- Data export format, deletion/retention terms, and exit procedure.
- Replacement option and tested portability boundary.
- Decision status: approved, evaluation-only, rejected, or pending verification.
- Date and source links for the evidence; recheck terms before material expansion or renewal.

A free tier with a hard quota is not necessarily time-limited, but it is not unlimited. Record its quota and determine whether exceeding it causes charges, throttling, suspension, or data loss. Do not describe such a service as unconditionally free.

## 10. Governance and applicability

This policy applies portfolio-wide to TRADIX, NEXORA, MegaMarket, EXVARLI, AAECN, the trading-intelligence system, and all current or future projects, subject to their approved scopes.

The policy supplements the Foundational Architecture Charter. It does not merge project ownership or make TRADIX the operator of independent products.

Any proposed exception must identify the affected project, dependency, costs, duration, data and continuity risks, exit plan, and reason the standard cannot be met. An exception requires explicit approval by the project owner before the dependency becomes operationally mandatory.

## 11. Governing statement

**Build for portability from day one. Run on existing owned hardware first. Move to VPS only when measured needs justify it. Move to owner-controlled physical infrastructure when scale and economics justify it. At every stage, preserve independent projects, complete data ownership, practical recovery, and the ability to leave the provider. Current execution must not depend on trials, expiring credits, or compulsory payments.**

**Portability is mandatory; premature infrastructure spending and complexity are not.**
