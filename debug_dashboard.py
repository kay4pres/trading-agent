import sys
sys.path.insert(0, r'E:\Me\TradingAgent')
from dashboard.app import app, load_premarket_watchlist

# Test 1: premarket watchlist loader
print("=== Test 1: load_premarket_watchlist ===")
w = load_premarket_watchlist()
print(f"Watchlist: {len(w)} stocks")
for s in w:
    print(f"  {s['symbol']}: score={s['total_score']} gap={s['gap_pct']:+.1f}%")

print()

# Test 2: scan endpoint
print("=== Test 2: /api/scan ===")
with app.test_client() as c:
    r = c.post('/api/scan', json={})
    print(f"status: {r.status_code}")
    print(f"data: {r.get_data(as_text=True)[:500]}")
