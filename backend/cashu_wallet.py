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
            socketio_logger.error(f"[CASHU] Error completing mint: {e}")
            return False
        finally:
            await mint.aclose()