"""Global earnings engine: opportunity radar, venture OS, income ledger, recursive learning.

The engine is deterministic and free-first. It ranks realistic ways to earn from a catalog,
turns a chosen opportunity into a 30-day company plan with role-based tasks, drafts outreach
and delivery assets locally (autopilot), tracks income, and feeds lessons back into the agent
system prompt so later plans improve.

Guardrails: the engine never sends messages, spends money, creates accounts, or makes payouts.
Those actions stay with the user or require explicit approval in chat.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from .config import DATA_DIR
from .engine.firecrawl import search_web

EARNINGS_DB = DATA_DIR / "earnings.db"
SETTINGS_FILE = DATA_DIR / "earnings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "currency": "USD",
    "skills": ["python", "automation", "writing", "research"],
    "weekly_hours": 10,
    "starting_capital": 0,
    "autopilot": False,
    "country": "Global",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS ventures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id TEXT NOT NULL,
    name TEXT NOT NULL,
    mission TEXT NOT NULL DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS venture_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venture_id INTEGER NOT NULL,
    phase TEXT NOT NULL,
    role TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    acceptance TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 2,
    estimate_min INTEGER NOT NULL DEFAULT 30,
    metric TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    draft TEXT,
    result TEXT,
    created_at REAL NOT NULL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_tasks_venture ON venture_tasks(venture_id, status, priority);
CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venture_id INTEGER,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    source TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS learning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venture_id INTEGER,
    lesson TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    uses INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    signals TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL
);
"""


def _conn() -> sqlite3.Connection:
    EARNINGS_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(EARNINGS_DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init() -> None:
    con = _conn()
    con.executescript(SCHEMA)
    con.commit()
    con.close()
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(json.dumps(DEFAULT_SETTINGS, indent=2), encoding="utf-8")


def get_settings() -> dict[str, Any]:
    init()
    settings = dict(DEFAULT_SETTINGS)
    try:
        settings.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return settings


def set_settings(patch: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    for key in ("currency", "skills", "weekly_hours", "starting_capital", "autopilot", "country"):
        if key in patch:
            settings[key] = patch[key]
    if isinstance(settings.get("skills"), str):
        settings["skills"] = [s.strip() for s in settings["skills"].split(",") if s.strip()]
    settings["autopilot"] = bool(settings.get("autopilot"))
    try:
        settings["weekly_hours"] = max(1, min(80, int(settings.get("weekly_hours") or 10)))
    except (TypeError, ValueError):
        settings["weekly_hours"] = 10
    try:
        settings["starting_capital"] = max(0.0, float(settings.get("starting_capital") or 0))
    except (TypeError, ValueError):
        settings["starting_capital"] = 0.0
    settings["currency"] = str(settings.get("currency") or "USD").upper()[:8]
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return settings


# --------------------------------------------------------------------------- catalog


# Catalog opportunities are platform-based rather than link-based. Give every
# venture a real site to open in the built-in browser by deriving it from the
# first known platform (live-web opportunities keep their own URL).
PLATFORM_URLS: dict[str, str] = {
    "reddit r/forhire": "https://www.reddit.com/r/forhire/",
    "notion marketplace": "https://www.notion.so/templates",
    "tiktok creative exchange": "https://creativecenter.tiktok.com/",
    "instagram reels": "https://www.instagram.com/",
    "onlinejobs.ph": "https://www.onlinejobs.ph/",
    "dataannotation": "https://www.dataannotation.tech/",
    "surge ai": "https://surgehq.ai/",
    "product hunt": "https://www.producthunt.com/",
    "local business groups": "",
    "local groups": "",
    "upwork": "https://www.upwork.com/",
    "fiverr": "https://www.fiverr.com/",
    "freelancer": "https://www.freelancer.com/",
    "linkedin": "https://www.linkedin.com/",
    "superprof": "https://www.superprof.com/",
    "preply": "https://preply.com/",
    "wyzant": "https://www.wyzant.com/",
    "rev": "https://www.rev.com/",
    "gotranscript": "https://www.gotranscript.com/",
    "gumroad": "https://gumroad.com/",
    "etsy": "https://www.etsy.com/",
    "youtube": "https://www.youtube.com/",
    "tiktok": "https://www.tiktok.com/",
    "substack": "https://substack.com/",
    "beehiiv": "https://www.beehiiv.com/",
    "hackerone": "https://www.hackerone.com/",
    "bugcrowd": "https://www.bugcrowd.com/",
    "intigriti": "https://www.intigriti.com/",
    "outlier": "https://www.outlier.ai/",
    "braintrust": "https://www.braintrust.dev/",
    "contra": "https://contra.com/",
    "github": "https://github.com/",
    "gengo": "https://gengo.com/",
    "proz": "https://www.proz.com/",
    "belay": "https://www.belay.com/",
    "billo": "https://www.billo.app/",
    "reddit": "https://www.reddit.com/",
    "facebook": "https://www.facebook.com/",
    "x": "https://x.com/",
}


def _opportunity_url(opp: dict[str, Any]) -> str:
    if opp.get("url"):
        return str(opp["url"])
    for platform in opp.get("platforms", []):
        key = str(platform).strip().lower()
        for prefix, url in PLATFORM_URLS.items():
            if key.startswith(prefix) and url:
                return url
    return ""


def _row(opp: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": opp["id"],
        "title": opp["title"],
        "category": opp["category"],
        "summary": opp["summary"],
        "platforms": opp["platforms"],
        "startup_cost": opp["startup_cost"],
        "time_to_cash_days": opp["time_to_cash_days"],
        "automation": opp["automation"],
        "demand": opp["demand"],
        "competition": opp["competition"],
        "risk": opp["risk"],
        "skills": opp["skills"],
        "offer": opp["offer"],
        "pricing": opp["pricing"],
        "first_steps": opp["first_steps"],
        "tags": opp.get("tags", []),
        "source": "catalog",
        "url": _opportunity_url(opp),
    }


CATALOG: list[dict[str, Any]] = [
    {
        "id": "ai-automation-agency",
        "title": "AI workflow automation for small businesses",
        "category": "Services",
        "summary": "Automate one painful workflow (leads, invoices, support, reports) for local or online businesses using Python, APIs and LLM steps.",
        "platforms": ["Upwork", "Fiverr", "LinkedIn", "local business groups"],
        "startup_cost": 0,
        "time_to_cash_days": 7,
        "automation": 90,
        "demand": 92,
        "competition": 62,
        "risk": 20,
        "skills": ["python", "automation", "api", "sales"],
        "offer": "Free 30-minute workflow audit, then a fixed-price automation package.",
        "pricing": "$150-$1,500 per workflow, $100-$500/month maintenance",
        "first_steps": [
            "Pick one niche (clinics, real estate, e-commerce) and one workflow.",
            "Build a 2-minute demo that turns a spreadsheet/email into an automated result.",
            "Write a one-page offer with before/after time saved.",
        ],
        "tags": ["b2b", "remote", "high-ticket"],
    },
    {
        "id": "web-scraping-service",
        "title": "Web scraping and data enrichment service",
        "category": "Services",
        "summary": "Deliver clean lead lists, competitor prices, market data and research datasets with scripts plus a quality report.",
        "platforms": ["Upwork", "Fiverr", "Freelancer"],
        "startup_cost": 0,
        "time_to_cash_days": 3,
        "automation": 96,
        "demand": 82,
        "competition": 55,
        "risk": 30,
        "skills": ["python", "scraping", "data"],
        "offer": "A sample 100-row dataset for free, then pay per 1,000 clean rows.",
        "pricing": "$25-$300 per dataset",
        "first_steps": [
            "Choose 3 public, permitted data categories (jobs, prices, directories).",
            "Build a reusable scraper + CSV cleaner + validation report.",
            "Publish two anonymized sample datasets as proof.",
        ],
        "tags": ["remote", "fast-cash", "compliance"],
    },
    {
        "id": "excel-sheets-automation",
        "title": "Excel and Google Sheets automation",
        "category": "Services",
        "summary": "Turn messy spreadsheets into automated dashboards, importers, formulas and Apps Script workflows for small teams.",
        "platforms": ["Fiverr", "Upwork", "Facebook groups"],
        "startup_cost": 0,
        "time_to_cash_days": 3,
        "automation": 88,
        "demand": 76,
        "competition": 45,
        "risk": 12,
        "skills": ["sheets", "excel", "automation"],
        "offer": "Fix one broken spreadsheet free for the first 3 clients; then flat-fee builds.",
        "pricing": "$30-$250 per sheet/dashboard",
        "first_steps": [
            "Collect 3 before/after spreadsheet demos.",
            "Create gig titles around 'dashboard', 'automation', 'inventory', 'payroll'.",
            "Offer a 24-hour turnaround.",
        ],
        "tags": ["fast-cash", "low-risk"],
    },
    {
        "id": "website-bugfix",
        "title": "Small website fixes and landing pages",
        "category": "Services",
        "summary": "Fix layout, forms, speed and mobile bugs or ship a one-page landing page for creators and small businesses.",
        "platforms": ["Fiverr", "Upwork", "Reddit r/forhire"],
        "startup_cost": 0,
        "time_to_cash_days": 2,
        "automation": 72,
        "demand": 88,
        "competition": 72,
        "risk": 15,
        "skills": ["html", "css", "javascript", "wordpress"],
        "offer": "One-page site or bug fix at a fixed price, delivered in 48 hours.",
        "pricing": "$25-$200 per fix, $150-$500 per landing page",
        "first_steps": [
            "Build 3 portfolio pages (local business, SaaS, personal brand).",
            "List concrete fixes: mobile overflow, broken form, slow images, SSL.",
            "Bid on 5 small jobs with a 1-sentence diagnosis.",
        ],
        "tags": ["fast-cash", "remote"],
    },
    {
        "id": "ai-chatbot-setup",
        "title": "AI chatbot and support-bot setup",
        "category": "Services",
        "summary": "Install a branded support bot trained on a business's docs, FAQ and policies, with handoff and analytics.",
        "platforms": ["Upwork", "Fiverr", "LinkedIn"],
        "startup_cost": 0,
        "time_to_cash_days": 5,
        "automation": 90,
        "demand": 85,
        "competition": 58,
        "risk": 30,
        "skills": ["llm", "python", "prompting", "support"],
        "offer": "A working demo bot on the business's own FAQ in 48 hours.",
        "pricing": "$200-$1,200 setup + $50-$200/month",
        "first_steps": [
            "Pick a niche with public FAQs (clinics, gyms, e-commerce).",
            "Build a demo bot with a clean widget and source citations.",
            "Send 10 demos with a 60-second Loom-style walkthrough.",
        ],
        "tags": ["b2b", "recurring", "high-demand"],
    },
    {
        "id": "code-review-service",
        "title": "Code review, tests and bug fixing",
        "category": "Services",
        "summary": "Review pull requests, add missing tests, fix small bugs and clean up scripts for solo founders and agencies.",
        "platforms": ["Upwork", "Contra", "GitHub"],
        "startup_cost": 0,
        "time_to_cash_days": 4,
        "automation": 75,
        "demand": 68,
        "competition": 52,
        "risk": 15,
        "skills": ["python", "javascript", "testing", "git"],
        "offer": "A free 5-point review of one pull request, then a paid review/test package.",
        "pricing": "$40-$400 per review or test package",
        "first_steps": [
            "Pick 2 stacks you know deeply (e.g. Python/FastAPI, React).",
            "Publish a sample review with severity labels and fixes.",
            "Offer a 48-hour turnaround with a short video summary.",
        ],
        "tags": ["developer", "remote"],
    },
    {
        "id": "google-maps-leads",
        "title": "Local lead generation and outreach lists",
        "category": "Services",
        "summary": "Build verified local business lists with contact details, websites and personalized opening lines for agencies and sales teams.",
        "platforms": ["Fiverr", "Upwork", "LinkedIn"],
        "startup_cost": 0,
        "time_to_cash_days": 2,
        "automation": 95,
        "demand": 78,
        "competition": 58,
        "risk": 35,
        "skills": ["research", "scraping", "data"],
        "offer": "10 free verified leads in one niche, then per-100 pricing.",
        "pricing": "$20-$150 per 100 leads",
        "first_steps": [
            "Choose one niche + city and define 6 data fields.",
            "Build a repeatable verification checklist (site, phone, socials).",
            "Publish a sample sheet with a privacy/compliance note.",
        ],
        "tags": ["fast-cash", "b2b", "compliance"],
    },
    {
        "id": "presentation-design",
        "title": "AI-assisted pitch decks and presentations",
        "category": "Services",
        "summary": "Produce clean investor, sales or training decks with copy, visuals and speaker notes in 48 hours.",
        "platforms": ["Fiverr", "Upwork", "Etsy templates"],
        "startup_cost": 0,
        "time_to_cash_days": 2,
        "automation": 70,
        "demand": 78,
        "competition": 68,
        "risk": 12,
        "skills": ["design", "writing", "slides"],
        "offer": "A free redesign of 2 slides to prove the style, then a full deck.",
        "pricing": "$50-$450 per deck",
        "first_steps": [
            "Create 3 deck styles with before/after slides.",
            "List clear packages: 10-slide, 20-slide, redesign.",
            "Ask 5 founders for a 2-slide test.",
        ],
        "tags": ["fast-cash", "low-risk"],
    },
    {
        "id": "resume-linkedin",
        "title": "Resume and LinkedIn optimization",
        "category": "Services",
        "summary": "Rewrite resumes and LinkedIn profiles for tech, healthcare and finance roles, with ATS-friendly formatting.",
        "platforms": ["Fiverr", "Upwork", "LinkedIn"],
        "startup_cost": 0,
        "time_to_cash_days": 2,
        "automation": 65,
        "demand": 86,
        "competition": 76,
        "risk": 18,
        "skills": ["writing", "recruiting", "research"],
        "offer": "Free ATS scan and one rewritten summary, then the full package.",
        "pricing": "$25-$150 per profile",
        "first_steps": [
            "Pick one role family and collect 5 real job descriptions.",
            "Create a before/after sample with keyword and bullet improvements.",
            "Offer 24-hour delivery and one revision.",
        ],
        "tags": ["fast-cash", "low-risk"],
    },
    {
        "id": "rlhf-data-annotation",
        "title": "AI evaluation and data annotation",
        "category": "Data & AI",
        "summary": "Get paid to rate model answers, label data and red-team AI outputs in your domains of expertise.",
        "platforms": ["Outlier", "Braintrust", "DataAnnotation", "Surge AI"],
        "startup_cost": 0,
        "time_to_cash_days": 2,
        "automation": 20,
        "demand": 90,
        "competition": 62,
        "risk": 20,
        "skills": ["english", "coding", "domain-expertise"],
        "offer": "Pass one assessment in your strongest domain and complete paid task batches.",
        "pricing": "$15-$200/hour depending on expertise",
        "first_steps": [
            "Pick the highest-paying domain you can defend (code, medicine, law, finance).",
            "Apply to 3 platforms with the same strong writing sample.",
            "Track acceptance rate and aim for high-quality batches.",
        ],
        "tags": ["remote", "fast-cash", "no-investment"],
    },
    {
        "id": "transcription-captioning",
        "title": "Transcription, captions and subtitles",
        "category": "Data & AI",
        "summary": "Clean AI transcripts, add captions and produce subtitle files for creators, courses and podcasts.",
        "platforms": ["Rev", "GoTranscript", "Fiverr", "Upwork"],
        "startup_cost": 0,
        "time_to_cash_days": 2,
        "automation": 45,
        "demand": 72,
        "competition": 62,
        "risk": 8,
        "skills": ["english", "listening", "editing"],
        "offer": "Free 1-minute sample with timecodes and clean punctuation.",
        "pricing": "$0.50-$3 per minute",
        "first_steps": [
            "Install Whisper and build a clean transcript template.",
            "Create a 60-second sample in two formats (SRT, readable doc).",
            "Apply to Rev/GoTranscript and publish a Fiverr gig.",
        ],
        "tags": ["fast-cash", "low-risk"],
    },
    {
        "id": "notion-templates",
        "title": "Notion and planner templates",
        "category": "Digital products",
        "summary": "Sell ready-made Notion dashboards, planners and trackers for freelancers, students and small teams.",
        "platforms": ["Gumroad", "Etsy", "Notion Marketplace"],
        "startup_cost": 0,
        "time_to_cash_days": 7,
        "automation": 96,
        "demand": 68,
        "competition": 78,
        "risk": 15,
        "skills": ["notion", "design", "organization"],
        "offer": "One niche template (freelance OS, study planner, content calendar) with a demo page.",
        "pricing": "$5-$39 per template, bundles $29-$79",
        "first_steps": [
            "Pick one narrow audience and one painful workflow.",
            "Build a polished template + 3-page demo + setup guide.",
            "Publish on Gumroad with a launch discount and free mini-template.",
        ],
        "tags": ["passive", "global", "low-risk"],
    },
    {
        "id": "prompt-library",
        "title": "Prompt packs and AI workflow templates",
        "category": "Digital products",
        "summary": "Package proven prompts and workflows for a specific job (sales, recruiting, real estate, teaching) and sell them.",
        "platforms": ["Gumroad", "Etsy", "Payhip"],
        "startup_cost": 0,
        "time_to_cash_days": 5,
        "automation": 95,
        "demand": 62,
        "competition": 82,
        "risk": 18,
        "skills": ["prompting", "writing", "marketing"],
        "offer": "A free 5-prompt sample in one niche, then a $19-$49 pack.",
        "pricing": "$9-$49 per pack",
        "first_steps": [
            "Choose a job role and collect 20 real tasks.",
            "Test prompts and record inputs/outputs as proof.",
            "Publish a free sample and a paid pack with updates.",
        ],
        "tags": ["passive", "global"],
    },
    {
        "id": "micro-saas",
        "title": "Micro-SaaS tool for one painful job",
        "category": "Digital products",
        "summary": "Ship a tiny paid web tool that solves one workflow for a niche (invoice reminders, review replies, report generator).",
        "platforms": ["Gumroad", "Product Hunt", "Reddit", "X"],
        "startup_cost": 0,
        "time_to_cash_days": 21,
        "automation": 90,
        "demand": 74,
        "competition": 76,
        "risk": 45,
        "skills": ["python", "javascript", "product", "marketing"],
        "offer": "A working MVP with one paid plan and a 7-day free trial.",
        "pricing": "$9-$49/month",
        "first_steps": [
            "Interview 5 people in one niche about a recurring manual task.",
            "Build the smallest useful version in 7 days.",
            "Launch to 20 warm prospects before adding features.",
        ],
        "tags": ["recurring", "global", "higher-risk"],
    },
    {
        "id": "faceless-youtube",
        "title": "Faceless YouTube / short-form channel",
        "category": "Content",
        "summary": "Publish niche explainers, listicles or story shorts using licensed visuals, AI voice and a repeatable editing system.",
        "platforms": ["YouTube", "TikTok", "Instagram Reels"],
        "startup_cost": 0,
        "time_to_cash_days": 30,
        "automation": 86,
        "demand": 76,
        "competition": 90,
        "risk": 45,
        "skills": ["writing", "video", "research"],
        "offer": "One channel, one format, 3 posts per week for 90 days.",
        "pricing": "Ad revenue + affiliates + sponsorships",
        "first_steps": [
            "Pick a niche with proven small channels and high retention.",
            "Write 20 hooks and outline 10 videos before publishing.",
            "Build a repeatable script > voice > edit > thumbnail pipeline.",
        ],
        "tags": ["audience", "long-game", "higher-risk"],
    },
    {
        "id": "niche-newsletter",
        "title": "Niche newsletter with affiliate revenue",
        "category": "Content",
        "summary": "Curate one narrow topic weekly, grow an email list and monetize with affiliates, sponsors and paid tiers.",
        "platforms": ["Substack", "beehiiv", "LinkedIn"],
        "startup_cost": 0,
        "time_to_cash_days": 30,
        "automation": 78,
        "demand": 64,
        "competition": 84,
        "risk": 35,
        "skills": ["writing", "research", "curation"],
        "offer": "A free weekly brief with one original insight and 10 links.",
        "pricing": "Affiliates, $5-$10/month paid tier, sponsors",
        "first_steps": [
            "Choose a topic you can curate for 12 months.",
            "Publish 4 issues before asking for signups.",
            "Add one affiliate and one paid-tier offer.",
        ],
        "tags": ["audience", "long-game"],
    },
    {
        "id": "ugc-ads",
        "title": "UGC-style product ads for brands",
        "category": "Content",
        "summary": "Script, shoot or generate short vertical product ads for e-commerce brands and test multiple hooks.",
        "platforms": ["Fiverr", "Billo", "TikTok Creative Exchange"],
        "startup_cost": 0,
        "time_to_cash_days": 5,
        "automation": 76,
        "demand": 80,
        "competition": 68,
        "risk": 25,
        "skills": ["video", "copywriting", "marketing"],
        "offer": "3 hook variations for one product, delivered in 3 days.",
        "pricing": "$50-$300 per ad, $300-$1,000 per pack",
        "first_steps": [
            "Create 3 spec ads for products you already own.",
            "Write a hook bank and a simple shot list.",
            "Pitch 10 DTC brands with a sample ad.",
        ],
        "tags": ["remote", "creative"],
    },
    {
        "id": "bug-bounty",
        "title": "Bug bounty hunting",
        "category": "Security",
        "summary": "Find and report valid security vulnerabilities in authorized public programs for cash rewards.",
        "platforms": ["HackerOne", "Bugcrowd", "Intigriti"],
        "startup_cost": 0,
        "time_to_cash_days": 14,
        "automation": 55,
        "demand": 74,
        "competition": 88,
        "risk": 42,
        "skills": ["security", "web", "networking"],
        "offer": "Pick one program, learn its scope, and submit one high-quality report.",
        "pricing": "$100-$10,000+ per valid report",
        "first_steps": [
            "Read program scopes and rules before testing anything.",
            "Practice on authorized labs and duplicate-prone checks.",
            "Write a clear report with impact, steps and a fix.",
        ],
        "tags": ["technical", "higher-risk", "compliance"],
    },
    {
        "id": "website-security-audit",
        "title": "Website security audit for small businesses",
        "category": "Security",
        "summary": "Run authorized basic audits (headers, TLS, backups, access, dependency checks) and deliver a prioritized fix report.",
        "platforms": ["Upwork", "Fiverr", "LinkedIn"],
        "startup_cost": 0,
        "time_to_cash_days": 7,
        "automation": 68,
        "demand": 62,
        "competition": 55,
        "risk": 45,
        "skills": ["security", "linux", "reporting"],
        "offer": "A free 5-point external check, then a written audit with fixes.",
        "pricing": "$100-$800 per audit",
        "first_steps": [
            "Build a checklist and a report template with severity levels.",
            "Only test sites with written permission.",
            "Create one anonymized sample audit.",
        ],
        "tags": ["b2b", "compliance", "higher-risk"],
    },
    {
        "id": "online-tutoring",
        "title": "Online tutoring (coding, math, English)",
        "category": "Teaching",
        "summary": "Teach 1:1 or small groups online with a simple curriculum, homework and progress reports.",
        "platforms": ["Superprof", "Preply", "Wyzant", "local groups"],
        "startup_cost": 0,
        "time_to_cash_days": 3,
        "automation": 48,
        "demand": 86,
        "competition": 66,
        "risk": 10,
        "skills": ["teaching", "python", "math", "english"],
        "offer": "A free 20-minute diagnostic lesson, then a 4-week plan.",
        "pricing": "$10-$60/hour",
        "first_steps": [
            "Pick one subject and one level you can teach well.",
            "Prepare a diagnostic quiz and a 4-week outline.",
            "Create profiles on 2 platforms and ask 3 people for trial lessons.",
        ],
        "tags": ["remote", "low-risk", "fast-cash"],
    },
    {
        "id": "translation-localization",
        "title": "Translation and localization",
        "category": "Teaching",
        "summary": "Translate documents, product pages and subtitles between languages you speak natively, with clean formatting.",
        "platforms": ["Gengo", "ProZ", "Fiverr", "Upwork"],
        "startup_cost": 0,
        "time_to_cash_days": 3,
        "automation": 42,
        "demand": 72,
        "competition": 70,
        "risk": 10,
        "skills": ["languages", "writing", "editing"],
        "offer": "Free 150-word sample in your best language pair.",
        "pricing": "$0.05-$0.20 per word",
        "first_steps": [
            "Choose your strongest language pair and 2 specializations.",
            "Create a sample translation with a glossary.",
            "Apply to Gengo/ProZ and publish a Fiverr gig.",
        ],
        "tags": ["remote", "low-risk"],
    },
    {
        "id": "technical-writing",
        "title": "Technical writing and documentation",
        "category": "Content",
        "summary": "Write API docs, tutorials, release notes and developer guides for startups and open-source projects.",
        "platforms": ["Upwork", "Contra", "GitHub", "LinkedIn"],
        "startup_cost": 0,
        "time_to_cash_days": 7,
        "automation": 66,
        "demand": 72,
        "competition": 55,
        "risk": 15,
        "skills": ["writing", "developer", "docs"],
        "offer": "A free edit of one existing doc page, then a paid docs sprint.",
        "pricing": "$0.10-$0.50 per word, $300-$2,000 per sprint",
        "first_steps": [
            "Pick 2 developer tools you know and audit their docs.",
            "Publish one strong tutorial as a writing sample.",
            "Pitch 10 open-source projects with a specific doc gap.",
        ],
        "tags": ["developer", "remote"],
    },
    {
        "id": "virtual-assistant",
        "title": "Remote research / virtual assistant",
        "category": "Services",
        "summary": "Handle research, inbox triage, scheduling, data entry and reporting for founders and small teams.",
        "platforms": ["OnlineJobs.ph", "Upwork", "Belay", "LinkedIn"],
        "startup_cost": 0,
        "time_to_cash_days": 2,
        "automation": 52,
        "demand": 88,
        "competition": 72,
        "risk": 14,
        "skills": ["organization", "research", "english"],
        "offer": "A free 2-hour trial task with a clear checklist and report.",
        "pricing": "$5-$25/hour",
        "first_steps": [
            "Choose 3 services you can deliver reliably.",
            "Create a one-page service menu and availability.",
            "Apply to 10 posts with a tailored 3-line pitch.",
        ],
        "tags": ["fast-cash", "remote", "low-risk"],
    },
    {
        "id": "discord-community",
        "title": "Discord community setup and moderation",
        "category": "Services",
        "summary": "Design servers, roles, onboarding, bots and moderation workflows for creators and small communities.",
        "platforms": ["Fiverr", "Upwork", "Reddit"],
        "startup_cost": 0,
        "time_to_cash_days": 4,
        "automation": 82,
        "demand": 58,
        "competition": 48,
        "risk": 18,
        "skills": ["discord", "community", "automation"],
        "offer": "A free server audit with a 1-page improvement plan.",
        "pricing": "$50-$400 per setup, $100-$500/month moderation",
        "first_steps": [
            "Build a demo server with clean onboarding and role logic.",
            "Create a setup checklist and moderation playbook.",
            "Pitch 10 creators with an audit screenshot.",
        ],
        "tags": ["remote", "recurring"],
    },
    {
        "id": "ai-voiceover",
        "title": "AI voiceover, audio cleanup and podcast editing",
        "category": "Content",
        "summary": "Clean audio, remove noise, generate licensed AI voiceovers and repurpose long recordings into clips.",
        "platforms": ["Fiverr", "Upwork", "Rev"],
        "startup_cost": 0,
        "time_to_cash_days": 2,
        "automation": 88,
        "demand": 66,
        "competition": 70,
        "risk": 22,
        "skills": ["audio", "editing", "ai"],
        "offer": "Free cleanup of a 60-second clip, then per-episode pricing.",
        "pricing": "$10-$150 per episode or clip pack",
        "first_steps": [
            "Build a repeatable cleanup chain (noise, levels, silence, captions).",
            "Create 3 before/after samples.",
            "Publish gigs for podcast editing and voiceover cleanup.",
        ],
        "tags": ["fast-cash", "creative"],
    },
]

CATEGORIES = sorted({opp["category"] for opp in CATALOG})


def _skill_set(settings: dict[str, Any]) -> set[str]:
    skills = settings.get("skills") or []
    if isinstance(skills, str):
        skills = skills.split(",")
    return {str(skill).strip().lower() for skill in skills if str(skill).strip()}


def _score(opp: dict[str, Any], skills: set[str]) -> tuple[float, str]:
    speed = max(0.0, 100.0 - float(opp["time_to_cash_days"]) * 3.5)
    free = 100.0 if float(opp["startup_cost"]) <= 0 else max(0.0, 100.0 - float(opp["startup_cost"]) / 10.0)
    hits = len({str(s).lower() for s in opp["skills"]} & skills)
    skill_bonus = min(15.0, hits * 7.5)
    score = (
        float(opp["demand"]) * 0.22
        + float(opp["automation"]) * 0.20
        + (100.0 - float(opp["competition"])) * 0.14
        + (100.0 - float(opp["risk"])) * 0.14
        + speed * 0.15
        + free * 0.07
        + skill_bonus
    )
    why = (
        f"cash in ~{opp['time_to_cash_days']}d · {opp['automation']}% automatable · "
        f"{'free start' if float(opp['startup_cost']) <= 0 else 'needs $' + str(opp['startup_cost'])}"
    )
    if hits:
        why += f" · matches {hits} skill(s)"
    return round(min(100.0, score), 1), why


def opportunities(
    query: str | None = None,
    category: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    skills = _skill_set(settings)
    q = (query or "").strip().lower()
    out: list[dict[str, Any]] = []
    for opp in CATALOG:
        if category and opp["category"].lower() != category.strip().lower():
            continue
        haystack = " ".join(
            [
                opp["title"],
                opp["summary"],
                opp["category"],
                " ".join(opp["platforms"]),
                " ".join(opp["skills"]),
                " ".join(opp.get("tags", [])),
            ]
        ).lower()
        if q and q not in haystack:
            continue
        item = _row(opp)
        item["score"], item["why"] = _score(opp, skills)
        out.append(item)
    out.sort(key=lambda item: item["score"], reverse=True)
    if limit:
        out = out[: max(1, int(limit))]
    return out


def get_opportunity(opportunity_id: str) -> dict[str, Any] | None:
    for opp in CATALOG:
        if opp["id"] == opportunity_id:
            settings = get_settings()
            item = _row(opp)
            item["score"], item["why"] = _score(opp, _skill_set(settings))
            return item
    return None


# --------------------------------------------------------------------------- ventures


def _task(
    phase: str,
    role: str,
    title: str,
    detail: str,
    acceptance: str,
    priority: int,
    estimate_min: int,
    metric: str | None = None,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "role": role,
        "title": title,
        "detail": detail,
        "acceptance": acceptance,
        "priority": priority,
        "estimate_min": estimate_min,
        "metric": metric,
    }


def _plan(opp: dict[str, Any], currency: str) -> list[dict[str, Any]]:
    platforms = ", ".join(opp["platforms"][:3])
    offer = opp["offer"]
    steps = " ".join(opp["first_steps"])
    return [
        _task(
            "Validate",
            "CEO",
            "Write the one-line offer and ideal customer",
            f"Turn this into one sentence: {offer} Customer: the niche you can reach fastest. Keep the promise measurable (time saved, result, deadline).",
            "A one-sentence offer + a named ideal customer + a price range.",
            1,
            25,
            "offer",
        ),
        _task(
            "Validate",
            "Researcher",
            "Choose platforms and optimize profiles",
            f"Pick the two fastest platforms from: {platforms}. Rewrite headline, bio, portfolio title and first offer around the niche. Platform rules and fees must be read before publishing.",
            "Two live profiles with the same niche, offer and proof asset.",
            1,
            45,
            "profiles",
        ),
        _task(
            "Validate",
            "Builder",
            "Build one proof asset",
            f"Create the smallest credible sample. {steps} It must be viewable without a call: demo link, before/after, sample dataset or 2-minute video.",
            "One proof asset the user can send in a pitch.",
            1,
            90,
            "proof",
        ),
        _task(
            "Validate",
            "Researcher",
            "Build a target list of 25 leads or 10 keywords",
            f"Use public sources and the chosen platforms. Record name, contact route, pain signal and a personalized opening line. Never scrape private data.",
            "25 qualified leads (or 10 buyer-intent keywords) in a sheet.",
            1,
            60,
            "leads",
        ),
        _task(
            "Launch",
            "Marketing",
            "Publish the offer and a portfolio post",
            f"Write one clear post with the offer, proof, price range and a call to action. Publish on the chosen platform/profile. Draft only until the user approves the account and the post.",
            "One published listing/post with a working contact route.",
            2,
            35,
            "publish",
        ),
        _task(
            "Launch",
            "Sales",
            "Send 10 personalized pitches",
            "Use the lead list. Each pitch: one observation about their business, one outcome, one proof link, one small ask. No mass spam; follow platform anti-spam rules.",
            "10 sent pitches, tracked with date and response.",
            1,
            50,
            "pitches",
        ),
        _task(
            "Launch",
            "Sales",
            "Follow up and book 2 calls",
            "Follow up once after 48 hours. Offer two time windows. Prepare 5 discovery questions and a fixed-price proposal template.",
            "2 booked calls or 2 written replies with a next step.",
            2,
            30,
            "calls",
        ),
        _task(
            "Deliver",
            "Builder",
            "Deliver the first paid engagement",
            f"Scope in writing, collect a deposit if possible, deliver in small checkpoints, and keep a change log. Pricing guide: {opp['pricing']}.",
            "Deliverable accepted by the client and payment received or invoiced.",
            1,
            180,
            "delivery",
        ),
        _task(
            "Deliver",
            "QA",
            "QA the delivery and collect a testimonial",
            "Test the result against the acceptance criteria. Ask for a short testimonial and permission to use an anonymized case study.",
            "QA checklist passed + testimonial or case-study permission.",
            2,
            30,
            "qa",
        ),
        _task(
            "Scale",
            "CEO",
            "Raise price and package the offer",
            "Turn the delivery into 2-3 fixed packages. Raise the price for the next client and add a maintenance retainer option where it fits.",
            "A public price list with 3 packages and one retainer.",
            3,
            35,
            "pricing",
        ),
        _task(
            "Scale",
            "Ops",
            "Systemize delivery with a checklist and templates",
            "Document every repeated step as a checklist or script. Automate the safest 30% first. Store templates in the workspace.",
            "A reusable delivery checklist and at least one automation script.",
            3,
            60,
            "systems",
        ),
        _task(
            "Scale",
            "Finance",
            "Review KPIs, log income, and write one lesson",
            "Record revenue, hours, pitches, calls and conversion. Write one lesson that changes the next plan. Feed it back into the learning bank.",
            "Income logged + one specific lesson saved.",
            2,
            25,
            "review",
        ),
    ]


def create_venture(opportunity_id: str, name: str | None = None, currency: str | None = None) -> dict[str, Any]:
    init()
    opp = get_opportunity(opportunity_id)
    if not opp:
        raise ValueError(f"Unknown opportunity: {opportunity_id}")
    settings = get_settings()
    currency = (currency or settings.get("currency") or "USD").upper()[:8]
    con = _conn()
    existing = con.execute(
        "SELECT * FROM ventures WHERE opportunity_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
        (opportunity_id,),
    ).fetchone()
    if existing:
        con.close()
        item = get_venture(existing["id"])
        if item:
            item["existing"] = True
            return item
        return {**dict(existing), "existing": True, "tasks": list_tasks(existing["id"]), "opportunity": opp}
    now = time.time()
    venture_name = (name or "").strip() or f"{opp['title']} venture"
    mission = (
        f"Earn the first {currency} within {opp['time_to_cash_days']} days by delivering: "
        f"{opp['offer']} Start with the 30-day plan, keep costs at zero, and log every result."
    )
    cur = con.execute(
        "INSERT INTO ventures (opportunity_id, name, mission, currency, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'active', ?, ?)",
        (opportunity_id, venture_name, mission, currency, now, now),
    )
    venture_id = cur.lastrowid
    for task in _plan(opp, currency):
        con.execute(
            "INSERT INTO venture_tasks (venture_id, phase, role, title, detail, acceptance, priority, estimate_min, metric, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (
                venture_id,
                task["phase"],
                task["role"],
                task["title"],
                task["detail"],
                task["acceptance"],
                task["priority"],
                task["estimate_min"],
                task["metric"],
                now,
            ),
        )
    con.commit()
    con.close()
    launch_lesson = (
        f"Launched '{venture_name}' from the {opp['category']} catalog. First bet: {opp['offer']} "
        f"Target first cash in {opp['time_to_cash_days']} days with zero startup cost."
    )
    add_learning(launch_lesson, tags=[opp["id"], opp["category"]], venture_id=venture_id)
    return get_venture(venture_id) or {}


def _venture_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    opp = get_opportunity(item["opportunity_id"])
    item["opportunity"] = opp
    return item


def get_venture(venture_id: int) -> dict[str, Any] | None:
    init()
    con = _conn()
    row = con.execute("SELECT * FROM ventures WHERE id = ?", (venture_id,)).fetchone()
    con.close()
    if not row:
        return None
    item = _venture_row(row)
    item["tasks"] = list_tasks(venture_id)
    item["income"] = income_for_venture(venture_id)
    item["progress"] = _progress(venture_id)
    return item


def list_ventures() -> list[dict[str, Any]]:
    init()
    con = _conn()
    rows = con.execute("SELECT * FROM ventures ORDER BY updated_at DESC").fetchall()
    con.close()
    out = []
    for row in rows:
        item = _venture_row(row)
        item["tasks"] = list_tasks(row["id"])
        item["progress"] = _progress(row["id"])
        item["income"] = income_for_venture(row["id"])
        out.append(item)
    return out


def list_tasks(venture_id: int) -> list[dict[str, Any]]:
    init()
    con = _conn()
    rows = con.execute(
        "SELECT * FROM venture_tasks WHERE venture_id = ? ORDER BY status = 'done', phase, priority, id",
        (venture_id,),
    ).fetchall()
    con.close()
    return [dict(row) for row in rows]


def _progress(venture_id: int) -> dict[str, int]:
    con = _conn()
    total = con.execute("SELECT COUNT(*) FROM venture_tasks WHERE venture_id = ?", (venture_id,)).fetchone()[0]
    done = con.execute(
        "SELECT COUNT(*) FROM venture_tasks WHERE venture_id = ? AND status = 'done'", (venture_id,)
    ).fetchone()[0]
    con.close()
    return {"total": total, "done": done, "pending": max(0, total - done)}


# --------------------------------------------------------------------------- income


def log_income(
    amount: float,
    source: str = "",
    notes: str = "",
    currency: str | None = None,
    venture_id: int | None = None,
) -> dict[str, Any]:
    init()
    settings = get_settings()
    currency = (currency or settings.get("currency") or "USD").upper()[:8]
    now = time.time()
    con = _conn()
    cur = con.execute(
        "INSERT INTO income (venture_id, amount, currency, source, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (venture_id, float(amount), currency, source[:500], notes[:2000], now),
    )
    con.commit()
    row = con.execute("SELECT * FROM income WHERE id = ?", (cur.lastrowid,)).fetchone()
    con.close()
    if venture_id:
        con = _conn()
        con.execute("UPDATE ventures SET updated_at = ? WHERE id = ?", (now, venture_id))
        con.commit()
        con.close()
    return dict(row) if row else {"amount": amount, "currency": currency}


def import_income_csv(csv_text: str, venture_id: int | None = None) -> dict[str, Any]:
    """Import income rows from CSV text (amount,source,notes,currency)."""
    import csv as _csv
    import io as _io
    reader = _csv.DictReader(_io.StringIO(csv_text or ""))
    imported = skipped = 0
    for row in reader:
        try:
            amount = float(str(row.get("amount") or "").replace("$", "").replace(",", ""))
        except ValueError:
            skipped += 1
            continue
        log_income(amount, source=str(row.get("source") or "csv-import")[:500], notes=str(row.get("notes") or "")[:2000], currency=str(row.get("currency") or "") or None, venture_id=venture_id)
        imported += 1
    return {"imported": imported, "skipped": skipped}


def income_for_venture(venture_id: int) -> dict[str, Any]:
    init()
    con = _conn()
    rows = con.execute(
        "SELECT currency, SUM(amount) AS total FROM income WHERE venture_id = ? GROUP BY currency",
        (venture_id,),
    ).fetchall()
    con.close()
    return {row["currency"]: round(float(row["total"] or 0), 2) for row in rows}


def income_totals() -> dict[str, float]:
    init()
    con = _conn()
    rows = con.execute("SELECT currency, SUM(amount) AS total FROM income GROUP BY currency").fetchall()
    con.close()
    return {row["currency"]: round(float(row["total"] or 0), 2) for row in rows}


def recent_income(limit: int = 20) -> list[dict[str, Any]]:
    init()
    con = _conn()
    rows = con.execute("SELECT * FROM income ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return [dict(row) for row in rows]


# --------------------------------------------------------------------------- learning


def add_learning(lesson: str, tags: list[str] | None = None, venture_id: int | None = None) -> dict[str, Any]:
    init()
    lesson = (lesson or "").strip()
    if not lesson:
        raise ValueError("Lesson is empty")
    now = time.time()
    con = _conn()
    cur = con.execute(
        "INSERT INTO learning (venture_id, lesson, tags, created_at) VALUES (?, ?, ?, ?)",
        (venture_id, lesson[:4000], ",".join(tags or []), now),
    )
    con.commit()
    row = con.execute("SELECT * FROM learning WHERE id = ?", (cur.lastrowid,)).fetchone()
    con.close()
    return dict(row) if row else {"lesson": lesson}


def list_learning(limit: int = 20) -> list[dict[str, Any]]:
    init()
    con = _conn()
    rows = con.execute(
        "SELECT * FROM learning ORDER BY created_at DESC LIMIT ?", (max(1, int(limit)),)
    ).fetchall()
    con.close()
    return [dict(row) for row in rows]


def top_learning(limit: int = 5) -> list[dict[str, Any]]:
    init()
    con = _conn()
    rows = con.execute(
        "SELECT * FROM learning ORDER BY uses DESC, created_at DESC LIMIT ?", (max(1, int(limit)),)
    ).fetchall()
    ids = [row["id"] for row in rows]
    if ids:
        con.execute(
            f"UPDATE learning SET uses = uses + 1 WHERE id IN ({','.join('?' for _ in ids)})", ids
        )
        con.commit()
    con.close()
    return [dict(row) for row in rows]


def context_block() -> str:
    settings = get_settings()
    ventures = [v for v in list_ventures() if v.get("status") == "active"][:3]
    if not ventures and not list_learning(1):
        return ""
    lines = ["## Earnings brain (persistent)"]
    totals = income_totals()
    if totals:
        lines.append("Income logged: " + ", ".join(f"{cur} {amt}" for cur, amt in totals.items()))
    for venture in ventures:
        pending = [t for t in venture.get("tasks", []) if t.get("status") != "done"]
        pending.sort(key=lambda t: (t.get("priority", 3), t.get("id", 0)))
        next_task = pending[0]["title"] if pending else "plan complete — review KPIs"
        lines.append(
            f"- Active venture #{venture['id']} '{venture['name']}' ({venture['progress']['done']}/{venture['progress']['total']} tasks). Next: {next_task}"
        )
    lessons = top_learning(4)
    if lessons:
        lines.append("Lessons from past work:")
        for lesson in lessons:
            lines.append(f"- {lesson['lesson'][:300]}")
    lines.append(
        "Use earnings_radar / earnings_launch / earnings_brief / earnings_complete_task for income work. "
        "Drafts only: never send outreach, create accounts, spend money, or promise income without explicit approval."
    )
    return "\n".join(lines)[:2200]


# --------------------------------------------------------------------------- brief + autopilot


DRAFT_TEMPLATES = {
    "offer": (
        "OFFER DRAFT\n"
        "I help {customer} {outcome} without {pain}, in {days} days.\n"
        "Package: {offer}\n"
        "Price: {pricing}\n"
        "Proof: {proof}\n"
        "Next step: a free 15-minute audit / sample."
    ),
    "profiles": (
        "PROFILE CHECKLIST\n"
        "Headline: {outcome} for {customer}\n"
        "About: problem > offer > proof > call to action\n"
        "Portfolio title: {offer}\n"
        "Add platform rules/fees check and a contact route."
    ),
    "proof": (
        "PROOF ASSET CHECKLIST\n"
        "- One before/after or demo link\n"
        "- Show the exact deliverable, not a description\n"
        "- Add a 60-90 second walkthrough\n"
        "- Include a measurable result or clear scope"
    ),
    "leads": (
        "LEAD LIST FIELDS\n"
        "name | niche | public contact route | pain signal | personalized opener | source\n"
        "Build 25 rows. Only use public/permitted data. Do not scrape private or gated data."
    ),
    "pitch": (
        "PITCH DRAFT\n"
        "Hi {{name}} — I noticed {{specific observation}}.\n"
        "I help {customer} {outcome}. Here is a quick proof: {{proof link}}.\n"
        "Would a 15-minute audit next week be useful? If not, I will not follow up again.\n"
        "— {{your name}}\n"
        "Personalize every line; no mass sends."
    ),
    "publish": (
        "LAUNCH POST DRAFT\n"
        "I built {offer} for {customer}.\n"
        "Why: {pain}.\n"
        "What you get: {{deliverables}}.\n"
        "Proof: {{proof link}}.\n"
        "Price: {pricing}.\n"
        "DM or comment 'START' and I will send the details."
    ),
    "delivery": (
        "DELIVERY CHECKLIST\n"
        "- Written scope + acceptance criteria + deadline\n"
        "- Deposit or milestone payment where possible\n"
        "- Weekly checkpoint and change log\n"
        "- Final QA against acceptance criteria\n"
        "- Ask for testimonial + referral"
    ),
    "pricing": (
        "PRICE TEST\n"
        "Package 1: small fixed outcome — {pricing}\n"
        "Package 2: full outcome + one revision\n"
        "Package 3: monthly maintenance/retainer\n"
        "Raise the next quote by 20% and track conversion."
    ),
    "default": (
        "NEXT ACTION\n"
        "Task: {task}\n"
        "Outcome wanted: {acceptance}\n"
        "Do the smallest version in one sitting. Log the result and one lesson."
    ),
}

METRIC_KEY = {
    "offer": "offer",
    "profiles": "profiles",
    "proof": "proof",
    "leads": "leads",
    "publish": "publish",
    "pitches": "pitch",
    "calls": "pitch",
    "delivery": "delivery",
    "qa": "delivery",
    "pricing": "pricing",
    "systems": "delivery",
    "review": "review",
}


def _draft_for(venture: dict[str, Any], task: dict[str, Any]) -> str:
    opp = venture.get("opportunity") or {}
    try:
        from .engine.tiny_brain import tiny_brain
        prompt = (
            f"Draft a concise, realistic, high-conversion action draft for venture '{venture.get('name')}' "
            f"task: '{task.get('title')}'. Focus on: {task.get('detail', '')}. "
            f"Acceptance criteria: {task.get('acceptance', '')}. Keep it practical and ready to use, no fake brackets."
        )
        ai_draft = tiny_brain(prompt)
        if ai_draft and len(ai_draft.strip()) > 30 and "No local tiny" not in ai_draft:
            return ai_draft.strip()
    except Exception:
        pass
    template = DRAFT_TEMPLATES.get(METRIC_KEY.get(str(task.get("metric") or ""), "default"), DRAFT_TEMPLATES["default"])
    try:
        return template.format(
            customer=(opp.get("skills") or ["clients"])[0] + " clients",
            outcome=opp.get("summary", task["title"])[:120],
            pain="inefficient manual workflows",
            days=opp.get("time_to_cash_days", 7),
            offer=opp.get("offer", task["title"]),
            pricing=opp.get("pricing", "fixed milestone price"),
            proof="verified case study",
            task=task["title"],
            acceptance=task["acceptance"],
        )
    except Exception:
        return f"# Task Draft: {task['title']}\n\nObjective: {task.get('acceptance', 'Complete task deliverables')}\n\nProposed Action:\n- Review requirements\n- Execute in workspace\n- Verify output"


def brief(venture_id: int | None = None) -> dict[str, Any]:
    init()
    if venture_id:
        ventures = [v for v in [get_venture(int(venture_id))] if v]
    else:
        ventures = [v for v in list_ventures() if v.get("status") == "active"]
    actions: list[dict[str, Any]] = []
    for venture in ventures:
        pending = [t for t in venture.get("tasks", []) if t.get("status") != "done"]
        pending.sort(key=lambda t: (t.get("priority", 3), t.get("id", 0)))
        for task in pending[:3]:
            draft = task.get("draft")
            if not draft:
                draft = _draft_for(venture, task)
                con = _conn()
                con.execute("UPDATE venture_tasks SET draft = ? WHERE id = ?", (draft, task["id"]))
                con.commit()
                con.close()
            actions.append(
                {
                    "venture_id": venture["id"],
                    "venture": venture["name"],
                    "task_id": task["id"],
                    "title": task["title"],
                    "role": task["role"],
                    "phase": task["phase"],
                    "priority": task["priority"],
                    "estimate_min": task["estimate_min"],
                    "acceptance": task["acceptance"],
                    "draft": draft,
                }
            )
    actions.sort(key=lambda item: (item["priority"], item["venture_id"]))
    settings = get_settings()
    return {
        "generated_at": time.time(),
        "currency": settings.get("currency"),
        "income": income_totals(),
        "actions": actions[:8],
        "lessons": top_learning(5),
        "ventures": [
            {
                "id": venture["id"],
                "name": venture["name"],
                "progress": venture["progress"],
                "income": venture.get("income", {}),
            }
            for venture in ventures
        ],
        "guardrail": "Autopilot drafts only. Sending messages, creating accounts, spending money and payouts need the user.",
    }


def complete_task(
    venture_id: int,
    task_id: int,
    result: str = "",
    income: float = 0,
    currency: str | None = None,
    lesson: str | None = None,
) -> dict[str, Any]:
    init()
    con = _conn()
    task = con.execute(
        "SELECT * FROM venture_tasks WHERE id = ? AND venture_id = ?", (task_id, venture_id)
    ).fetchone()
    if not task:
        con.close()
        raise ValueError(f"Task {task_id} not found in venture {venture_id}")
    now = time.time()
    con.execute(
        "UPDATE venture_tasks SET status = 'done', result = ?, completed_at = ? WHERE id = ?",
        (result[:4000], now, task_id),
    )
    con.execute("UPDATE ventures SET updated_at = ? WHERE id = ?", (now, venture_id))
    con.commit()
    con.close()
    if income and float(income) > 0:
        log_income(float(income), source=task["title"], notes=result[:1000], currency=currency, venture_id=venture_id)
    if lesson is None:
        lesson = f"{task['title']}: {(result or 'completed')[:280]}"
    add_learning(lesson, tags=[str(task["metric"] or task["phase"]).lower()], venture_id=venture_id)
    return {
        "task": dict(task) | {"status": "done", "result": result, "completed_at": now},
        "venture": get_venture(venture_id),
        "lesson": lesson,
    }


def autopilot_tick() -> dict[str, Any]:
    settings = get_settings()
    if not settings.get("autopilot"):
        return {"enabled": False, "drafts": []}
    drafts: list[dict[str, Any]] = []
    for venture in [v for v in list_ventures() if v.get("status") == "active"]:
        pending = [
            t for t in venture.get("tasks", []) if t.get("status") != "done" and not t.get("draft")
        ]
        pending.sort(key=lambda t: (t.get("priority", 3), t.get("id", 0)))
        for task in pending[:2]:
            draft = _draft_for(venture, task)
            con = _conn()
            con.execute("UPDATE venture_tasks SET draft = ? WHERE id = ?", (draft, task["id"]))
            con.commit()
            con.close()
            drafts.append(
                {"venture_id": venture["id"], "task_id": task["id"], "title": task["title"], "draft": draft}
            )
    return {"enabled": True, "drafts": drafts}


# --------------------------------------------------------------------------- overview + radar


def _next_actions(limit: int = 6) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for venture in [v for v in list_ventures() if v.get("status") == "active"]:
        pending = [t for t in venture.get("tasks", []) if t.get("status") != "done"]
        pending.sort(key=lambda t: (t.get("priority", 3), t.get("id", 0)))
        if pending:
            task = pending[0]
            actions.append(
                {
                    "venture_id": venture["id"],
                    "venture": venture["name"],
                    "task_id": task["id"],
                    "title": task["title"],
                    "role": task["role"],
                    "priority": task["priority"],
                    "estimate_min": task["estimate_min"],
                }
            )
    actions.sort(key=lambda item: item["priority"])
    return actions[:limit]


def overview() -> dict[str, Any]:
    init()
    settings = get_settings()
    ventures = list_ventures()
    launched = {v["opportunity_id"] for v in ventures if v.get("status") == "active"}
    best = opportunities(limit=8)
    for item in best:
        item["launched"] = item["id"] in launched
    learning = list_learning(6)
    totals = income_totals()
    active = [v for v in ventures if v.get("status") == "active"]
    return {
        "settings": settings,
        "currency": settings.get("currency", "USD"),
        "income": totals,
        "income_events": recent_income(5),
        "active_ventures": active,
        "ventures_count": len(active),
        "tasks_pending": sum(v["progress"]["pending"] for v in active),
        "tasks_done": sum(v["progress"]["done"] for v in active),
        "best_opportunities": best,
        "next_actions": _next_actions(),
        "learning": learning,
        "categories": CATEGORIES,
        "autopilot": bool(settings.get("autopilot")),
        "guardrail": (
            "Free-first ideas only. Income is not guaranteed. No spam, fake accounts, platform abuse, "
            "or regulated advice. The agent drafts; you approve sends, spend, contracts and payouts."
        ),
    }


async def radar(query: str | None = None, category: str | None = None, limit: int = 8) -> dict[str, Any]:
    results = opportunities(query=None, category=category, limit=limit)
    live_text = ""
    signals: list[dict[str, str]] = []
    q = (query or "").strip()
    if not q and category:
        q = f"remote {category} paying freelance opportunities 2026"
    if q:
        try:
            live_text = await search_web(q[:300], limit=8)
        except Exception as exc:
            live_text = f"Live search unavailable: {exc}"
        for line in live_text.splitlines():
            match = re.match(r"-\s+\*\*(.+?)\*\*(?:\s+—\s+(\S+))?(?::\s*(.*))?", line.strip())
            if match:
                signals.append(
                    {
                        "title": match.group(1)[:180],
                        "url": (match.group(2) or "")[:500],
                        "description": (match.group(3) or "")[:400],
                    }
                )
        con = _conn()
        con.execute(
            "INSERT INTO scans (query, signals, created_at) VALUES (?, ?, ?)",
            (q[:500], json.dumps(signals), time.time()),
        )
        con.commit()
        con.close()
        for idx, sig in enumerate(signals[:5]):
            if sig.get("title") and sig.get("url"):
                results.insert(0, {
                    "id": f"live-{int(time.time())}-{idx}",
                    "title": sig["title"],
                    "category": category or "Live Web Signals",
                    "summary": sig["description"] or sig["title"],
                    "platforms": ["Live Web", sig.get("url", "")[:45]],
                    "startup_cost": 0,
                    "time_to_cash_days": 5,
                    "automation": 90,
                    "demand": 92,
                    "competition": 45,
                    "risk": 15,
                    "skills": ["automation", "research"],
                    "offer": f"Direct deliverable for: {sig['title']}",
                    "pricing": "Milestone payout",
                    "first_steps": ["Open URL in built-in browser", "Extract specs", "Execute solution"],
                    "tags": ["live", "real-time"],
                    "source": "live_web",
                    "url": sig.get("url", ""),
                })
    return {
        "query": q,
        "opportunities": results,
        "signals": signals,
        "signals_text": live_text[:12000],
        "live_search": bool(q and signals),
        "note": (
            "Live signals come from Firecrawl when a key is configured. Verify every listing, "
            "fee and rule before acting; catalog scores are heuristics, not income guarantees."
        ),
    }


def last_scan() -> dict[str, Any] | None:
    init()
    con = _conn()
    row = con.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    if not row:
        return None
    item = dict(row)
    try:
        item["signals"] = json.loads(item["signals"])
    except Exception:
        item["signals"] = []
    return item
