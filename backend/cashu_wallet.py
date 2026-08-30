"""
Cashu wallet for HAMSTR.

Uses sixty_nuts.crypto and sixty_nuts.mint as low-level primitives only -
never sixty_nuts.wallet or sixty_nuts.relay. State lives in our own
cashu.db (see cashu_db.py), not synced to relays automatically. This
keeps the client fully radio-only-capable; any Nostr relay sync (NIP-60)
is a separate, explicitly-online-only feature layered on top later.
"""
import os
import sqlite3
import time
import uuid
import asyncio

from sixty_nuts import crypto
from sixty_nuts.mint import Mint
from coincurve import PublicKey

from socketio_logger import get_socketio_logger
from cashu_db import get_cashu_db_path

socketio_logger = get_socketio_logger()


class CashuWallet:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.db_path = get_cashu_db_path(base_dir)

    def _conn(self):
        return sqlite3.connect(self.db_path)

    # ───────────────────────── Local proof storage ─────────────────────────

    def get_balance(self, mint_url=None):
        """Sum of unspent proofs, optionally filtered to one mint."""
        conn = self._conn()
        try:
            if mint_url:
                row = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM proofs WHERE state = 'unspent' AND mint_url = ?",
                    (mint_url,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM proofs WHERE state = 'unspent'"
                ).fetchone()
            return row[0]
        finally:
            conn.close()

    def _store_proof(self, conn, amount, secret, C, keyset_id, mint_url):
        conn.execute(
            "INSERT INTO proofs (id, amount, secret, C, keyset_id, mint_url, state, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'unspent', ?)",
            (str(uuid.uuid4()), amount, secret, C, keyset_id, mint_url, int(time.time()))
        )

    def _record_transaction(self, conn, tx_type, amount, memo=None, event_id=None):
        conn.execute(
            "INSERT INTO cashu_transactions (id, type, amount, memo, event_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), tx_type, amount, memo, event_id, int(time.time()))
        )

    # ───────────────────────── Mint operations ─────────────────────────────

    async def _get_active_keyset(self, mint):
        """Get the first active keyset with a 'sat' unit for this mint."""
        keysets = await mint.get_active_keysets()
        for ks in keysets:
            if ks["unit"] == "sat":
                return ks
        if keysets:
            return keysets[0]
        raise RuntimeError("Mint returned no active keysets")

    async def request_mint_quote(self, mint_url, amount):
        """Step 1 of minting: get a Lightning invoice to pay.

        Returns dict with 'quote_id' and 'invoice' (bolt11 string).
        On the fee-free test mint, this invoice is fake and paying it
        is not required - the quote settles automatically.
        """
        mint = Mint(mint_url)
        try:
            quote = await mint.create_mint_quote(amount=amount, unit="sat")
            socketio_logger.info(f"[CASHU] Mint quote created: {quote.get('quote')}")
            return {
                "quote_id": quote["quote"],
                "invoice": quote.get("request", ""),
            }
        finally:
            await mint.aclose()

    async def check_and_complete_mint(self, mint_url, quote_id, amount, timeout=30, poll_interval=2):
        """Poll a mint quote until paid, then mint and store the resulting proofs.

        Returns True if proofs were successfully minted and stored, False on timeout/failure.
        """
        mint = Mint(mint_url)
        try:
            waited = 0
            while waited < timeout:
                status = await mint.get_mint_quote(quote_id)
                if status.get("paid") or status.get("state") == "PAID":
                    break
                await asyncio.sleep(poll_interval)
                waited += poll_interval
            else:
                socketio_logger.error(f"[CASHU] Mint quote {quote_id} not paid within {timeout}s")
                return False

            keyset = await self._get_active_keyset(mint)
            keyset_id = keyset["id"]

            outputs, secrets_list, blinding_factors = crypto.create_blinded_messages_for_amount(
                amount, keyset_id
            )

            mint_response = await mint.mint(quote=quote_id, outputs=outputs)
            signatures = mint_response["signatures"]

            conn = self._conn()
            try:
                for sig, secret_hex, r_hex in zip(signatures, secrets_list, blinding_factors):
                    K = crypto.get_mint_pubkey_for_amount(keyset["keys"], sig["amount"])
                    if K is None:
                        socketio_logger.error(f"[CASHU] No mint pubkey for amount {sig['amount']}")
                        continue
                    C_ = PublicKey(bytes.fromhex(sig["C_"]))
                    C = crypto.unblind_signature(C_, bytes.fromhex(r_hex), K)
                    self._store_proof(
                        conn,
                        amount=sig["amount"],
                        secret=secret_hex,
                        C=C.format(compressed=True).hex(),
                        keyset_id=sig["id"],
                        mint_url=mint_url,
                    )
                self._record_transaction(conn, "mint", amount, memo=f"Minted from {mint_url}")
                conn.commit()
                socketio_logger.info(f"[CASHU] Minted {amount} sats from {mint_url}")
                return True
            finally:
                conn.close()
        except Exception as e:
            import traceback
            traceback.print_exc()
            socketio_logger.error(f"[CASHU] Error completing mint: {e}")
            return False
        finally:
            await mint.aclose()

    # ───────────────────────── Swap / consolidation ─────────────────────────

    async def _get_input_fee(self, mint, keyset_ids):
        """Calculate the NUT-02 input fee for a set of input proofs' keyset ids.

        fee = ceil(sum(input_fee_ppk for each input) / 1000)
        Most mints (like the fee-free test mint) have input_fee_ppk = 0,
        but real mints often charge a small per-input fee on swaps/melts.
        """
        keysets_info = await mint.get_keysets_info()
        fee_ppk_by_id = {ks["id"]: ks.get("input_fee_ppk", 0) for ks in keysets_info}
        total_ppk = sum(fee_ppk_by_id.get(kid, 0) for kid in keyset_ids)
        return -(-total_ppk // 1000)  # ceiling division, no float rounding issues

    async def swap_proofs(self, mint_url, proof_ids, new_total=None):
        """Swap a set of local proofs (by their local db 'id') for fresh ones.

        Used both to consolidate fragmented denominations (optimize before a
        send) and, later, to unlock/reshape proofs. If new_total is omitted,
        the swap preserves the same total amount, just re-minted into
        possibly different denominations.

        Returns True on success, False on failure. Old proofs are marked
        'spent' only after the mint confirms the swap succeeded.
        """
        conn = self._conn()
        try:
            placeholders = ",".join("?" for _ in proof_ids)
            rows = conn.execute(
                f"SELECT id, amount, secret, C, keyset_id, mint_url FROM proofs "
                f"WHERE id IN ({placeholders}) AND state = 'unspent'",
                proof_ids
            ).fetchall()

            if len(rows) != len(proof_ids):
                socketio_logger.error("[CASHU] Some requested proofs are missing or already spent")
                return False

            total_in = sum(r[1] for r in rows)

            inputs = [
                {
                    "id": r[4],
                    "amount": r[1],
                    "secret": r[2],
                    "C": r[3],
                }
                for r in rows
            ]
        finally:
            conn.close()

        mint = Mint(mint_url)
        try:
            keyset = await self._get_active_keyset(mint)
            keyset_id = keyset["id"]

            if new_total is not None:
                amount_out = new_total
            else:
                input_keyset_ids = [r[4] for r in rows]
                fee = await self._get_input_fee(mint, input_keyset_ids)
                amount_out = total_in - fee
                if fee > 0:
                    socketio_logger.info(f"[CASHU] Swap fee: {fee} sat(s) - {total_in} -> {amount_out}")

            outputs, secrets_list, blinding_factors = crypto.create_blinded_messages_for_amount(
                amount_out, keyset_id
            )

            swap_response = await mint.swap(inputs=inputs, outputs=outputs)
            signatures = swap_response["signatures"]

            conn = self._conn()
            try:
                for sig, secret_hex, r_hex in zip(signatures, secrets_list, blinding_factors):
                    K = crypto.get_mint_pubkey_for_amount(keyset["keys"], sig["amount"])
                    if K is None:
                        socketio_logger.error(f"[CASHU] No mint pubkey for amount {sig['amount']}")
                        continue
                    C_ = PublicKey(bytes.fromhex(sig["C_"]))
                    C = crypto.unblind_signature(C_, bytes.fromhex(r_hex), K)
                    self._store_proof(
                        conn,
                        amount=sig["amount"],
                        secret=secret_hex,
                        C=C.format(compressed=True).hex(),
                        keyset_id=sig["id"],
                        mint_url=mint_url,
                    )

                # Only mark old proofs spent after new ones are safely stored
                placeholders = ",".join("?" for _ in proof_ids)
                conn.execute(
                    f"UPDATE proofs SET state = 'spent' WHERE id IN ({placeholders})",
                    proof_ids
                )
                self._record_transaction(conn, "swap", amount_out, memo=f"Swapped {total_in} -> {amount_out} at {mint_url}")
                conn.commit()
                socketio_logger.info(f"[CASHU] Swapped {total_in} sats into {len(signatures)} new proof(s)")
                return True
            finally:
                conn.close()
        except Exception as e:
            import traceback
            traceback.print_exc()
            socketio_logger.error(f"[CASHU] Error swapping proofs: {e}")
            return False
        finally:
            await mint.aclose()

    # ───────────────────────── Melt (send to Lightning) ─────────────────────

    async def create_melt_quote(self, mint_url, invoice):
        """Get a quote for paying a Lightning invoice with ecash.

        Returns dict with 'quote_id', 'amount' (sats to pay), and
        'fee_reserve' (max routing fee the mint may need - refunded as
        change via NUT-08 if the real fee is lower).
        """
        mint = Mint(mint_url)
        try:
            quote = await mint.create_melt_quote(invoice, unit="sat")
            return {
                "quote_id": quote["quote"],
                "amount": quote["amount"],
                "fee_reserve": quote.get("fee_reserve", 0),
            }
        finally:
            await mint.aclose()

    async def pay_melt_quote(self, mint_url, quote_id, proof_ids):
        """Pay a melt quote using the given local proofs (by db 'id').

        Selected proofs must total at least amount + fee_reserve + the
        NUT-02 input fee for however many proofs are used. Any unused
        fee reserve is recovered as change (NUT-08) and stored as a
        fresh proof rather than lost.
        """
        conn = self._conn()
        try:
            placeholders = ",".join("?" for _ in proof_ids)
            rows = conn.execute(
                f"SELECT id, amount, secret, C, keyset_id, mint_url FROM proofs "
                f"WHERE id IN ({placeholders}) AND state = 'unspent'",
                proof_ids
            ).fetchall()

            if len(rows) != len(proof_ids):
                socketio_logger.error("[CASHU] Some requested proofs are missing or already spent")
                return False

            total_in = sum(r[1] for r in rows)
            inputs = [
                {"id": r[4], "amount": r[1], "secret": r[2], "C": r[3]}
                for r in rows
            ]
        finally:
            conn.close()

        mint = Mint(mint_url)
        try:
            melt_quote = await mint.get_melt_quote(quote_id)
            fee_reserve = melt_quote.get("fee_reserve", 0)
            amount = melt_quote.get("amount", 0)

            input_keyset_ids = [r[4] for r in rows]
            input_fee = await self._get_input_fee(mint, input_keyset_ids)
            required_total = amount + fee_reserve + input_fee

            if total_in < required_total:
                socketio_logger.error(
                    f"[CASHU] Insufficient proofs for melt: selected {total_in}, "
                    f"need {required_total} (amount {amount} + fee_reserve {fee_reserve} + input_fee {input_fee})"
                )
                return {
                    "success": False,
                    "payment_preimage": None,
                    "error": f"Selected {total_in} sats, need {required_total} "
                             f"(invoice {amount} + routing fee_reserve {fee_reserve} + input_fee {input_fee})",
                }

            keyset = await self._get_active_keyset(mint)
            keyset_id = keyset["id"]

            # Blank outputs sized to cover the maximum possible change
            change_outputs, change_secrets, change_blinding_factors = (
                crypto.create_blinded_messages_for_amount(fee_reserve, keyset_id)
                if fee_reserve > 0 else ([], [], [])
            )

            melt_response = await mint.melt(quote=quote_id, inputs=inputs, outputs=change_outputs or None)
            payment_preimage = melt_response.get("payment_preimage")

            conn = self._conn()
            try:
                # Mark spent proofs
                placeholders = ",".join("?" for _ in proof_ids)
                conn.execute(
                    f"UPDATE proofs SET state = 'spent' WHERE id IN ({placeholders})",
                    proof_ids
                )

                # Recover any change the mint signed back
                change_sigs = melt_response.get("change") or []
                change_total = 0
                for sig, secret_hex, r_hex in zip(change_sigs, change_secrets, change_blinding_factors):
                    K = crypto.get_mint_pubkey_for_amount(keyset["keys"], sig["amount"])
                    if K is None:
                        continue
                    C_ = PublicKey(bytes.fromhex(sig["C_"]))
                    C = crypto.unblind_signature(C_, bytes.fromhex(r_hex), K)
                    self._store_proof(
                        conn,
                        amount=sig["amount"],
                        secret=secret_hex,
                        C=C.format(compressed=True).hex(),
                        keyset_id=sig["id"],
                        mint_url=mint_url,
                    )
                    change_total += sig["amount"]

                actual_fee = total_in - change_total - melt_quote.get("amount", 0)
                self._record_transaction(
                    conn, "melt", melt_quote.get("amount", 0),
                    memo=f"Paid Lightning invoice via {mint_url} (fee: {actual_fee} sat, change: {change_total} sat)"
                )
                conn.commit()
                socketio_logger.info(
                    f"[CASHU] Melt complete: paid {melt_quote.get('amount', 0)} sats, "
                    f"fee {actual_fee}, change {change_total} recovered"
                )
                return {"success": True, "payment_preimage": payment_preimage}
            finally:
                conn.close()
        except Exception as e:
            import traceback
            traceback.print_exc()
            socketio_logger.error(f"[CASHU] Error melting proofs: {e}")
            return {"success": False, "payment_preimage": None, "error": str(e)}
        finally:
            await mint.aclose()

    # ───────────────────────── Proof selection ──────────────────────────────

    def select_proofs(self, amount, mint_url=None):
        """Select unspent proofs to cover an amount.

        Returns dict with:
          'exact': True/False - whether the selected proofs sum to exactly `amount`
          'proof_ids': list of local proof ids selected
          'total': actual sum of selected proofs

        Strategy: fewest proofs covering the amount. If no exact match is
        possible from proofs on hand, selects the smallest total that is
        >= amount (never under) and reports 'exact': False so the caller
        can offer the adjusted amount, never silently under-deliver.
        """
        conn = self._conn()
        try:
            if mint_url:
                rows = conn.execute(
                    "SELECT id, amount FROM proofs WHERE state = 'unspent' AND mint_url = ? ORDER BY amount DESC",
                    (mint_url,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, amount FROM proofs WHERE state = 'unspent' ORDER BY amount DESC"
                ).fetchall()
        finally:
            conn.close()

        amounts = [r[1] for r in rows]
        n = len(amounts)

        # Exhaustive search only when cheap. Denominations are powers of 2,
        # so wallets rarely hold many proofs at once - but guard against an
        # exponential blowup if one ever does accumulate many.
        if n > 20:
            return self._select_proofs_greedy(rows, amount)

        best = None  # (total, ids)
        for mask in range(1, 1 << n):
            total = 0
            ids = []
            for i in range(n):
                if mask & (1 << i):
                    total += amounts[i]
                    ids.append(rows[i][0])
            if total >= amount:
                if best is None or total < best[0] or (total == best[0] and len(ids) < len(best[1])):
                    best = (total, ids)
                    if total == amount:
                        break  # can't do better than exact

        if best is None:
            return {"exact": False, "proof_ids": [], "total": 0}

        return {
            "exact": best[0] == amount,
            "proof_ids": best[1],
            "total": best[0],
        }

    def _select_proofs_greedy(self, rows, amount):
        """Fast fallback for select_proofs when there are too many proofs
        for exhaustive search. Not guaranteed optimal (may pick more
        proofs or a higher total than strictly necessary) but always
        correct: never under-delivers, always terminates quickly.
        """
        total = 0
        ids = []
        for proof_id, proof_amount in rows:  # already sorted largest-first
            if total >= amount:
                break
            total += proof_amount
            ids.append(proof_id)

        if total < amount:
            return {"exact": False, "proof_ids": [], "total": 0}

        return {
            "exact": total == amount,
            "proof_ids": ids,
            "total": total,
        }