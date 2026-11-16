# Hello World demo product

A deliberately tiny product used to exercise the TRADIX factory path end to end.

## Product behavior

Run:

```sh
node examples/hello-world/index.mjs
```

Expected output:

```text
Hello from TRADIX
```

Verify:

```sh
node examples/hello-world/test.mjs
```

## Factory execution

The PostgreSQL integration workflow performs the following in a disposable database:

1. Registers this demo as a separate service product using the restricted provisioner.
2. Creates its independent runtime and approval LOGIN mappings.
3. Records dossier version 1 through the product runtime identity.
4. Creates one low-risk task and one execution attempt.
5. Runs the program and checks its exact output.
6. Stores SHA-256-backed test, review, and health evidence.
7. Moves the task through planned, implementing, testing, review, candidate, deployed_test, and verified using the controlled transition function.

This is an automated integration demonstration, not a deployed service. The database is disposable CI PostgreSQL; no Neon or Production database is touched.
