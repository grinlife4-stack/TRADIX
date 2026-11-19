# Railway Staging — Resource Identity and Access Runbook

**Document ID:** TRADIX-OPS-RAILWAY-001  
**Status:** Operational reference  
**Scope:** TRADIX Railway staging environment for the Artifact Gateway  
**Last verified:** 2026-11-20  
**Authority:** Project owner

## 1. Purpose

Prevent false access-denied diagnoses and accidental operations against the wrong Railway resource. Railway resources must be resolved by their exact IDs and verified hierarchy, not by a remembered name, a guessed identifier, or an unrelated locally linked CLI context.

A previous inspection supplied an incorrect Project ID to a Railway MCP read. Railway returned a viewer/permission error. Repeating the same read with the actual Project ID succeeded and showed the account had the required access. The original error was therefore a resource-context error, not evidence that the user's workspace role needed to be changed.

## 2. Verified resource identity

The following identifiers were read from the connected Railway account and project on 2026-11-20:

| Resource | Name | Exact ID / value |
|---|---|---|
| Account | Grin Life | `a3a2fdc3-f37e-42fe-948c-fb26923d620b` |
| Workspace | Grin Life's Projects | `00fc16a5-f5e7-4c87-9bfd-f5af938912ec` |
| Project | TRADIX Artifact Gateway Staging | `9486abe6-dd45-4458-9100-1eb9b8e5dbdb` |
| Environment | staging | `b7e611ec-67b8-4f10-997e-b6a7dfd60d11` |
| Service | artifact-gateway | `5e9cb9bf-402a-4782-a821-92cf76d26b9a` |
| Volume | artifact-data | `35fe5a11-7391-414a-85e4-a37c0cc49d27` |
| Source repository | grinlife4-stack/TRADIX | GitHub repository |

These IDs are environment-specific operational identifiers, not credentials. Never place API tokens, passwords, private keys, or variable values in this document.

## 3. Required resolution order

Before any Railway read or write:

1. Confirm the authenticated Railway account with `whoami`.
2. List workspaces and select the exact workspace by both name and ID.
3. List projects within that workspace. Select the exact project by both name and ID.
4. Resolve the environment from that project and confirm its exact ID.
5. Resolve the service from that project/environment and confirm its exact ID.
6. For a dashboard URL, parse the Project ID and Service ID from the URL; parse Environment ID from its query parameter when present. Treat URL-provided IDs as the immediate context, then verify the hierarchy.
7. Pass explicit Project, Environment, and Service IDs to MCP/CLI operations whenever supported. Do not rely on implicit or stale linked context.
8. Before a write, re-read the target identity and confirm that all three scopes (project, environment, service) match the intended operation.

Do not infer IDs from names, copy IDs from another Railway project, or substitute a workspace ID for a project ID. Names are useful labels; IDs are the selectors.

## 4. Access-denied troubleshooting

If Railway returns `viewer`, `forbidden`, `not authorized`, or a similar permission error:

1. Stop. Do not change workspace membership, roles, service permissions, or credentials yet.
2. Check the exact Project ID supplied to the failing call against the verified project identity in Section 2 and the current project listing.
3. Re-resolve the project from the selected workspace, then re-resolve its environment and service.
4. Retry the same read-only operation once with the corrected explicit IDs.
5. Only if the correctly scoped read still fails, inspect the authenticated account, workspace membership, project-level access, and connector authorization separately.
6. Report which layer actually failed. Do not describe a wrong-resource-ID error as a role deficiency.

A successful read using the corrected IDs is evidence that the earlier failure was caused by incorrect resource context. It is not a reason to modify roles.

## 5. Secret and configuration handling

- Variable names may be listed for diagnostics; values must remain redacted.
- Never echo, copy into documentation, commit, or include secret values in logs or PR descriptions.
- Do not rotate, add, delete, or modify variables as part of access troubleshooting unless separately authorized.
- Do not change Railway roles, workspace membership, service settings, volumes, domains, or deployment configuration merely to resolve an identifier mismatch.

## 6. Verified staging baseline (2026-11-20)

At the time of verification:

- Workspace account role shown in Railway: Admin.
- Project: `TRADIX Artifact Gateway Staging`.
- Environment: `staging`.
- Service: `artifact-gateway`, online.
- Latest deployment: `SUCCESS`.
- Replica count: 1 running; 0 crashed.
- Volume: `artifact-data`, 500 MB, mounted at `/data`.
- Healthcheck path: `/health`.
- Public Railway domain: `artifact-gateway-staging.up.railway.app`.
- No staged changes or pending work were reported.
- Variable values were redacted and were not inspected.
- No Railway configuration, secret, role, deployment, or service setting was changed during this verification.

This is a dated observation, not a guarantee of current runtime state. Re-check live status before relying on it for a later operation.

## 7. Change discipline

- Read-only inspection may use this runbook as its starting point, but must still verify current IDs and state.
- Any infrastructure mutation requires explicit task-specific authorization.
- Never merge a documentation or code PR without the project owner's explicit approval.
- After an authorized mutation, verify by reading the exact same resource IDs and report the observed result.
- If a project, environment, service, or volume is recreated, update this runbook only after reading back the new IDs from Railway.

## 8. Minimum report format

For each Railway operation, record:

- Account and workspace name/ID.
- Project name/ID.
- Environment name/ID.
- Service name/ID, when applicable.
- Operation type (read-only or mutation).
- Result observed from Railway.
- Whether any configuration, secret, role, or deployment changed.

Do not report an access problem until the resource identity has been validated.
