# gVisor Sandbox Backend Design v0.1

**Status:** Design proposal only; not implemented or runtime-verified  
**Scope:** Add an optional stronger Linux execution backend without changing the existing Docker backend  
**Parent baseline:** Docker sandbox hardening branch, commit `12e67603760f09ac525e39bd52d5afede2a8e6db`

## 1. Decision

Add a future opt-in execution mode named `gvisor-sandbox`, implemented through the OCI runtime `runsc`.

For the first integration, keep Docker Engine as the image/container lifecycle interface and explicitly select the pre-registered `runsc` runtime with `docker run --runtime=runsc`. This is a distinct workload-isolation runtime, not a second Docker daemon and not a claim that Docker itself has been removed.

This is the lowest-complexity path because TRADIX already builds immutable OCI images and manages one-shot containers through Docker. It avoids introducing a second image store, containerd socket, OCI bundle lifecycle, and cleanup implementation before those are justified.

The existing `docker-sandbox` path must remain byte-for-byte untouched by the first gVisor implementation. The new mode is additive and opt-in.

## 2. What gVisor changes

gVisor's `runsc` is an OCI runtime. Its Sentry implements a Linux-like application kernel in userspace and mediates workload system calls; Gofer mediates filesystem access. This reduces direct exposure of the host kernel compared with ordinary `runc` containers.

gVisor is not a conventional VM and does not eliminate all host-kernel exposure. It has its own compatibility, performance, and operational trade-offs. It is defense-in-depth, not an absolute security guarantee.

Official references:
- https://gvisor.dev/docs/
- https://gvisor.dev/docs/architecture_guide/intro/
- https://gvisor.dev/docs/user_guide/install/
- https://gvisor.dev/docs/user_guide/faq/

## 3. Backend contract

The executor should evolve toward a small internal contract:

```text
ExecutionBackend
  id
  preflight()
  run(script, immutableImage, readOnlyWorkspace, limits, leaseGuard)
  terminate(executionId)
  collectResult(executionId)
```

Contract requirements:

- Backend selection comes only from a validated manifest enum.
- Every backend receives the same bounded task contract and immutable image reference.
- The backend receives no database URL, GitHub token, cloud credentials, Docker socket, or host secrets.
- Product workspace is read-only; writable scratch is ephemeral and size-bounded.
- Network is disabled by default. Any future network exception must be a separate explicit policy, not a backend default.
- CPU, memory, process count, file descriptors, file size, wall-clock time, and combined output remain bounded.
- A lease loss or timeout terminates the complete execution, not only the CLI parent process.
- Result/evidence format remains backend-neutral.
- Backend identity, runtime version, image digest, host architecture, and effective security settings are recorded with evidence.
- No backend may silently fall back to another backend.

This contract is a design target. It is not present in code yet.

## 4. Manifest and configuration proposal

Add `gvisor-sandbox` as a third allowed `execution_mode` only when the implementation and tests exist.

Proposed host configuration:

- `FACTORY_GVISOR_RUNTIME=runsc` (fixed allow-listed runtime name; never a user-supplied executable path).
- `FACTORY_SANDBOX_IMAGE=sha256:<64 hex>` (same immutable local image contract as Docker).
- Optional pinned `FACTORY_GVISOR_VERSION` for preflight comparison with the installed runtime.

Preflight must verify, before task lease acquisition:

1. Linux host and supported architecture (initial target: x86_64/amd64; add arm64 only after CI coverage).
2. Docker Engine is reachable.
3. The exact `runsc` runtime is registered with Docker and executable.
4. `docker info` reports the configured runtime; a harmless disposable smoke run using `--runtime=runsc` succeeds.
5. The immutable image exists locally and its inspected ID exactly matches the configured digest.
6. Runtime version is captured and meets the pinned compatibility policy.
7. No conflicting runtime configuration or unapproved runtime options are present.

If any preflight check fails, stop before lease acquisition and report a typed `BACKEND_UNAVAILABLE` or `BACKEND_MISCONFIGURED` error. Do not try `docker-sandbox` or `trusted-node`.

## 5. Isolation profile

The first gVisor backend must retain, not relax, the existing Docker sandbox controls:

- `--runtime=runsc`
- `--network none`
- `--read-only`
- `--cap-drop=ALL`
- `--security-opt=no-new-privileges:true`
- non-root UID/GID 65532
- private IPC and cgroup namespaces where supported by the configured Docker/runtime versions
- bounded `/tmp` and `/dev/shm`
- read-only product bind mount
- strict CPU, memory, swap, PID, ulimit, timeout, and output limits
- only explicitly approved non-secret environment variables

Do not add host paths, devices, privileged mode, host PID/network namespaces, runtime sockets, or application credentials.

Some controls may be unsupported or behave differently under particular Docker/gVisor versions. Unsupported controls are a hard failure until explicitly reviewed and tested; they are not silently omitted.

## 6. Compatibility and operational constraints

- gVisor requires Linux and currently documents x86_64/AMD64 and ARM64 support. The initial TRADIX implementation should target one architecture first and add the other only with CI coverage.
- Not every Linux syscall, `/proc`, or `/sys` behavior is implemented identically. Node lifecycle scripts and the pinned base image must pass a compatibility suite.
- Runtime installation/configuration is a host-administrator operation. TRADIX must not install packages, edit `/etc/docker/daemon.json`, restart Docker, or download runtime binaries during a task.
- Runtime package, `runsc`, and sidecar binaries must be version-pinned and integrity-verified. Do not rely on a moving `latest` URL.
- No paid service is required, but a Linux worker with administrative setup is required. This design does not claim that an iPad or Windows host can execute gVisor locally.
- The current CI runner must not be assumed to have `runsc` installed or Docker runtime registration. Use a dedicated self-hosted Linux runner only after its isolation and maintenance risks are accepted; otherwise keep CI in Docker mode and test gVisor on a separately provisioned disposable worker.

## 7. Security acceptance tests

Before enabling the mode for any task, test on a disposable Linux worker:

1. Runtime identity: the container demonstrably runs under `runsc`, not `runc`.
2. Non-root identity, zero effective capabilities, and no-new-privileges.
3. No IPv4 or active non-loopback IPv6 default egress route.
4. No DNS or outbound connectivity.
5. Read-only workspace and root filesystem.
6. Bounded writable scratch and shared memory.
7. No injected host/application secrets or runtime sockets.
8. CPU, memory, PID, output, and timeout limits are enforced.
9. Lease-loss and timeout kill the workload and descendants.
10. Malformed/missing runtime, image mismatch, and unsupported host all fail before lease acquisition.
11. Deliberate syscall-compatibility probes document supported/unsupported behavior.
12. Repeat the existing Hello World, test, review, health, retry, and evidence lifecycle through the real factory executor.

Security tests must inspect effective runtime behavior, not merely assert that a command-line flag was included.

## 8. Rollout and rollback

1. Keep current Docker mode as the default for its existing approved use.
2. Implement the backend contract and gVisor adapter in a separate branch.
3. Add unit tests for manifest validation, backend selection, preflight, and fail-closed behavior.
4. Add a gVisor-specific probe product and disposable-worker integration test.
5. Run comparative compatibility, performance, and resource tests against Docker mode.
6. Enable `gvisor-sandbox` only for explicitly selected low-risk test tasks on a dedicated worker.
7. Promote only after independent security review and recorded evidence.

Rollback is configuration-level: stop selecting `gvisor-sandbox`. Never rewrite existing task records or silently re-run a failed gVisor task with Docker. A new attempt must preserve the prior failure and use an explicitly authorized backend.

## 9. Alternatives considered

### Firecracker

Firecracker provides microVM isolation and a stronger separation model, but requires KVM-capable Linux hosts, guest kernel/rootfs management, VM lifecycle orchestration, networking setup, and more operational work. It is a later candidate for higher-risk workloads, not the next smallest step.

### Direct containerd + runsc

This removes Docker Engine from the execution path, but adds containerd client integration, image transfer/snapshot management, OCI spec generation, task lifecycle, and cleanup. Revisit only if Docker Engine becomes an actual portability or security bottleneck.

### Docker Engine + runsc (selected first)

Reuses the current immutable image and executor lifecycle while switching the OCI runtime. It is the smallest additive route, but it still depends on Docker daemon administration and must be treated as a separate configured runtime, not as a fully independent container control plane.

## 10. Explicit non-goals

- No change to the current Docker backend.
- No automatic gVisor installation or Docker daemon reconfiguration.
- No new paid infrastructure.
- No production deployment or database migration.
- No automatic fallback between execution modes.
- No claim that gVisor is a VM or provides perfect isolation.
- No changes to product dossiers or independent TRADIX products.

## 11. Current status

- Repository inventory found no existing gVisor or Firecracker implementation.
- Existing Docker sandbox remains the only implemented sandbox backend.
- This document is a design proposal, not an implementation or verification record.
- The next coding task, after this design is reviewed, is a minimal adapter contract plus manifest validation and fail-closed unit tests. Runtime integration must wait for a disposable Linux worker with a pinned, preconfigured `runsc`.
