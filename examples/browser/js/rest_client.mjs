// AgentDesk browser control plane — zero-dependency JS/TS client.
// Usage: node rest_client.mjs
const API = "http://127.0.0.1:8756/api/browser/sdk";
const TOKEN = process.env.AGENTDESK_BROWSER_TOKEN ||
  (await import("node:fs")).readFileSync(
    `${process.env.APPDATA}\\AgentDesk\\data\\browser-sdk.token`, "utf8").trim();

async function call(path, body) {
  const res = await fetch(API + path, {
    method: body ? "POST" : "GET",
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}: ${JSON.stringify(data)}`);
  return data;
}

const info = await call("/info");
console.log("CDP enabled:", info.cdp.enabled, "port:", info.cdp.port);
console.log("transports:", info.transports);

await call("/navigate", { url: "https://example.com" });
const snap = await call("/snapshot");
console.log("title:", snap.title);
console.log("text:", snap.text.split("\n").slice(0, 3).join(" | "));

// Arrow keys / chords are first-class:
await call("/act", { action: "key", key: "ArrowDown" });
await call("/act", { action: "key", key: "Control+l" });
