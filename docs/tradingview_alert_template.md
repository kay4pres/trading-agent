// TradingView Pine Script Alert Template
// ======================================
// Paste this into TradingView's Pine Script editor, add to your chart,
// then create an alert using "webhook" delivery.
//
//Webhook URL:
//  For local testing:  http://localhost:5050/webhook/tradingview
//  For public access: use ngrok:  ngrok http 5050
//    Then paste the ngrok URL + /webhook/tradingview
//
// In the alert dialog:
//   - Condition: your First Pullback indicator (or any condition)
//   - Expiration: 1 day (or session)
//   - Trigger: Once
//   - Webhook URL: paste the full URL here
//   - Message: paste the JSON below (without line breaks recommended)
//
// ──────────────────────────────────────────────────────────────────────────────
// Pine Script v5
// ──────────────────────────────────────────────────────────────────────────────

//@version=5
strategy("First Pullback Alert", overlay=true, default_qty_type=strategy.fixed, default_qty_value=100)

// ── Replace these with your actual indicator conditions ──────────────────────

// Example: price crosses above EMA 9 after a pullback
ema9  = ta.ema(close, 9)
pullback_low = ta.lowest(low, 5)[1]
first_break  = close > pullback_low and close > ema9 and close > open

// ── Alert condition ────────────────────────────────────────────────────────────
alertcondition(first_break, title="First Pullback", message=
'{"symbol":"{{ticker}}","price":"{{close}}","action":"buy","qty":"100","tv_alert":"First Pullback {{ticker}}"}')

// ── Optional: second alert for stop hit ──────────────────────────────────────
// alertcondition(stop_hit, title="Stop Hit", message=
// '{"symbol":"{{ticker}}","action":"stop_hit"}')
