# Slot E — Chart UI (live candles + indicators)

## Sources investigated

### TradingView Lightweight Charts (PRIMARY CANDIDATE)
- Source: https://github.com/tradingview/lightweight-charts ★16.6k Apache-2.0, last push 2026-07-08 (alive)
- Pro: HTML5 canvas, ~45KB minified, 60fps live updates, MIT-compatible (Apache)
- Pro: actively maintained by TradingView themselves
- Pro: drop-in candlestick/line/area; volume histogram; 100+ indicators built-in
- Pro: Apache-2.0 license — compatible with our closed-source UAT pipeline
- Con: requires feeding it OHLCV arrays; doesn't fetch data itself
- License: Apache-2.0 ✅ GREEN
- Demo: https://tradingview.github.io/lightweight-charts/

### Plotly.js (DASHBOARD ALTERNATIVE)
- Source: https://github.com/plotly/plotly.js ★18k MIT
- Pro: full charting lib, candlestick + many plot types
- Con: ~3MB minified; slower on large data; not optimized for streaming
- License: MIT ✅ GREEN
- Verdict: use for one-off tables/reports, NOT live charts

### Bokeh (Python-side)
- Source: https://github.com/bokeh/bokeh ★20.4k BSD-3-Clause, last push 2026-07-15 (alive)
- Pro: native Python; outputs JS; integrates with Flask
- Con: not optimized for streaming real-time; better for static visualizations
- License: BSD-3-Clause ✅ GREEN
- Verdict: use for end-of-day reports; not for live candle chart

### Streamlit / Dash / Reflex (Python web frameworks)
- Streamlit ★45.2k Apache-2.0 (alive)
- Dash ★24.3k MIT (alive)
- Reflex ★28.7k Apache-2.0 (alive)
- Pro: Python-native, full-stack
- Con: all three are "page-render-on-interaction" not "WebSocket-first" — bad fit for live ticks
- Con: bring heavy backend; not what we need (we already have Flask app.py)
- Verdict: KEEP existing Flask app; ADD chart widgets via Lightweight Charts

### Apache ECharts
- Source: https://github.com/apache/echarts ★66.8k Apache-2.0
- Pro: general-purpose; powerful
- Con: 1MB minified; generalist; no special trade-tuned features
- License: Apache-2.0 ✅ GREEN
- Verdict: NOT needed — Lightweight Charts is purpose-built for financial

### Chart.js + Custom Candle
- Source: chartjs/Chart.js ★65k MIT
- Pro: lightweight, simple
- Con: no native candlestick; community plugin is stale
- Verdict: NOT a candlestick solution

## Verdict (Slot E)
- **Primary**: **TradingView Lightweight Charts** (Apache-2.0, purpose-built, 60fps streaming)
- **Secondary**: Plotly.js for end-of-day reports / sector heatmaps
- **Architecture**: thin HTML+JS in `dashboard/static/charts/` rendered by existing Flask `app.py`
- **Data path**: Flask SSE endpoint `/stream/quotes` → Lightweight Charts `subscribeData`
- **Existing reuse**: existing Flask `app.py` (~60KB) handles routing; just add new blueprint

## Score
- Fit: 5/5 (purpose-built, free, licensed correctly, alive)
- Integration cost: 2/5 (add ~300 LoC Flask + JS; well-trodden pattern)
- Data cost: 0/5 (fully free)