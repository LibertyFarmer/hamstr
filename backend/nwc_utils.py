# Cross-platform nwc_utils using cryptography library (like your existing nwc_client.py)
import json
import base64
import time
import math
import hashlib
import secrets
import os # Added for os.urandom for IV

# Removed old Crypto imports as they are replaced by cryptography
# from Crypto import Random
# from Crypto.Cipher import AES

# Imports for cryptography library
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives import serialization # Needed for loading public keys from bytes

# nostr_sdk is used for key parsing and signing fallback
from nostr_sdk import Keys, PublicKey

# secp256k1 is an optional dependency, but we'll use cryptography for ECDH consistently
# try:
#     from secp256k1 import PrivateKey, PublicKey as Secp256k1PublicKey  # type: ignore
#     HAS_SECP256K1 = True
#     print("[NWC] Using secp256k1 for crypto operations")
# except ImportError:
#     HAS_SECP256K1 = False
#     print("[NWC] secp256k1 not available, using cryptography fallback")

# NIP-04 does not use custom padding/unpadding functions, cryptography handles PKCS7 padding
# BS = 16
# pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
# unpad = lambda s : s[:-ord(s[len(s)-1:])]

def _derive_shared_secret(privkey_hex: str, pubkey_hex: str) -> bytes:
    """
    Derives the NIP-04 shared secret (32-byte X-coordinate) using ECDH.
    Uses cryptography library.
    """
    # Load private key
    priv_key_int = int(privkey_hex, 16)
    private_key = ec.derive_private_key(priv_key_int, ec.SECP256K1(), default_backend())

    # Load public key
    # NIP-04 public keys are typically the 32-byte X-coordinate.
    # cryptography's from_encoded_point expects a compressed (02/03 prefix) or uncompressed (04 prefix) point.
    # We must prepend '02' for the compressed form if it's just the raw x-coordinate.
    if len(pubkey_hex) == 64:
        public_key_bytes = bytes.fromhex('02' + pubkey_hex)
    elif len(pubkey_hex) == 66 and (pubkey_hex.startswith('02') or pubkey_hex.startswith('03')):
        public_key_bytes = bytes.fromhex(pubkey_hex)
    elif len(pubkey_hex) == 128 and pubkey_hex.startswith('04'):
        public_key_bytes = bytes.fromhex(pubkey_hex)
    else:
        raise ValueError(f"Public key hex '{pubkey_hex}' is not in a recognized 64-char (x-coord), 66-char (compressed), or 128-char (uncompressed) hex format.")

    public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), public_key_bytes)

    # Derive shared secret (X-coordinate of the shared point)
    shared_secret = private_key.exchange(ec.ECDH(), public_key)
    
    # Ensure it's 32 bytes for AES-256 key
    if len(shared_secret) != 32:
        raise ValueError(f"Derived shared secret length is not 32 bytes ({len(shared_secret)}). Expected for AES key.")
    
    return shared_secret

def encrypt(privkey_hex, pubkey_hex, plaintext):
    """NIP-04 encryption using cryptography library for standard ECDH and AES-256-CBC."""
    try:
        # Derive AES key using standard ECDH
        aes_key = _derive_shared_secret(privkey_hex, pubkey_hex)
        
        # PKCS7 padding
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded_plaintext = padder.update(plaintext.encode('utf-8')) + padder.finalize()

        # Generate a random 16-byte IV (block_size is in bits, os.urandom expects bytes)
        iv = os.urandom(algorithms.AES.block_size // 8) # Corrected: Divide by 8 to get bytes

        # Create AES-CBC cipher.
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_plaintext) + encryptor.finalize()

        # Convert to base64
        cipher_b64 = base64.b64encode(ciphertext).decode('ascii')
        iv_b64 = base64.b64encode(iv).decode('ascii')

        return cipher_b64 + "?iv=" + iv_b64
    except Exception as e:
        raise Exception(f"Encryption failed: {e}")

def decrypt(privkey_hex, pubkey_hex, encrypted_content):
    """NIP-04 decryption using cryptography library for standard ECDH and AES-256-CBC."""
    try:
        if '?iv=' not in encrypted_content:
            raise ValueError("Invalid NIP-04 content format: missing '?iv=' separator.")

        parts = encrypted_content.split('?iv=')
        if len(parts) != 2:
            raise ValueError("Invalid NIP-04 content format: incorrect number of parts after splitting by '?iv='.")

        ciphertext_b64 = parts[0]
        iv_b64 = parts[1]

        ciphertext = base64.b64decode(ciphertext_b64)
        iv = base64.b64decode(iv_b64)

        # Derive AES key using standard ECDH
        aes_key = _derive_shared_secret(privkey_hex, pubkey_hex)

        # Create AES-CBC cipher.
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # Unpad PKCS7
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        plaintext_bytes = unpadder.update(padded_plaintext) + unpadder.finalize()
        
        return plaintext_bytes.decode('utf-8')
    except Exception as e:
        raise Exception(f"Decryption failed: {e}")

def sha256(text_to_hash):
    """SHA256 hash function"""
    m = hashlib.sha256()
    m.update(bytes(text_to_hash, 'UTF-8'))
    return m.digest().hex()

def getSignedEvent(event, privkey):
    """Create properly signed NOSTR event using nostr-sdk"""
    try:
        # Calculate event ID using correct NIP-01 format
        eventData = json.dumps([
            0,
            event['pubkey'],
            event['created_at'],
            event['kind'],
            event['tags'],
            event['content']
        ], separators=(',', ':'))
        
        event["id"] = sha256(eventData)
        
        # Use nostr-sdk for signing
        client_keys = Keys.parse(privkey) # privkey should be hex string
        event_id_bytes = bytes.fromhex(event["id"])
        signature = client_keys.sign_schnorr(event_id_bytes) # Removed .to_hex()
        event["sig"] = signature
        
        return event
    except Exception as e:
        raise Exception(f"Event signing failed: {e}")

def processNWCstring(string):
    """Parse NWC connection string"""
    if string[0:22] != "nostr+walletconnect://":
        print('Your pairing string was invalid, try one that starts with this: nostr+walletconnect://')
        return None
        
    string = string[22:]
    arr = string.split("&")
    item = arr[0].split("?")
    del arr[0]
    arr.insert(0, item[0])
    arr.insert(1, item[1])
    arr[0] = "wallet_pubkey=" + arr[0]
    arr2 = []
    obj = {}
    
    for item in arr:
        item = item.split("=")
        arr2.append(item[0])
        arr2.append(item[1])
        
    for index, item in enumerate(arr2):
        if item == "secret":
            arr2[index] = "app_privkey"
            
    for index, item in enumerate(arr2):
        if index % 2:
            obj[arr2[index - 1]] = item
    
    # Derive app_pubkey using nostr_sdk (consistent and reliable)
    try:
        client_keys = Keys.parse(obj["app_privkey"]) # app_privkey should be hex string
        obj["app_pubkey"] = client_keys.public_key().to_hex()
    except Exception as e:
        raise Exception(f"Failed to derive app_pubkey: {e}")
        
    return obj

# NWC Command Functions

def makeInvoice(nwc_obj, amt, desc):
    """Create Lightning invoice via NWC"""
    msg = json.dumps({
        "method": "make_invoice",
        "params": {
            "amount": amt * 1000,
            "description": desc,
        }
    })
    emsg = encrypt(nwc_obj["app_privkey"], nwc_obj["wallet_pubkey"], msg)
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [["p", nwc_obj["wallet_pubkey"]]],
        "created_at": math.floor(time.time()),
        "pubkey": nwc_obj["app_pubkey"],
    }
    event = getSignedEvent(obj, nwc_obj["app_privkey"])
    return event

def getBalance(nwc_obj):
    """Get wallet balance via NWC"""
    msg = {
        "method": "get_balance"
    }
    msg = json.dumps(msg)
    emsg = encrypt(nwc_obj["app_privkey"], nwc_obj["wallet_pubkey"], msg)
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [["p", nwc_obj["wallet_pubkey"]]],
        "created_at": math.floor(time.time()),
        "pubkey": nwc_obj["app_pubkey"],
    }
    event = getSignedEvent(obj, nwc_obj["app_privkey"])
    return event

def listTx(nwc_obj, params={}):
    """List transactions via NWC"""
    msg = {
        "method": "list_transactions",
        "params": params
    }
    msg = json.dumps(msg)
    emsg = encrypt(nwc_obj["app_privkey"], nwc_obj["wallet_pubkey"], msg)
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [["p", nwc_obj["wallet_pubkey"]]],
        "created_at": math.floor(time.time()),
        # Corrected: pubkey should be app_pubkey from nwc_obj, not app_privkey
        "pubkey": nwc_obj["app_pubkey"], 
    }
    event = getSignedEvent(obj, nwc_obj["app_privkey"])
    return event

def checkInvoice(nwc_obj, invoice=None, payment_hash=None):
    """Check invoice status via NWC"""
    if invoice is None and payment_hash is None:
        raise ValueError("Either 'invoice' or 'payment_hash' must be provided")
    
    params = {}
    if invoice is not None:
        params["invoice"] = invoice
    if payment_hash is not None:
        params["payment_hash"] = payment_hash

    msg = json.dumps({
        "method": "lookup_invoice",
        "params": params
    })
    emsg = encrypt(nwc_obj["app_privkey"], nwc_obj["wallet_pubkey"], msg)
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [["p", nwc_obj["wallet_pubkey"]]],
        "created_at": math.floor(time.time()),
        "pubkey": nwc_obj["app_pubkey"],
    }
    event = getSignedEvent(obj, nwc_obj["app_privkey"])
    return event

def getInfo(nwc_obj):
    """Get wallet info via NWC"""
    msg = {
        "method": "get_info"
    }
    msg = json.dumps(msg)
    emsg = encrypt(nwc_obj["app_privkey"], nwc_obj["wallet_pubkey"], msg)
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [["p", nwc_obj["wallet_pubkey"]]],
        "created_at": math.floor(time.time()),
        "pubkey": nwc_obj["app_pubkey"],
    }
    event = getSignedEvent(obj, nwc_obj["app_privkey"])
    return event

def tryToPayInvoice(nwc_obj, invoice, amnt=None):
    """Pay Lightning invoice via NWC (creates event only - no websocket sending)"""
    msg = {
        "method": "pay_invoice",
        "params": {
            "invoice": invoice,
        }
    }
    if amnt: 
        msg["params"]["amount"] = amnt
    msg = json.dumps(msg)
    emsg = encrypt(nwc_obj["app_privkey"], nwc_obj["wallet_pubkey"], msg)
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [["p", nwc_obj["wallet_pubkey"]]],
        "created_at": math.floor(time.time()),
        "pubkey": nwc_obj["app_pubkey"],
    }
    event = getSignedEvent(obj, nwc_obj["app_privkey"])
    return event

def didPaymentSucceed(nwc_obj, invoice):
    """Check if payment succeeded - returns event for checking"""
    return checkInvoice(nwc_obj, invoice=invoice)