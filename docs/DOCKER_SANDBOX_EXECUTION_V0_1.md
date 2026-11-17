# Docker Sandbox Execution v0.1

**Status:** Implemented as an opt-in execution backend; CI verification required  
**Backend:** Docker Engine, immutable local image ID  
**Scope:** Bounded execution of Node.js product lifecycle scripts

## Security controls

For each script, the factory executor starts a fresh container with:

- no network (`--network none`), with both IPv4 and IPv6 default-route absence checked by the runtime probe;
- private IPC and cgroup namespaces (`--ipc=private`, `--cgroupns=private`);
- read-only container root filesystem;
- product directory mounted read-only;
- non-root UID/GID 65532;
- all Linux capabilities dropped;
- no-new-privileges enabled;
- Docker's default seccomp profile retained;
- 64-process limit;
- 256 MiB memory limit, with swap capped to the same amount;
- one CPU quota;
- 256 file descriptors and 10 MiB maximum file size;
- separate 16 MiB `noexec`, `nosuid`, `nodev` temporary filesystems for both `/tmp` and `/dev/shm`;
- zero effective Linux capabilities, verified from `/proc/self/status`;
- `NoNewPrivs=1`, verified from `/proc/self/status`;
- only `NODE_ENV` and `HOME` passed into the container;
- 15-second stage timeout and 1 MiB combined output cap.

The image must already exist locally and `FACTORY_SANDBOX_IMAGE` must be its immutable `sha256:<64 hex>` image ID. The executor uses `--pull=never`; it never downloads an image during task execution. The CI image is based on the official Node.js 24.22.3 Bookworm slim image pinned by its multi-platform manifest digest.

The Docker daemon is a privileged host capability. Product containers never receive the Docker socket or daemon credentials. The executor host must be a dedicated worker with no production secrets and no unrelated workloads.

## Important limitation

This is container isolation, not a microVM boundary. Containers share the host kernel. It is suitable as a first bounded backend for generated product code on a dedicated, disposable worker, but it is not a claim of protection against a determined kernel-escape attacker. Do not execute hostile public submissions or arbitrary third-party code on a sensitive shared host. Higher-risk workloads require a stronger backend such as gVisor or Firecracker, behind the same execution interface.

## Execution modes

- `trusted-node`: legacy mode for reviewed, trusted code only.
- `docker-sandbox`: opt-in container mode; fails closed if Docker is unavailable or the immutable image ID is missing.

The executor does not fall back from `docker-sandbox` to `trusted-node`.

## Verification

The sandbox probe product checks non-root execution, zero effective capabilities, `NoNewPrivs=1`, absent application secrets, read-only workspace, bounded ephemeral `/tmp` and shared memory, and the absence of default IPv4 and IPv6 routes. CI must run this product through the real factory executor against disposable PostgreSQL before this backend is considered verified.

No Neon/Production migration, deployment, or paid service is authorized by this implementation.
