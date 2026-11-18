# NEXORA — Financial Infrastructure Decision Record

**Project:** NEXORA  
**Portfolio / control system:** TRADIX  
**Date:** 2026-11-18  
**Status:** PAUSED — no implementation authorized  
**Decision owner:** Project owner

## 1. Decision

The proposed standalone financial-infrastructure / digital-bank initiative is paused.

The immediate strategic priority is development of the TRADIX network. Building a bank, payment institution, EMI, CASP, crypto gateway, or a separate financial-services business is not part of the current execution scope and must not divert resources from TRADIX.

This is a pause, not approval to begin licensing, company formation, provider onboarding, or financial product development.

## 2. What was evaluated

The discussion considered a shared financial layer intended to support NEXORA and potentially MegaMarket, including:

- A multi-project, multi-currency internal ledger.
- Income and expense separation by project.
- Transaction reconciliation and audit records.
- Bank/payment-provider connectivity.
- A possible EUR-to-crypto conversion route and a dedicated wallet for NEXORA income.
- Potential marketplace payment orchestration for MegaMarket.

The proposed architecture distinguished software infrastructure from regulated financial services. Software for internal accounting and reconciliation is not itself a bank. Holding third-party funds, executing regulated payment services, issuing e-money, or providing crypto-asset services can require authorization or a regulated provider, depending on jurisdiction and actual fund flows.

## 3. Explicitly deferred

Until the pause is lifted, do not:

- Establish or market a NEXORA-branded bank or financial institution.
- Apply for banking, payment, e-money, or crypto-asset authorization.
- Build custody, customer wallets, pooled balances, split payouts, or money-transfer functions.
- Onboard Mangopay, Adyen, Stripe Connect, Kraken, Bitpanda, or another financial provider for this initiative.
- Create a financial-services entity or incur legal/compliance/provider costs for this proposal.
- Treat Gmail, a project name, or a self-custody wallet as a substitute for a verified legal account holder or regulated payment route.

The earlier provider names were evaluation candidates only, not selected partners or confirmed eligible services.

## 4. NEXORA app revenue: separate operational fact

This pause does not change the payment rules of third-party app platforms. For example, AdMob does not pay directly to a self-custody crypto-wallet address. Any future AdMob setup must use a payment method supported for the actual publisher account and country, with matching payee and account-holder details. A later conversion to crypto, if lawful and supported, would be a separate transaction through an eligible provider.

No bank account, exchange account, or wallet has been selected or connected by this decision record.

## 5. MegaMarket boundary

MegaMarket's eventual payment architecture must be decided from its real funds flow:

- If it only refers customers to merchants and receives affiliate commissions, it generally does not need to collect the customer's purchase funds.
- If it receives customer money and distributes proceeds to merchants or affiliates, that is a materially different marketplace-payment model and requires a separate legal and provider assessment.

No payment-collection or split-payout model is approved here.

## 6. Conditions for reopening

Reconsider this file only when the TRADIX network's architecture and operating model establish a concrete need for financial functionality.

Before any implementation decision, document:

1. The exact use case and whether funds belong to the project or to third parties.
2. The countries of establishment, operation, users, and payment flows.
3. The legal entity and beneficial owner that will contract with providers.
4. Whether the solution can remain internal software using licensed external providers.
5. The cost, licensing, compliance, and operational burden compared with the actual benefit.

The default design principle, if the matter is reopened, is to keep internal software separate from regulated custody and payment execution. Do not assume a standalone bank is necessary.

## 7. Current disposition

| Workstream | Status |
|---|---|
| Standalone financial institution / bank concept | PAUSED |
| Financial software core | NOT STARTED |
| Payment-provider selection | NOT SELECTED |
| Crypto conversion route | DEFERRED |
| Dedicated NEXORA wallet | NOT CREATED / NOT CONNECTED |
| AdMob payment setup | NOT PART OF THIS DECISION; follow platform-supported payout requirements when needed |
| MegaMarket marketplace payments | UNDECIDED; requires its actual funds-flow model |
| Strategic priority | TRADIX network development |

**Final rule:** No work on this financial-infrastructure proposal should proceed unless the project owner explicitly reopens it. TRADIX network development remains the active priority.
