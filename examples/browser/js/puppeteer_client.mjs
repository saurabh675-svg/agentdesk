// Connect Puppeteer to the AgentDesk browser (no Chromium download needed).
// Usage: npm i puppeteer-core && node puppeteer_client.mjs
import puppeteer from "puppeteer-core";

const CDP = process.env.AGENTDESK_CDP ?? "http://127.0.0.1:9333";

const browser = await puppeteer.connect({
  browserURL: CDP,
  defaultViewport: null,
});

const pages = await browser.pages();
const page = pages[0] ?? (await browser.newPage());
await page.goto("https://example.com", { waitUntil: "domcontentloaded" });
console.log("title:", await page.title());

// The session is the user's: Google/Kaggle/ChatGPT logins already work.
await page.goto("https://www.kaggle.com", { waitUntil: "domcontentloaded" });
console.log("kaggle title:", await page.title());

// Real mouse + keyboard, exactly like the agent does:
await page.mouse.move(120, 220);
await page.mouse.click(120, 220);
await page.keyboard.press("ArrowDown");
await page.keyboard.down("Control");
await page.keyboard.press("l");
await page.keyboard.up("Control");

await page.screenshot({ path: "agentdesk-cdp.png" });
console.log("screenshot written");
await browser.disconnect();
