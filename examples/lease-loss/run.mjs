import { writeFile } from "node:fs/promises";

await writeFile("/tmp/tradix-lease-loss-child.pid", String(process.pid));
await new Promise(resolve => setTimeout(resolve, 25000));
await writeFile("/tmp/tradix-lease-loss-child-survived", "child completed");
