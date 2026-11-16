import { createHash } from "node:crypto";
import { mkdir, readFile, realpath, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import pg from "pg";

const { Client } = pg;
const MAX_OUTPUT_BYTES = 1024 * 1024;
const COMMAND_TIMEOUT_MS = 15000;
const EXECUTOR_ID = "tradix-factory-executor-v0.1";

function fail(message) {
  throw new Error(message);
}

function assertString(value, label, max = 255) {
  if (typeof value !== "string" || !value.trim() || value.length > max) {
    fail(`Invalid manifest field: ${label}`);
  }
  return value;
}

function assertNodeScript(value, label) {
  assertString(value, label, 255);
  if (isAbsolute(value) || value.split(/[\\/]/).includes("..") || !value.endsWith(".mjs")) {
    fail(`${label} must be a relative .mjs script inside the product directory`);
  }
  return value;
}

async function runNodeScript(productRoot, script, label) {
  const scriptPath = await realpath(resolve(productRoot, assertNodeScript(script, label)));
  const rel = relative(productRoot, scriptPath);
  if (!rel || rel.startsWith(`..${sep}`) || rel === ".." || isAbsolute(rel)) {
    fail(`${label} resolves outside the product directory`);
  }

  return await new Promise((resolvePromise, reject) => {
    const child = spawn(process.execPath, [scriptPath], {
      cwd: productRoot,
      shell: false,
      windowsHide: true,
      env: {
        PATH: process.env.PATH ?? "",
        NODE_ENV: "test",
        HOME: process.env.HOME ?? ""
      },
      stdio: ["ignore", "pipe", "pipe"]
    });
    const stdout = [];
    const stderr = [];
    let bytes = 0;
    let settled = false;
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      finish(new Error(`${label} exceeded ${COMMAND_TIMEOUT_MS}ms`));
    }, COMMAND_TIMEOUT_MS);

    function finish(error, result) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error);
      else resolvePromise(result);
    }

    for (const [stream, chunks] of [[child.stdout, stdout], [child.stderr, stderr]]) {
      stream.on("data", chunk => {
        bytes += chunk.length;
        if (bytes > MAX_OUTPUT_BYTES) {
          child.kill("SIGKILL");
          finish(new Error(`${label} output exceeded ${MAX_OUTPUT_BYTES} bytes`));
          return;
        }
        chunks.push(chunk);
      });
    }
    child.on("error", error => finish(error));
    child.on("close", code => {
      const out = Buffer.concat(stdout).toString("utf8");
      const err = Buffer.concat(stderr).toString("utf8");
      if (code !== 0) {
        finish(new Error(`${label} failed with exit code ${code}: ${err || out}`));
      } else {
        finish(null, { stdout: out, stderr: err, exitCode: code });
      }
    });
  });
}

function artifactPayload(result, stage) {
  const content = [
    `stage=${stage}`,
    `exit_code=${result.exitCode}`,
    "stdout:",
    result.stdout,
    "stderr:",
    result.stderr
  ].join("\n");
  return {
    content,
    sha256: createHash("sha256").update(content).digest("hex"),
    byteSize: Buffer.byteLength(content)
  };
}

async function transition(client, taskId, attemptId, from, to) {
  await client.query(
    "SELECT factory.transition_task($1,$2,$3,'agent',$4,$5,$6)",
    [
      taskId,
      to,
      `task.${to}`,
      EXECUTOR_ID,
      `factory-executor:${taskId}:${to}`,
      attemptId
    ]
  );
}

async function recordEvidence(client, taskId, attemptId, type, result) {
  const payload = artifactPayload(result, type);
  const evidenceDir = resolve(process.env.FACTORY_EVIDENCE_DIR ?? "/tmp/tradix-factory-executor", taskId);
  await mkdir(evidenceDir, { recursive: true });
  await writeFile(resolve(evidenceDir, `${type}.txt`), payload.content, { mode: 0o600 });
  await client.query(
    "SELECT factory.record_task_evidence($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)",
    [
      taskId,
      attemptId,
      type,
      `ci://factory-executor/${taskId}/${type}.txt`,
      payload.sha256,
      payload.byteSize,
      "text/plain",
      type,
      `Output captured by ${EXECUTOR_ID}`,
      JSON.stringify({ executor: EXECUTOR_ID, exit_code: result.exitCode })
    ]
  );
  process.stdout.write(`PASS evidence: ${type} sha256=${payload.sha256}\n`);
}

async function main() {
  const manifestArg = process.argv[2];
  if (!manifestArg) fail("Usage: node runner.mjs <product-manifest.json>");
  if (!process.env.DATABASE_URL) fail("DATABASE_URL is required");

  const manifestPath = resolve(process.cwd(), manifestArg);
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  if (manifest.schema_version !== 1) fail("Unsupported product execution manifest version");
  if (manifest.execution_mode !== "trusted-node") {
    fail("Only execution_mode=trusted-node is supported; this runner is not an OS sandbox");
  }

  const baseDir = await realpath(dirname(manifestPath));
  const productRoot = await realpath(resolve(baseDir, assertString(manifest.product_dir, "product_dir", 255)));
  const productRelative = relative(baseDir, productRoot);
  if (productRelative.startsWith(`..${sep}`) || productRelative === ".." || isAbsolute(productRelative)) {
    fail("product_dir must resolve inside the manifest directory");
  }
  const task = manifest.task ?? {};
  const attempt = manifest.attempt ?? {};
  const dossier = manifest.dossier ?? {};
  const scripts = manifest.scripts ?? {};

  const taskKey = assertString(task.task_key, "task.task_key", 120);
  const attemptKey = assertString(attempt.idempotency_key, "attempt.idempotency_key", 255);
  const runScript = assertNodeScript(scripts.run, "scripts.run");
  const testScript = assertNodeScript(scripts.test, "scripts.test");
  const reviewScript = assertNodeScript(scripts.review, "scripts.review");
  const healthScript = assertNodeScript(scripts.health, "scripts.health");

  const client = new Client({ connectionString: process.env.DATABASE_URL, connectionTimeoutMillis: 10000 });
  await client.connect();
  try {
    await client.query("BEGIN");
    const dossierResult = await client.query(
      "SELECT factory.record_product_dossier((SELECT project_id FROM factory.project_identities WHERE role_name=session_user AND identity_kind='runtime'), $1::jsonb, $2) AS version",
      [JSON.stringify(dossier), `${taskKey}:dossier-v1`]
    );
    if (Number(dossierResult.rows[0]?.version) !== 1) {
      fail("Product dossier version 1 was not confirmed");
    }

    const taskResult = await client.query(
      "SELECT factory.create_task($1,$2,$3,$4::jsonb,$5,$6,$7::jsonb) AS task_id",
      [
        taskKey,
        assertString(task.title, "task.title", 160),
        assertString(task.request_text, "task.request_text", 12000),
        JSON.stringify(task.acceptance_criteria),
        task.risk_class ?? "low",
        task.approval_required ?? false,
        JSON.stringify(task.approval_scope ?? {})
      ]
    );
    const taskId = taskResult.rows[0].task_id;

    const attemptResult = await client.query(
      "SELECT factory.create_task_attempt($1,$2,$3,$4,$5::jsonb) AS attempt_id",
      [
        taskId,
        attemptKey,
        attempt.worker_role ?? "implementer",
        attempt.branch_name ?? null,
        JSON.stringify(attempt.metadata ?? { executor: EXECUTOR_ID })
      ]
    );
    const attemptId = attemptResult.rows[0].attempt_id;
    await client.query("COMMIT");

    const state = await client.query(
      "SELECT t.status, a.status AS attempt_status, count(DISTINCT e.event_seq)::int AS event_count, count(DISTINCT ev.evidence_id)::int AS evidence_count FROM factory.tasks t JOIN factory.task_attempts a ON a.task_id=t.task_id LEFT JOIN factory.task_events e ON e.task_id=t.task_id LEFT JOIN factory.task_evidence ev ON ev.task_id=t.task_id WHERE t.task_id=$1 AND a.attempt_id=$2 GROUP BY t.status,a.status",
      [taskId, attemptId]
    );
    if (state.rows[0]?.status === "verified") {
      const row = state.rows[0];
      if (row.attempt_status !== "succeeded" || row.event_count !== 7 || row.evidence_count !== 3) {
        fail("Previously verified task has inconsistent attempt, event, or evidence records");
      }
      process.stdout.write(`ALREADY VERIFIED task=${taskId} attempt=${attemptId} events=${row.event_count} evidence=${row.evidence_count}\\n`);
      return;
    }
    if (state.rows[0]?.status !== "queued" || state.rows[0]?.attempt_status !== "running") {
      fail(`Task/attempt is in state ${state.rows[0]?.status}/${state.rows[0]?.attempt_status}; refusing implicit recovery or duplicate execution`);
    }

    await transition(client, taskId, attemptId, "queued", "planned");
    await transition(client, taskId, attemptId, "planned", "implementing");

    let currentState = "implementing";
    try {
      const runResult = await runNodeScript(productRoot, runScript, "product run");
      const testResult = await runNodeScript(productRoot, testScript, "product test");

      await transition(client, taskId, attemptId, currentState, "testing");
      currentState = "testing";
      await recordEvidence(client, taskId, attemptId, "test_report", {
        stdout: [runResult.stdout, testResult.stdout].join("\\n"),
        stderr: [runResult.stderr, testResult.stderr].join("\\n"),
        exitCode: 0
      });

      await transition(client, taskId, attemptId, currentState, "review");
      currentState = "review";
      const reviewResult = await runNodeScript(productRoot, reviewScript, "product review");
      await recordEvidence(client, taskId, attemptId, "review_report", reviewResult);

      await transition(client, taskId, attemptId, currentState, "candidate");
      currentState = "candidate";
      await transition(client, taskId, attemptId, currentState, "deployed_test");
      currentState = "deployed_test";

      const healthResult = await runNodeScript(productRoot, healthScript, "product health check");
      await recordEvidence(client, taskId, attemptId, "health_check", healthResult);

      // Commit attempt success and the terminal task transition atomically.
      // A failed terminal transition must never leave a succeeded attempt behind.
      await client.query("BEGIN");
      try {
        await client.query(
          "SELECT factory.finish_task_attempt($1,$2,'succeeded')",
          [taskId, attemptId]
        );
        await transition(client, taskId, attemptId, currentState, "verified");
        await client.query("COMMIT");
        currentState = "verified";
      } catch (finalizeError) {
        await client.query("ROLLBACK");
        throw finalizeError;
      }
    } catch (error) {
      try {
        const attemptState = await client.query(
          "SELECT status FROM factory.task_attempts WHERE task_id=$1 AND attempt_id=$2",
          [taskId, attemptId]
        );
        if (attemptState.rows[0]?.status === "running") {
          await client.query(
            "SELECT factory.finish_task_attempt($1,$2,'failed')",
            [taskId, attemptId]
          );
          if (currentState !== "verified") {
            await client.query(
              "SELECT factory.transition_task($1,'failed','task.failed','agent',$2,$3,$4)",
              [taskId, EXECUTOR_ID, `factory-executor:${taskId}:failed`, attemptId]
            );
          }
        }
      } catch (cleanupError) {
        process.stderr.write(`FACTORY_EXECUTOR_CLEANUP_FAILED: ${cleanupError.message}\\n`);
      }
      throw error;
    }

    const verified = await client.query(
      "SELECT t.status, a.status AS attempt_status, count(DISTINCT e.event_seq)::int AS event_count, count(DISTINCT ev.evidence_id)::int AS evidence_count FROM factory.tasks t JOIN factory.task_attempts a ON a.task_id=t.task_id LEFT JOIN factory.task_events e ON e.task_id=t.task_id LEFT JOIN factory.task_evidence ev ON ev.task_id=t.task_id WHERE t.task_id=$1 AND a.attempt_id=$2 GROUP BY t.status,a.status",
      [taskId, attemptId]
    );
    const row = verified.rows[0];
    if (row?.status !== "verified" || row?.attempt_status !== "succeeded" ||
        row.event_count !== 7 || row.evidence_count !== 3) {
      fail("Final factory verification did not satisfy task, attempt, event, and evidence invariants");
    }
    process.stdout.write(
      `VERIFIED task=${taskId} attempt=${attemptId} events=${row.event_count} evidence=${row.evidence_count}\n`
    );
  } finally {
    await client.end();
  }
}

main().catch(error => {
  process.stderr.write(`FACTORY_EXECUTOR_FAILED: ${error.stack ?? error.message}\n`);
  process.exitCode = 1;
});
