# NEXORA 0.5.2 — Local Candidate Verification

**Status:** Local test candidate only; not a production release and not yet committed to the TRADIX repository.  
**Baseline:** `NEXORA-0.5.1.zip`  
**Candidate archive:** `NEXORA-0.5.2.zip`  
**Candidate size:** 6,643,232 bytes  
**SHA-256:** `4cf1fe5163c01bb516df0ac6c4a11b361fb539208594d022dcd6da87d66c3c6e`

## Changes

- Corrected `manifest.webmanifest` default language from stale Persian to English.
- Corrected manifest direction from RTL to LTR, matching the supported English/French/Spanish release.
- Replaced the stale Persian-only HTML description with an English description.
- Bumped the service-worker cache from v7 to v8 so installed clients refresh the changed app shell.
- Added a regression test for manifest language/direction and HTML description.

## Verification

- ZIP integrity: PASS (19 files).
- JavaScript syntax checks: PASS.
- Node smoke tests: **24/24 PASS**.
- Existing English/French/Spanish UI and 30-day written program localization checks remain passing.

## Not included / still pending

- Approved repository logo integration into header, player artwork, and PWA icons. The app package still uses the temporary lettermark.
- Source import into `projects/NEXORA/` in the TRADIX repository.
- Physical iPad/iPhone Safari testing, offline install/launch, background audio and Lock Screen behavior, accessibility review, and production HTTPS deployment.
- Professional audio catalogue and documented commercial rights for production content.

This verification covers automated source checks only. It does not establish browser acceptance, deployment, or production readiness.
