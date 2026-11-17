# Factory Executor v0.1

The executor consumes one product manifest and uses that product's dedicated PostgreSQL runtime LOGIN to run a bounded product lifecycle.

## Run

From the repository root:

```sh
npm install --prefix runtime/factory-executor
DATABASE_URL='postgresql://<product-runtime-login>@<host>/<database>?sslmode=verify-full' \
  node runtime/factory-executor/runner.mjs examples/hello-world/product.json
```

The database identity is authoritative. The manifest cannot select or override a project ID.

## Manifest contract

- `schema_version: 1`
- `execution_mode: "trusted-node"`
- product directory constrained beneath the manifest directory
- four relative `.mjs` scripts: run, test, review, health
- product dossier, task definition, a stable top-level `dossier_idempotency_key`, and a task-scoped attempt idempotency key

## Execution path

1. Record or retrieve the product dossier through the manifest's stable product-scoped `dossier_idempotency_key`; this identity is independent of `task.task_key`, so multiple tasks can reference the same unchanged dossier version.
2. Create or retrieve the task using its product-scoped task key.
3. Create or retrieve the attempt using its task-scoped idempotency key. New attempts remain `queued`.
4. Refuse execution when a task requires human approval and the exact attempt/scope has no approved `begin_implementation` decision. This preflight happens before lease acquisition, and PostgreSQL independently enforces the same exact-attempt/scope approval check inside the acquisition function.
5. Acquire a task lease. PostgreSQL issues a monotonically increasing fencing token bound to the task, attempt, and worker ID; acquisition changes the attempt to `running`.
6. Renew the lease every 10 seconds against a 60-second TTL. Each renewal query has a 5-second client timeout. If renewal fails, terminate the entire child process tree and refuse to start another stage.
7. Run the product and test scripts with a 15-second timeout and a combined 1 MiB output cap per script.
8. Record test, review, and health evidence with SHA-256 digests.
9. Route every transition, evidence write, and attempt completion through a fenced database function. A stale worker is rejected before idempotency replay or mutation.
10. Mark attempt success, transition the task to `verified`, and release the lease in one database transaction.
11. On an exact retry after verification, validate the attempt, seven lifecycle events, and three evidence records before returning success.

Task, attempt, evidence, lifecycle, and lease writes use narrowly scoped SECURITY DEFINER database functions. The product runtime cannot write those tables or call the legacy unfenced write APIs directly.

## Recovery boundary

The runner intentionally refuses to resume an interrupted task from an intermediate lifecycle state. It does not yet have durable stage checkpoints or proof that re-running a product script is side-effect safe. The database supports lease takeover for the same attempt after expiry, but automatic stage-level resume is not implemented. This is a deliberate fail-closed boundary, not a recovery feature.

## Security boundary

**This is a trusted-code runner, not a sandbox.** It invokes Node.js scripts from the product directory. A script can still exercise the operating-system permissions of the runner process, including filesystem and network access available to that process. Path checks, a child-process environment allow-list, process-tree termination, output limits, and timeouts do not create an OS security boundary.

Only run code that has been reviewed and explicitly trusted. Do not use this runner for arbitrary third-party submissions or untrusted pull-request code. Before that use case, replace the execution backend with an isolated sandbox/container or remote worker with restricted filesystem, network, CPU, memory, process, and credential access. Never expose database credentials or deployment secrets to product code.

The current GitHub workflow uses a disposable PostgreSQL service and a CI-only product LOGIN. It does not connect to Neon or Production and does not deploy the product.

## Evidence durability limitation

The v0.1 runner writes evidence files to `FACTORY_EVIDENCE_DIR` (default `/tmp/tradix-factory-executor`) and records a logical `ci://` object URI in PostgreSQL. The GitHub workflow uploads those files as a short-retention CI artifact. This is sufficient for disposable CI verification, but it is **not** a durable, cross-host artifact store and the `ci://` URI is not a public download URL. Do not treat production evidence portability or long-term recovery as implemented until a provider-neutral artifact-storage adapter, export/import procedure, and restore/hash-integrity test exist.

## Docker sandbox mode

For generated code that should not run with the executor host's permissions, use a manifest with `execution_mode: "docker-sandbox"`. Build or provision an approved sandbox image on a dedicated Linux worker, then set `FACTORY_SANDBOX_IMAGE` to the local immutable image ID returned by `docker image inspect --format='{{.Id}} <image>'`.

The image must be present before execution. The runner uses `--pull=never`, rejects mutable tags, and fails closed if Docker or the image is unavailable. It does not fall back to `trusted-node`.

The Docker backend disables networking, mounts the product directory read-only, runs as UID/GID 65532, drops Linux capabilities, enables no-new-privileges, uses a read-only root filesystem, caps CPU/memory/processes/output/time, and passes no application secrets. A fresh container is used for each lifecycle script.

See [Docker Sandbox Execution v0.1](../../docs/DOCKER_SANDBOX_EXECUTION_V0_1.md) for the full boundary and limitations. Docker containers share the host kernel; use a dedicated disposable worker and do not treat this as microVM-grade isolation.


## Optional gVisor sandbox mode

A third execution mode, `gvisor-sandbox`, is available for explicitly selected manifests on a dedicated Linux x86_64 worker. It uses Docker Engine with the fixed OCI runtime name `runsc`; it does not install or configure gVisor.

Before opening a database connection or acquiring a task lease, the runner:
1. Confirms the host is Linux x86_64.
2. Confirms Docker reports a registered `runsc` runtime.
3. Confirms the local immutable image ID exactly matches `FACTORY_SANDBOX_IMAGE`.
4. Starts the pinned image's Node binary once with `--runtime=runsc`, no network, a read-only root, no capabilities, and no-new-privileges.

Any failed check stops execution. There is no fallback to Docker's default runtime or `trusted-node`. Every product stage also uses `--runtime=runsc` and retains the Docker sandbox restrictions.

To opt in, set `execution_mode` to `gvisor-sandbox` in a reviewed product manifest and set `FACTORY_SANDBOX_IMAGE` to the exact local image ID. Do not enable this mode until a disposable Linux x86_64 worker has been provisioned and its Docker daemon has been configured by an administrator with a pinned, integrity-verified gVisor release.

The normal CI runner tests the adapter's selection and fail-closed logic; it does not claim to execute the gVisor runtime. A separate integration test on a real runsc-enabled worker is still required. See [the gVisor backend design](../../docs/GVISOR_SANDBOX_BACKEND_V0_1.md).
