# TRADIX gVisor Worker Setup v0.1

**Purpose:** prepare one disposable Linux x86_64 worker for the opt-in `gvisor-sandbox` backend.
**Status:** procedure only; no worker has been provisioned or runtime-verified.

## Constraints

- Use an isolated, disposable Linux x86_64 machine. Do not use a developer workstation containing credentials or personal data.
- Linux kernel 5.6 or newer; Docker Engine installed and managed by the host administrator.
- Do not expose the Docker socket to product code. Do not run untrusted workloads on the Docker host outside the gVisor executor.
- Do not install on Windows or iPad. WSL is not accepted as the first security-validation host.
- No Railway deployment or paid resource is required for this procedure.
- Initial worker must have outbound network disabled for task containers; host management access is separate and restricted.
- Never place Neon, GitHub, cloud, wallet, or other application credentials on the worker.

## 1. Host inspection

Copy the repository script to the Linux worker and run:

```bash
bash tests/gvisor_worker_preflight.sh
```

The default mode is read-only. It checks Linux, x86_64, kernel version, Docker daemon reachability, `runsc` presence, and Docker runtime registration.

## 2. Install gVisor as a host administrator

Use the official signed gVisor APT repository on a supported Debian/Ubuntu x86_64 host. The official installation guide is authoritative:
https://gvisor.dev/docs/user_guide/install/

Install prerequisites and configure the official signing key/repository as documented there. Then:

```bash
sudo apt-get update
apt-cache madison runsc
```

Select and record one exact package version from the repository metadata. Do not use an unpinned `latest` binary download. Install the selected version explicitly:

```bash
sudo apt-get install runsc=<EXACT_VERSION_FROM_APT_CACHE>
sudo apt-mark hold runsc
runsc --version
```

Record the exact package version, source repository, package architecture, and `runsc --version` output in the worker inventory. Package installation must be performed by the host administrator, not by a TRADIX task. If the exact package version cannot be resolved or signature verification fails, STOP.

The official gVisor package install may configure Docker automatically. If it does not, follow the official Docker quick start and register `runsc` using `sudo runsc install`, then restart Docker during a planned maintenance window:
https://gvisor.dev/docs/user_guide/quick_start/docker/

Do not overwrite an existing Docker daemon configuration blindly. Back it up and review the merged configuration before any change.

## 3. Verify actual runtime execution

After installation and Docker registration:

```bash
bash tests/gvisor_worker_preflight.sh --probe
```

This runs a disposable `hello-world` container with `--runtime=runsc` and `--network=none`. It is a smoke test only, not the TRADIX security acceptance suite.

## 4. Connect to TRADIX only after host checks

Do not register this host as a production worker yet. First provide the preflight output and exact runtime/package version. Then run the repository integration test:

```bash
bash tests/gvisor_runtime_integration.sh
```

The integration test must pass on this disposable worker. Capture its output as evidence. Any failed preflight, unsupported security control, image digest mismatch, or runtime ambiguity blocks worker registration. There is no fallback to `docker-sandbox` or `trusted-node`.

## 5. Operational safeguards

- Keep the worker dedicated to sandbox workloads; do not co-host databases, secrets, or production services.
- Restrict SSH/management access and patch the host on a controlled schedule.
- Keep Docker daemon and `runsc` versions recorded and pinned; upgrades require repeating the acceptance suite.
- Worker loss must not corrupt task state; task/event truth remains in the factory ledger.
- gVisor is defense-in-depth, not a VM and not an absolute isolation guarantee. Consider Firecracker/microVM for higher-risk hostile workloads.

## Acceptance status

| Gate | Required evidence | Initial status |
|---|---|---|
| Linux x86_64 + kernel >= 5.6 | preflight output | NOT_RUN |
| Docker daemon + runsc registered | preflight output | NOT_RUN |
| Actual runsc hello-world | probe output | NOT_RUN |
| TRADIX gVisor integration | integration script output | NOT_RUN |
| Independent security review | review record | NOT_RUN |

## Official references

- Installation: https://gvisor.dev/docs/user_guide/install/
- Docker quick start: https://gvisor.dev/docs/user_guide/quick_start/docker/
- Release policy: https://gvisor.dev/release/
