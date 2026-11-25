# Skill: Web Research

## When to use
Fact-finding, comparisons, market/price research, current events, verifying claims, finding tutorials/docs, due diligence on anything.

## Workflow
1. **Break the question into 2-4 specific search queries.** Use the web_search tool (DuckDuckGo); for depth, ask Perplexity (web deck) which cites sources.
2. **Open the top results with fetch_url.** Skim for the answer; prefer primary sources (official docs, papers, gov sites, original announcements) over aggregators.
3. **Cross-check**: any number, date, or claim that matters must appear in 2 independent sources, or be flagged "single source".
4. **Note dates**: prefer recent info; label anything older than a year.
5. **Synthesize**: answer the user's ACTUAL question first, then key findings, then sources (title + URL). Distinguish facts vs opinion vs estimate.
6. **Honesty**: say plainly when something could not be verified. Never invent a source, number, or quote.

## Power moves
- Behind a login wall? Ask the web decks (ChatGPT/Gemini can browse or know recent facts).
- Need a lot of pages fast? Use the browser panel or Playwright MCP.
- Non-English sources fine — translate mentally, cite the original.
