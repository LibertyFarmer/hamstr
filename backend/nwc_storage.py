import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import json
import logging
import urllib.parse
from socketio_logger import get_socketio_logger

socketio_logger = get_socketio_logger()

class NWCStorage:
    def __init__(self, app_dir):
        """Initialize NWC storage with app directory path."""
        self.storage_path = os.path.join(app_dir, 'data', '.nwc_data')
        self._ensure_key()

    def _ensure_key(self):
        """Create or load encryption key (reuse same pattern as NSEC storage)."""
        key_path = os.path.join(os.path.dirname(self.storage_path), '.nwc_key')
        if not os.path.exists(key_path):
            # Generate a key using system-specific data
            system_data = self._get_system_data()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'hamstr_nwc_storage',  # Fixed salt is OK for our use case
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(system_data.encode()))
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, 'wb') as f:
                f.write(key)
        else:
            with open(key_path, 'rb') as f:
                key = f.read()
        
        self.fernet = Fernet(key)

    def _get_system_data(self):
        """Get system-specific data for key derivation (same as NSEC storage)."""
        import platform
        
        # Try machine-id first
        machine_id_path = '/etc/machine-id'
        if os.path.exists(machine_id_path):
            with open(machine_id_path, 'r') as f:
                return f.read().strip()
        
        # Fallback to platform-specific info
        system = platform.system()
        if system == 'Windows':
            return platform.node()  # Windows computer name
        else:
            # Linux/Mac
            try:
                return os.uname().nodename
            except AttributeError:
                return platform.node()

    def parse_nwc_uri(self, nwc_uri):
        """
        Parse NWC connection URI format:
        nostr+walletconnect://pubkey?relay=wss://relay.com&secret=hex_secret
        
        Returns dict with connection details or raises ValueError
        """
        if not nwc_uri.startswith("nostr+walletconnect://"):
            raise ValueError("Invalid NWC URI format - must start with 'nostr+walletconnect://'")
        
        # Remove protocol prefix
        uri_parts = nwc_uri[22:]  # Remove "nostr+walletconnect://"
        
        # Split pubkey from query params
        if "?" not in uri_parts:
            raise ValueError("Missing query parameters in NWC URI")
        
        pubkey, query_string = uri_parts.split("?", 1)
        
        # Parse query parameters
        params = urllib.parse.parse_qs(query_string)
        
        if "relay" not in params or "secret" not in params:
            raise ValueError("Missing required parameters (relay, secret) in NWC URI")
        
        relay = params["relay"][0]  # Take first relay if multiple
        secret = params["secret"][0]
        
        # Validate hex formats
        if len(pubkey) != 64:
            raise ValueError("Invalid pubkey length - must be 64 hex characters")
        if len(secret) != 64:
            raise ValueError("Invalid secret length - must be 64 hex characters")
        
        try:
            bytes.fromhex(pubkey)
            bytes.fromhex(secret)
        except ValueError:
            raise ValueError("Invalid hex format in pubkey or secret")
        
        return {
            'wallet_pubkey': pubkey,
            'relay': relay,
            'secret': secret
        }

    def store_nwc_connection(self, nwc_uri):
        """Store encrypted NWC connection from URI string."""
        try:
            # Parse the NWC URI
            connection_data = self.parse_nwc_uri(nwc_uri)
            
            # Add timestamp
            connection_data['timestamp'] = str(int(os.path.getctime(self.storage_path))) if os.path.exists(self.storage_path) else '0'
            
            # Encrypt and store
            encrypted_data = self.fernet.encrypt(json.dumps(connection_data).encode())
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, 'wb') as f:
                f.write(encrypted_data)
            return True
        except Exception as e:
            logging.error(f"Error storing NWC connection: {str(e)}")
            socketio_logger.error(f"[NWC] Error storing connection: {str(e)}")
            return False

    def get_nwc_connection(self):
        """Retrieve decrypted NWC connection details."""
        try:
            if not os.path.exists(self.storage_path):
                return None
            with open(self.storage_path, 'rb') as f:
                encrypted_data = f.read()
            data = json.loads(self.fernet.decrypt(encrypted_data))
            return data
        except Exception as e:
            logging.error(f"Error retrieving NWC connection: {str(e)}")
            socketio_logger.error(f"[NWC] Error retrieving connection: {str(e)}")
            return None

    def clear_nwc_connection(self):
        """Remove stored NWC connection."""
        try:
            if os.path.exists(self.storage_path):
                os.remove(self.storage_path)
            return True
        except Exception as e:
            logging.error(f"Error clearing NWC connection: {str(e)}")
            socketio_logger.error(f"[NWC] Error clearing connection: {str(e)}")
            return False

    def has_nwc_connection(self):
        """Check if NWC connection is stored."""
        return os.path.exists(self.storage_path)

    def get_nwc_relay_url(self):
        """Get just the relay URL for bandwidth-optimized packet transmission."""
        connection = self.get_nwc_connection()
        if connection and 'relay' in connection:
            return connection['relay']
        return None

    def test_nwc_connection(self, nwc_uri):
        """
        Test NWC connection validity (for online setup phase).
        This would be expanded to actually test connectivity when implementing NWC client.
        """
        try:
            # Parse URI to validate format
            connection_data = self.parse_nwc_uri(nwc_uri)
            
            # For now, just validate the format
            # TODO: In full implementation, this would connect to the relay and test auth
            logging.info(f"NWC URI format validated - Relay: {connection_data['relay']}")
            socketio_logger.info(f"[NWC] Connection format validated - Relay: {connection_data['relay']}")
            
            return {
                'success': True,
                'relay': connection_data['relay'],
                'wallet_pubkey': connection_data['wallet_pubkey'][:8] + '...'  # Partial for logging
            }
        except Exception as e:
            logging.error(f"NWC connection test failed: {str(e)}")
            socketio_logger.error(f"[NWC] Connection test failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }