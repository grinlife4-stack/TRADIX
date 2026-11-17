# NEXORA 0.5.3 — Local Source Package Verification

**Status:** Locally verified source package; not deployed and not yet merged.  
**Package:** `NEXORA-0.5.3-source-package.zip`  
**SHA-256:** `0064a4bc1c6b774aa300e90f1b09dda43102dbc80f603dbac2e93e4fb14b23fe`

## Changes from 0.5.2

- Replaced the temporary lettermark in the app header with the approved NEXORA logo.
- Replaced the player artwork lettermark with the same approved logo.
- Added a scalable square SVG PWA icon shell using the approved logo on a navy field.
- Updated the Service Worker cache to v9.
- Added a regression test for logo references in the header, player, favicon, and PWA manifest.
- Kept the logo as one shared asset at `projects/NEXORA/assets/brand/NEXORA-Official-Logo.png`; the app expects to run from `projects/NEXORA/app/`.

## Automated verification

- JavaScript syntax checks: PASS.
- Node smoke tests: **25/25 PASS**.
- Manifest and app-shell checks: PASS.
- Three-language UI and localized 30-day practice checks: PASS.
- Audio asset presence and playback event wiring checks: PASS.
- Brand reference regression test: PASS.

## Important boundaries

- The ZIP contains app source and synthesized prototype audio files. It does not duplicate the shared logo image already stored in the TRADIX repository.
- The app source ZIP has been prepared locally; the complete app source tree has **not yet been imported into the GitHub branch**.
- The iOS touch-icon still points to the shared portrait logo image; a square raster derivative needs preparation and visual validation.
- Physical iPad/iPhone Safari, PWA installation, offline launch, background/Lock Screen audio, accessibility, and HTTPS deployment remain unverified.
- This is not a production release.
