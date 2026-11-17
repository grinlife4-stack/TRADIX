# NEXORA — Sleep & Wellness App

**Project ID:** NEXORA-WELLNESS  
**Working product name:** NEXORA (subject to name, domain, trademark, and store checks)  
**Product category:** Sleep, relaxation, mindfulness, and guided meditation  
**Portfolio:** TRADIX  
**Project type:** Independently managed TRADIX portfolio project  
**Project workspace:** `projects/NEXORA/` inside the TRADIX repository  
**Direction:** Independent NEXORA roadmap, brand, product data, runtime, and release lifecycle; shared TRADIX capabilities only through explicit interfaces  
**Dossier status:** Execution-first MVP definition  
**Date:** 2026-11-17  
**Portfolio/control repository:** TRADIX  
**Project workspace:** `projects/NEXORA/` (dedicated project boundary; a separate repository is not required)  
**Product runtime:** Not deployed  
**Commercial status:** Not launched

> The purpose of NEXORA is to define and deliver a focused, usable sleep and wellness product. Product decisions must be based on user needs, technical feasibility, legal requirements, and evidence gathered for NEXORA. This dossier does not authorize paid services, production launch, or collection of unnecessary sensitive data.

## Approved brand asset

**Approved repository brand asset:** `projects/NEXORA/assets/brand/NEXORA-Official-Logo.png` (gold Tree of Life mark on deep navy, with the NEXORA wordmark). The file is committed on the NEXORA working branch and its blob SHA was verified. The logo is approved for product use. Integration into the app header, player artwork, and PWA icons remains pending; do not substitute generated artwork or temporary lettermarks.

## 1. Product decision

NEXORA will build an independent consumer application focused on sleep, relaxation, mindfulness, and guided meditation. The precise feature set must be validated against user needs and delivery constraints.

The initial product hypothesis includes the following capabilities, subject to prioritization and validation:
- Sleep stories and sleep audio.
- Relaxing music and ambient soundscapes.
- Guided meditation.
- Breathing exercises.
- Short daily mindfulness sessions.
- Favorites, recently played, and simple user progress.
- Free entry experience and a premium content membership, once payment and legal requirements are ready.

Do not copy a competitor's product structure or assume that another company's feature set, user journey, or business model is right for NEXORA. Prioritize only capabilities supported by user evidence and a realistic first-release scope.

## 2. Execution principle

**Primary success measure for the first phase: time to first working, testable release.**

- Prefer established, boring, replaceable technologies over experimental architecture.
- Build the smallest coherent product that users can install/open and use.
- Do not build AI personalization, social networks, wearables, complex analytics, or a large content-management platform in the first release.
- Do not delay the first prototype for extensive market research or speculative differentiation.
- Perform only the checks that prevent avoidable legal, security, content-rights, or platform failures.
- Keep the architecture extensible, but do not implement future scale before it is needed.

## 3. Product independence

- NEXORA is one of several independent projects managed under the TRADIX portfolio; it is not a feature or subsystem of another TRADIX product.
- NEXORA has its own product roadmap, brand, source boundaries, content rights, product data, runtime, release lifecycle, and commercial decisions.
- Its project files belong in the dedicated `projects/NEXORA/` workspace inside the TRADIX repository. A separate repository is not the default requirement.
- TRADIX provides portfolio-level governance and reusable development, testing, packaging, security, and delivery capabilities through explicit, versioned interfaces.
- NEXORA must not depend on the TRADIX control plane at runtime; shared tooling is for development and delivery, not a runtime dependency.
- NEXORA must not share product data, credentials, or business logic with MegaMarket, CPIIE, AAECN, the AI trading platform, or other projects.

## 4. First executable MVP

### Core screens
1. Home: continue listening, featured sleep/meditation content, and clear category navigation.
2. Sleep: sleep stories, ambient sounds, and sleep music.
3. Meditate: guided sessions and simple programs.
4. Breathe: guided breathing exercises with visual timing.
5. Player: play/pause, progress, favorites, sleep timer, and next item.
6. Profile/settings: language, basic preferences, privacy, and local data controls.

### Core capabilities
- Responsive PWA, designed for iPad and mobile first.
- Browse and search a small starter content catalog.
- Audio playback with tested interruption and recovery behavior.
- Sleep timer and fade-out where supported by the platform.
- Favorites and recently played.
- Basic local preferences and progress.
- A small, curated starter library sufficient to demonstrate the complete experience.
- Persian and English interface foundations; ship the first language set that can be completed reliably.

### Explicitly out of scope for first release
- AI coach or AI-generated therapeutic advice.
- Social/community features, messaging, and coaching marketplace.
- Wearable and health-platform integrations.
- Advanced personalization and recommendation engine.
- Large-scale content studio or complex CMS.
- Multi-user accounts and cross-device synchronization unless a demonstrated MVP blocker requires them.
- Medical diagnosis, treatment, or claims to cure sleep or mental-health conditions.

## 5. Content and intellectual property

- Create original product identity, interface, recordings, scripts, text, and artwork. Do not copy competitors' protected branding, content, or UI assets.
- Use original content or commercially licensed content with documented rights for intended territories and distribution channels.
- Each asset must have a record of creator/source, license, allowed use, territory, attribution requirement, expiry/revocation status, and file hash.
- Start with a small library; content volume must not block the first functioning product.
- No content may be published when its commercial rights are unclear.

## 6. Technical direction

Preferred initial implementation:
- Responsive web app / PWA.
- iPad/mobile-first touch interface.
- Simple content catalog separated from application code.
- Local storage for basic preferences and favorites; choose storage only after a short compatibility check.
- Audio files served from a replaceable storage/CDN provider when online delivery is needed.
- No mandatory AI API.
- No always-on backend unless required for a specific first-release capability.
- Keep provider-specific storage, authentication, analytics, and payment code behind replaceable interfaces.

The first technical spike must focus only on the risks that can block the MVP: installability, audio playback, background/lock-screen behavior where supported, sleep timer, offline behavior for selected assets, and iPad Safari compatibility.

## 7. Monetization

Treat monetization as an unvalidated business hypothesis, not a fixed product decision. Evaluate free access, one-time purchases, subscriptions, partnerships, or other suitable models using customer research and unit economics. Do not select or implement a payment model until pricing, demand, provider availability, cancellation, refund, tax, and consumer-law requirements are verified for the launch market.

Do not build a complex billing system before the core app works. Do not present subscription screens as functional before payment integration is real.

Track revenue and unit economics after real users exist:
- Paying subscribers and conversion.
- Monthly recurring revenue (MRR) and annual recurring revenue (ARR).
- Renewal, churn, refunds, and failed payments.
- Net revenue after store/payment fees and content costs.
- Acquisition cost and payback period when acquisition spending begins.


## 8. Privacy, safety, and legal boundaries

- Minimize personal data; basic MVP use should not require sensitive health information.
- Provide clear privacy information and a way to clear local preferences/progress.
- No medical diagnosis, treatment, or cure claims.
- NEXORA is a wellness product, not a medical device or replacement for professional care.
- Adults are the initial audience; children's use requires separate safeguarding and legal review.
- Complete applicable GDPR, consumer-rights, subscription, and content licensing checks before commercial launch.

## 9. Fast execution sequence

### Phase 1 — Working shell
- Establish the dedicated NEXORA project workspace inside the TRADIX repository at `projects/NEXORA/`.
- Implement navigation, home, categories, player shell, and responsive design.
- Load a small catalog of content metadata.
- Deliver a build that runs on iPad and mobile browsers.

### Phase 2 — Real core experience
- Integrate rights-cleared audio.
- Implement playback, sleep timer, favorites, and basic breathing sessions.
- Test interruptions, reloads, and supported offline behavior.
- Fix critical usability and playback defects.

### Phase 3 — First release candidate
- Add a small set of guided meditations and sleep content.
- Complete privacy/settings and content attribution.
- Run a short real-device test.
- Publish a controlled test build for user evaluation.

### Phase 4 — Monetization
- Add free/premium entitlement and subscription only after the core experience is stable.
- Test purchase, renewal state, cancellation, and restore flows end-to-end before taking real customers.

No phase is considered complete without a working artifact and recorded test evidence.

## 10. Acceptance criteria for first usable release

- The app opens and navigates correctly on a physical iPad and representative mobile browser.
- A user can browse and play at least one rights-cleared audio item.
- Play/pause, progress, and sleep timer work on tested devices.
- Favorites persist across normal restarts.
- Breathing exercise can be started, followed, and ended.
- No placeholder control falsely reports a completed action.
- Content rights are documented.
- Privacy information and local data clearing are available.
- Critical playback and data-loss defects are resolved.

## 11. Current status

| Item | Status |
|---|---|
| Product direction | Independent sleep and wellness PWA; English, French, and Spanish release scope |
| Product model | Not fixed; validate against user needs and market evidence |
| Execution priority | Fastest path to first usable build |
| Project workspace | `projects/NEXORA/` in the TRADIX repository; approved brand asset committed; app source package prepared but not yet imported |
| MVP prototype | NEXORA 0.5.3 source package prepared locally; 25/25 automated smoke tests pass; full app source import into this repository remains pending |
| Content assets | Three synthesized prototype ambience tracks; production-quality audio and commercial content rights remain pending |
| iPad/audio test | Physical iPad/iPhone Safari, background audio, accessibility, and HTTPS deployment remain unverified |
| Backend | Not selected; minimize for first release |
| Payments/subscriptions | Not connected |
| Production release | Not authorized |

## 12. Latest source verification — 2026-11-18

- Source baseline: `NEXORA-0.5.1.zip`; local candidate advanced to `NEXORA-0.5.3-source-package.zip`.
- Baseline SHA-256: `33cace591cd000cafdaebf7093a8a818d62e140beddf6d9c6a8815adfd4b4098`; ZIP integrity passed (22 entries); baseline automated smoke tests: 23/23 passed.
- Local `NEXORA-0.5.2` corrected stale PWA manifest metadata (`lang=en`, `dir=ltr`). Local `NEXORA-0.5.3` integrates the approved logo into header/player references and an SVG PWA icon shell, and bumps the service-worker cache to v9.
- Candidate SHA-256: `4cf1fe5163c01bb516df0ac6c4a11b361fb539208594d022dcd6da87d66c3c6e`; ZIP integrity passed (19 files); automated smoke tests: 24/24 passed.
- The 0.5.3 source package is a local test artifact only; full source import into the repository remains pending. It is not a production release.
- The archive supports English, French, and Spanish, including all 30 written guided-practice days in those languages.
- The 0.5.3 app source now references the approved shared logo in header/player and SVG PWA icon. A square iOS touch-icon derivative remains pending.
- Physical-device/browser acceptance testing and production deployment remain unverified.

## 13. Change control

This file is the TRADIX-level project index and governance record. Product source code, audio assets, content-rights records, user data, and release artifacts belong in the dedicated `projects/NEXORA/` workspace, with project-specific access and release boundaries. Keep the first release narrow and executable. Any expansion beyond the MVP requires evidence that it is necessary, not merely attractive.
