import { createHash } from "node:crypto";
import { lstat, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { resolve, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const MANIFEST_NAME = "ci-evidence-manifest.json";

function required(env, key, pattern) {
  const value = env[key];
  if (typeof value !== "string" || !pattern.test(value)) {
    throw new Error(`Missing or invalid GitHub Actions context: ${key}`);
  }
  return value;
}

async function listEvidenceFiles(root, current = root) {
  const entries = await readdir(current, { withFileTypes: true });
  const files = [];
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const absolute = resolve(current, entry.name);
    const info = await lstat(absolute);
    if (info.isSymbolicLink()) {
      throw new Error(`Evidence directory must not contain symbolic links: ${relative(root, absolute)}`);
    }
    if (info.isDirectory()) {
      files.push(...await listEvidenceFiles(root, absolute));
      continue;
    }
    if (!info.isFile() || entry.name === MANIFEST_NAME) continue;
    const content = await readFile(absolute);
    const after = await lstat(absolute);
    if (after.size !== info.size || after.mtimeMs !== info.mtimeMs) {
      throw new Error(`Evidence file changed while being hashed: ${relative(root, absolute)}`);
    }
    files.push({
      path: relative(root, absolute).split(sep).join("/"),
      sha256: createHash("sha256").update(content).digest("hex"),
      byte_size: content.byteLength
    });
  }
  return files;
}

export async function buildEvidenceManifest({ directory, env = process.env, now = new Date() }) {
  const root = resolve(directory);
  await mkdir(root, { recursive: true });
  const eventPath = env.GITHUB_EVENT_PATH;
  let event = {};
  if (eventPath) {
    event = JSON.parse(await readFile(eventPath, "utf8"));
  }
  const pullRequest = Array.isArray(event.pull_request) ? event.pull_request[0] : event.pull_request;
  const manifest = {
    schema_version: 1,
    evidence_kind: "github_actions_ci",
    source: {
      repository: required(env, "GITHUB_REPOSITORY", /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/),
      commit_sha: required(env, "GITHUB_SHA", /^[a-f0-9]{40}$/),
      ref: required(env, "GITHUB_REF", /^refs\/[A-Za-z0-9_./-]+$/),
      workflow: required(env, "GITHUB_WORKFLOW", /^.{1,200}$/),
      run_id: required(env, "GITHUB_RUN_ID", /^\d+$/),
      run_attempt: required(env, "GITHUB_RUN_ATTEMPT", /^\d+$/),
      event_name: required(env, "GITHUB_EVENT_NAME", /^[a-z_]+$/),
      actor: required(env, "GITHUB_ACTOR", /^[A-Za-z0-9-]+$/),
      job: required(env, "GITHUB_JOB", /^[A-Za-z0-9_-]+$/),
      pull_request_number: Number.isInteger(pullRequest?.number) ? pullRequest.number : null,
      run_url: `${env.GITHUB_SERVER_URL ?? "https://github.com"}/${env.GITHUB_REPOSITORY}/actions/runs/${env.GITHUB_RUN_ID}`
    },
    created_at: now.toISOString(),
    files: await listEvidenceFiles(root)
  };
  const output = resolve(root, MANIFEST_NAME);
  await writeFile(output, `${JSON.stringify(manifest, null, 2)}\n`, { mode: 0o600 });
  return { output, manifest };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const directory = process.argv[2] ?? "/tmp/tradix-factory-executor";
  try {
    const { output, manifest } = await buildEvidenceManifest({ directory });
    process.stdout.write(`PASS CI evidence manifest: ${output} files=${manifest.files.length} run=${manifest.source.run_id}\n`);
  } catch (error) {
    process.stderr.write(`FAIL CI evidence manifest: ${error.message}\n`);
    process.exitCode = 1;
  }
}
