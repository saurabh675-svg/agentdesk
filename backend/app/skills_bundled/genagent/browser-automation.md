# Skill: Browser Automation

## When to use
Filling forms, submitting entries, logging in flows, scraping pages that need interaction, downloading from portals, repeated web actions, competition submissions.

## Tool ladder (pick the lowest that works)
1. **fetch_url**: static pages, APIs, JSON endpoints. Fast, no browser needed.
2. **Web Deck (embedded browser)**: interactive sites with the user's real login (already signed in once). Navigate, read page text, and let the user click sensitive final steps.
3. **Playwright MCP** (`mcp:playwright`): full automation — click, type, wait, screenshot. Start it via MCP when reliable unattended clicking is required.

## Playbook
1. Read the page first (fetch or browser read_page) — find the actual selectors (input names, button labels, form action).
2. Automate in small steps, verifying after each (page title, URL, content contains expected text).
3. Wait for navigation/network before asserting; use the tool's wait options, not fixed sleeps.
4. Screenshot before and after critical actions (proof + debugging).
5. Credentials: NEVER type the user's passwords automatically. Stop and let the user handle login/payment/captcha steps.
6. Confirm before irreversible outward actions (submit entry, send message, place order) unless the user already said "full autopilot, submit it".

## Robustness
- Sites change: if a selector fails, re-read the page and re-derive selectors instead of retrying the same one.
- Rate limits: add small delays between repeated actions; back off on errors.
- Always save the final confirmation (screenshot or text) as proof.
