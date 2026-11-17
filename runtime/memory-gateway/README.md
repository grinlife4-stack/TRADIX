# TRADIX Memory Gateway

Read-only HTTP access to persisted project memory. Each project has its own bearer token; the caller cannot choose a project in the URL.

## Runtime

Requirements: Node.js 24+ and PostgreSQL 15+.

Required environment:
- `DATABASE_URL`: PostgreSQL connection URL for a dedicated login that is a member of `memory_gateway_runtime` only.
- `PORT`: optional HTTP port; defaults to `8787`.

Start:

```sh
npm install --ignore-scripts --no-audit --no-fund
npm start
```

Health check:

```sh
curl http://127.0.0.1:8787/health
```

Project-scoped context retrieval:

```sh
curl -H "Authorization: Bearer $TRADIX_PROJECT_MEMORY_TOKEN" \
  "https://gateway.example/v1/context"
```

The bearer token is a high-entropy project credential. Store only its SHA-256 digest in `memory_gateway_tokens.token_hash`; never store or log the raw token. Issue a separate random token for each project, set `expires_at` where appropriate, and revoke by setting `revoked_at`. Tokens must contain 40–256 URL-safe characters.

## Database authorization

Apply `migrations/0001_memory_gateway.sql` followed by `migrations/0002_memory_gateway_project_auth.sql` only to a disposable or explicitly approved isolated database.

The migration creates:
- `memory_gateway_runtime`: non-login API role with execute permission on one token-resolving function and no direct table access.
- `memory_gateway_owner`: non-login SECURITY DEFINER owner with read-only table grants.
- forced row-level security on project-owned memory tables, scoped through a transaction-local project ID set only after a token is validated.
- `memory_gateway_tokens`: token hashes mapped to one project, with expiry and revocation.

Create a separate login for the service and grant it membership in `memory_gateway_runtime`. Do not use a superuser, schema owner, or migration login for the HTTP service. Production connection URLs must use TLS and must not include `sslmode=disable`.

## API behavior

- `GET /health`: unauthenticated liveness response; does not prove database readiness.
- `GET /v1/context`: requires a project-scoped bearer token.
- Caller-supplied `project` query parameter: rejected with HTTP 400.
- Missing, unknown, expired, or revoked token: HTTP 401.
- Unsupported methods: HTTP 405, rejected before any request body is read.
- Request bodies: not supported.
- Database/query failure: HTTP 503.

The gateway is read-only. It does not create projects, missions, decisions, checkpoints, or events. Writes and approvals belong to separately authorized control-plane components.

## Verification

CI applies both migrations to temporary PostgreSQL, verifies that the runtime login cannot read tables directly, checks project-token resolution and revocation, and runs the HTTP integration test using the restricted login. This is not deployment approval and does not authorize applying migrations to Neon Production.
