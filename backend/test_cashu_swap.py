"""
Standalone test for the swap operation - run from your backend folder:
    python test_cashu_swap.py

Takes your existing unspent proof(s) and swaps them for the same total
amount, reshaped into fresh denominations. Uses the same mint your
existing proofs came from.
"""
import os
os.environ['HAMSTR_ROLE'] = 'client'
import asyncio
import sqlite3
from cashu_wallet import CashuWallet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


async def main():
    wallet = CashuWallet(BASE_DIR)

    conn = sqlite3.connect(wallet.db_path)
    rows = conn.execute(
        "SELECT id, amount, mint_url FROM proofs WHERE state = 'unspent'"
    ).fetchall()
    conn.close()

    if not rows:
        print("No unspent proofs found - run test_cashu_mint.py first.")
        return

    print("Unspent proofs before swap:")
    for r in rows:
        print(" ", r)

    mint_url = rows[0][2]
    proof_ids = [r[0] for r in rows]
    total = sum(r[1] for r in rows)

    print(f"\nSwapping {len(proof_ids)} proof(s) totaling {total} sats at {mint_url}...")
    result = await wallet.swap_proofs(mint_url, proof_ids)
    print("Swap completed successfully:", result)

    print("\nBalance after swap:", wallet.get_balance(mint_url), "sats")


if __name__ == "__main__":
    asyncio.run(main())