# TRADIX Operating Instructions

These instructions are mandatory for any assistant or agent working on TRADIX.

## 1. Treat TRADIX as an existing, multi-part, general-purpose system

TRADIX is a general-purpose, all-rounder, extensible execution system. Do not redefine it around one product or mission. MegaMarket is one mission used to develop and validate TRADIX, not the definition or boundary of TRADIX.

Assume prior work may exist across multiple Git branches, pull requests, connected services, databases, deployments, files, and conversation history. The default branch alone is never a complete representation of the system.

## 2. Mandatory preflight before assessing, planning, or building

Before claiming what TRADIX has, lacks, or needs:

1. Retrieve relevant prior project context and decisions. Do not ask the user to repeat information already available.
2. Inspect the repository identity, default branch, **all relevant branches**, recent commits, open and recently closed pull requests, and their diffs.
3. Inspect project instructions, architecture documents, manifests, source files, tests, workflows, configuration templates, and product-specific folders across relevant branches.
4. Inspect connected infrastructure and services that are part of the project, including databases, branches, schemas, migrations, records where safe, deployments, storage, and monitoring.
5. Cross-check code, tests, database state, deployment state, and documentation. A document describing a feature is not proof it is implemented; a table existing is not proof the feature works.
6. Search for an existing implementation or in-progress work before proposing a new component, tool, engine, or dependency.
7. Record the evidence and the exact branch/service/environment it came from.

If a source cannot be accessed, report that specific source as inaccessible. Do not silently omit it and do not infer that its contents or capabilities are absent.

## 3. Required status vocabulary

Classify every relevant capability using these distinct states:

- **Present and verified:** implementation and appropriate tests or live evidence confirm it.
- **Present, incomplete:** implementation exists but required behavior, tests, or integration is missing.
- **Documented only:** described in plans or docs, but implementation is not verified.
- **In progress:** exists in an active branch, pull request, or deployment workflow.
- **Absent after search:** searched all relevant accessible locations and found no implementation.
- **Unknown / inaccessible:** evidence is insufficient or access is unavailable.

Never equate "not found in main" with "does not exist". Never equate "not accessible" with "absent".

## 4. No duplicate work

Before recommending or creating anything new, compare it against existing code, branches, PRs, database objects, service configurations, and previous decisions. Prefer completing, repairing, integrating, or replacing existing work over creating a duplicate.

Do not recommend infrastructure or dependencies merely because they are familiar. Justify each addition against a demonstrated requirement and prefer free/open-source, portable, replaceable options where practical.

## 5. Change and safety controls

- Read-only inspection is the default.
- Do not commit, push, merge, deploy, delete, migrate, rotate credentials, or change production data without explicit user authorization for that action.
- Use isolated branches and test environments for proposed changes.
- Preserve existing work and decisions. Do not perform broad cleanup or rewrites without a specific approved scope.
- Report exactly what was inspected, changed, tested, and left untouched.

## 6. TRADIX mission-development rule

Use a concrete mission to reveal real capability gaps, but keep the TRADIX core general-purpose. Distinguish:
- general capabilities belonging in TRADIX,
- mission-specific modules belonging to the relevant product/project,
- external tools/services that can be connected and replaced.

Do not attempt to complete every hypothetical capability before execution. Build only against verified requirements and observed gaps.

## 7. Required output for a system audit

An audit must include:
1. Scope inspected (repositories, branches, PRs, services, environments).
2. A capability matrix with the status vocabulary above.
3. Evidence references (file paths, branch names, PR numbers, database/service identifiers).
4. Risks, blockers, and genuinely missing capabilities.
5. The smallest safe next action.

Do not present an audit as complete if any material part of the system was not inspected. State the limitation plainly.
