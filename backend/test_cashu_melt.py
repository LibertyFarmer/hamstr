"""
Standalone test for the melt operation - run from your backend folder:
    python test_cashu_melt.py <invoice>

You need a real bolt11 invoice for a small amount (5-10 sats) - generate
one from any Lightning wallet you have (e.g. the NWC wallet you use for
zap testing). Whether this actually pays depends on whether the test
mint has real Lightning backing behind it - that's part of what we're
finding out. Either way, nothing you own is at risk: a failure costs
nothing (proofs are only marked spent after success), and a success
just means the mint paid your real invoice using worthless test tokens.
"""
import os
os.environ['HAMSTR_ROLE'] = 'client'
import sys
import asyncio
from cashu_wallet import CashuWallet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_cashu_melt.py <bolt11_invoice>")
        return

    invoice = sys.argv[1]
    wallet = CashuWallet(BASE_DIR)
    mint_url = "https://testnut.cashu.space"

    print(f"Balance before: {wallet.get_balance(mint_url)} sats")

    print("Requesting melt quote...")
    quote = await wallet.create_melt_quote(mint_url, invoice)
    print("Quote:", quote)

    # Small buffer on top of amount + fee_reserve since the exact NUT-02
    # input fee depends on how many proofs get selected - pay_melt_quote
    # does the authoritative check and will tell us clearly if this
    # buffer wasn't enough.
    needed_estimate = quote['amount'] + quote['fee_reserve'] + 3
    print(f"\nSelecting proofs (targeting ~{needed_estimate} sats to leave room for input fees)...")

    selection = wallet.select_proofs(needed_estimate, mint_url)
    print("Selected proofs:", selection)

    if not selection['proof_ids']:
        print("Not enough balance to cover this invoice + fees.")
        return

    print(f"\nPaying with {len(selection['proof_ids'])} proof(s), total {selection['total']} sats...")
    result = await wallet.pay_melt_quote(mint_url, quote['quote_id'], selection['proof_ids'])

    if result['success']:
        print("\nMelt reported SUCCESS.")
        if result['payment_preimage']:
            print(f"Payment preimage (proof of real payment): {result['payment_preimage']}")
        else:
            print("No preimage returned - mint claimed success but gave no independent proof.")
    else:
        print(f"\nMelt FAILED: {result.get('error', 'see traceback above')}")
        print("Nothing was spent - your balance is unaffected.")

    print(f"\nBalance after: {wallet.get_balance(mint_url)} sats")
    print("\nCheck your Lightning wallet now to see if the sats actually arrived.")
    print("That's the real confirmation - independent of anything this script reports.")


if __name__ == "__main__":
    asyncio.run(main())