#!/usr/bin/env bash
# Read-only host readiness check for the TRADIX gVisor worker.
# Optional --probe runs one disposable hello-world container through runsc.
set -Eeuo pipefail

probe=0
if [[ "${1:-}" == "--probe" ]]; then probe=1; elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--probe]" >&2; exit 64
fi

fail=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then printf 'PASS  %s\n' "$label"
  else printf 'BLOCK %s\n' "$label"; fail=1; fi
}

echo "TRADIX gVisor worker preflight (read-only)"
printf 'OS: '; . /etc/os-release 2>/dev/null && printf '%s %s\n' "${ID:-unknown}" "${VERSION_ID:-unknown}" || echo unknown
printf 'Kernel: '; uname -r
printf 'Arch: '; uname -m

[[ "$(uname -s)" == Linux ]] && echo "PASS  Linux host" || { echo "BLOCK Linux host required"; fail=1; }
[[ "$(uname -m)" == x86_64 ]] && echo "PASS  x86_64 architecture" || { echo "BLOCK initial backend requires x86_64"; fail=1; }

kernel="$(uname -r | sed 's/[^0-9.].*//')"
if [[ "$(printf '%s\n' 5.6 "$kernel" | sort -V | head -n1)" == 5.6 ]]; then
  echo "PASS  kernel >= 5.6"
else
  echo "BLOCK kernel >= 5.6 required by gVisor"; fail=1
fi

command -v docker >/dev/null 2>&1 && echo "PASS  Docker CLI present" || { echo "BLOCK Docker CLI missing"; fail=1; }
command -v runsc >/dev/null 2>&1 && echo "PASS  runsc executable present" || { echo "BLOCK runsc missing"; fail=1; }

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "PASS  Docker daemon reachable"
    runtimes="$(docker info --format '{{json .Runtimes}}' 2>/dev/null || true)"
    if printf '%s' "$runtimes" | grep -Eq '"runsc"[[:space:]]*:'; then
      echo "PASS  Docker runtime runsc registered"
    else
      echo "BLOCK Docker runtime runsc not registered"; fail=1
    fi
    docker info --format 'Docker server: {{.ServerVersion}} | Driver: {{.Driver}} | Cgroup: {{.CgroupVersion}}' 2>/dev/null || true
  else
    echo "BLOCK Docker daemon unavailable or permission denied"; fail=1
  fi
fi

if command -v runsc >/dev/null 2>&1; then
  runsc --version 2>&1 | head -n 2 || true
fi

if [[ $probe -eq 1 ]]; then
  if [[ $fail -ne 0 ]]; then
    echo "SKIP  runtime probe because host preflight has blockers"
  else
    echo "RUN   disposable runsc hello-world probe"
    docker run --rm --pull=missing --runtime=runsc --network=none hello-world
    echo "PASS  runsc container probe"
  fi
fi

if [[ $fail -ne 0 ]]; then
  echo "RESULT: BLOCKED. No host changes were made."
  exit 2
fi
if [[ $probe -eq 0 ]]; then
  echo "RESULT: HOST CHECKS PASS. Run with --probe to verify an actual runsc container."
else
  echo "RESULT: HOST CHECKS AND RUNSC PROBE PASS."
fi
