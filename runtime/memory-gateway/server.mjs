import { createServer } from "node:http";
import worker from "./index.mjs";

const port = Number(process.env.PORT || 8787);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("PORT must be a valid TCP port");
}

const server = createServer({ maxHeaderSize: 16 * 1024 }, async (incoming, outgoing) => {
  // Reject unsupported methods before touching or buffering their request bodies.
  if (incoming.method !== "GET") {
    outgoing.writeHead(405, {
      "content-type": "application/json",
      "cache-control": "no-store",
      "connection": "close"
    });
    outgoing.end(JSON.stringify({ error: "method_not_allowed" }));
    incoming.resume();
    return;
  }

  // This API has no request-body contract. Reject even a GET with a body.
  if ((Number(incoming.headers["content-length"] || 0) > 0) || incoming.headers["transfer-encoding"]) {
    outgoing.writeHead(400, {
      "content-type": "application/json",
      "cache-control": "no-store",
      "connection": "close"
    });
    outgoing.end(JSON.stringify({ error: "request_body_not_supported" }));
    incoming.resume();
    return;
  }

  try {
    const url = new URL(incoming.url || "/", "http://127.0.0.1");
    const headers = new Headers();
    for (const [name, value] of Object.entries(incoming.headers)) {
      if (Array.isArray(value)) headers.set(name, value.join(", "));
      else if (value !== undefined) headers.set(name, value);
    }
    const response = await worker.fetch(new Request(url, { method: "GET", headers }));
    outgoing.writeHead(response.status, Object.fromEntries(response.headers));
    outgoing.end(Buffer.from(await response.arrayBuffer()));
  } catch (error) {
    console.error("memory gateway request failed", { message: error?.message });
    if (!outgoing.headersSent) outgoing.writeHead(500, { "content-type": "application/json" });
    outgoing.end(JSON.stringify({ error: "internal_error" }));
  }
});

server.requestTimeout = 10_000;
server.headersTimeout = 10_000;
server.keepAliveTimeout = 5_000;
server.maxRequestsPerSocket = 100;

server.listen(port, "0.0.0.0", () => {
  console.log(`memory-gateway listening on ${port}`);
});

let shuttingDown = false;
async function shutdown() {
  if (shuttingDown) return;
  shuttingDown = true;
  server.close(async () => {
    await worker.close();
    process.exit(0);
  });
  setTimeout(() => process.exit(1), 10_000).unref();
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
