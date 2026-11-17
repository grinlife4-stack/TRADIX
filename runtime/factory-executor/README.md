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
- product dossier, task definition, and idempotency keys

## Execution path

1. Record dossier version 1 through the runtime dossier function.
2. Create or retrieve the task using its product-scoped task key.
3. Create or retrieve the attempt using its task-scoped idempotency key. New attempts remain `queued`.
4. Acquire a task lease. PostgreSQL issues a monotonically increasing fencing token bound to the task, attempt, and worker ID; acquisition changes the attempt to `running`.
5. Renew the lease every 10 seconds against a 60-second TTL. If renewal fails, terminate the active child process and refuse to start another stage.
6. Run the product and test scripts with a 15-second timeout and a combined 1 MiB output cap per script.
7. Record test, review, and health evidence with SHA-256 digests.
8. Route every transition, evidence write, and attempt completion through a fenced database function. A stale worker is rejected before idempotency replay or mutation.
9. Mark attempt success, transition the task to `verified`, and release the lease in one database transaction.
10. On an exact retry after verification, validate the attempt, seven lifecycle events, and three evidence records before returning success.

Task, attempt, evidence, lifecycle, and lease writes use narrowly scoped SECURITY DEFINER database functions. The product runtime cannot write those tables or call the legacy unfenced write APIs directly.

## Recovery boundary

The runner intentionally refuses to resume an interrupted task from an intermediate lifecycle state. It does not yet have durable stage checkpoints or proof that re-running a product script is side-effect safe. The database supports lease takeover for the same attempt after expiry, but automatic stage-level resume is not implemented. This is a deliberate fail-closed boundary, not a recovery feature.

## Security boundary

**This is a trusted-code runner, not a sandbox.** It invokes Node.js scripts from the product directory. A script can still exercise the operating-system permissions of the runner process, including filesystem and network access available to that process. Path checks, a child-process environment allow-list, process-tree termination, output limits, and timeouts do not create an OS security boundary.

Only run code that has been reviewed and explicitly trusted. Do not use this runner for arbitrary third-party submissions or untrusted pull-request code. Before that use case, replace the execution backend with an isolated sandbox/container or remote worker with restricted filesystem, network, CPU, memory, process, and credential access. Never expose database credentials or deployment secrets to product code.

The current GitHub workflow uses a disposable PostgreSQL service and a CI-only product LOGIN. It does not connect to Neon or Production and does not deploy the product.
