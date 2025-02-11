import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import json
import logging
from socketio_logger import get_socketio_logger

socketio_logger = get_socketio_logger()

class NSECStorage:
    def __init__(self, app_dir):
        """Initialize NSEC storage with app directory path."""
        self.storage_path = os.path.join(app_dir, 'data', '.nsec_data')
        self._ensure_key()

    def _ensure_key(self):
        """Create or load encryption key."""
        key_path = os.path.join(os.path.dirname(self.storage_path), '.nsec_key')
        if not os.path.exists(key_path):
            # Generate a key using system-specific data
            system_data = self._get_system_data()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'hamstr_nsec_storage',  # Fixed salt is OK for our use case
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
        """Get system-specific data for key derivation."""
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

    def store_nsec(self, nsec):
        """Store encrypted NSEC."""
        try:
            data = {
                'nsec': nsec,
                'timestamp': str(int(os.path.getctime(self.storage_path))) if os.path.exists(self.storage_path) else '0'
            }
            encrypted_data = self.fernet.encrypt(json.dumps(data).encode())
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, 'wb') as f:
                f.write(encrypted_data)
            return True
        except Exception as e:
            logging.error(f"Error storing NSEC: {str(e)}")
            return False

    def get_nsec(self):
        """Retrieve decrypted NSEC."""
        try:
            if not os.path.exists(self.storage_path):
                return None
            with open(self.storage_path, 'rb') as f:
                encrypted_data = f.read()
            data = json.loads(self.fernet.decrypt(encrypted_data))
            return data['nsec']
        except Exception as e:
            logging.error(f"Error retrieving NSEC: {str(e)}")
            return None

    def clear_nsec(self):
        """Remove stored NSEC."""
        try:
            if os.path.exists(self.storage_path):
                os.remove(self.storage_path)
            return True
        except Exception as e:
            logging.error(f"Error clearing NSEC: {str(e)}")
            return False

    def has_nsec(self):
        """Check if NSEC is stored."""
        return os.path.exists(self.storage_path)