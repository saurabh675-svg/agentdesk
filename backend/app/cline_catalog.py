"""Free Cline plugins/extensions catalog (data, no code needed for you to add manually)."""


CATALOG = [
    {"name": "Cline Git Helper", "command": "git checkout -b cline/fix-x && git push -u origin HEAD", "type": "terminal", "desc": "Branches, commits, pushes from chat"},
    {"name": "Cline Code Review", "command": "git diff --stat && git diff HEAD^ --unified=0", "type": "terminal", "desc": "Pre-push diff review"},
    {"name": "Cline API Saver", "command": "gh api repos/owner/repo/pulls?state=all -f 'head=repo:branch' -f 'base=main' -F '[\"files\"][]=README.md'", "type": "terminal", "desc": "Generate PRs"},
    {"name": "Cline Code Runner", "command": "dotnet run --project src/Web", "type": "terminal", "desc": "Run projects"},
    {"name": "Cline GitHub Diff", "command": "gh api repos/owner/repo/commits -f 'since=2026-11-01' -f 'per_page=10'", "type": "terminal", "desc": "Recent commits"},
    {"name": "Cline Web Researcher", "command": "curl -s 'https://api.perplexity.ai/search/query' -H 'Authorization: Bearer $PERPLEXITY_API_KEY' -d '{\"query\": \"$QUERY\"}'", "type": "terminal", "desc": "Research queries"},
    {"name": "Cline API Docs Agent", "command": "curl -s https://api.openai.com/v1/files | jq '{data: [.data[].filename]}'", "type": "terminal", "desc": "OpenAI file listing"},
    {"name": "Cline Sdk Search", "command": "npx -y tsc --noEmit && npx vite build", "type": "terminal", "desc": "Build/check frontend"},
    {"name": "Cline Sort Projects", "command": "mkdir -p codex-rename && git mv src src-legacy && git mv src-legacy/app.ts src/app.ts 2>/dev/null || true", "type": "terminal", "desc": "Refactor names"},
    {"name": "Cline Todo Writer", "command": "echo '1. take screenshot' >> plan.md", "type": "terminal", "desc": "Track tasks in Markdown"},
]


def install_free_extensions() -> list[dict]:
    return CATALOG
