"""Export the AgentDesk live OpenAPI 3.1 document and generate SDK clients.

The FastAPI app *is* the contract: we import it, ask for its schema and write
`docs/openapi.json`. From that single document we generate:

  * `sdk-ts/generated/client.ts`  — typed fetch client (TypeScript)
  * `sdk-py/generated/client.py`  — typed httpx client (Python)

Both are marked as generated; never hand-edit them. Re-run this script after
changing any route:

    python scripts/export_openapi.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

GENERATED_BANNER_TS = """/**
 * AUTO-GENERATED — do not edit.
 * Source: docs/openapi.json  ·  Regenerate: python scripts/export_openapi.py
 */
"""

GENERATED_BANNER_PY = '''"""AUTO-GENERATED — do not edit.

Source: docs/openapi.json  ·  Regenerate: python scripts/export_openapi.py
"""
'''


def build_schema() -> dict:
    from app.main import app

    schema = app.openapi()
    schema["openapi"] = "3.1.0"
    schema["info"]["title"] = "AgentDesk API"
    schema["info"]["description"] = (
        "Loopback HTTP/WebSocket API for the AgentDesk desktop app. "
        "Authenticate with the desktop bearer token (or the browser SDK token "
        "on /api/browser/sdk/* and /api/browser/bidi/*)."
    )
    return schema


def _ops(schema: dict) -> list[tuple[str, str, dict]]:
    out: list[tuple[str, str, dict]] = []
    for path, methods in (schema.get("paths") or {}).items():
        for method, spec in (methods or {}).items():
            if method.lower() in ("get", "post", "put", "patch", "delete"):
                out.append((method.upper(), path, spec))
    out.sort(key=lambda row: (row[1], row[0]))
    return out


def _param_names(spec: dict) -> list[str]:
    names: list[str] = []
    for param in spec.get("parameters") or []:
        schema = param.get("schema") or {}
        names.append(param.get("name") or schema.get("title") or "arg")
    body = spec.get("requestBody") or {}
    for content in (body.get("content") or {}).values():
        schema = (content or {}).get("schema") or {}
        names.append(str(schema.get("title") or "body"))
    return names


def _ts_type(spec: dict) -> str:
    schema = spec.get("schema") or {}
    if "$ref" in schema:
        return "unknown"
    kind = schema.get("type")
    return {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "array": "unknown[]",
        "object": "Record<string, unknown>",
    }.get(str(kind), "unknown")


def gen_typescript(schema: dict) -> str:
    lines = [GENERATED_BANNER_TS, ""]
    lines.append("export const BASE_URL = 'http://127.0.0.1:8756';")
    lines.append("")
    lines.append("export class AgentDeskHttpError extends Error {")
    lines.append("  constructor(public status: number, message: string) { super(message); }")
    lines.append("}")
    lines.append("")
    lines.append("export interface RequestOptions {")
    lines.append("  method: string;")
    lines.append("  path: string;")
    lines.append("  query?: Record<string, unknown>;")
    lines.append("  body?: unknown;")
    lines.append("}")
    lines.append("")
    lines.append("export function createClient(token: string, baseUrl = BASE_URL) {")
    lines.append("  const request = async (opts: RequestOptions) => {")
    lines.append("    const url = new URL(opts.path, baseUrl);")
    lines.append("    if (opts.query) Object.entries(opts.query).forEach(([k, v]) => url.searchParams.set(k, String(v)));")
    lines.append("    const res = await fetch(url.toString(), {")
    lines.append("      method: opts.method,")
    lines.append("      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },")
    lines.append("      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),")
    lines.append("    });")
    lines.append("    const text = await res.text();")
    lines.append("    const data = text ? JSON.parse(text) : null;")
    lines.append("    if (!res.ok) throw new AgentDeskHttpError(res.status, data?.detail ?? text);")
    lines.append("    return data;")
    lines.append("  };")
    lines.append("")
    lines.append("  const client = {")
    for path, methods in sorted((schema.get("paths") or {}).items()):
        for method, spec in sorted((methods or {}).items()):
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            args = _param_names(spec)
            path_params = [a for a in args if "{" + a + "}" in path]
            query_params = [a for a in args if a not in path_params and a != "body"]
            body_param = "body" if "body" in args else None
            # path template
            tpl = path
            for a in path_params:
                tpl = tpl.replace("{" + a + "}", '${encodeURIComponent(String(args["' + a + '"]))}')
            opts = [f'method: "{method.upper()}"', f"path: `{tpl}`"]
            if query_params:
                opts.append(
                    "query: { "
                    + ", ".join(f'{a}: args["{a}"]' for a in query_params)
                    + " }"
                )
            if body_param:
                opts.append("body: args.body")
            sig = ", ".join(f'{a}: any' for a in args)
            key = json.dumps(f"{method.upper()} {path}")
            lines.append(f"  {key}: (args: any = {{}}) => request({{ {', '.join(opts)} }}),")
    lines.append("  } as const;")
    lines.append("")
    lines.append("  return client;")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def gen_python(schema: dict) -> str:
    lines = [GENERATED_BANNER_PY, "", "from __future__ import annotations", "", "import json", "from typing import Any", "", ""]
    lines.append("BASE_URL = \"http://127.0.0.1:8756\"")
    lines.append("")
    lines.append("")
    lines.append("class AgentDeskError(RuntimeError):")
    lines.append("    def __init__(self, status: int, detail: str) -> None:")
    lines.append("        super().__init__(f\"HTTP {status}: {detail}\")")
    lines.append("        self.status = status")
    lines.append("        self.detail = detail")
    lines.append("")
    lines.append("")
    lines.append("class AgentDeskClient:")
    lines.append('    """Typed loopback client for the AgentDesk API (generated)."""')
    lines.append("")
    lines.append("    def __init__(self, token: str, base_url: str = BASE_URL, timeout: float = 60.0) -> None:")
    lines.append("        self._token = token")
    lines.append("        self._base_url = base_url.rstrip(\"/\")")
    lines.append("        self._timeout = timeout")
    lines.append("")
    lines.append("    def _request(self, method: str, path: str, **params: Any) -> Any:")
    lines.append("        import urllib.parse, urllib.request")
    lines.append("")
    lines.append("        url = self._base_url + path")
    lines.append("        query = {k: v for k, v in params.items() if v is not None and k != \"body\"}")
    lines.append("        if query:")
    lines.append("            url += \"?\" + urllib.parse.urlencode({k: str(v) for k, v in query.items()})")
    lines.append("        body = params.get(\"body\")")
    lines.append("        data = None")
    lines.append("        if body is not None:")
    lines.append("            data = json.dumps(body).encode(\"utf-8\")")
    lines.append("        req = urllib.request.Request(url, data=data, method=method)")
    lines.append("        req.add_header(\"Authorization\", f\"Bearer {self._token}\")")
    lines.append("        req.add_header(\"Content-Type\", \"application/json\")")
    lines.append("        try:")
    lines.append("            with urllib.request.urlopen(req, timeout=self._timeout) as resp:")
    lines.append("                raw = resp.read().decode(\"utf-8\", \"replace\")")
    lines.append("        except urllib.error.HTTPError as exc:")
    lines.append("            raw = exc.read().decode(\"utf-8\", \"replace\")")
    lines.append("            try:")
    lines.append("                detail = json.loads(raw).get(\"detail\", raw)")
    lines.append("            except Exception:")
    lines.append("                detail = raw")
    lines.append("            raise AgentDeskError(exc.code, str(detail)) from exc")
    lines.append("        except urllib.error.URLError as exc:")
    lines.append("            raise AgentDeskError(0, str(exc.reason)) from exc")
    lines.append("        if not raw:")
    lines.append("            return None")
    lines.append("        try:")
    lines.append("            return json.loads(raw)")
    lines.append("        except Exception:")
    lines.append("            return raw")
    lines.append("")
    names: set[str] = set()
    for path, methods in sorted((schema.get("paths") or {}).items()):
        for method, spec in sorted((methods or {}).items()):
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            args = _param_names(spec)
            slug = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_") or "root"
            name = f"{method.lower()}_{slug}"
            while name in names:
                name += "_x"
            names.add(name)
            arg_sig = ", ".join(f"{a}=None" for a in args)
            lines.append(f"    def {name}(self{', ' if arg_sig else ''}{arg_sig}) -> Any:")
            call = ", ".join(f"{a}={a}" for a in args)
            lines.append(f"        return self._request(\"{method.upper()}\", {json.dumps(path)}{', ' if call else ''}{call})")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    schema = build_schema()
    out_json = ROOT / "docs" / "openapi.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

    ts_path = ROOT / "sdk-ts" / "generated" / "client.ts"
    ts_path.parent.mkdir(parents=True, exist_ok=True)
    ts_path.write_text(gen_typescript(schema), encoding="utf-8")

    py_path = ROOT / "sdk-py" / "generated" / "client.py"
    py_path.parent.mkdir(parents=True, exist_ok=True)
    py_path.write_text(gen_python(schema), encoding="utf-8")

    ops = len(_ops(schema))
    print(f"wrote {out_json.relative_to(ROOT)} ({ops} operations)")
    print(f"wrote {ts_path.relative_to(ROOT)}")
    print(f"wrote {py_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
