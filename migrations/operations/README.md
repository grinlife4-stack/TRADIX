# Product onboarding operations (draft)

This is the administrative path for registering a new TRADIX product. It is deliberately separate from every product runtime API.

## Authority split

1. A trusted database administrator with `CREATEROLE` creates the product runtime LOGIN and approval LOGIN, and grants each exactly one authority group.
2. The same administrator creates or reuses one factory-wide provisioning LOGIN. It receives `SET TRUE, INHERIT FALSE` membership in `factory_identity_admin`; it does not inherit that authority and is not a product runtime.
3. The provisioner connects separately and runs `register_product.sql`. That transaction creates the product registry row and maps exactly one runtime identity and one approval identity.
4. The product runtime uses its own runtime LOGIN and its own Product Dossier API instance to create dossier version 1 through `factory.record_product_dossier`.

The runtime API cannot create roles, products, identity mappings, or approvals. Product identities are never shared between products.

## Preconditions

- The reviewed factory role bootstrap and draft ledger migration must already exist in the target database.
- This runbook is not permission to apply either migration to Neon or Production.
- Use an isolated test database first. Do not use Production for onboarding tests.
- Confirm that the product key is unique and follows the registry constraint: lowercase letters, digits, and hyphens, beginning with a letter.
- A Git repository is optional. Set `repository_full_name` to an empty string for physical products or services without a repository.

## Step 1: create the identities

Run `create_product_logins.sql` as a trusted administrator with `CREATEROLE`, supplying non-secret role names:

- `runtime_login`: a new, product-specific LOGIN.
- `approval_login`: a different, product-specific LOGIN.
- `provisioner_login`: the trusted factory-wide provisioning LOGIN (create once, then reuse).

The script creates roles without passwords. Set credentials out-of-band using your approved secret manager. If using psql interactively, use its `\\password role_name` command; never put passwords in SQL files, command arguments, chat, Git, or shell history.

The runtime role must inherit only `factory_runtime`; the approval role must inherit only `factory_approval_authority`. The provisioner must be NOINHERIT and receive only SET-only membership in `factory_identity_admin`.

## Step 2: register the product

Connect as the provisioner LOGIN and run the registration script with psql variables, for example:

```sh
psql "$FACTORY_PROVISIONER_DATABASE_URL" \
  -X -v ON_ERROR_STOP=1 \
  -v project_key='sample-product' \
  -v display_name='Sample Product' \
  -v product_type='service' \
  -v repository_full_name='' \
  -v runtime_login='factory_rt_sample_product' \
  -v approval_login='factory_approver_sample_product' \
  -f migrations/operations/register_product.sql
```

The connection string must come from a secure environment/secret store, not from a committed file. The registration transaction is atomic: the project row and both identity mappings either commit together or roll back together.

Database constraints enforce:
- unique project key;
- each LOGIN maps to only one project;
- exactly one runtime and one approval identity kind per project;
- identity kind must match the LOGIN's granted authority group;
- runtime, approval, identity-admin, and executor-owner authorities cannot be combined.

## Step 3: create dossier version 1

Configure a separate Product Dossier API instance using the product's runtime LOGIN and a unique API key. Submit a dossier that satisfies `schemas/product-dossier-v1.schema.json` with an `Idempotency-Key`. The API derives the project identity from PostgreSQL `session_user`; callers must not send a `project_id`.

Do not reuse the provisioner or approval credentials in the runtime API.

## What this does not do

- It does not execute migrations, connect to Neon, deploy services, create API keys, or set passwords.
- It does not grant a product runtime the ability to create products or alter identity mappings.
- It does not authorize Production operations.
