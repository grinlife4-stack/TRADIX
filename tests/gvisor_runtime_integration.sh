#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "FAIL: gVisor integration requires Linux" >&2
  exit 1
fi
if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "FAIL: gVisor integration v0.1 supports x86_64 only" >&2
  exit 1
fi
command -v docker >/dev/null || { echo "FAIL: docker CLI is missing" >&2; exit 1; }
command -v node >/dev/null || { echo "FAIL: node is required to parse Docker runtime metadata" >&2; exit 1; }

image="${FACTORY_SANDBOX_IMAGE:-}"
if [[ ! "$image" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo "FAIL: FACTORY_SANDBOX_IMAGE must be an immutable sha256 image ID" >&2
  exit 1
fi

runtimes="$(docker info --format '{{json .Runtimes}}')"
node --input-type=module - "$runtimes" <<'NODE'
const value = JSON.parse(process.argv[2]);
if (!value || typeof value !== "object" || !Object.hasOwn(value, "runsc")) {
  console.error("FAIL: Docker does not report the runsc runtime");
  process.exit(1);
}
NODE

actual_image="$(docker image inspect --format '{{.Id}}' "$image")"
[[ "$actual_image" == "$image" ]] || { echo "FAIL: local image ID mismatch" >&2; exit 1; }

name="tradix-gvisor-integration-$RANDOM-$$"
cleanup() { docker rm --force "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run --detach --pull=never --runtime=runsc \
  --name "$name" \
  --network none \
  --ipc=private \
  --cgroupns=private \
  --read-only \
  --cap-drop=ALL \
  --security-opt=no-new-privileges:true \
  --pids-limit=64 \
  --memory=256m \
  --memory-swap=256m \
  --cpus=1 \
  --user=65532:65532 \
  --ulimit nofile=256:256 \
  --ulimit fsize=10485760:10485760 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m,uid=65532,gid=65532,mode=1777 \
  --shm-size=16m \
  "$image" -e 'setTimeout(() => { console.log("TRADIX_GVISOR_RUNTIME_OK"); }, 5000)' >/dev/null

runtime="$(docker inspect --format '{{.HostConfig.Runtime}}' "$name")"
[[ "$runtime" == "runsc" ]] || {
  echo "FAIL: container HostConfig.Runtime is '$runtime', expected runsc" >&2
  exit 1
}

status="$(docker wait "$name")"
[[ "$status" == "0" ]] || { echo "FAIL: gVisor smoke container exited with $status" >&2; exit 1; }
logs="$(docker logs "$name")"
grep -F "TRADIX_GVISOR_RUNTIME_OK" <<< "$logs" >/dev/null || {
  echo "FAIL: gVisor smoke container did not produce its success marker" >&2
  exit 1
}

echo "PASS: Docker executed the pinned image using runsc with the required sandbox limits"
