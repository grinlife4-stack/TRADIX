# NEXORA Business — Project Dossier

**Project ID:** NEXORA-BUSINESS  
**Working product name:** NEXORA Business  
**Dossier status:** Initial definition / discovery  
**Date:** 2026-11-17  
**Control record:** TRADIX repository  
**Product repository:** Not created yet  
**Product runtime:** Not deployed  
**Commercial status:** Not launched

> This dossier records the product boundary and first validation plan. It does not authorize deployment, paid services, external integrations, customer-data collection, or commercial launch. The name NEXORA is provisional until domain, app-store, and trademark checks are completed.

## 1. Product mission

Build a small, dependable business operations application for micro and small businesses. The first release should solve a narrow set of recurring administrative tasks without requiring a cloud account, paid AI API, bank integration, marketplace integration, or always-on server.

The product must be genuinely usable on iPad and mobile browsers, with an installable Progressive Web App (PWA) experience where supported.

## 2. Product boundary and independence

- NEXORA Business is an independent product, not a Tradix subsystem.
- Its source code, data model, release lifecycle, product identity, and future runtime belong to its own repository and environments.
- Tradix may provide reusable development, testing, packaging, security, and delivery capabilities through explicit, versioned interfaces.
- NEXORA must not require Tradix at runtime.
- NEXORA must not share product data, credentials, customer records, or business logic with MegaMarket, CPIIE, AAECN, the AI trading platform, or XENORA AI.
- No project-to-project integration is in scope unless separately approved.

## 3. Target users

Initial target: owner-operated and small businesses that prepare quotes, calculate prices, track basic stock, and follow order status.

Candidate segments for validation:
- Small manufacturers and workshops
- Wholesalers and distributors
- Contractors and service businesses

Do not target all business types at once. Select one segment after customer interviews and paid-pilot evidence.

## 4. MVP scope

### Included in the first offline-capable release

1. Product and service catalogue with units and editable cost inputs.
2. Cost and margin calculator with explicit formulas and editable assumptions.
3. Quote / pro-forma invoice creation, numbering, preview, and PDF export.
4. Basic customer records stored locally.
5. Basic order/quote status tracking.
6. Local persistence with explicit export, backup, and restore.
7. Responsive interface suitable for iPad and mobile.
8. Persian, English, and German localization foundations; launch languages are subject to validation.

### Deferred until validated

- Multi-user collaboration and synchronization
- Cloud backup and cross-device sync
- Online payments, subscriptions, and licensing enforcement
- Bank, accounting, tax-authority, e-invoice, or marketplace integrations
- Automated email, SMS, WhatsApp, or messaging delivery
- AI features and paid model APIs
- Advanced inventory, purchasing, warehouse, and accounting workflows
- Native App Store / Play Store distribution

## 5. Core product principles

- Offline-first for core workflows.
- No mandatory external API for core calculations or document creation.
- User owns and can export their data in documented formats.
- No silent data loss: backup and restore must be tested.
- Transparent formulas; no hidden margin, tax, or rounding behavior.
- Secure local storage appropriate to the chosen platform; explain device-loss and browser-storage limitations.
- Accessibility, localization, and usable touch targets are baseline requirements.
- External providers must be replaceable; avoid unnecessary vendor lock-in.
- Fail clearly when a capability is unavailable; never simulate a successful export, backup, payment, or sync.

## 6. Technical direction — provisional

Preferred initial shape:
- Responsive web application / PWA.
- Local-first persistence using browser-supported storage, selected after a small iPad compatibility spike.
- Deterministic calculation module with unit-tested formulas.
- PDF generation performed locally where technically reliable.
- Export/import using documented JSON and CSV formats where appropriate.
- No backend required for the first single-device MVP.

A technical spike must verify iPad Safari storage behavior, installability, PDF generation, backup/restore, and data durability before committing to the final implementation stack.

## 7. Monetization hypotheses

Potential models to test, not decisions:
- One-time purchase for a single-device edition.
- Paid Pro upgrade for advanced templates, exports, and expanded records.
- Optional subscription only if a real recurring service is later introduced, such as secure sync, multi-user access, or hosted backup.

Do not impose a subscription merely to create recurring revenue. The product must deliver recurring value if recurring billing is used. Payment provider, tax handling, refund policy, consumer rights, and applicable EU/German requirements must be reviewed before accepting money.

## 8. Validation gates

### Gate A — Problem validation
- Interview at least 15 prospective users in one selected segment.
- Observe their current quote/cost/order workflow.
- Identify one costly or frequent pain point.
- Record willingness to pay separately from positive feedback.

### Gate B — Prototype validation
- Deliver a working prototype with real calculations and PDF output.
- Test on a physical iPad and at least one desktop browser.
- Verify persistence after app closure/reopen.
- Verify export, backup, and restore using real test data.
- No unresolved data-loss or calculation correctness defect.

### Gate C — Paid pilot
- Seek at least 3 independent paying pilot customers.
- Record actual payment, active use, support burden, and repeated usage.
- Do not infer product-market fit from downloads, compliments, or free signups.

### Gate D — Commercial release
- Security and privacy review.
- Terms, privacy notice, data-retention and deletion behavior.
- Pricing, refunds, taxes, and applicable legal review.
- Verified hosting/distribution plan if online services are introduced.
- Release checklist and rollback/recovery procedure.

## 9. Acceptance criteria for MVP

The MVP is not accepted until:
- Cost, markup, margin, discount, and rounding formulas have documented definitions and tests.
- A user can create, save, reopen, edit, and export a quote.
- Local records survive normal app closure and device restart.
- Backup can be exported and restored into a clean app installation.
- The app clearly communicates that local-only data is not automatically synchronized or protected from device loss.
- Core workflows function without network access after the app is installed/cached.
- No fake payment, sync, backup, or notification success states exist.
- iPad touch interaction and responsive layout pass manual testing.

## 10. Explicit non-goals and restrictions

- No accounting or tax-compliance claims in the MVP.
- No claim that generated quotes are legally compliant invoices in every jurisdiction.
- No bank access or payment initiation.
- No scraping or unauthorized collection of third-party data.
- No mandatory AI dependency.
- No automatic emails/messages or external side effects without explicit user action.
- No production deployment, paid service, or commercial account setup without separate approval.

## 11. Initial risks

| Risk | Control |
|---|---|
| Product scope expands into full ERP | Keep MVP to quotes, cost calculation, basic customer/order tracking |
| Local browser storage is cleared or device is lost | Visible backup/export and tested restore; explain limitations |
| iPad browser differences | Early physical-device compatibility spike |
| Incorrect cost/margin formulas | Documented formulas, edge-case tests, user-verifiable breakdown |
| Customers expect tax/accounting compliance | Clear product boundary and jurisdiction-specific review |
| Subscription has no recurring value | Validate one-time purchase first; subscription only for ongoing service |
| Product name unavailable | Domain, trademark, and app-store checks before brand commitment |

## 12. Immediate next actions

1. Validate the provisional name NEXORA in relevant domain, trademark, and app-store databases.
2. Select one initial customer segment.
3. Conduct problem interviews and capture current workflow evidence.
4. Build a narrow iPad PWA technical spike for local persistence, PDF, and backup/restore.
5. Freeze MVP requirements only after Gates A and the technical spike are complete.
6. Create a separate NEXORA product repository before product implementation; do not place product code in the Tradix control repository.

## 13. Current status

| Item | Status |
|---|---|
| Product dossier | Recorded in Tradix on an unmerged documentation branch |
| Product name | Provisional; availability not checked |
| Customer segment | Not selected |
| Customer demand | Not validated |
| MVP implementation | Not started |
| iPad compatibility | Not tested |
| Product repository | Not created |
| Hosting / backend | Not selected; not needed for initial offline MVP |
| Payment / subscription | Not selected; not connected |
| Production release | Not authorized |

## 14. Change control

Keep this dossier as the Tradix-level project index and governance record. Product implementation, detailed technical specifications, customer data, and release artifacts belong in the separate NEXORA repository once created. Update statuses only with verifiable evidence. Do not mark a gate complete based on plans or generated mockups.
