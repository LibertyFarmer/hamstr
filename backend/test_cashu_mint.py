"""
Standalone test for Step 4 - run this from your backend folder:
    python test_cashu_mint.py

Tests the full mint (LN->ecash) flow against the fee-free test mint.
No real payment needed - this mint auto-settles quotes.
"""
import os
os.environ['HAMSTR_ROLE'] = 'client'
import asyncio
from cashu_wallet import CashuWallet
from cashu_db import init_cashu_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


async def main():
    init_cashu_db(BASE_DIR)
    wallet = CashuWallet(BASE_DIR)

    mint_url = "https://testnut.cashu.space"
    amount = 64

    print(f"Requesting mint quote for {amount} sats from {mint_url}...")
    quote = await wallet.request_mint_quote(mint_url, amount)
    print("Quote:", quote)

    print("Checking/completing mint (test mint auto-settles, no real payment needed)...")
    result = await wallet.check_and_complete_mint(
        mint_url, quote['quote_id'], amount, timeout=20, poll_interval=2
    )
    print("Mint completed successfully:", result)

    print("Wallet balance:", wallet.get_balance(mint_url), "sats")


if __name__ == "__main__":
    asyncio.run(main())