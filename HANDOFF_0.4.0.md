# AgentDesk 0.4.0 Handoff — 2026-11-24

Snapshot after one-by-one enhancement pass. See `docs/UPDATES.md` for the
full change log and `CHANGELOG.md` for the release history.

## Architecture (unchanged)
- Electron shell (`electron/main.js`) + Preload bridge (`electron/preload.js`)
- FastAPI backend (`backend/app/main.py`, port 8756) + llama.cpp (`:11435`)
- React/Vite UI (`frontend/`) — three panels: Sidebar / ChatPane / RightPane
- SQLite (`data/agentdesk.db`), settings DPAPI-encrypted, browser profile persistent

## Enhancements landed in this pass
- Electron: window bounds persistence, backend-log open CTA, port-in-use
  probe, configurable hotkey (settings `hotkey`), preload quit/restart/getBackendLog
- Backend: `browser_pdf` / `browser_extract` / `apply_diff` tools, session
  rewind (`POST /api/sessions/{id}/rewind-to/{message_id}`), health-weighted
  Auto routing, in-place retry with backoff (429/5xx, max 2), scope-bound
  approvals, rate limiting (240/min, `AGENTDESK_RATE_LIMIT`), structured shell
  stdout/stderr, typed `SafePathError` reasons, skills validation + mtime cache,
  MCP presets (sqlite/docker/slack/obsidian/linear/s3/hf/perplexity/openweather/postgres)
  + env scrub, missions goal/criteria/outputs, plans diff, brain sanitization,
  earnings CSV import (`POST /api/earnings/income/import-csv`), provider-health
  metrics (`GET /api/provider-health/metrics`, tokens/ttft/error classes),
  diagnostics + FTS brain (previous batch)
- Frontend: error boundary (root + app), sidebar filter, aria labels, engine pills
  from `/api/diagnostics` + health dot, settings search + Test config + Reset +
  effective-config preview, approvals filter, Earn income chart, Copy message,
  LocalModels delete lock
- SDK: Python typed errors + retry/timeout/version + gateway-token doc;
  TypeScript `AgentDeskError` + `tool_choice/response_format/seed`
- Packaging/CI: NSIS x64+ia32, portable+zip targets, GitHub Actions CI,
  pre-commit (ruff + typecheck)

## Verification commands
```
npm run typecheck
./backend/.venv/Scripts/python.exe -W error::SyntaxWarning -m py_compile backend/app/...
npm run build:ui   (run locally; esbuild spawn may be sandboxed)
```

## Known deferred (heavy / external)
- Code-signing certificate (requires purchased cert), delta updates, electron-updater wire-up
- Playwright isolated contexts per workflow, virtualized message list (react-window)
- i18n extraction, OpenTelemetry tracing, MCP workspace auto-scoping
- Streamed partial tool-argument rendering in UI
