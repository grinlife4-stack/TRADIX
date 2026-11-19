export const GVISOR_RUNTIME = "runsc";

export class GvisorPreflightError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "GvisorPreflightError";
    this.code = code;
  }
}

export function parseDockerRuntimes(output) {
  let runtimes;
  try {
    runtimes = JSON.parse(output);
  } catch {
    throw new GvisorPreflightError("BACKEND_MISCONFIGURED", "Docker returned invalid runtime metadata");
  }
  if (!runtimes || typeof runtimes !== "object" || Array.isArray(runtimes)) {
    throw new GvisorPreflightError("BACKEND_MISCONFIGURED", "Docker runtime metadata has an invalid shape");
  }
  return runtimes;
}

export function assertGvisorRuntimeRegistered(output) {
  const runtimes = parseDockerRuntimes(output);
  if (!Object.hasOwn(runtimes, GVISOR_RUNTIME)) {
    throw new GvisorPreflightError(
      "BACKEND_UNAVAILABLE",
      "gVisor runtime 'runsc' is not registered with Docker; refusing execution"
    );
  }
  return runtimes[GVISOR_RUNTIME];
}

export function assertImmutableImageId(image) {
  if (typeof image !== "string" || !/^sha256:[a-f0-9]{64}$/.test(image)) {
    throw new GvisorPreflightError(
      "BACKEND_MISCONFIGURED",
      "gvisor-sandbox requires FACTORY_SANDBOX_IMAGE to be an immutable sha256 image ID"
    );
  }
  return image;
}

export function buildGvisorRuntimeArgs() {
  return [`--runtime=${GVISOR_RUNTIME}`];
}

export async function preflightGvisorSandbox({ image, platform, arch, runCommand }) {
  assertImmutableImageId(image);
  if (platform !== "linux") {
    throw new GvisorPreflightError("BACKEND_UNAVAILABLE", "gvisor-sandbox requires a Linux execution host");
  }
  if (arch !== "x64") {
    throw new GvisorPreflightError("BACKEND_UNAVAILABLE", "gvisor-sandbox v0.1 supports x86_64/amd64 only");
  }
  if (typeof runCommand !== "function") {
    throw new TypeError("runCommand is required");
  }

  const runtimeInfo = await runCommand(
    ["info", "--format", "{{json .Runtimes}}"],
    "Docker runtime inventory"
  );
  const registered = assertGvisorRuntimeRegistered(runtimeInfo.stdout);

  const imageInfo = await runCommand(
    ["image", "inspect", "--format", "{{.Id}}", image],
    "sandbox image identity check"
  );
  if (imageInfo.stdout.trim() !== image) {
    throw new GvisorPreflightError(
      "BACKEND_MISCONFIGURED",
      "Local sandbox image ID does not exactly match FACTORY_SANDBOX_IMAGE"
    );
  }

  // Execute the pinned image's Node binary under runsc. This proves the
  // configured runtime can start this exact image before a task lease exists.
  await runCommand(
    [
      "run", "--rm", "--pull=never", ...buildGvisorRuntimeArgs(),
      "--network", "none", "--read-only", "--cap-drop=ALL",
      "--security-opt=no-new-privileges:true", "--user=65532:65532",
      "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m,uid=65532,gid=65532,mode=1777",
      "--entrypoint", "node", image, "--version"
    ],
    "gVisor runtime smoke test"
  );

  return {
    runtime: GVISOR_RUNTIME,
    runtimeRegistration: registered,
    imageId: image,
    platform,
    architecture: arch
  };
}
