# TRADIX Product Dossier API

A small authenticated HTTP adapter for reading and appending one product's dossier versions.

## Isolation model

Run one API instance per product. Each instance receives:
- a PostgreSQL `DATABASE_URL` for that product's dedicated LOGIN;
- a `PRODUCT_DOSSIER_API_KEY` unique to that instance.

The database LOGIN must be mapped to exactly one `factory.projects` row and be a member of `factory_runtime` only. At startup, the API verifies the login's runtime membership, rejects approval/executor memberships, verifies exactly one identity mapping, and checks that RLS exposes exactly one matching product.

The service does not accept a project ID from the caller. It resolves the product from the database login. Do not run a multi-product API instance with a shared privileged database account. The database's `session_user` identity is the isolation boundary.

## Environment

Required:
- `DATABASE_URL`: PostgreSQL URL for the product-specific runtime LOGIN.
- `PRODUCT_DOSSIER_API_KEY`: unique bearer token, at least 64 characters.
- `PORT`: optional, defaults to `8788`.

Hosted PostgreSQL connections must use `sslmode=verify-full` or `verify-ca`. `sslmode=disable` is rejected unless `NODE_ENV=test`. Never place production credentials in source control or CI fixtures.

## Run

```sh
npm install
npm start
```

## Endpoints

- `GET /health`: unauthenticated liveness response. Database identity is checked before the server starts listening.
- `GET /v1/product`: authenticated product identity resolved from the database session.
- `GET /v1/dossier`: latest dossier version for this product.
- `GET /v1/dossier/versions?limit=20`: newest versions, limit 1–100.
- `POST /v1/dossier`: append a new dossier version or return the existing version for an exact idempotent retry. Requires `Idempotency-Key` and a JSON dossier body.

The POST body follows `schemas/product-dossier-v1.schema.json`. The `project_id` field is forbidden because product identity is server-bound. Product type must match the database registry. Runtime writes are restricted to `lifecycle.state = pending_approval`; a runtime cannot mark a dossier active or otherwise bypass the separate approval-controlled writer that has not yet been implemented. A reused idempotency key with different content returns HTTP 409.

## Authority and limits

- Writes call only `factory.record_product_dossier`; the runtime LOGIN has no direct table-write privilege.
- The database function enforces the pending-approval lifecycle state, so the gate cannot be bypassed by calling SQL directly or using another API adapter.
- Dossier versions are append-only and isolated by forced RLS.
- The API does not create products, change identity mappings, record human approvals, manage credentials, deploy software, or run production migrations.
- Product-specific operational data and binary artifacts remain in their own systems; the dossier is the versioned product specification and planning record.
- The API is a code artifact, not a deployed service. No deployment or Neon migration is authorized by this package.

## CI

The factory-ledger workflow installs the pinned `pg` dependency, starts this API against disposable PostgreSQL using a CI-only product LOGIN, and tests authentication, product resolution, dossier write/read, idempotent retry, and rejection of caller-supplied project identity and mismatched product type.
