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

TRADIX is the software factory and shared engineering environment. It exists to design, build, test, package, secure, prepare, and technically support software systems.

TRADIX is not the owner or day-to-day operator of the products it creates. A product does not become an operational department of TRADIX merely because TRADIX built it, hosts its source workspace, or supplies reusable engineering capabilities.

The architecture is therefore: **one builder, multiple independently owned and operated systems.**

## 2. TRADIX responsibilities and limits

TRADIX is responsible for:
- Building and evolving reusable engineering foundations, templates, tools, and shared technical capabilities.
- Turning approved product requirements into working software.
- Technical design, implementation, testing, packaging, security engineering, and release preparation.
- Providing documented, versioned interfaces through which products may use shared capabilities.
- Reducing duplicated engineering effort across current and future products.

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

## 5. Specialist systems and factories — the X pattern

A specialist system created by TRADIX may itself operate as a specialized factory within its domain.

**X** is the designated example of this pattern for financial software:
- X is built and technically established by TRADIX.
- X belongs within the TRADIX architecture as a system created by the software factory; it is not a peer replacement for TRADIX.
- After establishment, X independently manages its own specialist roadmap, records, internal systems, and day-to-day operation within its authorized scope.
- X may build and maintain specialist financial capabilities for products through explicit interfaces and separately defined service agreements.
- X does not thereby become the owner of the financial records, funds, accounts, or business operations of the products it serves.
- Each served product retains its own financial records and ownership boundary. Consolidated reporting may exist, but it does not replace the separate records of each product.
- Inter-product transactions must be traceable and reconciled in the records of the relevant parties.

X is a specialist software and operating system, not automatically a bank, payment institution, custodian, e-money issuer, or licensed crypto-asset service provider. Regulated activities must be assessed separately for the relevant jurisdictions and performed only where legally permitted and appropriately authorized or provided by an eligible regulated partner.

The same specialist-factory pattern may be used for future domains, but its scope and authority must be documented rather than assumed.

## 6. Authority and decision boundaries

| Decision or responsibility | Default authority |
|---|---|
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

## 10. Application to the portfolio

This charter applies to all existing and future TRADIX portfolio products and systems, including NEXORA, MegaMarket, AAECN, the trading-intelligence system, X, and future initiatives, subject to their approved scopes and any explicitly approved exception.

Existing project-specific dossiers remain authoritative for their own product requirements and status. They must be interpreted consistently with this charter. If a project-specific document conflicts with this charter on ownership or authority, the conflict must be recorded and resolved through an explicit, approved amendment; it must not silently override the foundational rule.

## 11. Change control and precedence

This is a governing architecture document, not an informal note.

- The charter is the default source of truth for builder-versus-owner boundaries across the TRADIX portfolio.
- Changes require explicit approval by the project owner and must be recorded as a versioned amendment with rationale and effective date.
- Product-specific documents may add detail but may not silently weaken or reverse the foundational ownership boundaries.
- Implementation must follow the charter. If existing code or documents conflict with it, record the discrepancy and plan a controlled correction rather than pretending the conflict does not exist.

## 12. Foundational statement

**TRADIX builds. Each product owns itself and operates independently. Shared foundations are built once and reused.**

**One factory. Independent products. Repeatable production.**
