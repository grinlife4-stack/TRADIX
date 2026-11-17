# TRADIX Memory Gateway

Read-only HTTP access to the project's persisted memory/context snapshot.

## Runtime

Requirements: Node.js 24+ and PostgreSQL 15+.

Required environment:
- `DATABASE_URL`: PostgreSQL connection URL.
- `MEMORY_GATEWAY_API_KEY`: bearer token with at least 64 characters.
- `PORT`: optional HTTP port; defaults to `8787`.

Start:

```sh
npm start
```

Health check:

```sh
curl http://127.0.0.1:8787/health
```

Authenticated context retrieval:

```sh
curl -H "Authorization: Bearer $MEMORY_GATEWAY_API_KEY" \
  "http://127.0.0.1:8787/v1/context?project=tradix"
```

## Database TLS

TLS is required by default. Production connection URLs must use a TLS-capable PostgreSQL endpoint and must not set `sslmode=disable`.

For disposable local PostgreSQL only, the connection URL may explicitly include `?sslmode=disable`. Never carry this setting into a hosted or production environment.

## API behavior

- `GET /health`: unauthenticated liveness response; does not prove database readiness.
- `GET /v1/context?project=<project_key>`: requires `Authorization: Bearer <key>`.
- Invalid project key: HTTP 400.
- Missing/invalid bearer token: HTTP 401.
- Unknown project: HTTP 404.
- Database or query failure: HTTP 503.

The gateway is read-only. It does not create projects, missions, decisions, checkpoints, or events. Writes and approvals belong to separately authorized control-plane components.

## Migration and tests

`migrations/0001_memory_gateway.sql` is a draft migration. Apply it only to a disposable or explicitly approved isolated database. CI applies it to a temporary PostgreSQL 17 service and runs SQL plus HTTP integration tests.

This CI coverage is not a deployment approval and does not authorize applying the migration to Neon Production.
