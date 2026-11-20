# NEXORA Logo: Ownership and TRADIX Development Workspace

**Decision:** 2026-11-19  
**Scope:** NEXORA brand master and TRADIX development copy

## 1. Ownership and source of truth

NEXORA owns its name, identity, and official logo. The independent repository `grinlife4-stack/NEXORA` is the sole authoritative location for the master artwork:

- Canonical path: `projects/NEXORA/assets/brand/NEXORA-Official-Logo.png`
- Canonical Git blob SHA: `7f2a39590db755077b0a903cf93056121e0ef1b5`

The exact PNG historically committed in TRADIX through PR #40 is preserved byte-for-byte in the NEXORA repository. The NEXORA copy is the ownership and source-of-truth copy.

## 2. TRADIX development location

TRADIX may retain the corresponding file at:

`projects/NEXORA/assets/brand/NEXORA-Official-Logo.png`

Its role is limited to NEXORA development activities performed with TRADIX capabilities: design, implementation, testing, build, packaging, and delivery. This is a working copy, not an independent master.

TRADIX does not own the NEXORA brand or artwork. The presence of a NEXORA development workspace inside TRADIX does not make NEXORA a TRADIX subsystem and does not create a parent-child relationship.

## 3. Runtime and release boundary

- NEXORA app source and releases must use the logo from NEXORA-owned project assets.
- NEXORA runtime must not load the logo from a TRADIX URL or require TRADIX to be available.
- TRADIX may use its local working copy during development and packaging.
- Any delivery artifact must include the required asset locally within the NEXORA artifact.

## 4. Copy integrity and updates

1. NEXORA's canonical master is authoritative.
2. Refresh the TRADIX working copy from the NEXORA master.
3. Record the canonical Git blob SHA and verify byte identity after copying.
4. If a mismatch is found, stop and reconcile it; do not silently select the TRADIX version.
5. Only the NEXORA owner may approve a change to the artwork.
6. Platform derivatives may change technical dimensions, file format, or transparent padding only; they must not redraw, crop, recolor, or alter the composition.

## 5. Reconciliation result

The source package's JPEG and PNG were decoded and compared: both are 784×1168 RGB images with zero per-channel pixel difference. The JPEG was therefore redundant and has been removed. The corrected 0.5.4 source archive contains neither a second PNG master nor a JPEG copy; the only master is stored in the independent NEXORA repository.

The TRADIX working copy was synchronized from the NEXORA canonical file. Its Git blob SHA now matches the NEXORA master exactly: `7f2a39590db755077b0a903cf93056121e0ef1b5`. Platform icons remain technical derivatives, not additional master files.

## 6. What this decision does not do

It does not merge the projects, transfer NEXORA ownership to TRADIX, authorize TRADIX as a runtime dependency, or give TRADIX independent authority to change NEXORA's artwork.
