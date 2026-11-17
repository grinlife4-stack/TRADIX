# NEXORA — Calm-Pattern Wellness App

**Project ID:** NEXORA-WELLNESS  
**Working product name:** NEXORA (subject to name, domain, trademark, and store checks)  
**Product category:** Sleep, relaxation, mindfulness, and guided meditation  
**Reference product:** Calm  
**Direction:** User-approved; execute a close functional/business-model adaptation without copying protected material  
**Dossier status:** Execution-first MVP definition  
**Date:** 2026-11-17  
**Control record:** TRADIX repository  
**Product repository:** Not created  
**Product runtime:** Not deployed  
**Commercial status:** Not launched

> The purpose of NEXORA is to get the first usable product running quickly by following an already successful product model. This is not an open-ended search for a novel wellness concept. Reuse familiar, proven product patterns while creating original branding, code, content, and assets. This dossier does not authorize paid services, production launch, or collection of unnecessary sensitive data.

## 1. Product decision

NEXORA will build a Calm-style consumer wellness application.

The product should provide the familiar core experience:
- Sleep stories and sleep audio.
- Relaxing music and ambient soundscapes.
- Guided meditation.
- Breathing exercises.
- Short daily mindfulness sessions.
- Favorites, recently played, and simple user progress.
- Free entry experience and a premium content membership, once payment and legal requirements are ready.

Do not spend time searching for a different product category or inventing a new wellness methodology. The task is to reproduce the useful product structure and user journey with original implementation and legally usable content.

## 2. Execution principle

**Primary success measure for the first phase: time to first working, testable release.**

- Prefer established, boring, replaceable technologies over experimental architecture.
- Build the smallest coherent product that users can install/open and use.
- Do not build AI personalization, social networks, wearables, complex analytics, or a large content-management platform in the first release.
- Do not delay the first prototype for extensive market research or speculative differentiation.
- Perform only the checks that prevent avoidable legal, security, content-rights, or platform failures.
- Keep the architecture extensible, but do not implement future scale before it is needed.

## 3. Product independence

- NEXORA is an independent product, not a Tradix subsystem.
- Its source code, content rights, user data, release lifecycle, and runtime belong in its own repository and environments.
- Tradix may provide reusable development, testing, packaging, security, and delivery capabilities through explicit, versioned interfaces.
- NEXORA must not require Tradix at runtime.
- NEXORA must not share product data, credentials, or business logic with MegaMarket, CPIIE, AAECN, the AI trading platform, or XENORA AI.
- No product code or user content belongs in the Tradix control repository.

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

- Calm is a reference for product structure and user experience, not a source of assets.
- Never copy Calm's recordings, scripts, text, artwork, branding, or protected UI assets.
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

Follow the familiar Calm-style model:
- Free tier with a limited but genuinely usable starter experience.
- Premium monthly and annual membership for the broader library and programs.
- Subscription activation is deferred until pricing, payment provider, cancellation, refund, tax, and consumer-law requirements are verified for the launch market.

Do not build a complex billing system before the core app works. Do not present subscription screens as functional before payment integration is real.

Track revenue and unit economics after real users exist:
- Paying subscribers and conversion.
- Monthly recurring revenue (MRR) and annual recurring revenue (ARR).
- Renewal, churn, refunds, and failed payments.
- Net revenue after store/payment fees and content costs.
- Acquisition cost and payback period when acquisition spending begins.

Calm's revenue is evidence that the category can support a business; it is not a forecast for NEXORA.

## 8. Privacy, safety, and legal boundaries

- Minimize personal data; basic MVP use should not require sensitive health information.
- Provide clear privacy information and a way to clear local preferences/progress.
- No medical diagnosis, treatment, or cure claims.
- NEXORA is a wellness product, not a medical device or replacement for professional care.
- Adults are the initial audience; children's use requires separate safeguarding and legal review.
- Complete applicable GDPR, consumer-rights, subscription, and content licensing checks before commercial launch.

## 9. Fast execution sequence

### Phase 1 — Working shell
- Create the independent NEXORA product repository.
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
| Product direction | Approved: Calm-style sleep, relaxation, meditation app |
| Product model | Follow proven Calm structure; no new concept exploration |
| Execution priority | Fastest path to first usable build |
| Product repository | Not created |
| MVP code | Not started |
| Content assets | Not selected; rights must be verified |
| iPad/audio test | Not performed |
| Backend | Not selected; minimize for first release |
| Payments/subscriptions | Not connected |
| Production release | Not authorized |

## 12. Change control

This file is the Tradix-level project index and governance record. Product source code, audio assets, content-rights records, user data, and release artifacts belong in the separate NEXORA repository. Keep the first release narrow and executable. Any expansion beyond the MVP requires evidence that it is necessary, not merely attractive.
