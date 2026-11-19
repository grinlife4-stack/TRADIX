# TRADIX Verified Activity Record — 2026-11-19

**Record type:** Initial evidence-backed activity baseline  
**Prepared from:** GitHub repository metadata, commit metadata, pull-request descriptions, workflow definitions, and GitHub Actions run/job results available on 2026-11-19.  
**Scope:** Facts that can be tied to a repository object or CI result. This is not a claim that the entire historical conversation or every prior action has been reconstructed.

## Evidence labels

- **CONFIRMED:** Directly visible in GitHub metadata, repository content, or a completed Actions run/job.
- **PR-REPORTED:** Stated in a pull-request description; not independently re-executed as part of this record.
- **NOT VERIFIED:** No adequate evidence was available in the inspected GitHub records.
- **OUT OF SCOPE:** Requires separate operational access or evidence not present in this repository record.

## 1. Repository and active gVisor work

### 1.1 Current gVisor branch

**CONFIRMED**
- Repository: `grinlife4-stack/TRADIX`
- Branch: `integration/gvisor-backend-v0-1`
- Observed branch HEAD: `ab72e0f9185b271fdf94ce753ddf44ff899d758c`
- Commit message: `fix(ci): pass disposable database container to gVisor preflight test`
- Commit timestamp: `2026-11-19T19:11:06Z`
- Parent commit: `b433cb10516e1eb43cc91d1ff521a89ea30944fd`
- The branch exists. No pull request for this branch was created in the inspected actions recorded here.

### 1.2 CI on the observed gVisor HEAD

**CONFIRMED**
Both workflow runs below target the exact observed HEAD `ab72e0f9185b271fdf94ce753ddf44ff899d758c` and completed successfully:

| Workflow | Run ID | Result |
|---|---:|---|
| `factory-ledger-contract` | `44595714267` | success |
| `tests` | `44595714440` | success |

The `factory-ledger-contract` job completed all listed steps successfully, including:
- PostgreSQL ledger isolation, immutability, approval gates, idempotency, worker lease fencing and concurrency tests.
- CI evidence-manifest generation tests.
- gVisor runtime preflight contract unit test.
- S3-compatible upload, read-back and restore integration test against ephemeral RustFS.
- Docker sandbox image build.
- gVisor runtime availability/fail-closed validation step.
- Remote-artifact-required fail-closed check.
- Sandbox boundary probe and bounded Hello World execution.
- Exact retry and approval-preflight checks.
- Evidence-manifest build and artifact upload.

**Important interpretation:** The workflow is written to run the real gVisor integration only if `runsc` is registered in Docker. Otherwise it verifies that gVisor execution fails closed and that no task is created. The successful job alone does **not** prove that `runsc` was installed or that a workload actually ran under gVisor. The job step's successful completion is confirmed; which conditional branch executed is not independently established by the job summary inspected for this record.

The separate `tests` workflow also completed successfully on the same HEAD. The workflow step `python -m pytest -q` passed; the exact test count was not captured in this record.

### 1.3 gVisor design boundary

**CONFIRMED — repository document content**
The branch's `docs/GVISOR_SANDBOX_BACKEND_V0_1.md` describes:
- An opt-in `gvisor-sandbox` execution mode using Docker Engine with explicit `--runtime=runsc`.
- Preflight checks before database connection, task creation, or lease acquisition.
- No fallback to Docker or trusted-node mode when gVisor preflight fails.
- Existing Docker sandbox controls intended to remain in force.
- A future backend abstraction that is not yet a complete pluggable multi-provider implementation.
- A requirement for a dedicated disposable Linux worker for real gVisor runtime verification.

The document itself explicitly warns that live `runsc` worker execution has not yet been runtime-verified. A successful fail-closed CI path must not be represented as a successful live gVisor execution.

## 2. Remote evidence storage — PR #59

**CONFIRMED — PR metadata**
- PR: https://github.com/grinlife4-stack/TRADIX/pull/59
- Title: Store executor evidence remotely before database receipts
- State observed: open; not merged.
- Head branch: `integration/executor-remote-evidence-v0-1`
- Base branch: `integration/artifact-store-s3-v0-1`
- Head SHA shown in PR metadata: `25032707cc1981aefa09a8448aecbe249440fbc2`
- This is a stacked PR and its description says it must not be merged independently into `main`.

**PR-REPORTED / Actions evidence**
The PR description reports successful remote evidence upload/read-back checks using ephemeral RustFS, including Docker-sandbox and trusted-node flows, retry behavior, approval rejection, and a sandbox check for storage credentials. It explicitly says this is not Backblaze B2 production verification.

Actions run:
- https://github.com/grinlife4-stack/TRADIX/actions/runs/44594743658
- Run ID: `44594743658`
- Workflow: `factory-ledger-contract`
- Conclusion: success.
- The run metadata's `head_commit.id` is `b634ea0fdc3f390221d47cfb5ea5238184bc9a11`, while the PR metadata currently reports head SHA `25032707cc1981aefa09a8448aecbe249440fbc2`. This SHA difference is recorded rather than silently treating them as identical.

**NOT VERIFIED / OUT OF SCOPE**
- Backblaze B2 live credentials, live upload, restore, or production durability.
- Any production deployment or production database change.

## 3. Artifact Intake / Gateway — PR #45

**CONFIRMED — PR metadata**
- PR: https://github.com/grinlife4-stack/TRADIX/pull/45
- Title: Integrate artifact intake and gateway on mainline
- State observed: open; draft; not merged.
- Head branch: `integration/artifact-gateway-mainline`
- Base: `main`
- Head SHA: `1184f8bc35451dbf4ab6280a2fdf9e7f5a7e982d`

**PR-REPORTED**
The PR description reports 25 tests passed on the stated HEAD. It describes bounded file intake, ZIP checks and safe extraction, bounded PDF/DOCX/XLSX reading, authenticated project-bound API, content-addressed storage, S3-compatible read-back verification, and GitHub Contents API hash verification.

**Explicit boundaries stated in the PR**
- No NEXORA files, credentials, project data, or repository configuration changed.
- No Railway configuration, secrets, B2 credentials, or live remote storage changed.
- No production deployment or merge performed.

The 25-test count is recorded as PR-reported here; the corresponding Actions run was not independently inspected in this baseline.

## 4. Execution & Delivery Engine / Tool Catalog — PR #39

**CONFIRMED — PR metadata**
- PR: https://github.com/grinlife4-stack/TRADIX/pull/39
- Title: Propose reusable Execution & Delivery Engine
- State observed: open; draft; not merged.
- Head branch: `feat/execution-delivery-engine-architecture-2026-11-17`
- Base: `main`
- Head SHA: `c7f60da71a6054b9b810e48aea6f77840716dcbb`

**PR-REPORTED**
The PR description reports a successful Actions run (ID `44120659686`) with 17 tests passed on the exact SHA above.

The PR description explicitly limits the Tool Catalog to metadata: it does not install packages, execute arbitrary commands, probe networks, store credentials, sign, or deploy. A catalog status of `connected` must not be interpreted as proof of a real operational connection or health check.

## 5. Actions and boundaries recorded as not performed

The inspected PR descriptions and branch records state the following boundaries:
- No PR merge is recorded for PRs #39, #45, or #59 in the metadata inspected.
- No production deployment is recorded in the inspected work.
- No live Backblaze B2 verification is established.
- No live gVisor workload execution is established by the evidence summarized above.
- No Railway setting or secret change is established by this record.

These are bounded statements about the inspected records, not proof that no such event ever occurred elsewhere.

## 6. Gaps in the historical record

The following cannot be reconstructed reliably from the inspected GitHub evidence alone:
1. Every instruction, decision, correction, and approval exchanged in ChatGPT conversations.
2. Every attempted tool call, including failed calls that did not create a GitHub object or CI run.
3. Exact wall-clock times for actions that have no server-side timestamp.
4. Whether a successful conditional CI step exercised its real-runtime branch or its fail-closed branch, unless the step logs are inspected.
5. Live Railway, B2, Neon, or worker-host state unless separately queried and captured.
6. Whether a human manually changed infrastructure outside the connected GitHub records.

Do not fill these gaps by inference. Add later evidence as dated append-only entries and preserve the source URL, commit SHA, workflow run ID, or other immutable reference.

## 7. Record maintenance rule

For each future material action, record:
- timestamp (UTC);
- repository, branch, and before/after commit SHA;
- action and actor/tool;
- exact files or resources changed;
- test command or workflow run ID and conclusion;
- evidence links;
- failures and corrective actions;
- explicit statement of what was not tested or not changed.

Never label a feature "verified" merely because code exists or a design document describes it. Distinguish unit tests, integration tests, disposable infrastructure tests, and live production verification.


## 8. Append-only correction and evidence update — 2026-11-19T19:52Z

This section supersedes the earlier point-in-time observation in §1.1 and adds evidence obtained after the initial record was committed. The earlier observation is retained as historical data, not silently rewritten.

### 8.1 Current branch and pull request state

**CONFIRMED — GitHub branch and PR metadata**
- Branch: `integration/gvisor-backend-v0-1`
- Current HEAD at this update: `6e74c7d78912996a4845d5ad9d4a60e348fcb5c1`
- Parent of that HEAD: `ab72e0f9185b271fdf94ce753ddf44ff899d758c`
- The current HEAD is the audit-record commit `docs(audit): record verified TRADIX activity baseline`.
- A dedicated PR does exist: [PR #60](https://github.com/grinlife4-stack/TRADIX/pull/60), titled **Add optional fail-closed gVisor runsc execution mode**.
- PR #60 is open, draft, not merged; head is this gVisor branch and base is `integration/executor-remote-evidence-v0-1`.
- PR #60 is stacked on PR #59 and the earlier artifact, Tool Catalog, adapter, executor, ledger, and sandbox PR chain. It must not be merged independently into `main`.

### 8.2 CI on the exact current HEAD

**CONFIRMED — GitHub Actions run metadata, job summaries, and logs**

Both workflows below ran against the exact current HEAD `6e74c7d78912996a4845d5ad9d4a60e348fcb5c1` and completed successfully:

| Workflow | Run ID | Job ID | Conclusion |
|---|---:|---:|---|
| `tests` | `44602524286` | `135837428858` | success |
| `factory-ledger-contract` | `44602524390` | `135837429484` | success |

Evidence links:
- [tests run 44602524286](https://github.com/grinlife4-stack/TRADIX/actions/runs/44602524286)
- [factory-ledger-contract run 44602524390](https://github.com/grinlife4-stack/TRADIX/actions/runs/44602524390)

The Python test log explicitly reports **99 passed, 1 warning**. The warning is a Starlette/httpx TestClient deprecation warning; it did not fail the run.

The factory-ledger-contract job log confirms:
- gVisor runtime preflight unit suite: **6 passed**.
- The hosted runner reported: `runsc is not registered`.
- The runner then emitted `GvisorPreflightError: gVisor runtime 'runsc' is not registered with Docker; refusing execution`.
- The workflow verified the gVisor probe task count remained zero and printed: `PASS: no task was created and no lease was acquired`.
- The workflow continued through its remaining steps and completed successfully, including the remote-artifact-required fail-closed check, Docker sandbox boundary probe, bounded Hello World, exact retry, approval preflight, evidence-manifest generation and upload.
- The same job also exercised the disposable PostgreSQL ledger/fencing checks and ephemeral RustFS upload/read-back/restore check.

**Correct interpretation:** This is now direct evidence that the current branch passes its CI contract and that the gVisor path correctly refuses execution when `runsc` is absent, before task creation or lease acquisition. It is **not** evidence of a real workload running under gVisor. The CI runner did not have `runsc` registered, so the live integration branch was not executed.

### 8.3 PR #59 and PR #45 workflow clarification

**CONFIRMED — Actions run lookup**
- PR #59's current head is `25032707cc1981aefa09a8448aecbe249440fbc2`. Its associated recorded runs `44594766340` (`tests`) and `44594766337` (`factory-ledger-contract`) both completed successfully on that SHA.
- PR #45's head is `1184f8bc35451dbf4ab6280a2fdf9e7f5a7e982d`. Its recorded `tests` run `44587004809` completed successfully on that SHA.
- PR #45, #59, and #60 were all open, draft, and unmerged at the time of this inspection.

### 8.4 Other nearby PRs distinguished by scope

**CONFIRMED — PR metadata**
- PR #60 is the gVisor change.
- PR #62 is a separate hardened Docker sandbox execution change. It targets `integration/factory-executor-lease-runtime` and is not the gVisor PR.
- PR #61 is the lease-aware factory executor change.
- PR #58 is the worker lease-fencing change.
- PR #57 is the content-addressed S3 artifact-store change.
- PR #56 is the CI evidence-manifest change.
- PR #46 is the metadata-only Tool Catalog; PR #47 defines the adapter contract.
- These PRs form multiple stacked chains. Their open status does not mean they are integrated into `main`.

### 8.5 Remaining limits

**NOT VERIFIED / OUT OF SCOPE**
- A real `runsc`-backed product workload on a Linux worker where Docker actually registers `runsc`.
- Backblaze B2 live credentials, upload, restore, or production durability. The CI storage provider here is disposable RustFS.
- Production deployment, Railway changes, production database changes, or production secrets.
- A complete reconstruction of every ChatGPT instruction, attempted tool call, or manual action outside the inspected GitHub records.

No PR was merged and no production deployment was performed as part of this evidence update.
