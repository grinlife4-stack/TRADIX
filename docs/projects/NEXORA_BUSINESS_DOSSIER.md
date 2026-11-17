# NEXORA — Sleep, Calm & Meditation Product Dossier

**Project ID:** NEXORA-WELLNESS  
**Working product name:** NEXORA (consumer brand subject to checks)  
**Product category:** Sleep, relaxation, mindfulness and guided meditation  
**Benchmark:** Calm (product and business-model reference only; no copying of brand, content, UI, or protected material)  
**Dossier status:** Direction approved; discovery and validation pending  
**Date:** 2026-11-17  
**Control record:** TRADIX repository  
**Product repository:** Not created yet  
**Product runtime:** Not deployed  
**Commercial status:** Not launched

> This dossier records the newly approved product direction. It does not authorize production deployment, paid services, collection of sensitive health data, external integrations, or commercial launch. NEXORA must be an original product, not a replica of Calm. The name requires domain, trademark, and app-store checks.

## 1. Product mission

Build a simple, dependable digital wellness application that helps adults establish better sleep routines, relax, and practice short guided mindfulness sessions.

The commercial reference is Calm: a focused consumer product combining sleep content, guided sessions, repeat usage, and paid membership. NEXORA must find its own audience, content identity, language strategy, and reason to be chosen.

The first release should prioritize:
- Sleep routines and sleep-focused audio.
- Short relaxation and breathing sessions.
- Guided meditation for beginners and regular users.
- A lightweight daily practice and progress history.

NEXORA is a wellness product, not a medical device, diagnostic service, psychotherapy service, or substitute for professional care.

## 2. Product boundary and independence

- NEXORA is an independent product, not a Tradix subsystem.
- Its source code, content rights, user data, product identity, release lifecycle, and runtime belong to its own repository and environments.
- Tradix may provide reusable development, testing, packaging, security, and delivery capabilities through explicit, versioned interfaces.
- NEXORA must not require Tradix at runtime.
- NEXORA must not share product data, credentials, user records, or business logic with MegaMarket, CPIIE, AAECN, the AI trading platform, or XENORA AI.
- No project-to-project integration is in scope unless separately approved.

## 3. Target users and positioning hypotheses

Initial target: adults who want practical help with sleep routines, everyday stress, and consistent short mindfulness practice.

Potential segments to validate:
- People who have difficulty winding down at night.
- Beginners who find long meditation programs difficult to sustain.
- Persian-speaking users underserved by high-quality localized wellness content.
- Users who want an offline-capable, low-friction alternative to content-heavy apps.

Do not target every wellness audience at launch. Select one primary segment using observed behavior and willingness-to-pay evidence.

## 4. MVP scope

### Included in the first validation prototype

1. Sleep section with a small curated set of original or properly licensed ambient audio.
2. Sleep timer with fade-out and reliable background playback where platform rules allow.
3. Short guided breathing exercises with clear timing and optional audio guidance.
4. A small set of guided meditation sessions, initially 3–10 minutes.
5. Simple daily check-in for sleep quality and practice completion; avoid collecting unnecessary sensitive details.
6. Favorites and recently played items.
7. Local-first preferences and progress, with clear export/delete behavior.
8. Responsive PWA interface designed for iPad and mobile first.
9. Persian and English foundations; additional languages only after validation.
10. Clear content attribution and license records for every audio/text asset.

### Deferred until validated

- Large content library and frequent content production.
- Personalized recommendations or AI-generated therapy-like guidance.
- Social features, community, coaching, and user-to-user messaging.
- Wearable, Apple Health, Google Fit, or sleep-device integrations.
- Cloud synchronization and multi-device profiles.
- Native App Store / Play Store distribution.
- Clinical assessments, diagnosis, treatment plans, or medical claims.
- Corporate wellness contracts and B2B dashboards.

## 5. Differentiation hypotheses

NEXORA should not compete by trying to outspend Calm on celebrity voices or enormous content libraries. That would be an expensive way to lose.

Test these narrower advantages:
- Strong Persian-first content and localization, with English as a second launch language only if quality is maintained.
- Offline-capable core experience and transparent data handling.
- Short, practical sessions rather than overwhelming content catalogs.
- Sleep-first onboarding and a low-friction nightly routine.
- A clear, calm interface with no manipulative streaks, shame prompts, or misleading health claims.

These are hypotheses, not proven advantages. Validate them with real users before committing to a broad build.

## 6. Technical direction — provisional

Preferred initial shape:
- Responsive web application / PWA, iPad and mobile first.
- Local-first storage for preferences and basic progress.
- Audio playback designed around browser and operating-system background-playback limitations; verify on physical iPad and target phones.
- Content catalog separated from the application code so licensed assets can be replaced without rewriting the product.
- Explicit content metadata: creator, source, license, permitted territories, attribution, expiry/revocation status, and file hash.
- No mandatory AI API, external account, or always-on backend for the first prototype.
- Optional cloud sync and subscription infrastructure only after retention and willingness-to-pay are demonstrated.

A technical spike must verify installation, audio playback, timer behavior, background playback, storage durability, offline access, and accessibility on actual target devices.

## 7. Content, safety, privacy and legal boundaries

- Use only original content or assets with documented commercial rights for the intended territories and platforms.
- Do not copy Calm scripts, recordings, branding, illustrations, UI, or other protected materials.
- No fabricated testimonials, medical endorsements, or efficacy claims.
- Do not claim to cure insomnia, anxiety, depression, or other conditions.
- Clearly distinguish general wellness content from medical advice.
- Provide an appropriate crisis/help notice and direct users in urgent distress to qualified local services; the app is not an emergency service.
- Minimize personal data. Sleep and mood entries can be sensitive; collect only what the feature needs.
- Before any cloud profile or subscription, complete privacy, security, GDPR, retention, deletion, consent, and consumer-law reviews for target markets.
- Age scope for the initial release: adults. Do not target children without a separate safeguarding and legal review.

## 8. Monetization hypotheses

Potential model:
- Free tier with a useful starter selection and basic timer/breathing tools.
- Premium monthly and annual membership for the full curated library, structured programs, and additional sleep content.
- A limited one-time purchase may be tested only if it can support ongoing content costs.

Do not introduce a subscription merely because Calm uses one. Recurring billing is justified only if NEXORA provides recurring value through new content, programs, or services.

Track:
- Annual recurring revenue (ARR) and recognized revenue separately.
- Paying subscribers and conversion rate.
- Monthly and annual plan mix.
- Renewal, churn, refund, and failed-payment rates.
- Gross margin after content licensing/production, distribution, payment fees, and support.
- Customer acquisition cost (CAC), payback period, and lifetime value (LTV).
- Weekly retention and repeated sleep-session usage.

Public Calm revenue estimates are not a forecast for NEXORA. Private-company estimates, app-store spending estimates, and audited company revenue are different measures and must never be presented as interchangeable.

## 9. Validation gates

### Gate A — Market and problem validation
- Compare Calm, Headspace, Sleep Cycle, and relevant regional products by pricing, audience, content format, retention mechanisms, and available financial evidence.
- Interview at least 15 adults in one selected segment.
- Test a clear landing-page proposition and actual willingness to pay, not just positive reactions.
- Identify one repeated use case NEXORA can serve better or more accessibly.

### Gate B — Content and prototype validation
- Produce or license a small starter library with complete rights records.
- Build a working prototype with sleep timer, audio playback, breathing, and a small guided-session catalog.
- Test on a physical iPad and representative mobile devices.
- Verify offline behavior, audio interruption/recovery, timer accuracy, accessibility, and data deletion.
- No unresolved content-rights, privacy, or critical playback defects.

### Gate C — Retention and paid pilot
- Run a controlled pilot with real users.
- Measure activation, repeat sessions, weekly retention, sleep-session completion, and qualitative feedback.
- Test a real paid offer with clear terms and refund handling.
- Do not infer product-market fit from downloads, compliments, or free signups.

### Gate D — Commercial release
- Content-rights and attribution audit.
- Privacy, security, GDPR, consumer-rights, and subscription review.
- Pricing and cancellation flows tested end-to-end.
- Support, deletion, incident, and content-removal processes ready.
- Release, monitoring, backup, and rollback procedures verified.

## 10. Acceptance criteria for the first MVP

The MVP is not accepted until:
- Users can find and play a session with minimal steps.
- Sleep timer and fade-out behave reliably on tested devices.
- Audio rights and attribution are documented for every included asset.
- Core selected content is available offline where licensing permits.
- Preferences and progress persist across normal app restarts.
- Users can clear local progress and understand what is stored.
- No fake playback, timer, offline, subscription, or health-outcome success states exist.
- iPad touch interaction, responsive layout, accessibility, and localization pass manual testing.
- No medical diagnosis, treatment, or cure claims appear in product copy.

## 11. Initial risks

| Risk | Control |
|---|---|
| Calm and Headspace dominate awareness and content scale | Focus on one underserved segment and a narrow use case |
| Content production/licensing becomes expensive | Start with a small library; track cost per usable minute and rights scope |
| Users try once and do not return | Validate repeated nightly use and retention before expanding |
| Background audio behaves differently across devices | Test on physical devices before locking architecture |
| Subscription churn is high | Prove recurring value and renewal intent before scaling |
| Wellness copy drifts into medical claims | Editorial and legal review; explicit product boundary |
| Sensitive data is collected unnecessarily | Data minimization, local-first defaults, deletion controls |
| Brand name is unavailable | Trademark, domain, and app-store checks before commitment |

## 12. Immediate next actions

1. Replace the former business-software scope with this sleep, relaxation, and meditation direction.
2. Complete a competitor and pricing benchmark, separating verified financial statements from estimates and app-store spending data.
3. Select one primary audience and one initial language-market combination.
4. Validate content rights and prepare a small original/licensed starter library.
5. Build a narrow iPad-first PWA prototype for audio, sleep timer, breathing, and local preferences.
6. Create a separate NEXORA product repository before product implementation; do not place product code or user content in the Tradix control repository.

## 13. Current status

| Item | Status |
|---|---|
| Product direction | Approved: sleep, relaxation, meditation |
| Calm benchmark | Approved as business/product reference only |
| Brand/name availability | Not checked; provisional |
| Primary audience | Not selected |
| Market demand and willingness to pay | Not validated |
| Content library and rights | Not prepared |
| MVP implementation | Not started |
| iPad/audio compatibility | Not tested |
| Product repository | Not created |
| Hosting / backend | Not selected; not required for initial prototype |
| Subscription / payments | Not selected; not connected |
| Production release | Not authorized |

## 14. Change control

This dossier is the Tradix-level project index and governance record. Product implementation, detailed technical specifications, audio assets, content rights records, user data, and release artifacts belong in the separate NEXORA repository once created. Update statuses only with verifiable evidence. Do not mark a gate complete based on plans, mockups, or market estimates.
