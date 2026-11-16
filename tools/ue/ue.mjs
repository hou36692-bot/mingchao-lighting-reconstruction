// Minimal UE_MCP_Bridge WebSocket client (no MCP layer).
// Usage: node ue.mjs <method> [jsonParams]
//
// Environment:
//   UE_PROJECT  (required) path to the UE project root; the bridge port is read
//               from <UE_PROJECT>/Saved/UE_MCP_Bridge/port.json
//   UE_MCP_WS   (optional) path to a WebSocket module exporting a `ws`-compatible
//               default (e.g. .../node_modules/ws/wrapper.mjs). If unset, the
//               bare `ws` package is resolved relative to this file, so
//               `npm i ws` at the repository root is enough.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const project = process.env.UE_PROJECT;
if (!project) {
  console.error("UE_PROJECT is not set (path to the UE project root)");
  process.exit(1);
}

let WebSocket;
if (process.env.UE_MCP_WS) {
  ({ default: WebSocket } = await import(pathToFileURL(process.env.UE_MCP_WS).href));
} else {
  try {
    ({ default: WebSocket } = await import("ws"));
  } catch {
    console.error(
      "Cannot load a WebSocket implementation: set UE_MCP_WS to a ws module path, " +
      "or run `npm i ws` at the repository root"
    );
    process.exit(1);
  }
}

const lock = path.join(project, "Saved/UE_MCP_Bridge/port.json");
if (!fs.existsSync(lock)) {
  console.error(`Bridge port file not found: ${lock} (is the UE_MCP_Bridge plugin running?)`);
  process.exit(1);
}
const port = JSON.parse(fs.readFileSync(lock, "utf8")).port;

export function call(method, params = {}, timeoutMs = 60000) {
  const id = `r${Date.now()}${Math.floor(Math.random() * 1000)}`;
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}`);
    const timer = setTimeout(() => { try { ws.terminate(); } catch {} reject(new Error(`timeout ${method}`)); }, timeoutMs);
    ws.on("open", () => ws.send(JSON.stringify({ id, method, params, timeoutMs })));
    ws.on("message", (raw) => {
      let msg;
      try { msg = JSON.parse(raw.toString()); } catch { return; }
      if (msg.id !== id) return;
      clearTimeout(timer);
      try { ws.close(); } catch {}
      resolve(msg);
    });
    ws.on("error", (e) => { clearTimeout(timer); reject(e); });
  });
}

const [method, paramsArg] = process.argv.slice(2);
if (method) {
  const params = paramsArg ? JSON.parse(paramsArg) : {};
  call(method, params)
    .then((r) => console.log(JSON.stringify(r, null, 2)))
    .catch((e) => { console.error("ERR", e.message); process.exit(1); });
}
