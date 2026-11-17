# MegaMarket Migration Manifest

**Generated:** 2026-11-17
**Source repository:** `grinlife4-stack/TRADIX`
**Source branch:** `feat/megamarket-cpiie-readonly-core-2026-11-17`
**Exact source HEAD:** `5b80cfbaf46d9f7ae5290b8a458e12ac7b9ce034`
**PR:** [#35](https://github.com/grinlife4-stack/TRADIX/pull/35), open / Draft / unmerged
**CI evidence:** [Run #580](https://github.com/grinlife4-stack/TRADIX/actions/runs/44109059127), success on the exact source HEAD; 108 passed, 4 subtests passed.
**PR commit history inspected:** first page of up to 100 commits returned by GitHub; total history count is not yet established.

## Product-owned files at source HEAD

| Path | Git blob SHA | Bytes |
|---|---|---:|
| `products/megamarket/AFFILIATE_OPERATING_BOUNDARY_2026-11-17.md` | `19efd76afd5919d88ffc4975e28ab954ded5b332` | 5546 |
| `products/megamarket/AI_REVIEW_BRIEF.md` | `f43503f3e98749e9294d132e08b778c7e7538b56` | 15966 |
| `products/megamarket/COMPANY_POLICY_INTELLIGENCE_AND_INTERACTION_ENGINE_2026-11-17.md` | `867bdf7eff6b893ada6254cc673c4d1fdd6a7705` | 20853 |
| `products/megamarket/MARKET_REALITY_AND_ECONOMIC_VALIDATION_2026-11-17.md` | `096b0943f19ceab38cb061e5db12e8ecbb1a6864` | 31184 |
| `products/megamarket/MEGAMARKET_OPERATIONALIZATION_PLAN.md` | `6f2bf8c248511321ee51d0ceff8d296f2816e23b` | 10718 |
| `products/megamarket/PROJECT_SUMMARY_AND_DECISIONS.md` | `b4ac0260348ba9f982649bc718df93c0fbf525e2` | 37101 |
| `products/megamarket/README.md` | `37e8615dd4ca0e8182b350ea1332660d76e06e7f` | 31432 |
| `products/megamarket/UNIFIED_PRODUCT_ARCHITECTURE_AND_AFFILIATE_RULES_2026-11-17.md` | `ea147ee66918f3f99b640d98f21163fcd2ab982c` | 22011 |
| `products/megamarket/cpiie/README.md` | `17220d8372fa5fb5d71ca5a247f70927afff799e` | 11317 |
| `products/megamarket/cpiie/__init__.py` | `164b4a978b0793f9cedaec8bc6356a9a178eb476` | 32907 |
| `products/megamarket/cpiie/audit_ledger.py` | `a56ca7a5302fcdf977177c82188bafba7de66c70` | 9874 |
| `products/megamarket/cpiie/discovery.py` | `1ff2f2249b6855533d66cd13d900fe0ab3252a82` | 3563 |
| `products/megamarket/cpiie/fetch.py` | `e14cd5b5cd040ccb26adc24106100d8c3c3dfa24` | 8168 |
| `products/megamarket/cpiie/monitor.py` | `e6fa6a4bf91131ba59590a82bdb0097c2fadc15a` | 10740 |
| `products/megamarket/cpiie/reviewer_auth.py` | `5d024ea88af041147ec3121213b5ece021784679` | 5505 |
| `tests/megamarket_cpiie/test_audit_ledger.py` | `99490027ee111858f1cd86ea3f40193ff0f79c6e` | 5812 |
| `tests/megamarket_cpiie/test_discovery.py` | `e8d956e369b69ba01caf74301bafd7515ea1e6f5` | 1752 |
| `tests/megamarket_cpiie/test_fetch.py` | `d4efbe1e88a98309f6b7042c8e53ce1e7e617bcd` | 16151 |
| `tests/megamarket_cpiie/test_monitor.py` | `7354f322de40bc636d2ffa0643aa70f63b68a650` | 10021 |
| `tests/megamarket_cpiie/test_monitor_process_kill.py` | `d645a2d6befb0dabc486a3c568873548be4f26b9` | 3319 |
| `tests/megamarket_cpiie/test_monitor_recovery_concurrency.py` | `9fbe0606d0caff002cd68e907616be0f1593a2ce` | 3936 |
| `tests/megamarket_cpiie/test_registry.py` | `7a8cd946424f37d89995aece86fd14273e6febd1` | 23985 |

## Migration invariants

1. Import from the exact source HEAD above; do not copy from a stale chat excerpt or a prior CI SHA.
2. Preserve the PR commit history where possible. A simple directory copy is not equivalent to history preservation.
3. Record the full destination tree manifest and compare every migrated file's Git blob SHA or equivalent content hash.
4. Include the product documentation, CPIIE source, and CPIIE tests listed above. Separately inspect root-level dependency/configuration files and CI workflows before deciding which are product-owned versus factory-owned; do not blindly copy TRADIX-wide settings.
5. Re-run the destination repository's full CI on its imported HEAD. The source CI result does not automatically validate the destination repository.
6. Recreate the development PR in the destination repository, then update TRADIX's control-plane links.
7. Keep PR #35 open/Draft and do not delete the source subtree until destination hashes, history, clean checkout, and CI are verified.

## Current blocker

The connected GitHub toolset in this session exposes repository inspection and Git object/branch operations, but no repository creation or repository import operation. No destination repository was found in the accessible repository list or search. Therefore no destination was created and no source files were moved or deleted.

## Scope restrictions

MegaMarket/CPIIE remains development-only, manually invoked, and read-only. No retailer or affiliate account, external write, order, payment, email, deployment, or commercial workflow is authorized by this migration manifest.


## Completed source-tree and history inspection (2026-11-17)

- Recursive Git tree inspected at exact source HEAD `5b80cfbaf46d9f7ae5290b8a458e12ac7b9ce034`; GitHub returned `truncated=false`.
- The PR #35 commits endpoint was paginated: page 1 returned 100 commits, page 2 returned 3, and page 3 returned 0. **Total PR commits: 103.** The final commit is the exact source HEAD above. The first returned commit's parent is `511d09c13ed215896114e64a62bd3fcc308f9263`; the final commit's parent is `e2a2ac772f932ac6fb286fc4c3df78098651139f`. The API response gives a continuous parent chain through the listed commits.
- Source tree contains exactly 22 product-owned paths already listed above, plus the TRADIX factory files described below. Product file list was verified against the recursive tree, not inferred from the manifest.

## Root-level migration classification

| Source path | Decision | Reason |
|---|---|---|
| `products/megamarket/**` (8 docs + 6 CPIIE files) | INCLUDE | MegaMarket-owned documentation and implementation |
| `tests/megamarket_cpiie/**` (7 tests) | INCLUDE | Product-owned test suite |
| `.gitignore` | ADAPT | Generic Python ignores are reusable; inspect and retain only relevant entries |
| `.github/workflows/tests.yml` | ADAPT | Generic Python/pytest workflow is reusable, but must run against MegaMarket's own project metadata and tests |
| `pyproject.toml` | RECREATE, DO NOT COPY | Current package is named `tradix`; its metadata and pytest `testpaths = ["tests"]` describe the factory repository. Create MegaMarket-specific package metadata and explicit test configuration after deciding package layout |
| `README.md` | REWRITE | Current file identifies TRADIX as the public project entry point |
| `.github/workflows/verify-backblaze-b2.yml` | EXCLUDE | Factory storage verification workflow, unrelated to MegaMarket |
| `scripts/verify_backblaze_b2.py` | EXCLUDE | Factory storage utility |
| `src/tradix/**` | EXCLUDE | TRADIX factory implementation |
| `docs/AUTONOMOUS_SOFTWARE_FACTORY_MASTER_PLAN.md`, `docs/BACKBLAZE_B2_SETUP.md`, `docs/architecture/**` | EXCLUDE | Factory-level plans, setup, and repository-boundary/migration records |

### Dependency and test findings

- The source `pyproject.toml` declares project name `tradix`, Python `>=3.11`, no runtime dependencies, and optional `dev = ["pytest>=8.0"]` plus `storage = ["boto3>=1.34"]`.
- The CPIIE files in the product subtree use the Python standard library in the reviewed source. Do not carry the TRADIX `storage` extra or boto3 into MegaMarket without a demonstrated product requirement.
- Existing generic test workflow uses Python 3.12, installs `-e ".[dev]"`, and runs `python -m pytest -q`. Reuse only after the new MegaMarket `pyproject.toml` has been authored and a clean destination checkout proves the install/test path.
- Do not copy the Backblaze workflow or factory storage code into MegaMarket.

## Migration readiness update

The source inventory, all 103 PR commits, and root-level ownership classification are now inspected. This closes the earlier uncertainty about PR history count and root configuration scope. It does **not** perform migration: the destination repository is still absent, so no import, destination hash comparison, clean checkout, or destination CI has occurred.
