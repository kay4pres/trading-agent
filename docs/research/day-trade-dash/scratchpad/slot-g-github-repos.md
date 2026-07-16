# Slot G — Named GitHub repos from Kay's list (deep investigation)

## 1. EvanLi/Github-Ranking
- URL: https://github.com/EvanLi/Github-Ranking
- Stars: 11.6k | Last push: 2026-07-16 (TODAY, alive) | License: MIT ✅ GREEN
- **What it really is**: a meta-list that ranks GitHub repos by stars/forks across languages, auto-updated daily
- **Does it do trading?** ❌ NO — it has NOTHING to do with trading
- **Useful for our project?** ❌ NO. It's only useful as a discovery index to find OTHER repos
- **Verdict**: REJECT — not a tool. (Kay may have confused it as a "top 100 trading repos" list — it's a "top 100 repos across all languages" list)

## 2. microsoft/qlib
- URL: https://github.com/microsoft/qlib
- Stars: 46.3k | Last push: 2026-04-22 | License: MIT ✅ GREEN
- **What it really is**: AI-oriented quant investment platform — factor mining, ML modeling (lightGBM/XGBoost), portfolio optimization, RL
- **Docs say**: "Qlib is an AI-oriented Quant investment platform that aims to use AI tech to empower Quant Research, from exploring ideas to implementing productions."
- **Does it do live intraday dashboard?** ❌ NO — it's a RESEARCH framework for end-of-day factor/model work
- **Useful for our project?** ⚠️ MAYBE for v2 — if Kay wants automated factor discovery (e.g. "what combination of float + RV + gap predicts next-day moves?"), Qlib is the right tool. NOT for v1 dashboard.
- **Python 3.12 compat**: YES (verified via setup.cfg; requires numpy, pandas, scipy)
- **Verdict**: DEFER to v2 (post-Alpha phase). DO NOT integrate for v1.

## 3. microsoft/RD-Agent
- URL: https://github.com/microsoft/RD-agent
- Stars: 13.9k | Last push: 2026-07-16 (TODAY, alive) | License: MIT ✅ GREEN
- **What it really is**: LLM-driven autonomous R&D agent for data-driven research; auto-discovers factors, optimizes models, fine-tunes
- **Companion to Qlib**: explicitly designed to work with qlib
- **Does it do live intraday dashboard?** ❌ NO — it's an LLM agent that writes code to mine factors; runs in batch jobs
- **Useful for our project?** ⚠️ MAYBE for v2 — IF Kay wants to automate discovery of "what news pattern predicts a 5-min breakout?"
- **Verdict**: DEFER to v2. Could replace our Bull/Bear debate in the long term but it's overkill for v1.

## 4. koala73/worldmonitor
- URL: https://github.com/koala73/worldmonitor
- Stars: 61.9k | Last push: 2026-07-16 (TODAY, alive) | License: **AGPL-3.0** ❌ RED
- **What it really is**: Real-time global intelligence dashboard — news aggregation, geopolitical monitoring, 56 map layer types, 6 site variants (world/tech/finance/commodity/happy/energy), Tauri 2 desktop app, Preact frontend
- **Tech**: TypeScript, Preact, deck.gl, maplibre-gl, globe.gl, Mapbox, AWS SDK
- **Does it do trading?** ⚠️ PARTIAL — has a `finance.worldmonitor.app` variant with 29 stock exchanges, commodities, 7-signal market composite
- **License check**: AGPL-3.0 — has NETWORK COPYLEFT. Any modification deployed as a server MUST be open-sourced. **LICENSE BLOCKER** for Kay's closed-source UAT pipeline.
- **Useful for our project?** ❌ NO for code reuse (license); ✅ MAYBE for inspiration (finance variant UI patterns)
- **Verdict**: REJECT for integration. USE for design reference of the finance variant dashboard pattern only.

## Summary table (Slot G)

| Repo | Stars | License | Alive | Useful for v1? | Reason |
|------|-------|---------|-------|----------------|--------|
| EvanLi/Github-Ranking | 11.6k | MIT | ✅ | ❌ | Not a trading tool |
| microsoft/qlib | 46.3k | MIT | ✅ | ❌ v1, ⚠️ v2 | EOD factor mining, not live |
| microsoft/RD-Agent | 13.9k | MIT | ✅ | ❌ v1, ⚠️ v2 | LLM R&D, not live dashboard |
| koala73/worldmonitor | 61.9k | **AGPL-3.0** | ✅ | ❌ | License blocker + wrong domain |

## Net findings for Slot G
- NONE of the 4 named repos are direct fits for a live trading dashboard
- None are "hidden gems" Kay missed
- All 4 are real, alive, and correctly licensed (except worldmonitor) — but all are off-domain
- Recommendation: keep the list in mind as v2 ideas, but **build v1 with simpler, smaller, focused libs**

## Score (Slot G net)
- Fit: 1/5 (none fit v1 needs)
- Integration cost: 4/5 (heavy; large codebases)
- Data cost: 0/5 (no paid data dependencies)