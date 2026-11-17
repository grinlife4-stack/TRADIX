# Architecture Decision: Independent Product Repositories

**Decision date:** 2026-11-17  
**Status:** Accepted as the target architecture; migration is pending.

## Decision

TRADIX is the software-factory control plane. It must not become the source repository or runtime owner for independent products.

Each independent product owns its source code, tests, release history, product data, runtime configuration, credentials, and deployment lifecycle in a separate repository and isolated environment.

TRADIX may provide reusable factory capabilities through versioned, documented interfaces. It may hold only control-plane records needed to coordinate work: project identifier, repository reference, task state, policy gates, approvals, CI/release evidence references, and high-level status. Product-specific implementation, secrets, operational datasets, and commercial workflows must not be copied into TRADIX core.

## MegaMarket boundary

- MegaMarket is an independent product.
- CPIIE is a MegaMarket-owned subsystem, not a generic TRADIX service.
- The target repository is a dedicated MegaMarket repository, separate from `grinlife4-stack/TRADIX`.
- TRADIX should retain a concise handoff/status record and links to MegaMarket's repository, PRs, CI runs, and release evidence.
- Shared factory functions may be consumed by MegaMarket only through stable, explicit interfaces. MegaMarket must remain operable without a hard dependency on TRADIX being deployed.

## Current deviation and migration gate

As of 2026-11-17, MegaMarket code still resides under `products/megamarket/` in the public TRADIX repository. A directory boundary is not a repository/security boundary. PR #35 remains open and Draft and contains CPIIE implementation code, including the new standalone audit-ledger primitive.

This is a transitional deviation, not the desired architecture. Do not merge PR #35 into TRADIX main. Do not delete or rewrite the existing branch while the destination repository is unavailable.

Migration must preserve:
1. Full Git history where technically possible, plus a verified source archive and commit/hash manifest.
2. Exact source tree, tests, CI workflows, project metadata and dependency declarations.
3. PR #35's unmerged work and its exact tested commit history.
4. Evidence links and CI results, clearly distinguishing tested SHAs from later commits.
5. A reproducible clean checkout and passing CI in the destination repository.

After the destination repository exists and its visibility/access policy is confirmed:
- import the product history and source tree into that repository;
- recreate or port the open development PR against the new repository;
- run CI on the imported head SHA and compare file manifests/hashes;
- update TRADIX's project registry/status links;
- only then archive or remove the duplicated product subtree from TRADIX, through a separately reviewed PR.

## Security and operating rules

- Keep product credentials and private signing keys outside both source repositories.
- Keep MegaMarket/CPIIE read-only and development-only until its own readiness gates pass.
- Never treat a passing CI run as production authorization.
- No merge, repository deletion, visibility change, external integration, affiliate registration, purchase, payment, or commercial operation is implied by this architecture decision.

## Repository creation limitation

The connected GitHub actions currently available in this session can inspect and modify existing repositories and branches, but do not expose a repository-creation/import operation. Therefore the destination repository has not been created by this change. The source remains intact; migration is explicitly blocked until the destination repository is created and accessible.

## Cumulative capability-growth model

TRADIX is not merely a coordinator that distributes work to independent products. It is a continuously improving software factory whose reusable capabilities can grow through the work performed in its project portfolio.

The intended feedback loop is:

1. TRADIX provides the current set of shared, versioned factory capabilities to a selected project through explicit interfaces.
2. The project develops and validates its own product-specific solution in its own repository and environment.
3. When that work produces a capability that is genuinely reusable beyond the originating product, the capability is proposed for promotion into TRADIX.
4. The candidate is generalized, reviewed, tested independently, documented, versioned, and checked for security, licensing, operational cost, and backward compatibility.
5. Once accepted, TRADIX publishes the capability through a stable interface. Other projects may adopt it independently and at a controlled version.
6. Feedback from later projects can improve the shared capability through the same controlled process.

### Promotion boundary

- A project-specific feature, business rule, dataset, credential, or runtime workflow stays with that project.
- Only a capability with demonstrated cross-project value may be promoted to the factory.
- Promotion must not create a hard runtime dependency that prevents an independent product from operating when TRADIX is unavailable.
- Shared capabilities must have an owner, version, interface contract, tests, changelog, compatibility policy, and deprecation path.
- A capability is not considered reusable merely because it could theoretically be reused. Require at least one concrete use case outside its originating project, or a documented factory-level need, before making it core.
- Failed experiments and unproven abstractions remain in the originating project until evidence justifies promotion.

### Growth and isolation are complementary

Project independence does not mean that projects cannot contribute to the factory. It means that contribution is deliberate and controlled rather than achieved by mixing repositories or importing product code wholesale.

The target is cumulative learning without shared failure domains: projects can strengthen TRADIX, and TRADIX can accelerate later projects, while each product retains control of its own source, data, runtime, release decisions, and operational risks.
