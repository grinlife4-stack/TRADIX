# TRADIX Hardware Resource Manager — Contract v0.1

**Status:** Draft architecture and data contract; not an implemented scheduler  
**Parent baseline:** `factory/ci-evidence-manifest-v0-1`  
**Scope:** Hardware inventory, capability discovery, resource admission, leases, and portable execution placement.

## 1. Purpose

The Hardware Resource Manager (HRM) lets TRADIX use heterogeneous computers without binding the factory to a particular CPU, GPU, operating system, cloud, or hardware vendor. It inventories compute nodes, exposes verified capabilities, admits bounded workloads, and records allocation evidence.

HRM is a control-plane capability. It does not itself execute untrusted product code and does not give agents direct infrastructure credentials.

## 2. Non-negotiable invariants

1. **Vendor-neutral:** hardware is described by capabilities and standard interfaces, not by brand-specific assumptions. Vendor adapters are replaceable.
2. **No false aggregation:** RAM and accelerator memory on different devices are not represented as one physically unified pool. A workload must fit the memory limits of the device(s) it actually uses.
3. **Fail closed:** unknown, stale, contradictory, or unverified capacity is unavailable for new admission.
4. **Reserve before launch:** a workload receives a time-bounded allocation lease before a worker starts it.
5. **Fence stale workers:** every allocation has a monotonically increasing fencing token. A worker whose lease expires or is revoked cannot publish a result or commit a state transition.
6. **Isolation remains mandatory:** resource allocation never weakens the executor sandbox, network policy, filesystem policy, or secret boundary.
7. **No overcommit by default:** CPU, RAM, accelerator memory, and storage reservations are hard admission limits. Explicit future policies may permit bounded CPU overcommit only.
8. **Evidence follows execution:** inventory snapshot, admission decision, allocation, lease renewals, release, and observed usage are recorded with task/run identifiers.
9. **Portable products:** a product may request capabilities (for example, Linux + 4 vCPU + 8 GiB RAM + CUDA-compatible GPU) but must not require a particular physical node name.
10. **Human approval for irreversible cost:** provisioning paid compute, changing spending limits, or destructive infrastructure operations remain approval-gated.

## 3. Logical components

- **Node Agent:** read-only discovery and telemetry on each managed host. It reports facts; it cannot grant itself capacity or approve work.
- **Inventory Registry:** stores node identity, hardware topology, software/runtime capabilities, health, provenance, and freshness.
- **Admission Controller:** compares a validated resource request with currently allocatable capacity and policy.
- **Lease/Fencing Service:** issues, renews, expires, and revokes allocation leases. The durable store is authoritative.
- **Placement Adapter:** translates a portable allocation into a target-specific operation (local process, container runtime, or remote worker). Adapters are replaceable.
- **Usage Reporter:** records measured usage and reconciles it against reservations.
- **Audit/Evidence Writer:** appends decision and execution evidence to the factory ledger and artifact store.

Agents and product code may request resources through a narrow API. They may not edit inventory, choose privileged hosts, bypass admission, or alter limits.

## 4. Node lifecycle

`DISCOVERED → QUARANTINED → VERIFIED → AVAILABLE → DRAINING → OFFLINE`

- A new or changed node enters `QUARANTINED`.
- Hardware facts, OS/runtime support, clock, storage health, and isolation preflight must pass before `VERIFIED`.
- Only a verified, fresh, healthy node may become `AVAILABLE`.
- `DRAINING` stops new allocations and allows bounded work to finish or checkpoint.
- Missing heartbeats, failed integrity checks, or contradictory telemetry move a node out of `AVAILABLE`.
- Rejoining a node requires revalidation; a prior status is not blindly trusted.

## 5. Capability model

Inventory must distinguish:

- CPU architecture, logical/physical cores, instruction features, NUMA topology, and allocatable CPU quota.
- System memory total, available, reserved, and allocatable bytes.
- Each accelerator separately: vendor, model, architecture, device identifier scoped to the node, memory total/free/reserved, supported runtimes/APIs, and health.
- Storage devices and volumes separately: type, capacity, free bytes, filesystem, mount, read/write health, and whether ephemeral.
- Network interfaces and verified link speed/duplex; network reachability is a separate health check.
- Power and thermal telemetry when available. Missing telemetry is recorded as unknown, not as healthy.
- OS, kernel, container runtime, sandbox backend, driver/runtime versions, and supported execution profiles.

A GPU capability is not inferred from a product name alone. Runtime compatibility must be probed on the actual host. For example, an AMD card is not assumed to support a CUDA workload.

## 6. Workload resource request

A product stage requests minimum and maximum bounds, not a named machine:

- CPU architecture/features and vCPU/millicore request.
- RAM bytes and optional hard memory limit.
- Accelerator requirements per device: API/runtime, count, minimum per-device VRAM, and optional architecture/features.
- Scratch and persistent storage requirements, IOPS/throughput where measurable.
- Network profile (none, restricted egress, or explicitly approved service access).
- Runtime profile and sandbox requirement.
- Maximum wall time, output limit, process limit, and lease duration.
- Placement constraints only when technically necessary (for example, same-node shared memory); no user-facing product may pin itself to a provider-specific host by default.

Admission must reject a request if a required field is missing, a limit cannot be enforced, capacity is stale, or a security profile is unavailable.

## 7. Admission and scheduling

1. Validate request against a versioned schema and product policy.
2. Read a fresh inventory snapshot and subtract active reservations.
3. Filter nodes by verified health, runtime compatibility, security profile, and required capabilities.
4. Score eligible nodes using a documented policy (fit, locality, reliability, energy/cost, and current load).
5. Atomically reserve resources and issue a lease with a new fencing token.
6. Start the workload through the selected placement adapter.
7. Renew lease only while worker health and policy checks pass.
8. On expiry/revocation, terminate or isolate the worker; reject stale writes/results.
9. Reconcile measured usage, release reservation, and append evidence.

Initial scheduling should be deterministic and conservative (best-fit among eligible nodes). Sophisticated bin-packing or predictive scheduling is deferred until measured workload data exists.

## 8. Resource accounting and safety

- CPU: reserve in millicores or enforceable CPU quota; distinguish physical cores from logical threads.
- RAM: reserve bytes and enforce hard cgroup/container limits where supported.
- GPU: reserve per physical device and per-device VRAM; do not add VRAM across cards as if it were unified memory.
- Storage: reserve workspace and persistent volume separately; prevent one task from exhausting the host filesystem.
- Network: apply explicit egress policy; no network by default for untrusted stages.
- Power/thermal: observe and alert where sensors exist; never infer safe capacity from PSU label wattage alone.
- Legacy hosts and unsupported drivers may be used for isolated tests, but must not be marked production-capable without passing the relevant profile.

## 9. Portability and failure behavior

The registry stores hardware facts, while products store capability requirements. Placement adapters isolate local Docker, gVisor, future runtimes, and remote hosts behind one contract. A missing adapter must make the capability unavailable, not trigger an unsafe fallback.

If the controller, registry, lease store, or evidence writer is unavailable, no new workload is admitted. Existing work follows the executor's bounded lease policy; it must not continue indefinitely without a valid lease. Recovery requires reconciliation of leases and fencing tokens before new allocations.

## 10. Phased implementation

### HRM-0 — Contract (this PR)
- Define node inventory and workload request schemas.
- Define lifecycle, admission, lease, fencing, and evidence invariants.
- Keep all discovered hardware untrusted until verified.

### HRM-1 — Read-only inventory
- Implement a local discovery CLI/agent for CPU, RAM, storage, network, OS, and accelerators.
- Emit a signed or hashed inventory snapshot; do not execute workloads or change host configuration.
- Add fixtures for mixed legacy and modern hosts.

### HRM-2 — Single-node admission
- Add deterministic capacity accounting and a durable reservation/lease record.
- Integrate with the existing executor's task lease and fencing contract.
- Prove over-allocation is rejected and stale workers cannot commit.

### HRM-3 — Multi-node placement
- Add replaceable local/remote placement adapters.
- Test node loss, stale telemetry, lease expiry, drain, and recovery.
- Measure real workloads before tuning placement.

### HRM-4 — Accelerator support
- Probe each GPU and runtime independently.
- Test actual model/framework compatibility and per-device memory limits.
- Add AMD/NVIDIA adapters only where a supported runtime passes host-level tests.

## 11. Acceptance criteria

This contract is not considered implemented until all of the following are demonstrated:

- A read-only inventory report correctly distinguishes CPU, system RAM, each GPU, storage, and network.
- Unknown or stale measurements are excluded from allocatable capacity.
- Two concurrent requests cannot reserve the same capacity.
- A request exceeding CPU, RAM, per-device VRAM, storage, or time limits is rejected.
- Lease expiry issues a higher fencing token and stale workers cannot publish results.
- Node drain and node loss do not silently lose task state or evidence.
- The same product request can run on two different compatible nodes without changing product code.
- A complete test report and reproducible evidence manifest are attached to the release candidate.

## 12. Current known hardware inventory

Only user-reported categories are known at this stage: two or three AMD RX 580 8 GB cards; Enermax and Cooler Master modular power supplies; multiple multi-slot motherboards, cases, CPUs, RAM modules, monitors, TP-Link 16-port switches, MikroTik hAP lite routers, and modems. Exact models, health, interfaces, and compatibility are **not verified**. These items must not be entered as allocatable production capacity until physically inspected and tested.

## 13. Explicit non-goals

This contract does not provision paid cloud resources, flash firmware, overclock hardware, change BIOS settings, expose management ports to the internet, deploy a production scheduler, or claim that the user's current hardware has been tested.
