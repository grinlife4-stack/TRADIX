# ECOSCAN 0.1 Contract Schemas

These JSON Schema Draft 2020-12 documents define the first draft contracts for source registration, measurements, scan coverage, and portable export manifests.

- `source-registry.schema.json`
- `measurement.schema.json`
- `coverage.schema.json`
- `export-manifest.schema.json`

**Status:** Draft contract baseline, not yet approved as a stable compatibility guarantee.

All schemas reject unknown properties. This is intentionally strict for 0.1: an incompatible field addition requires an explicit schema version change or a documented compatible extension mechanism. Implementations must validate both the schema and cross-field semantics. The measurement schema constrains kind/unit/value compatibility. Importers must additionally reject duplicate export paths, symlinks, path traversal, timestamp inversions, cross-project references, unauthorized owners/operators, out-of-scope sources, and incomparable measurement aggregates. JSON Schema validation alone cannot enforce those runtime authorization and filesystem checks.

Schema URI identifiers use a reserved documentation domain and are not fetch endpoints. Implementations should vendor the schema files rather than resolve them over the network.

The `credential_ref` field is only an opaque reference slot. JSON Schema cannot prove that a non-empty string is a reference rather than a copied secret. Runtime configuration must accept only explicitly configured reference schemes/resolvers and must reject inline secret material; the resolver must return credentials only to the authorized adapter at execution time. Provider locators must likewise be checked for embedded credentials before storage or logging.
