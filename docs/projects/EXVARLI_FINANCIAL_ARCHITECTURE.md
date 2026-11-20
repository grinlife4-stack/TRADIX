# EXVARLI — Multi-Project Financial Architecture

**Document ID:** EXVARLI-ARCH-MULTIPROJECT-001  
**Status:** FOUNDATIONAL / GOVERNING  
**Scope:** EXVARLI and every current or future project connected to its financial-management capabilities  
**Effective date:** 2026-11-19  
**Authority:** Project owner

## 1. Foundational principle

**EXVARLI manages financial complexity centrally while preserving the complete financial, legal, operational, and data separation of every project.**

EXVARLI is designed to support projects with different business domains, economic models, revenue structures, cost structures, currencies, jurisdictions, risk profiles, and compliance obligations. Its strength is not merely handling multiple projects; it is correctly distinguishing their different financial identities and applying the right rules to each.

A new project must not require rebuilding the financial-management foundation from zero. It should be onboarded through a project-specific financial profile, configuration, approved integrations, and validation.

## 2. Three-layer architecture

### 2.1 Shared EXVARLI core

Build and maintain common capabilities once, including:

- General ledger engine and configurable chart-of-accounts framework.
- Double-entry accounting controls where applicable.
- Income, expense, asset, liability, receivable, and payable records.
- Transaction ingestion, normalization, classification, and reconciliation.
- Cash-flow, budgeting, forecasting, and financial reporting.
- Document evidence, audit trail, approvals, and change history.
- Role-based access, project isolation, permissions, and revocation.
- Currency handling, exchange-rate provenance, and valuation policies.
- Standard integration interfaces for eligible banks, payment providers, wallets, marketplaces, and accounting systems.
- Data export, migration, continuity, and manager-replacement capabilities.

Shared code and standards do not mean shared ownership, pooled funds, merged ledgers, or unrestricted access to project data.

### 2.2 Project-specific financial profile

Each project receives its own versioned profile. The profile defines at minimum:

1. Project identity, domain, legal owner, and operating entities.
2. Business and economic model.
3. Revenue streams, recognition rules, timing, and settlement sources.
4. Expense categories, cost centers, procurement, and payment obligations.
5. Functional, reporting, and settlement currencies.
6. Countries, jurisdictions, tax treatment, and compliance requirements.
7. Dedicated accounts, payment routes, wallets, and their legal account holders.
8. Project-specific chart-of-accounts mapping and accounting policies.
9. Reconciliation rules, evidence requirements, and exception handling.
10. Risk controls, approval thresholds, access roles, and segregation of duties.
11. Financial KPIs, budgets, forecasts, and reporting requirements.
12. Authorized external integrations and their status.
13. Data-retention, export, migration, and termination rules.

Profiles must be configurable and versioned. A profile change must be attributable, approved where required, and auditable.

### 2.3 Independent project financial perimeter

Every project remains a distinct financial and legal boundary:

- Its revenue, expenses, assets, liabilities, receivables, payables, and detailed ledger remain attributable to that project and its lawful owner.
- Its bank accounts, provider accounts, wallets, and funds remain under the ownership and control of the legally designated person or entity for that project.
- EXVARLI acts only within an explicit service mandate and permission scope. It does not become the owner or custodian of project funds by managing financial records.
- Project data is logically isolated. Access to one project does not imply access to another.
- Each project can export its records and evidence in usable formats and can replace EXVARLI or continue independently without losing its accounts, funds, records, or operating continuity.

## 3. Portfolio-level visibility without financial merger

EXVARLI may produce portfolio-wide dashboards, consolidated management views, cross-project cash-flow summaries, and comparative performance reports.

Such views are analytical overlays only. They must preserve project attribution and must not:

- Merge independent legal entities or accounting ledgers.
- Treat one project's cash as another project's available funds.
- Net receivables, liabilities, taxes, or obligations across projects without a lawful, documented transaction and accounting treatment.
- Transfer funds or create inter-project balances without explicit authorization, legal basis, and traceable records.
- Hide the original project, account, currency, source, or transaction behind an aggregate figure.

Every consolidated figure must be drillable to its originating project and underlying records, subject to access permissions.

## 4. Project onboarding: configure, validate, connect

Adding a new project follows a repeatable process:

1. Create a unique project identity and isolated financial workspace.
2. Define and approve its financial profile.
3. Map its economic model, revenue streams, expenses, currencies, and accounting treatment.
4. Identify legal owners, jurisdictions, tax and regulatory requirements.
5. Register its accounts and payment routes only after provider eligibility, ownership, identity, and authorization checks.
6. Configure integrations and least-privilege access.
7. Validate transaction ingestion, classification, reconciliation, reporting, and audit evidence.
8. Run controlled test cases and resolve exceptions.
9. Approve activation for the specific capabilities that passed validation.
10. Monitor the profile and version changes over the project's lifecycle.

Creating a profile does not itself open a bank account, establish a provider relationship, authorize regulated activity, or prove that a payment route is operational. Each such capability has its own verification and activation gate.

## 5. Different domains require different financial logic

EXVARLI must not force every project into one generic business model. Examples include:

- **Digital products and subscriptions:** app-store proceeds, subscriptions, advertising, refunds, chargebacks, platform fees, and delayed settlements.
- **Affiliate commerce:** commissions by program, network, merchant, and settlement source; pending, approved, reversed, rejected, payable, and paid states.
- **Manufacturing and trade:** inventory, raw materials, production costs, landed cost, receivables, supplier payables, and sales margins.
- **Real estate:** rent, deposits, maintenance, taxes, acquisition and disposal costs, asset valuation, and property-level cash flow.
- **Investment activity:** capital allocation, realized and unrealized results, exposure, risk limits, fees, and valuation evidence, subject to applicable law.

These are examples, not fixed templates. A project may combine multiple economic activities and therefore require multiple linked subprofiles while retaining one distinct project boundary.

## 6. EXVARLI responsibilities and limits

Within the mandate granted by each project, EXVARLI may provide end-to-end financial management: bookkeeping, ledger maintenance, reconciliation, settlement monitoring, receivables and payables tracking, budgeting, cash-flow management, forecasting, reporting, evidence management, and financial controls.

EXVARLI must not assume that software capability grants legal authority to provide banking, payment services, e-money, custody, exchange, investment, or crypto-asset services. Regulated activities must be separately assessed for the relevant jurisdiction and performed only where legally permitted and appropriately authorized or provided by an eligible regulated provider.

EXVARLI must not receive or hold customer or seller funds merely because it manages a project's finances. Funds-flow design must match the project's actual business model and approved provider arrangements.

## 7. Independence, portability, and replacement

EXVARLI is a replaceable financial-management system, not a lock-in mechanism.

For every project, the architecture must preserve:

- Complete project-level ledger and transaction exports.
- Supporting documents, reconciliation evidence, audit history, and profile versions.
- Documented schemas and integration interfaces.
- Clear ownership of credentials and provider accounts by the lawful account holder.
- Revocable EXVARLI permissions.
- A documented handover path to another manager or an independent operating process.
- Continuity if EXVARLI is unavailable, replaced, sold, or discontinued.

No project may lose access to its funds, accounts, records, or business operations because its EXVARLI service relationship ends.

## 8. Non-negotiable architectural rules

1. One shared EXVARLI core; separate project profiles and financial perimeters.
2. No cross-project ledger merger or unapproved pooling of funds.
3. No inference of ownership from management access.
4. No provider connection or regulated activity without the required legal, identity, ownership, and authorization checks.
5. Least-privilege access and explicit project-level authorization.
6. Every transaction and aggregate must retain source and project attribution.
7. Project profiles and their changes must be versioned and auditable.
8. Reuse shared capabilities where suitable; do not force unsuitable accounting logic onto a project.
9. Every project must remain portable and independently operable.
10. A new project is onboarded by defining and validating its profile, not by rebuilding the common foundation.

## 9. Application to the current portfolio

- **NEXORA:** its own financial profile, ledger, accounts, records, revenue streams, expenses, and compliance requirements.
- **MegaMarket:** its own financial profile and ledger, including affiliate commission lifecycle and network-level reconciliation. Under the current affiliate-referral model, customer purchase funds remain with the seller and are not collected or held by EXVARLI.
- **Future projects:** each receives a separate profile based on its actual economic model, legal structure, jurisdiction, and operating requirements.

Portfolio reporting may include all of them, but their detailed financial records and ownership remain separate.

## 10. Governing statement

**EXVARLI is one financial-management core capable of understanding and managing many different economic models. It centralizes financial management, not ownership, funds, or project identity.**

**One core. Distinct project profiles. Independent financial boundaries.**

## 11. EXVARLI as an independent TRADIX-built tool

EXVARLI is an independent financial-management tool built through the TRADIX factory lifecycle and catalogued in the TRADIX toolbox. Its presence in the TRADIX repository or toolbox is for construction history, documentation, version discovery, and maintainability; it does not make EXVARLI a TRADIX submodule or operational department.

- EXVARLI has its own identity, product/system scope, configuration, data stores, access controls, release lifecycle, and operating responsibility.
- EXVARLI must be deployable and usable without TRADIX running or being reachable.
- TRADIX may build, test, document, and deliver EXVARLI upgrades, but does not thereby gain access to EXVARLI's financial records, credentials, accounts, funds, or daily decisions.
- EXVARLI remains independently replaceable, exportable, portable, stoppable, and maintainable.
- The TRADIX toolbox catalogue may identify EXVARLI and link to its governing specification; it must not become the default runtime store for EXVARLI's financial records or secrets.

This tool relationship does not change EXVARLI's multi-project financial mandate or the independent financial perimeter of every project it serves.
