# ECOSCAN Claude Code instructions

Read `AGENTS.md` in this directory and the repository root instructions first. Then read the ECOSCAN specification, implementation plan, threat model, and versioned schemas.

Preserve ECOSCAN's independent runtime boundary. Do not add TRADIX imports, network adapters, credentials, schedules, services, or deployments without explicit authorization. All source execution remains default-deny and read-only. Do not claim the filesystem adapter, export/import, or live provider integration exists until implemented and tested.
