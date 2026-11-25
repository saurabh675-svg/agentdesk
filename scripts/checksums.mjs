// Writes release/SHA256SUMS.txt for every artifact — free integrity alternative to signing.
// Usage: node scripts/checksums.mjs
import { createHash } from "node:crypto";
import { createReadStream, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const dir = path.resolve(root, process.env.AGENTDESK_RELEASE_DIR || "release");
const files = readdirSync(dir)
  .filter((f) => /\.(exe|zip|msi)$/i.test(f))
  .sort();
const lines = [];
for (const f of files) {
  const hash = createHash("sha256");
  await new Promise((resolve, reject) => {
    const s = createReadStream(path.join(dir, f));
    s.on("data", (c) => hash.update(c));
    s.on("end", resolve);
    s.on("error", reject);
  });
  lines.push(`${hash.digest("hex")}  ${f}`);
}
writeFileSync(path.join(dir, "SHA256SUMS.txt"), lines.join("\n") + "\n");
console.log(`Wrote ${lines.length} checksums to release/SHA256SUMS.txt`);
for (const l of lines) console.log(l);
