# Session entry point

Read [AGENTS.md](AGENTS.md) before any work. It requires reading the [Ecosystem Master Map](docs/ECOSYSTEM_MASTER_MAP.md) and the applicable project dossier/status.

For new capabilities and material architectural changes, follow the mandatory TRADIX ready-made capability audit in `AGENTS.md` before designing or implementing. Record why reuse/integration is or is not preferable to custom development.

For every Bridge-related task, apply the portfolio-wide ownership, external-connectivity, and separation rules: the designated project/tool owns its Bridge; BRIDEX is only the engineering/generation method and never owns or permanently mediates project Bridges. The owner must be able to connect the Bridge to authorized external applications and operate it after separation from the originating ecosystem. OBIS is the default external contract; TIIS is optional and limited to authorized TRADIX-internal integration. Receiving projects own their own ingress/validation boundary. Read `docs/PORTFOLIO_INDEPENDENCE_AND_BRIDGE_STANDARD.md`, `docs/BRIDEX_OWNERSHIP_AND_PORTABILITY_POLICY.md`, and `docs/BRIDGE_INSTALLATION_OPERATION_AND_EXTERNAL_INTEROPERABILITY_STANDARD.md` before changing Bridge architecture.

Do not begin implementation, move files, change project boundaries, or alter shared capabilities until the target project and scope are identified under those rules.
