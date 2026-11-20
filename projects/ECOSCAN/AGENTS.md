# ECOSCAN project instructions

Before changing ECOSCAN, read:

1. The repository root `AGENTS.md`.
2. `docs/FOUNDATIONAL_ARCHITECTURE_CHARTER.md`.
3. `docs/tools/ECOSCAN_SPEC.md`.
4. `docs/tools/ECOSCAN_IMPLEMENTATION_PLAN.md`.
5. `docs/tools/ECOSCAN_THREAT_MODEL_AND_ACCEPTANCE_MATRIX.md`.
6. `standards/ecoscan/0.1/README.md` and all relevant schemas.

## Non-negotiable boundaries

- ECOSCAN is an independent tool. It must run without TRADIX and must not import `tradix.*`.
- The runtime core starts with Python standard library only. Optional provider dependencies belong in isolated extras.
- No source discovery, network call, provider credential, scheduled scan, background daemon, upload, write, delete, or deployment without explicit owner authorization.
- Default deny: global, project, subsystem, source, and owner/operator authorization gates must all pass before an adapter is invoked.
- Never represent missing, disabled, failed, or unauthorized sources as zero.
- Keep every project's registry, database, exports, checkpoints, and retention separate.
- Never place secret values in the registry. The current parser treats `credential_ref` as opaque but cannot prove it is a safe reference; any future resolver must enforce an allowlisted reference scheme. No credential resolver exists yet.
- Local filesystem scans require explicit allowlisted roots, no-follow behavior, mount boundaries, resource budgets, and negative tests.
- Reuse existing provider APIs/adapters only behind an independent ECOSCAN interface; never import TRADIX runtime code.
- Keep the canonical schemas under `standards/ecoscan/0.1/` synchronized byte-for-byte with packaged copies.
- Report tests, limitations, and unimplemented phases accurately. A passing unit test is not proof of live integration or production security.
