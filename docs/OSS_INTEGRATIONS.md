# Open-source integrations in AgentDesk

AgentDesk is built on top of work from other open-source projects. This page
records **what we took, from where, under which licence, and what we changed** —
so the provenance of every borrowed idea stays clear.

Only permissively licensed projects (MIT / Apache-2.0) are used. No code was
copied from products with unclear or commercial terms.

| Project | Licence | What AgentDesk uses it for |
| --- | --- | --- |
| [OpenHands](https://github.com/All-Hands-AI/OpenHands) | MIT | Skill packs (desktop-electron, e2e-testing, frontend-development, frontend-api-contracts, local-stack-runtime, telemetry-analytics, pr-design-doc) and its "installed runtime vs installed artifact" testing discipline |
| [deepagents](https://github.com/langchain-ai/deepagents) | MIT | Context summarization + message eviction middleware, sub-agent architecture (profiles, stateless report-only children), skill loader shape, filesystem backends, rubric verify-loop (grader evaluates transcript before finishing) |
| [GenAgent](https://github.com/) | MIT (bundled LICENSE) | Plain-markdown skill format (converted on import), gateway failover: live /models discovery, per-model fallback, sanitised retry events, skill bundles for data analysis, browser automation, documents |
| [browser-pilot](https://github.com/) | MIT-ish (extractPage + performAction loop) | Page snapshot, numbered elements, batch fill, structured extract, JSON decision validation |
| [Playwright](https://github.com/microsoft/playwright) | Apache-2.0 | Browser automation core (our browser tool wraps it) |
| [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python) | Apache-2.0 | Optional undetected driver for anti-bot sites (`backend/app/vendor/patchright`) |
| [Camoufox](https://github.com/daijro/camoufox) | MIT | Evaluated as an optional anti-detect Firefox driver (not enabled by default) |
| [FastAPI](https://github.com/tiangolo/fastapi) / [React](https://github.com/facebook/react) / [Electron](https://github.com/electron/electron) / [Llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT / BSD / MIT | The app shell, API layer, UI and local model runtime |

## What was ported, and how

### 1. Context compaction — `backend/app/agent_context.py`

Before: the agent kept a crude sliding window. Past 20 messages, everything
between the system prompt and the last 16 was silently dropped, so long tasks
forgot their middle and repeated themselves.

After: deepagents' two techniques, reimplemented without LangChain:

* **Tool-result eviction** — old tool outputs become one-line stubs
  (`[older tool output elided - 4812 chars. First line: ...]`).
* **Summarization** — the evicted middle is summarized by the *same* provider
  that is running the turn (no tools, 700 max tokens), with a deterministic
  digest as fallback when the provider fails.

Measured on a synthetic 62-message history: **37 684 → 5 695 estimated tokens**
while keeping the system prompt, the original request and the recent turns.

A provider "context length exceeded" error now triggers an aggressive
compaction and a retry instead of failing the turn.

### 2. Sub-agents — `backend/app/subagent_profiles.py` + `spawn_agent` tool

deepagents' sub-agent idea, adapted to AgentDesk:

* Five profiles: `general-purpose`, `researcher`, `code-reviewer`,
  `test-runner`, `doc-writer`. Each has its own system prompt, its own step
  budget and a **restricted tool set** (the researcher and the reviewer never
  get a write tool).
* The child is stateless: it sees only the task you give it, and only its
  final report comes back to the parent — so delegating keeps the parent's
  context clean.
* Sub-agents reuse the **parent's tool dispatcher**, so policy checks,
  approval prompts, telemetry and the native secret scrubbing all behave
  exactly as they do for the main agent.
* `subagents.run_many()` runs several children in parallel.

Our own addition (not from upstream): the AgentDesk *sub-agent pool*
(`backend/app/subagents.py`) of long-running background agents with their own
sessions, reachable from the Sessions API. The two concepts coexist: the pool
is for long jobs you watch, the profiles are for delegate-and-continue work.

### 3. Skill packs — `backend/app/skills_import.py`

AgentDesk's skill layout (`<folder>/SKILL.md` with YAML frontmatter) is the
same one OpenHands and deepagents use, so those packs import as-is — from a
folder **or straight from a `.zip` file**, without unpacking it first.

* `GET /api/extensions/skills/scan?path=…` — preview what a folder or zip
  contains.
* `POST /api/extensions/skills/import` — install everything found.
* Plain-markdown skills (GenAgent style) are converted on import.
* 14 skills ship bundled (`backend/app/skills_bundled/`, 252 KB, each with the
  upstream licence file) and are seeded on first run without ever
  overwriting a user edit.

### 4. Browser hardening — `backend/app/tools/browser.py`

Not a port, a fix: the browser now uses the **real Chrome** the user already
has (trusted by Google sign-in and by bot checks) with a stealth init script,
and it detects human-verification challenges instead of timing out on them:

* `chromium_sandbox=True` was breaking real Chrome on this machine — the
  launcher now tries variants in order and records why each failed.
* Challenge pages never fire a `load` event, so navigation used to die with a
  timeout. Now the timeout is interpreted: the page is inspected, a
  Cloudflare/Turnstile/captcha challenge is reported as
  `HUMAN_VERIFICATION_REQUIRED`, and the agent stops looping and waits for a
  human.

## Licence files kept with the code

```
backend/app/skills_bundled/openhands/LICENSE-OpenHands.txt
backend/app/skills_bundled/deepagents/LICENSE-deepagents.txt
backend/app/skills_bundled/genagent/LICENSE-GenAgent.txt
```

Ported source files carry a short attribution line in their module docstring
(for example `backend/app/agent_context.py` and `backend/app/subagent_profiles.py`).


### 5. Browser-pilot page intelligence — `backend/app/tools/browser.py` + `browser_snapshot.py`

Ported from browser-pilot's `extractPage()` / `performAction()`:

* Numbered snapshot with rich fields (href, placeholder, checked, disabled, offscreen, scroll) — same `data-pilot-id` numbering the model sees.
* Tools: `browser_snapshot`, `browser_find_by_text`, `browser_fill_form`, `browser_extract_text`, `browser_structured_extract`, `browser_scroll_to_element`.
* Performs settle() + scrollIntoView + force-click fallback like `performAction`, with `last_error` surfaced in the next observation (`previous_error` pattern).
* Verified on a local pilot test page: 5 elements parsed, find-by-text hit Submit, fill_form wrote the email field, structured extract returned headings/links/tables.

### 6. Rubric verify-loop — `backend/app/agent_rubric.py` + `verify_work` tool

Ported from deepagents `middleware/rubric.py` (no LangChain):

* Bounded transcript (first user msg + last 30, 4000 chars each), nonce-bracketed payload with sanitised tags.
* Grader returns `satisfied / needs_revision / failed` with per-criterion gaps; consistency is validated (satisfied + failing criterion is rejected).
* Criterion set is frozen on first pass; under-coverage triggers one retry; unverified satisfied is downgraded.
* On `needs_revision`, feedback is injected as a user message and the agent resumes (max 2 revisions default). Grader runs with no tools via the same provider.
* Auto-rubric inferred from the request when `rubric_text` is blank. Enable in Settings → Auto route → Rubric verify. Live events: `rubric_evaluation` (banner in UI).

### 7. Gateway failover — `backend/app/engine/gateways.py` + routing in `agent.py`

Ported from GenAgent `gatewayManager.js`:

* Live `/models` discovery (cached 1h), `pick_models()` prefers known-good ids then `:free` then rest.
* Per-model failover: `model_not_found` / `empty_response` tries the next model on the same gateway before falling to the next gateway.
* Failures classified (`auth_failed`, `rate_limited`, `model_not_found`, `empty_response`, `timeout`, `provider_5xx`) and recorded to `provider_health` + telemetry; notices are sanitised (no keys/bodies).
* Auto routing skips cooling providers, seeds the first live model, and keeps health-weighted order.

### 8. Hermas (MIT) — scheduler NL + skill evolution

Ported `hermas/hermas/scheduler.py` (`parse_schedule` / `_compute_next`) and `hermas/hermas/evolution.py` (propose→approve→install→rollback) into `backend/app/schedule_nl.py` and `backend/app/skills_evolution.py`.

* **NL schedules** — "every weekday at 8:30", "daily 09:00", "every 15m", "in 2h" via `POST /api/automations/nl` and the `schedule_create_nl` agent tool. Fixed one bug from the source: "daily 09:00" without "at" now parses (source required "at").
* **Skill evolution gate** — propose → approve → install → rollback|reject with backup snapshot and ledger at `data/skills-evolution.json`. Tools `skill_propose`, `skill_approve`, `skill_rollback`; routes under `/api/extensions/skills/evolution`.
* Their Set-of-Marks browser (`browser.py`) matches the `browser_som.py` we already built — no change needed there.
