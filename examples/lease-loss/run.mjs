import { spawn } from "node:child_process";
import { writeFile } from "node:fs/promises";

const grandchild = spawn(process.execPath, [
  "-e",
  "setTimeout(() => require('node:fs').writeFileSync('/tmp/tradix-lease-loss-grandchild-survived', 'grandchild completed'), 25000)"
], { stdio: "ignore" });

await writeFile("/tmp/tradix-lease-loss-child.pid", String(process.pid));
await writeFile("/tmp/tradix-lease-loss-grandchild.pid", String(grandchild.pid));
await new Promise(resolve => setTimeout(resolve, 25000));
await writeFile("/tmp/tradix-lease-loss-child-survived", "child completed");
