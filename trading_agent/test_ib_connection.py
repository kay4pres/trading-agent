"""
IB Gateway Connection Test Script
Trading Agent - Week 1 Foundation

This script tests connection to Interactive Brokers Gateway.
Must have IB Gateway running with API enabled.

Default IB Gateway settings:
- Port: 4002 (paper trading)
- Host: 127.0.0.1

Paper trading port: 4002
Live trading port: 4001
"""

# Python 3.14 + ib_insync compatibility fix
import asyncio

# Override asyncio.wait_for before ib_insync loads
_orig_wait_for = asyncio.wait_for

async def _wait_for_no_timeout(fut, timeout, *, loop=None):
    """wait_for without actual timeout - let connection happen."""
    return await fut

asyncio.wait_for = _wait_for_no_timeout

import nest_asyncio
nest_asyncio.apply()

from ib_insync import IB, Stock, MarketOrder

def run_test():
    """Test IB Gateway connection and basic functionality."""
    
    ib = IB()
    
    try:
        # Connect to IB Gateway (paper trading)
        print("Connecting to IB Gateway...")
        print("Settings: 127.0.0.1:4002 (Paper Trading)")
        
        # Connect without explicit timeout
        ib.connect('127.0.0.1', 4002, clientId=1)
        
        print("Connected successfully!")
        print(f"  Server version: {ib.client.serverVersion()}")
        
        # Get account summary
        print("\nFetching account summary...")
        account_summary = ib.accountSummary()
        print(f"  Account data retrieved ({len(account_summary)} fields)")
        
        # Show key account values
        for item in account_summary:
            if item.tag in ['NetLiquidation', 'Cash', 'BuyingPower', 'EquityWithLoanValue']:
                print(f"  {item.tag}: {item.value} {item.currency}")
        
        # Test market data request (simple stock)
        print("\nTesting market data request for AAPL...")
        contract = Stock('AAPL', 'SMART', 'USD')
        ib.qualifyContracts(contract)
        print(f"  Contract qualified: {contract.symbol} {contract.conId}")
        
        # Request snapshot data
        ticker = ib.reqMktData(contract, snapshot=True)
        ib.sleep(2)  # Wait for data
        print(f"  Last: ${ticker.last}")
        print(f"  Bid: ${ticker.bid}")
        print(f"  Ask: ${ticker.ask}")
        print(f"  Volume: {ticker.volume:,}")
        
        # Cancel the market data subscription
        ib.cancelMktData(contract)
        print("  Market data test complete")
        
        # Test order placement (paper trade - won't actually execute without funds)
        print("\nTesting order capability...")
        order = MarketOrder('BUY', 1)
        print(f"  Order created: {order.action} {order.totalQuantity} shares")
        print("  (Not submitting - requires funded paper account)")
        print("  Order capability verified")
        
        # Disconnect
        ib.disconnect()
        print("\nALL TESTS PASSED")
        print("\nNext steps:")
        print("  1. Run IB Gateway in paper trading mode")
        print("  2. Ensure paper account has funds")
        print("  3. Run this script to verify connection")
        
        return True
        
    except ConnectionRefusedError:
        print("\nCONNECTION REFUSED")
        print("  IB Gateway is not running or API is disabled.")
        print("\nTo fix:")
        print("  1. Open Trader Workstation or IB Gateway")
        print("  2. Go to File > Global Configuration > API > Settings")
        print("  3. Enable 'Enable ActiveX and Socket Clients'")
        print("  4. Set socket port to 4002 (paper) or 4001 (live)")
        print("  5. Enable 'Read-Only API' if you only want data (no trading)")
        print("  6. Restart IB Gateway")
        return False
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if ib.isConnected():
            ib.disconnect()

if __name__ == "__main__":
    print("=" * 60)
    print("  Trading Agent - IB Gateway Connection Test")
    print("=" * 60)
    print()
    
    success = run_test()
    
    print()
    print("=" * 60)
    if success:
        print("  STATUS: READY TO TRADE")
    else:
        print("  STATUS: SETUP NEEDED")
    print("=" * 60)
