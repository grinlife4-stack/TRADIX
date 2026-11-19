# Hello World demo product

A deliberately tiny service product used to exercise TRADIX's manifest-driven factory executor.

## Product behavior

Run directly:

```sh
node examples/hello-world/index.mjs
node examples/hello-world/test.mjs
```

Expected output: `Hello from TRADIX`.

## Factory execution

The product manifest is `product.json`. The executor is invoked with a product runtime database login:

```sh
npm install --prefix runtime/factory-executor
DATABASE_URL='postgresql://<product-runtime-login>:<credential>@<host>/<database>' \
  node runtime/factory-executor/runner.mjs examples/hello-world/product.json
```

The runner:
1. Records dossier version 1 using the product runtime identity
2. Creates an idempotent task and execution attempt through restricted database functions
3. Executes the product, test, review, and health scripts as separate Node processes
4. Records SHA-256-backed evidence through the restricted runtime API
5. Advances the task through the controlled lifecycle and verifies the final database state

The database stores evidence metadata, hashes, and logical object references. CI also uploads the captured text evidence as a short-lived workflow artifact.

## Security boundary

This first executor supports only `execution_mode: trusted-node`. It starts Node scripts without a shell, limits runtime duration and captured output, confines script paths to the product directory, and does not pass the database URL to child processes. **It is not an operating-system sandbox.** Only run trusted product source code. Untrusted or third-party code requires a separate isolated execution environment before it can be admitted.

The workflow uses disposable CI PostgreSQL. It does not connect to Neon, Production, or a deployed service.
