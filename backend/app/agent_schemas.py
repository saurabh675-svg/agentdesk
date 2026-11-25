"""Tool schema registry (extracted from agent.py for the 0.5 agent split).

Every entry is an OpenAI-style function-calling schema. The runner imports
this module; nothing here may import ``agent`` (no cycles).
"""

from __future__ import annotations

from . import subagent_profiles as subagents

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and folders in the workspace as a tree.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative folder, default '.'"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from the workspace, with line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace one unique occurrence of old_string with new_string in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Grep search across workspace files for a substring or regex pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "String or regex pattern to search for"},
                    "path": {"type": "string", "description": "Folder or file to search in, default '.'"},
                    "regex": {"type": "boolean", "description": "Whether query is a regex, default false"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "openclaw_run",
            "description": "Execute a task via OpenClaw Gateway or CLI for multi-channel personal agent automation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task or instruction for OpenClaw"},
                    "mode": {"type": "string", "enum": ["run", "status", "skills"], "description": "Execution mode"},
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cline_run",
            "description": "Dispatch a precision coding or refactoring task to the installed Cline agent CLI with auto-approval and file diffing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Coding instruction or refactoring goal for Cline"},
                    "mode": {"type": "string", "enum": ["act", "plan"], "description": "Execution mode (default: act)"},
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "openhands_run",
            "description": "Dispatch a benchmark SWE engineering or repository task to an OpenHands runner (via local server on port 3000 or Docker).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "SWE task or feature requirement for OpenHands"},
                    "action": {"type": "string", "enum": ["run", "status", "start_container"], "description": "Action to perform"},
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_dependency",
            "description": "Self-healing tool to auto-install a missing Python package via pip or a Windows CLI tool via winget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["python", "winget"], "description": "Package type"},
                    "name": {"type": "string", "description": "Package name or Winget ID"},
                },
                "required": ["type", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_search",
            "description": "Search the MCP registry for servers that provide tools for a missing capability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query, e.g. postgres, sqlite, docker, github, slack"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_install",
            "description": "Install and hot-load a new MCP tool server dynamically without restarting the application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_id": {"type": "string", "description": "Unique identifier for the server"},
                    "name": {"type": "string", "description": "Friendly display name"},
                    "command": {"type": "string", "description": "npx or uvx"},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Arguments for command"},
                },
                "required": ["server_id", "command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "power_automate_flow",
            "description": "Run a Microsoft Power Automate Desktop flow headlessly with optional JSON input arguments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flow_name": {"type": "string", "description": "Name of the Power Automate Desktop flow"},
                    "input_args": {"type": "object", "description": "Key-value input variables for the flow"},
                },
                "required": ["flow_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "windows_uia_inspect",
            "description": "Inspect accessible UI elements and buttons of a Windows app using native Windows UI Automation (Win32 UIA).",
            "parameters": {
                "type": "object",
                "properties": {
                    "window_title": {"type": "string", "description": "Title or partial title of the target window"},
                },
                "required": ["window_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "windows_schtask",
            "description": "Create, list, run, or delete persistent background Windows Scheduled Tasks (schtasks) that run even when AgentDesk is closed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "create", "delete", "run"], "description": "Action to perform"},
                    "task_name": {"type": "string", "description": "Name for the task (e.g. DailyBrief, CodeRadar)"},
                    "schedule": {"type": "string", "enum": ["DAILY", "HOURLY", "MINUTE", "ONLOGON", "WEEKLY"], "description": "Schedule frequency"},
                    "time": {"type": "string", "description": "24-hour time HH:MM (e.g. 09:00)"},
                    "command": {"type": "string", "description": "Optional custom command to run headlessly"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "freeai_gpu_run",
            "description": "Offload Python, PyTorch, or CUDA compute to a cloud NVIDIA A100 GPU (20GB VRAM) via Free.ai (uses daily 30K free tokens).",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "Python or CUDA script to execute on the A100 GPU"},
                    "timeout": {"type": "integer", "description": "Maximum execution time in seconds (default 120)"},
                },
                "required": ["script"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "self_learn_skill",
            "description": "Manually compile verified instructions, workflows, and procedures into a permanent reusable skill.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Skill name"},
                    "description": {"type": "string", "description": "Short summary of what this skill does"},
                    "instructions": {"type": "string", "description": "Markdown instructions and code examples"},
                },
                "required": ["name", "instructions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the workspace. Requires user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string", "description": "Optional relative working directory"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Open a URL in the built-in browser and show it to the user.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element in the browser using a CSS selector.",
            "parameters": {
                "type": "object",
                "properties": {"selector": {"type": "string"}},
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": "Type into a browser input using a CSS selector, optionally pressing Enter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                    "submit": {"type": "boolean"},
                },
                "required": ["selector", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_elements",
            "description": "List visible interactive elements (links, buttons, inputs) with stable indices. Prefer this over guessing CSS selectors or coordinates; then use browser_click_element / browser_type_element with the index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max elements (default 60)."},
                    "annotate": {"type": "boolean", "description": "Overlay numbered marks on the screenshot."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click_element",
            "description": "Click a browser element by the index returned from browser_elements (reliable self-clicking).",
            "parameters": {
                "type": "object",
                "properties": {"index": {"type": "integer"}},
                "required": ["index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_type_element",
            "description": "Type into a browser element by index from browser_elements, optionally pressing Enter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "text": {"type": "string"},
                    "submit": {"type": "boolean"},
                },
                "required": ["index", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_press",
            "description": "Press a keyboard key in the browser page, e.g. Enter, Escape, Tab.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_select",
            "description": "Select an option in a dropdown by value.",
            "parameters": {
                "type": "object",
                "properties": {"selector": {"type": "string"}, "value": {"type": "string"}},
                "required": ["selector", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_scroll",
            "description": "Scroll the current page vertically.",
            "parameters": {
                "type": "object",
                "properties": {"delta_y": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_wait",
            "description": "Wait for a selector or for literal text to appear on the page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                    "timeout": {"type": "integer", "description": "Milliseconds, default 20000"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_links",
            "description": "List links on the current page (text and href).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_read",
            "description": "Read the visible text of the current page.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_pdf",
            "description": "Save the current page as a PDF to data/uploads and return its path.",
            "parameters": {"type": "object", "properties": {"filename": {"type": "string", "description": "PDF filename, default page.pdf"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_extract",
            "description": "Extract HTML tables from the current page as Markdown tables.",
            "parameters": {"type": "object", "properties": {"max_tables": {"type": "integer", "description": "Maximum tables to extract, default 5"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_snapshot",
            "description": "browser-pilot style page snapshot: URL, title, scroll position, readable main text and a numbered element list with rich fields (href, placeholder, checked, disabled, offscreen). Use this before any click/type to ground targets precisely.",
            "parameters": {"type": "object", "properties": {"text_limit": {"type": "integer", "description": "Max chars of readable text, default 3600"}, "element_limit": {"type": "integer", "description": "Max elements, default 120"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_find_by_text",
            "description": "Find elements whose visible text contains the given phrase (case-insensitive). Use when you know what you want to click but not its index.",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fill_form",
            "description": "Fill multiple indexed fields in one call. Each field has an index from browser_snapshot/browser_elements, text to enter, and optional submit=true to press Enter.",
            "parameters": {"type": "object", "properties": {"fields": {"type": "array", "items": {"type": "object", "properties": {"index": {"type": "integer"}, "text": {"type": "string"}, "submit": {"type": "boolean"}}, "required": ["index", "text"]}}}, "required": ["fields"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_extract_text",
            "description": "Read text from one indexed element, or from the page main if no index is given (browser-pilot extract action).",
            "parameters": {"type": "object", "properties": {"index": {"type": "integer", "description": "Optional indexed element to read"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_structured_extract",
            "description": "Structured extraction: headings, links, tables and key text as JSON. Prefer over browser_read when you need machine-readable facts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_scroll_to_element",
            "description": "Scroll an indexed element into view without pixel guessing.",
            "parameters": {"type": "object", "properties": {"index": {"type": "integer"}}, "required": ["index"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_diff",
            "description": "Apply a multi-file patch. Each entry has path, old_string and new_string (exact unique match).",
            "parameters": {"type": "object", "properties": {"patches": {"type": "array", "items": {"type": "object", "properties": {"path": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}}, "required": ["path", "old_string", "new_string"]}}}, "required": ["patches"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_back",
            "description": "Go back one page in the browser.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_forward",
            "description": "Go forward one page in the browser.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_set_of_marks",
            "description": "Set-of-Marks grounding: annotates the screenshot with numbered badges matching browser_elements indices. Call, then reference a number in your browser_click_element call.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_create_nl",
            "description": "Create a scheduled automation from natural language ('every weekday at 8:30', 'daily 09:00', 'every 15m', 'in 2h'). Hermas-style; the prompt is run through the normal agent loop when due.",
            "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "prompt": {"type": "string"}, "schedule": {"type": "string", "description": "Natural-language schedule text"}}, "required": ["prompt", "schedule"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_propose",
            "description": "Propose a new skill for approval (Hermas evolution gate). Nothing installs without approve. files is a map of relative path -> content (SKILL.md plus optional references).",
            "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "files": {"type": "object"}, "score": {"type": "number"}}, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_approve",
            "description": "Approve and install a proposed skill by id (snapshots any prior skill for rollback).",
            "parameters": {"type": "object", "properties": {"skill_id": {"type": "string"}}, "required": ["skill_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_rollback",
            "description": "Roll back an installed skill to its previous version.",
            "parameters": {"type": "object", "properties": {"skill_id": {"type": "string"}}, "required": ["skill_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_work",
            "description": "Ask a grader to check your work so far against a rubric (what done means). Returns satisfied / needs_revision with specific gaps. Use after edits, refactors, or before claiming a task is done. If omitted, an auto-rubric is inferred from your request.",
            "parameters": {"type": "object", "properties": {"rubric": {"type": "string", "description": "Optional explicit rubric. If omitted, one is inferred."}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spawn_agent",
            "description": (
                "Delegate a self-contained task to a specialised sub-agent and get its final "
                "report back. The sub-agent runs its own loop with its own step budget and a "
                "restricted tool set, so a long or context-heavy job does not flood your "
                "context. You only receive its final report - intermediate steps are not shown "
                "to the user, so relay what matters in your own answer. Available sub-agents:\n"
                + subagents.profile_listing()
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "profile": {
                        "type": "string",
                        "enum": list(subagents.PROFILES.keys()),
                        "description": "Which sub-agent to run.",
                    },
                    "task": {
                        "type": "string",
                        "description": (
                            "The complete objective. State exactly what to do and what the final "
                            "report must contain. The sub-agent cannot ask questions."
                        ),
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional background the sub-agent cannot see (paths, findings, constraints).",
                    },
                },
                "required": ["profile", "task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List installed skills with their descriptions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live web with Firecrawl and return titles, descriptions and URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query, natural language or quoted phrases.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (1-20, default 10).",
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "use_skill",
            "description": "Load the full instructions of an installed skill by name.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pc_info",
            "description": "Report OS, CPU, RAM, disk, hostname, Python, and available local tools (fast, no extra calls).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_external",
            "description": "Open a URL in the user's system browser (external Chrome/Edge) using its existing profile. Use for signing in on a real full-featured Chrome browser.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "URL to open in the external browser."}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_set_zoom",
            "description": "Set the inbuilt Chromium page zoom level (e.g. 1.5 = 150%, 0.8 = 80%).",
            "parameters": {
                "type": "object",
                "properties": {"factor": {"type": "number", "description": "Zoom factor: 1.0 = 100%, >1.0 enlarges, <1.0 shrinks."}},
                "required": ["factor"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kaggle_credits",
            "description": "Check the PC for the Kaggle CLI, API keys/env vars, and Kaggle account state (work fast in background).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "credentials_check",
            "description": (
                "Check the PC for all saved/stored credentials: Kaggle config+env+CLI, "
                "per-gateway API keys, OpenRouter key, Firecrawl key, GitHub token. Reports which "
                "are set, where they live, and any suspect/missing ones. Use this when the user "
                "asks to check credentials or API keys, or to see if something needs fixing."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_pr_summary",
            "description": "List open/recent pull requests from a GitHub repo (needs GITHUB_TOKEN or Settings GitHub token).",
            "parameters": {
                "type": "object",
                "properties": {"repo": {"type": "string", "description": "owner/repo, e.g. openai/openai"}},
                "required": ["repo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show the current branch, status, and recent commit summary in the workspace.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_automation",
            "description": "Create a persistent background automation that re-runs a prompt on a fixed interval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Human-readable name."},
                    "prompt": {"type": "string", "description": "Prompt the agent runs when the job is due."},
                    "interval_minutes": {
                        "type": "integer",
                        "description": "Repeat interval in minutes (5-14400, default 15).",
                    },
                },
                "required": ["name", "prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_automations",
            "description": "List persistent background automations and their status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scaffold_project",
            "description": "Scaffold a developer project in the workspace: .vscode settings, Makefile, CI templates, CONTRIBUTING.md, DEVELOPMENT.md.",
            "parameters": {"type": "object", "properties": {"project_name": {"type": "string"}}},
            "required": ["project_name"],
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_health_log",
            "description": "Read recent backend/agent health log errors to self-diagnose and fix crashes.",
            "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "max lines, default 50"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "brain_add",
            "description": "Add a note to the global brain (second brain) — persists across all AgentDesk sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "link": {"type": "string", "description": "Optional URL/page link"},
                },
                "required": ["title", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "brain_search",
            "description": "Search the global brain notes by query.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "brain_context",
            "description": "Return the latest global brain context (up to 60k chars).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_use_run",
            "description": "Run an autonomous Browser-Use task on the browser (visit sites, click, extract text). Needs an OpenAI-compatible key for Browser-Use.",
            "parameters": {
                "type": "object",
                "properties": {"prompt": {"type": "string", "description": "Browser automation prompt, e.g. 'Find the top news on Hacker News and summarize it.'"}},
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "askui_run",
            "description": "Run AskUI Vision Agent task on desktop/mobile (see AskUI preset in Settings -> MCP).",
            "parameters": {
                "type": "object",
                "properties": {"prompt": {"type": "string", "description": "AskUI task prompt, e.g. 'Take a screenshot of my desktop and describe it.'"}},
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "interpreter_run",
            "description": "Run Interpreter Desktop task: PDFs, files, research, desktop tasks. Needs `interpreter` CLI installed.",
            "parameters": {
                "type": "object",
                "properties": {"prompt": {"type": "string", "description": "Interpreter Desktop prompt, e.g. 'Open the attached PDF and summarize it.'"}},
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "power_automate_run",
            "description": "Run or open a Power Automate Desktop flow/dismiss. Needs PAD installed; also bridges via `PAD` command-line flows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "open_flow | run_flow | list_flows | dismiss_flow"},
                    "name": {"type": "string", "description": "Flow name or ID"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tiny_brain",
            "description": "Always-on tiny local decision/brain model via llama.cpp (fast small model for quick calls).",
            "parameters": {
                "type": "object",
                "properties": {"prompt": {"type": "string", "description": "Short decision/brain prompt, e.g. 'What is the capital of France?'"}},
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_automation",
            "description": "Cancel an existing automation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Automation id from list_automations (or name as fallback)."}
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_screenshot",
            "description": "Capture the desktop screen and show it in the Screen panel.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_click",
            "description": "Click at desktop coordinates. Requires approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"]},
                    "clicks": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_type",
            "description": "Type text on the desktop keyboard. Requires approval.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_hotkey",
            "description": "Press a keyboard shortcut, e.g. ['ctrl','s']. Requires approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_scroll",
            "description": "Scroll the desktop with the mouse wheel. Requires approval.",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "integer"}},
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_elements",
            "description": "List accessible controls (buttons, fields, tabs) of the foreground desktop window via Windows UI Automation, with indices and bounds. Prefer this over raw coordinate clicking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "window_title": {"type": "string", "description": "Partial window title; defaults to the foreground window."},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "windows_uia_click",
            "description": "Click a named desktop control via Windows UI Automation (reliable, no coordinate guessing). Requires approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "window_title": {"type": "string"},
                    "element_name": {"type": "string"},
                },
                "required": ["window_title", "element_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_create",
            "description": "Create a structured plan with steps for a complex task, then execute step by step.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short plan name."},
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of step titles (strings) or objects {title, detail}.",
                    },
                    "session_id": {"type": "integer"},
                },
                "required": ["name", "steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_update_step",
            "description": "Mark a plan step as pending/in_progress/done/blocked and store its result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {"type": "string"},
                    "step": {"type": "integer", "description": "Zero-based step index."},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "done", "blocked"]},
                    "result": {"type": "string"},
                },
                "required": ["plan_id", "step"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_list",
            "description": "List active or all plans.",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string", "description": "Optional filter: active, complete."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_chatbot",
            "description": (
                "Ask the signed-in ChatGPT or Gemini web chat a question through the built-in "
                "model lacks. The prompt leaves this machine, so it requires approval."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "site": {"type": "string", "enum": ["chatgpt", "gemini"]},
                    "prompt": {"type": "string", "description": "The full question to send."},
                },
                "required": ["site", "prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earnings_radar",
            "description": (
                "Rank free-first earning opportunities from the global catalog (services, AI data work, "
                "content, digital products, security, teaching). Optionally run a live Firecrawl scan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Optional live search/query filter, e.g. 'AI automation freelance'."},
                    "category": {"type": "string", "description": "Optional category: Services, Data & AI, Content, Digital products, Security, Teaching."},
                    "limit": {"type": "integer", "description": "How many ranked opportunities (default 8)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earnings_launch",
            "description": "Turn an opportunity id from earnings_radar into a venture with a 30-day company plan and role-based tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "opportunity_id": {"type": "string"},
                    "name": {"type": "string", "description": "Optional venture/company name."},
                    "currency": {"type": "string", "description": "Currency for the first target, e.g. USD or INR."},
                },
                "required": ["opportunity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earnings_brief",
            "description": "Founder briefing: next highest-priority tasks, locally drafted outreach/delivery assets, KPIs and past lessons.",
            "parameters": {
                "type": "object",
                "properties": {"venture_id": {"type": "integer", "description": "Optional venture id; omit for all active ventures."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earnings_complete_task",
            "description": "Mark a venture task done, optionally log income, and save a lesson for recursive learning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "venture_id": {"type": "integer"},
                    "task_id": {"type": "integer"},
                    "result": {"type": "string", "description": "What was produced / outcome."},
                    "income": {"type": "number", "description": "Optional amount earned by this task."},
                    "currency": {"type": "string"},
                    "lesson": {"type": "string", "description": "Optional lesson to improve future plans."},
                },
                "required": ["venture_id", "task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earnings_log_income",
            "description": "Log real income to the earnings ledger. Only record money actually received or invoiced.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "source": {"type": "string"},
                    "notes": {"type": "string"},
                    "currency": {"type": "string"},
                    "venture_id": {"type": "integer"},
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earnings_learn",
            "description": "Save a durable business/earning lesson that is injected into future plans and turns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lesson": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "venture_id": {"type": "integer"},
                },
                "required": ["lesson"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earnings_autopilot",
            "description": "Read/toggle earnings autopilot or run one draft tick. Autopilot only drafts local assets; it never sends or spends.",
            "parameters": {
                "type": "object",
                "properties": {"action": {"type": "string", "enum": ["status", "on", "off", "tick"]}},
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "earnings_report",
            "description": "Full earnings dashboard data: income, active ventures, task counts, best opportunities, next actions and lessons.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
