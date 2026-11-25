"""Developer-owned scaffold: one-click .vscode, CI, branch/PR tooling, Makefile."""

import json
from pathlib import Path


def scaffold_project(workspace: str, project_name: str = "agentdesk") -> dict:
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)

    files = {
        ".vscode/settings.json": json.dumps(
            {
                "files.associations": {"*.log": "log"},
                "editor.formatOnSave": True,
            },
            indent=2,
        ),
        "Makefile": "# Build, test, and lint\n\nformat: ## format code\n\t@echo \"run format\"\n\ntest: ## run tests\n\t@echo \"run tests\"\n\n.PHONY: format test\n",
        "CONTRIBUTING.md": "# How to contribute\n\n## Setup\n- install deps: `npm install` / `pip install -r requirements.txt`\n\n## Workflow\n1. Create branch: `git checkout -b feature/your-name`\n2. Make changes, run tests: `make test`\n3. Open PR: `gh pr create --title \"describe change\"`\n",
        ".github/pull_request_template.md": "## Description\n\n## Changes\n\n## Testing\n\n## Screenshots\n",
        "DEVELOPMENT.md": "# Development guide\n\n- Build: `npm run build`\n- Test: `make test`\n- Lint: `make format`\n- Run: `npm run dev`\n",
    }
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(text, encoding="utf-8")

    tools = list(Path(root).glob("**/*.{js,ts,py,json,md}"))[:100]
    return {
        "name": project_name,
        "root": str(root),
        "files_created": sorted(rel for rel in files if (root / rel).exists()),
        "files_count": len(tools),
    }
