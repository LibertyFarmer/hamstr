import sqlite3
conn = sqlite3.connect('data/cashu.db')
proofs = conn.execute("SELECT amount, keyset_id, mint_url, state FROM proofs").fetchall()
print(f"Total proofs: {len(proofs)}")
for p in proofs:
    print(p)

txs = conn.execute("SELECT type, amount, memo FROM cashu_transactions").fetchall()
print(f"\nTransactions: {len(txs)}")
for t in txs:
    print(t)
conn.close()