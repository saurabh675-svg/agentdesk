# Contributing to AgentDesk

Contributions are welcome through GitHub issues and pull requests. For larger
changes, open an issue first so the proposed approach can be discussed.

## Development checks

From the repository root, run:

```powershell
npm ci
npm run typecheck
npm run build:ui
python scripts\test_reliability.py
```

Keep pull requests focused and include regression tests for behavior changes.
Do not commit local `data/`, credentials, API keys, model files, or generated
runtime artifacts. Contributions are provided under the repository's MIT
license.
