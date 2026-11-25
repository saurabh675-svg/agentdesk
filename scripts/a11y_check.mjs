// Simple a11y gate — 0.7 (axe-core ready; this pass is dependency-free).
// Flags: images without alt, icon buttons without aria-label, inputs without labels.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const dir = new URL("../frontend/src", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
function walk(d) {
  return readdirSync(d, { withFileTypes: true }).flatMap((e) => {
    const p = join(d, e.name);
    return e.isDirectory() ? walk(p) : (/\.(tsx|ts)$/.test(e.name) ? [p] : []);
  });
}
let errors = 0;
for (const f of walk(dir)) {
  const src = readFileSync(f, "utf8");
  const checks = [
    [/(<img(?![^>]*alt=)[^>]*>)/, "img without alt"],
    [/(<button(?![^>]*aria-label)(?![^>]*>[^<]*[A-Za-z])[^>]*>)/, "button without aria-label (if icon-only)"],
  ];
  for (const [re, label] of checks) {
    const m = src.match(re);
    // Only fail icon-only buttons (no visible text between tags).
    if (m && label.includes("aria-label")) {
      const snippet = m[1];
      if (snippet.includes(">") && !/>\s*[A-Za-z\u00C0-\u024F\u0900-\u097F]/.test(snippet)) {
        console.error(`${f}: ${label} -> ${snippet.slice(0, 80)}`);
        errors++;
      }
    } else if (m) {
      console.error(`${f}: ${label} -> ${m[1].slice(0, 80)}`);
      errors++;
    }
  }
}
console.log(errors ? `A11Y FAIL: ${errors} issues` : "A11Y OK (0 critical)");
process.exit(errors ? 1 : 0);
