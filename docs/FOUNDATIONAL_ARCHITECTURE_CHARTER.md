# TRADIX — Foundational Architecture Charter

**Document ID:** TRADIX-ARCH-CHARTER-001  
**Status:** FOUNDATIONAL / GOVERNING  
**Scope:** TRADIX and every current or future product, system, and specialist factory built within its portfolio  
**Authority:** Project owner  
**Effective date:** 2026-11-18  
**Change policy:** This charter remains in force unless the project owner explicitly approves a versioned amendment.

> **One factory. Independent products. Repeatable production.**

## 1. Foundational rule

**TRADIX builds; each product owns itself and operates independently.**

Independence is not a later feature added to the portfolio. It is the original foundational purpose that shaped TRADIX from the beginning. TRADIX exists to create and deliver complete systems while preserving each system's ownership, operational autonomy, data control, and ability to continue, change providers, or replace shared capabilities without being captured by the factory or by another project. The standards and mechanisms added over time make this founding principle measurable and enforceable; they do not change the project's original direction.

TRADIX is the complete product and software factory for the portfolio. It designs, builds, tests, packages, secures, prepares, releases, and continuously develops complete products and systems, not merely shared infrastructure. This includes the financial system X. X follows the same TRADIX production lifecycle as MegaMarket, NEXORA, and every other product.

TRADIX is not the owner or day-to-day operator of the products it creates. A product does not become an operational department of TRADIX merely because TRADIX built it, hosts its source workspace, or supplies reusable engineering capabilities.

The architecture is therefore: **one builder, multiple independently owned and operated systems.**

## 2. TRADIX responsibilities and limits

TRADIX is responsible for:
- Building complete products and systems from approved requirements, including their application logic, user interfaces, domain capabilities, and technical components.
- Building and evolving reusable engineering foundations, templates, tools, and shared technical capabilities.
- Designing, implementing, testing, securing, integrating, packaging, and preparing products for release.
- Continuing technical development of products when authorized through their product requirements and priorities.
- Providing documented, versioned interfaces through which products may use shared capabilities.
- Reusing suitable foundations to reduce duplicated engineering effort without reducing the completeness of product delivery.

TRADIX does not automatically:
- Own product roadmaps, product priorities, business models, or operational decisions.
- Own or centralize a product's records, data, assets, accounts, credentials, funds, or customer relationships.
- Run a product's daily business or become a mandatory runtime dependency.
- Override a product's authorized decisions merely because it created the software.

Any exceptional service or operational role for TRADIX must be explicitly defined, authorized, scoped, and documented. It must never be inferred from the builder relationship.

## 3. Independent product ownership

Every product or system created by TRADIX is an independent operating and ownership boundary.

Each product is responsible for its own:
- Product identity, purpose, roadmap, requirements, priorities, and acceptance decisions.
- Project records, data, files, assets, and content rights.
- Accounts, credentials, access policies, and security responsibilities.
- Financial records, budgets, revenues, expenses, and liabilities, where applicable.
- Users, customers, suppliers, contracts, and business relationships.
- Operational procedures, service delivery, monitoring, and incident decisions.
- Release authorization, lifecycle, and product-specific compliance obligations.

A product may use a dedicated workspace inside the TRADIX repository or a separate repository. Repository location does not change the product's ownership boundary. Access, data, credentials, and operational authority must remain explicitly separated.

A product may request engineering work from TRADIX. That request does not transfer product ownership or operational authority to TRADIX.

## 4. Shared foundations and reuse

Common capabilities should be engineered once and reused by multiple products through explicit, documented, versioned interfaces.

Examples may include:
- Build, test, packaging, and deployment tooling.
- Security controls and engineering standards.
- Reusable interface components and application foundations.
- Logging, observability, and technical diagnostics.
- Common schemas, adapters, and integration libraries.
- Documentation templates and release processes.

Reuse must reduce cost and complexity without merging independent product ownership.

Rules:
1. Do not rebuild an existing suitable shared capability from zero without a documented reason.
2. Do not force every product to adopt a shared capability when it does not fit its requirements.
3. Shared components must have clear interfaces, versioning, ownership, and change control.
4. Product data and secrets must not be pooled merely because products use the same technical foundation.
5. A shared development tool must not silently become a shared production dependency.
6. Products must be able to replace or stop using a shared component without surrendering their identity, records, or operational control.

## 5. X — the financial system product

**X is a TRADIX-built product/system, not a separate factory and not an exception to the TRADIX production model.**

- TRADIX defines and builds X through the same end-to-end production lifecycle used for MegaMarket, NEXORA, and other products.
- TRADIX is responsible for X's product engineering: architecture, implementation, software components, integration, testing, security engineering, packaging, and release preparation.
- X's financial domain makes its requirements, controls, data model, and compliance analysis specialized; it does not change who builds it or create a different production method.
- Once delivered, X has its own product identity, approved roadmap, records, data, accounts, decisions, and day-to-day operating boundary.
- X does not become the owner of the financial records, funds, accounts, or business operations of other products merely because it may provide financial software capabilities to them.
- Each product retains its own records and ownership boundary. Any cross-product financial records or transactions must be explicitly defined, attributable, and auditable.

Building X as software does not by itself authorize regulated activities. Banking, payment, custody, e-money, or crypto-asset services must be assessed separately for the relevant jurisdictions and performed only where legally permitted and appropriately authorized or provided by an eligible regulated partner.

## 6. Authority and decision boundaries

| Decision or responsibility | Default authority |
|---|---|
| Complete product construction and technical development, including X | TRADIX |
| Shared engineering foundations and TRADIX technical standards | TRADIX |
| Product purpose, roadmap, priorities, and acceptance | The respective product |
| Product records, data, assets, accounts, and credentials | The respective product |
| Product daily operations and commercial decisions | The respective product |
| Specialist domain roadmap and internal operation | The respective specialist system, within its authorized scope |
| Cross-product interface and shared-component changes | Defined jointly through documented change control |
| Exceptional transfer of ownership or operational authority | Project owner, explicitly documented |

No technical convenience, shared repository, common infrastructure, or historical implementation detail silently changes this authority table.

## 7. Independence without unnecessary duplication

The architecture must preserve both sides of the design:
- **Independence:** each product controls its own domain, records, decisions, and operations.
- **Reuse:** common engineering foundations are built once and reused where appropriate.

Do not confuse independence with rebuilding every technical component separately. Do not confuse reuse with centralizing product ownership.

The target is a repeatable production model in which a new product can be established quickly using proven foundations while retaining its own ownership and operating boundaries.

## 8. Product lifecycle

The standard lifecycle is:
1. The product's need, purpose, and requirements are defined by or explicitly approved for that product.
2. TRADIX designs and builds the requested software capability.
3. The work is tested, documented, and prepared for handover or controlled release.
4. The product accepts the deliverable and authorizes its use or release.
5. The product operates and evolves independently.
6. TRADIX may perform further technical development when commissioned or authorized, without acquiring product ownership.

A product may remain in a shared TRADIX repository. Physical repository separation is not mandatory; logical ownership, access control, data separation, and operational independence are mandatory.

## 9. Non-negotiable constraints

The following are architectural violations:
- Treating TRADIX as the owner or default operator of every product.
- Treating an independent product as merely a feature or department of TRADIX.
- Centralizing product records, credentials, accounts, or funds without explicit authorization and a valid legal and technical basis.
- Making a product depend on TRADIX being continuously available at runtime when that dependency is not an explicit product requirement.
- Duplicating suitable shared foundations without a reason.
- Allowing shared infrastructure to erase product-specific security, privacy, financial, or compliance boundaries.
- Assuming that building software grants authority to operate a regulated service.

## 10. Portfolio formation logic and strategic sequence

The portfolio did not originate as a collection of unrelated product ideas. It is one deliberately developing system of capabilities and products, formed by identifying a foundational need, using real projects to expose execution requirements, and creating further projects when concrete gaps are discovered.

The sequence and rationale are:

1. **TRADIX came first as a fundamental need.** The original requirement was to establish a durable product and software factory capable of designing, building, testing, integrating, securing, packaging, releasing, and developing complete products. TRADIX is not a later administrative layer inferred from the other projects; it is a foundational project in its own right and the production capability around which the portfolio is developed.
2. **MegaMarket was created after TRADIX as a large, purposeful growth target.** Its scale and real product requirements were intended to drive TRADIX toward practical, end-to-end capability. MegaMarket is both an independent product and a demanding real-world development target for the factory.
3. **NEXORA was then created as a lighter, focused execution-validation project.** During the MegaMarket path, it became clear that proceeding directly toward full-scale execution without first validating practical delivery could expose MegaMarket to serious later problems. NEXORA provides a smaller, controlled environment in which TRADIX's ability to deliver and operate a complete product can be tested before those risks become expensive.
4. **X emerged from a financial limitation discovered along that path.** The work showed that product construction and execution also require a dedicated financial system. X is therefore a distinct product built by TRADIX, not a separate factory or a change to TRADIX's production model.
5. **Completing X is intended to address financial-system needs across the portfolio.** X is not only a standalone product: its completion is also intended to provide the financial capabilities required by MegaMarket and NEXORA. This does not mean those products are automatically complete or integrated when X is complete. Each product's adapters, workflows, permissions, accounting treatment, reconciliation, audit trail, and end-to-end behavior must still be explicitly implemented and tested.
6. **Further projects may be created when real needs are discovered.** The portfolio is deliberately extensible. A new project should be created when a concrete capability gap, execution risk, or strategic requirement cannot be properly addressed by the existing projects. Project creation is driven by demonstrated need, not by a desire to increase the project count.

### Portfolio-wide interpretation

- These projects are parts of one coherent, evolving portfolio, not unrelated initiatives.
- Their missions and product boundaries remain distinct; their development rationale and contribution to the whole are connected.
- TRADIX remains the foundational builder and develops every product through the same complete production lifecycle.
- A product may solve a capability gap for another product while retaining its own identity, roadmap, records, and operating boundary.
- Completing a shared or specialist product does not silently complete the integration or acceptance work of the products that consume it.
- The sequence describes the actual discovery and development logic; it does not require projects to be executed strictly one after another. Work may overlap where priorities and dependencies allow.

This section records the portfolio owner's stated strategic logic and must guide future architecture, prioritization, project creation, and interpretation of dependencies across the portfolio.

## 11. Application to the portfolio

This charter applies to all existing and future TRADIX portfolio products and systems, including NEXORA, MegaMarket, AAECN, the trading-intelligence system, X, and future initiatives, subject to their approved scopes and any explicitly approved exception.

Existing project-specific dossiers remain authoritative for their own product requirements and status. They must be interpreted consistently with this charter. If a project-specific document conflicts with this charter on ownership or authority, the conflict must be recorded and resolved through an explicit, approved amendment; it must not silently override the foundational rule.

## 11. Change control and precedence

This is a governing architecture document, not an informal note.

- The charter is the default source of truth for builder-versus-owner boundaries across the TRADIX portfolio.
- Changes require explicit approval by the project owner and must be recorded as a versioned amendment with rationale and effective date.
- Product-specific documents may add detail but may not silently weaken or reverse the foundational ownership boundaries.
- Implementation must follow the charter. If existing code or documents conflict with it, record the discrepancy and plan a controlled correction rather than pretending the conflict does not exist.

## 12. Foundational statement

**TRADIX builds complete products and systems. Each product owns itself and operates independently. Shared foundations are built once and reused.**

**One factory. Independent products. Repeatable production.**


## 13. EXVARLI multi-project financial architecture

EXVARLI must operate as a reusable, multi-project financial-management system. It must support projects with different business domains, economic models, revenue and expense structures, currencies, jurisdictions, risk profiles, and compliance requirements through separate, versioned project financial profiles.

The governing design is:

- **One shared EXVARLI core:** common accounting, ledger, reconciliation, cash-flow, budgeting, forecasting, reporting, evidence, audit, permissions, and integration capabilities are engineered once and reused.
- **Distinct project profiles:** each project defines its own legal owner, business model, revenue streams, expense categories, currencies, accounting mappings, tax and compliance rules, accounts, integrations, controls, and financial KPIs.
- **Independent financial perimeters:** each project retains its own ownership, accounts, funds, detailed ledger, records, liabilities, permissions, and operational continuity.

EXVARLI may provide portfolio-wide dashboards and consolidated management reporting, but these are analytical views only. They must preserve source-project attribution and must never merge independent ledgers, imply that one project's funds are available to another, or create cross-project transfers without explicit authorization, lawful basis, and auditable accounting treatment.

A new project must be onboarded by creating, validating, and activating its own financial profile. It must not require rebuilding the shared financial-management foundation. Profile creation alone does not open accounts, establish provider relationships, activate payment routes, or authorize regulated activities; those require separate legal, identity, ownership, provider, and permission checks.

EXVARLI is a replaceable manager, not the owner or custodian of project assets. Each project must retain exportability, revocable access, and the ability to replace EXVARLI or operate independently without losing funds, accounts, records, or continuity.

The detailed governing specification is maintained in [EXVARLI — Multi-Project Financial Architecture](projects/EXVARLI_FINANCIAL_ARCHITECTURE.md). This section applies to every current and future portfolio project.


## 14. Mandatory portfolio-wide Bridge and independence standard

Every current and future product, project, application, service, tool, agent, factory, and technical subsystem must follow the governing [Portfolio-Wide Independence and Bridge Standard](PORTFOLIO_INDEPENDENCE_AND_BRIDGE_STANDARD.md).

TRADIX owns and maintains the shared Bridge protocol, generation foundations, documentation, versioning, and conformance tests. Each product or tool owns, secures, operates, and maintains its own dedicated Bridge. A Bridge must be independently operable without TRADIX and must not make the product's core runtime depend on TRADIX availability. Separate-process execution is the default; an in-process Bridge requires a documented justification and equivalent fault/resource isolation.

This requirement is automatic for all new work and applies to existing systems during material changes, integration, and production-readiness review. Every project dossier and relevant technical decision record must state its Bridge status and record the required independence, security, data-boundary, conformance, and recovery checks. A project that has not yet integrated with TRADIX must explicitly record that status; it must not claim Bridge conformance until the checks pass.

No project-specific file, template, workflow, or implementation may silently waive this requirement. Exceptions and amendments require explicit, documented project-owner approval.


### Multi-party interoperability requirement

A product's Bridge is not a TRADIX-only connector. It must be designed, where applicable, to communicate securely with other portfolio products, independent third-party applications and services, and other independently operated Bridges. TRADIX is one optional peer, not a mandatory hub, relay, registry, or identity provider. Peer relationships require explicit trust, authentication, scoped authorization, capability negotiation, and auditable data-sharing rules. The Bridge protocol must remain vendor-neutral, and integrations must not require all traffic to pass through TRADIX. See the governing [Portfolio-Wide Independence and Bridge Standard](PORTFOLIO_INDEPENDENCE_AND_BRIDGE_STANDARD.md).
