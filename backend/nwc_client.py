import asyncio
import json
import time
import secrets
import hashlib
import logging
from typing import Optional, Dict, Any, Tuple
import websockets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
from socketio_logger import get_socketio_logger

# Import existing NOSTR SDK components
from nostr_sdk import Keys, Event, EventBuilder, Tag, Kind, Timestamp, PublicKey, UnsignedEvent
import nostr_sdk

socketio_logger = get_socketio_logger()

class NWCClient:
    def __init__(self, connection_data: Dict[str, str]):
        """
        Initialize NWC client with connection data from parsed URI.
        
        Args:
            connection_data: Dict with 'wallet_pubkey', 'relay', 'secret'
        """
        self.wallet_pubkey = connection_data['wallet_pubkey']
        self.relay_url = connection_data['relay']
        self.client_secret_hex = connection_data['secret']
        
        # Create client keys from the secret
        self.client_keys = Keys.from_hex(self.client_secret_hex)
        self.client_pubkey = self.client_keys.public_key()
        
        # Convert wallet pubkey string to PublicKey object
        self.wallet_pubkey_obj = PublicKey.from_hex(self.wallet_pubkey)
        
        logging.info(f"[NWC] Initialized client with wallet: {self.wallet_pubkey[:8]}...")
        logging.info(f"[NWC] Client pubkey: {self.client_pubkey.to_hex()[:8]}...")
        logging.info(f"[NWC] Relay: {self.relay_url}")

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test NWC connection by requesting wallet info (kind 13194).
        This verifies connectivity and authentication.
        
        Returns:
            Dict with success status and connection details
        """
        try:
            logging.info(f"[NWC] Testing connection to {self.relay_url}")
            socketio_logger.info(f"[NWC] Testing connection to wallet via {self.relay_url}")
            
            # Connect to NWC relay
            async with websockets.connect(self.relay_url) as websocket:
                # Request wallet info event (kind 13194)
                info_filter = {
                    "kinds": [13194],
                    "authors": [self.wallet_pubkey]
                }
                
                req_message = json.dumps(["REQ", "test_info", info_filter])
                await websocket.send(req_message)
                
                # Wait for response with timeout
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(response)
                    
                    if data[0] == "EVENT":
                        event_data = data[2]
                        if event_data.get("kind") == 13194:
                            # Parse wallet capabilities
                            content = event_data.get("content", "")
                            capabilities = content.split() if content else []
                            
                            logging.info(f"[NWC] Wallet capabilities: {capabilities}")
                            socketio_logger.info(f"[NWC] Connected to wallet. Capabilities: {', '.join(capabilities)}")
                            
                            return {
                                'success': True,
                                'relay': self.relay_url,
                                'wallet_pubkey': self.wallet_pubkey[:8] + '...',
                                'capabilities': capabilities,
                                'connected': True
                            }
                    
                    # If we reach here, didn't get expected response
                    logging.warning(f"[NWC] Unexpected response format: {data}")
                    return {
                        'success': False,
                        'error': 'Wallet not responding or incompatible format'
                    }
                    
                except asyncio.TimeoutError:
                    logging.warning(f"[NWC] Connection test timeout")
                    return {
                        'success': False,
                        'error': 'Connection timeout - wallet may be offline'
                    }
                    
        except Exception as e:
            logging.error(f"[NWC] Connection test failed: {e}")
            socketio_logger.error(f"[NWC] Connection test failed: {str(e)}")
            return {
                'success': False,
                'error': f'Connection failed: {str(e)}'
            }

    def _encrypt_nip04(self, message: str) -> str:
        """
        Encrypt message using NIP-04 format for NWC communication.
        
        Args:
            message: Plaintext message to encrypt
            
        Returns:
            Encrypted message in NIP-04 format
        """
        try:
            # Generate ECDH shared secret
            shared_point = self.client_keys.ecdh(self.wallet_pubkey_obj)
            shared_secret = shared_point[:32]  # Use X coordinate only
            
            # Generate random IV
            iv = secrets.token_bytes(16)
            
            # Create AES cipher
            cipher = Cipher(
                algorithms.AES(shared_secret),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # Pad message to AES block size
            message_bytes = message.encode('utf-8')
            padding_length = 16 - (len(message_bytes) % 16)
            padded_message = message_bytes + bytes([padding_length] * padding_length)
            
            # Encrypt
            encrypted = encryptor.update(padded_message) + encryptor.finalize()
            
            # Format as base64 with IV
            encrypted_b64 = base64.b64encode(encrypted).decode()
            iv_b64 = base64.b64encode(iv).decode()
            
            return f"{encrypted_b64}?iv={iv_b64}"
            
        except Exception as e:
            logging.error(f"[NWC] Encryption failed: {e}")
            raise

    def _decrypt_nip04(self, encrypted_content: str) -> str:
        """
        Decrypt NIP-04 format message from NWC wallet.
        
        Args:
            encrypted_content: Encrypted message in format "content?iv=base64iv"
            
        Returns:
            Decrypted plaintext message
        """
        try:
            # Parse content and IV
            if "?iv=" not in encrypted_content:
                raise ValueError("Invalid NIP-04 format - missing IV")
            
            encrypted_b64, iv_b64 = encrypted_content.split("?iv=", 1)
            encrypted = base64.b64decode(encrypted_b64)
            iv = base64.b64decode(iv_b64)
            
            # Generate ECDH shared secret
            shared_point = self.client_keys.ecdh(self.wallet_pubkey_obj)
            shared_secret = shared_point[:32]  # Use X coordinate only
            
            # Create AES cipher
            cipher = Cipher(
                algorithms.AES(shared_secret),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Decrypt
            decrypted = decryptor.update(encrypted) + decryptor.finalize()
            
            # Remove padding
            padding_length = decrypted[-1]
            message = decrypted[:-padding_length]
            
            return message.decode('utf-8')
            
        except Exception as e:
            logging.error(f"[NWC] Decryption failed: {e}")
            raise

    async def send_payment_request(self, lightning_invoice: str) -> Dict[str, Any]:
        """
        Send encrypted NIP-47 payment request to wallet.
        
        Args:
            lightning_invoice: Lightning invoice to pay
            
        Returns:
            Dict with payment result
        """
        try:
            logging.info(f"[NWC] Sending payment request for invoice")
            socketio_logger.info(f"[NWC] Sending payment request to wallet")
            
            # Create payment request payload
            request_payload = {
                "method": "pay_invoice",
                "params": {
                    "invoice": lightning_invoice
                }
            }
            
            # Encrypt the payload
            encrypted_content = self._encrypt_nip04(json.dumps(request_payload))
            
            # Create NIP-47 event (kind 23194)
            tags = [
                Tag.parse(["p", self.wallet_pubkey])  # Recipient
            ]
            
            # Build and sign the event
            event_builder = EventBuilder(Kind(23194), encrypted_content, tags)
            event = self.client_keys.sign_event_builder(event_builder)
            
            # Connect to relay and send
            async with websockets.connect(self.relay_url) as websocket:
                # Send the payment request event
                event_message = json.dumps(["EVENT", event.as_json()])
                await websocket.send(event_message)
                
                # Wait for response (kind 23195)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    
                    if data[0] == "EVENT":
                        response_event = data[2]
                        if response_event.get("kind") == 23195:
                            # Decrypt the response
                            encrypted_response = response_event.get("content", "")
                            decrypted_response = self._decrypt_nip04(encrypted_response)
                            response_data = json.loads(decrypted_response)
                            
                            logging.info(f"[NWC] Payment response: {response_data}")
                            
                            if response_data.get("error"):
                                error = response_data["error"]
                                return {
                                    'success': False,
                                    'error_code': error.get("code", "UNKNOWN"),
                                    'error_message': error.get("message", "Payment failed")
                                }
                            else:
                                result = response_data.get("result", {})
                                return {
                                    'success': True,
                                    'preimage': result.get("preimage", "")
                                }
                    
                    # Unexpected response format
                    return {
                        'success': False,
                        'error_code': 'UNEXPECTED_RESPONSE',
                        'error_message': 'Unexpected response format from wallet'
                    }
                    
                except asyncio.TimeoutError:
                    return {
                        'success': False,
                        'error_code': 'TIMEOUT',
                        'error_message': 'Payment request timed out'
                    }
                    
        except Exception as e:
            logging.error(f"[NWC] Payment request failed: {e}")
            return {
                'success': False,
                'error_code': 'NETWORK_ERROR',
                'error_message': f'Payment request failed: {str(e)}'
            }

    def get_connection_summary(self) -> Dict[str, str]:
        """
        Get summary of connection details for logging/display.
        
        Returns:
            Dict with safe connection info (no secrets)
        """
        return {
            'wallet_pubkey_preview': self.wallet_pubkey[:8] + '...',
            'client_pubkey_preview': self.client_pubkey.to_hex()[:8] + '...',
            'relay': self.relay_url,
            'status': 'configured'
        }