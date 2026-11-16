import { createServer } from "node:http";
import worker from "./index.mjs";

const port = Number(process.env.PORT || 8787);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("PORT must be a valid TCP port");
}

const server = createServer(async (incoming, outgoing) => {
  try {
    const host = incoming.headers.host || "127.0.0.1";
    const url = new URL(incoming.url || "/", `http://${host}`);
    const headers = new Headers();
    for (const [name, value] of Object.entries(incoming.headers)) {
      if (Array.isArray(value)) headers.set(name, value.join(", "));
      else if (value !== undefined) headers.set(name, value);
    }
    const init = { method: incoming.method || "GET", headers };
    if (init.method !== "GET" && init.method !== "HEAD") {
      const chunks = [];
      for await (const chunk of incoming) chunks.push(chunk);
      init.body = Buffer.concat(chunks);
    }
    const response = await worker.fetch(new Request(url, init));
    outgoing.writeHead(response.status, Object.fromEntries(response.headers));
    outgoing.end(Buffer.from(await response.arrayBuffer()));
  } catch (error) {
    console.error("memory gateway request failed", { message: error?.message });
    if (!outgoing.headersSent) outgoing.writeHead(500, { "content-type": "application/json" });
    outgoing.end(JSON.stringify({ error: "internal_error" }));
  }
});

server.listen(port, "0.0.0.0", () => {
  console.log(`memory-gateway listening on ${port}`);
});

function shutdown() {
  server.close(() => process.exit(0));
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
