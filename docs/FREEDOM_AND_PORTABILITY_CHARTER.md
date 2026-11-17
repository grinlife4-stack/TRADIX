# TRADIX Freedom, Independence, and Portability Charter

**Status:** Design charter v1.0 — implementation is staged and evidence-gated  
**Applies to:** TRADIX factory core, every product dossier, runtime, capability adapters, data, and deployment target

## 1. Foundational principle

TRADIX is intended to be an owner-directed, independently operable production factory. It must not become dependent on one AI model, chat account, cloud vendor, database vendor, repository host, operating system, programming language, or deployment provider.

Freedom means the owner can choose, replace, move, extend, pause, or retire capabilities without losing the factory's identity, records, products, or operational continuity. It does not mean uncontrolled execution or the absence of accountability.

## 2. Owner authority and replaceable interfaces

- The owner is the ultimate authority over the factory's purpose, ownership, standing policies, and reserved decisions.
- Administrators and delegates receive explicit, scoped, revocable permissions.
- Conversational AI interfaces are replaceable tools. They do not own the factory, its memory, its policies, its approvals, or its products.
- No model provider may become a single point of failure or the only holder of operational context.
- The exact owner identity, email hierarchy, and emergency ownership-transfer procedure remain **deferred decisions**. This charter does not define or change them.

## 3. Product independence and factory-wide reuse

- Every product has its own dossier, lifecycle, goals, budget, tasks, decisions, evidence, artifacts, permissions, and operational history.
- Product data and authority must not leak across project boundaries.
- Shared factory capabilities are reusable only through versioned, documented interfaces.
- Reuse requires compatibility, dependency, license, security, provenance, and test-evidence checks. Unverified copying is not accepted as reuse.
- The factory may produce software, digital services, physical products, and other product categories. Software is a capability, not the definition or limit of TRADIX.

## 4. Technology and provider freedom

- Prefer open standards, portable formats, and free/open-source components when they meet the required security, reliability, and capability level.
- Paid or proprietary providers may be used only as replaceable adapters when justified; they must not become embedded assumptions in core contracts.
- Keep provider-specific credentials and APIs behind adapters. Never place secrets in source control or product artifacts.
- Maintain documented alternatives for critical capabilities where practical.
- A capability is available only after its real access, permissions, limits, and behavior have been tested. A configured name or theoretical integration is not proof.

## 5. Autonomous operation under owner-defined policy

- The factory should independently plan, build, test, repair, verify, and report routine work that falls within an explicit project scope and standing resource policy.
- Reversible, low-risk actions already authorized by policy should not require repetitive human approval.
- The factory must stop or request the required authority for actions outside policy, including production-impacting changes, destructive or irreversible operations, sensitive access changes, legal/financial commitments, and spending beyond an approved ceiling.
- Agents and models may propose or execute only within granted permissions. They cannot approve their own work, expand their own authority, or silently redefine the owner's objective.
- Every material action must be attributable and supported by durable events, artifacts, and verification evidence.

## 6. Portability and recovery

TRADIX must be designed so the owner can move it to another provider or self-hosted environment without rebuilding its identity or losing product history.

Portable scope includes:
- source code, schemas, migrations, and build/deployment definitions;
- database records, event history, product dossiers, decisions, and approvals;
- artifact payloads, metadata, hashes, and provenance;
- non-secret configuration and capability definitions;
- identity mappings and permission policy, subject to secure re-enrollment;
- encrypted backups and the documented procedures required to restore them.

Secrets must be transferred through a secure secret-management process, never embedded in ordinary exports or source control. Provider-specific state must be identified and either exported, reconstructed, or explicitly marked non-portable.

A backup is not proven until a restore has been completed and integrity-checked in an isolated target environment. A code clone alone is not a factory migration.

## 7. No silent lock-in

- Core data models and APIs must be documented and versioned.
- Export/import paths must use documented, inspectable formats.
- Critical services must have an exit strategy and a tested replacement path before they become irreplaceable dependencies.
- Product records must remain readable independently of the AI model or user interface that created them.
- The factory must be able to operate in a reduced mode if an optional provider is unavailable.

## 8. Change discipline

This charter establishes design direction, not blanket authorization for risky operations. Implementation proceeds in small, testable stages. No production migration, deployment, paid-resource commitment, secret change, ownership transfer, or merge to the default branch is authorized by this document.

Deferred decisions remain deferred until the owner explicitly decides them. In particular, the two-email ownership/recovery design is not implemented or finalized here.

## 9. Acceptance criteria

The freedom and portability goals are not considered achieved until tests demonstrate that:

1. a conversational AI provider can be replaced without losing factory state;
2. products remain isolated while approved shared capabilities can be reused;
3. the core can run without any single optional provider;
4. source, database, artifacts, configuration, and audit history can be exported;
5. a complete backup can be restored on a different isolated environment;
6. restored records, artifact hashes, permissions, and product histories pass integrity checks;
7. routine in-policy work can proceed autonomously while reserved actions remain gated;
8. the owner can inspect, export, move, or retire the factory without needing the original vendor's continued cooperation.

Until these tests pass, portability and independence are architectural requirements, not achieved capabilities.
