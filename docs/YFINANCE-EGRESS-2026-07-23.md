# YFINANCE-EGRESS-2026-07-23

**Severity:** MEDIUM (not a Phase A blocker, but will block Phase B real scanner work)
**Status:** OPEN
**Created:** 2026-07-23 18:17 Berlin
**Owner:** TBD (Kay to assign, or auto-task to gitea-agent / nas-ssh-access for investigation)

---

## Symptom

`yfinance` outbound calls from the `trading-agent-dev` container on the NAS time out after 30 seconds:

```
curl: (28) Connection timed out after 30002 milliseconds
```

`fincept_connector.py` falls back to a stub and gets 20/24 quotes (HTTP 404 for 4 delisted symbols: NKLA, MAXN, OPGN, MULN).

## Impact

- **Phase A (Dev environment) smoke test:** Not impacted. smoke_e2e.py doesn't depend on yfinance.
- **Phase B (UAT) real scanner work:** BLOCKED. The premarket and intraday scanners that pull quotes from yfinance will degrade. The 4 HTTP 404 delisted symbols (NKLA, MAXN, OPGN, MULN) will need to be filtered out at the source list level.

## Root Cause (Suspected)

The NAS host (`10.8.0.10`) has restricted egress. The container inherits the host's network namespace (default Docker setup, not network=host but bridged with NAT), so outbound TCP from the container to `query1.finance.yahoo.com` and friends is filtered by either:
- A firewall rule on the NAS (iptables on ADM)
- The Asustor ADM default outbound policy
- ISP-level block (less likely — yfinance is a common service)

Not yet confirmed which. The container is on the `trading-agent_default` Docker network.

## Workarounds (in priority order)

### Option A: Pre-fetch and cache quotes (recommended for Day 5)

Use a `quotes_cache` service on the Windows host (or a container with working egress) to pre-fetch and serve quotes from a local cache. The agent reads from cache instead of direct yfinance.

Pros: Zero infra change, works around the egress issue.
Cons: Stale data risk (cache TTL), adds a dependency on Windows-side polling.

### Option B: Add yfinance to an allowlist on the NAS

Investigate Asustor ADM's firewall / Security Advisor. Add `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, etc. to an outbound allowlist.

Pros: Real-time data, no staleness.
Cons: Requires NAS admin access + verifying the firewall UI. May not be possible on Asustor ADM.

### Option C: Use Alpaca instead of yfinance for quotes

Alpaca is already wired into the system (the Bull/Bear pipeline uses Alpaca WS). Switch the scanner source from yfinance to Alpaca's `stocks/snapshots` API.

Pros: Already authenticated, no new egress, professional-grade data.
Cons: Alpaca's free tier has rate limits (200 requests/min). Will need batching.

### Option D: Use IBKR market data instead

Once REA-0.3 (IBKR market data subs on `DU1234567`) is resolved, the IBKR relay (`scripts/ibgw_relay.py`) can serve quotes via `/marketdata/snapshot`.

Pros: Single source of truth (IBKR is the broker).
Cons: Blocked on REA-0.3. And IBKR market data subscriptions cost extra.

## Recommendation

Go with **Option A** for Day 5 (pre-fetch cache on Windows). Plan to migrate to **Option C** (Alpaca) once Bull/Bear pipeline is fully wired and stable. **Option D** is the long-term target.

## Investigation TODO (delegate to nas-ssh-access)

1. Verify egress is blocked, not just slow: `docker exec trading-agent-dev timeout 10 curl -v https://query1.finance.yahoo.com/v7/finance/quote 2>&1 | head -30`
2. Test other common endpoints: `docker exec ... timeout 10 curl -v https://api.alpaca.markets/v2/stocks/snapshots?symbols=AAPL 2>&1 | head -30`
3. Check NAS firewall rules: `ssh Ai_agent_01@10.8.0.10 sudo iptables -L -n 2>&1 | head -30` (may need sudo, may not be available)
4. Check ADM Security Advisor: log into `https://10.8.0.10:19943` → Security Advisor → see if outbound is restricted

## Decision Pending

Kay to choose Option A, B, C, or D. Each has different cost/benefit tradeoffs.

---

*See also:*
- `E:\Me\TradingAgent\scripts\fincept_connector.py` — current yfinance wrapper with fallback
- `E:\Me\TradingAgent\trading_agent\data_plane\` — where scanner data is assembled
- `E:\Me\TradingAgent\docs\point-of-truth.md` — Day 4 final update (Phase A green)
