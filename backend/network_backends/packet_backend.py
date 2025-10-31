"""
Packet Backend - Wraps existing HAMSTR packet system logic.

This backend preserves all your existing hard work in ConnectionManager,
PacketHandler, MessageProcessor, etc. while providing the new modular interface.
"""

import logging
from typing import Optional, Dict, Any
from .base_backend import NetworkBackend, BackendType, BackendStatus

# Import your existing modules (these will be reused)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# We'll import these as needed - avoiding circular imports
# from connection_manager import ConnectionManager
# from packet_handler import PacketHandler  
# from message_processor import MessageProcessor

class PacketBackend(NetworkBackend):
    """
    Packet backend that wraps the existing HAMSTR packet system.
    
    This backend reuses all existing logic from ConnectionManager,
    PacketHandler, and MessageProcessor while providing the new
    modular backend interface.
    """
    
    def __init__(self, config, is_server: bool, core_instance=None):
        """
        Initialize packet backend using existing HAMSTR components.
        
        Args:
            config: Configuration object
            is_server: True if server instance
            core_instance: Reference to Core instance (REQUIRED for packet backend)
        """
        super().__init__(config, is_server)
        
        if core_instance is None:
            raise ValueError("PacketBackend requires core_instance - cannot be None")
        
        # Use Core's existing components instead of creating new ones
        self.core = core_instance
        self.connection_manager = core_instance.connection_manager
        self.packet_handler = core_instance.packet_handler
        self.message_processor = core_instance.message_processor
        
        logging.info(f"[PACKET_BACKEND] Initialized packet backend for {'server' if is_server else 'client'}")
        logging.info(f"[PACKET_BACKEND] Using Core's existing packet system components")
        self._update_status(BackendStatus.DISCONNECTED)
        
        # For servers, start TNC connection immediately
        if is_server:
            if not self.connection_manager.start():
                logging.error("[PACKET_BACKEND] Failed to start TNC connection")
                raise RuntimeError("Could not establish TNC connection for packet backend")
            logging.info("[PACKET_BACKEND] Server TNC connection established")
    
    def get_backend_type(self) -> BackendType:
        """Return the backend type."""
        return BackendType.PACKET
    
    def connect(self, remote_callsign: tuple) -> Optional[object]:
        """
        Connect to remote station using existing packet system logic.
        
        Args:
            remote_callsign: Tuple of (callsign, ssid)
            
        Returns:
            Session object if successful, None if failed
        """
        try:
            self._update_status(BackendStatus.CONNECTING)
            
            # Use existing connection manager logic
            if not self.connection_manager.tnc_connection:
                # Start the connection manager (establishes TNC connection)
                if not self.connection_manager.start():
                    logging.error("[PACKET_BACKEND] Failed to start connection manager")
                    self._update_status(BackendStatus.ERROR)
                    return None
            
            # Create session using existing logic
            session = self.connection_manager.connect(remote_callsign)
            
            if session:
                self._update_status(BackendStatus.CONNECTED)
                logging.info(f"[PACKET_BACKEND] Connected to {remote_callsign}")
                return session
            else:
                self._update_status(BackendStatus.ERROR)
                logging.error(f"[PACKET_BACKEND] Failed to connect to {remote_callsign}")
                return None
                
        except Exception as e:
            self._update_status(BackendStatus.ERROR)
            logging.error(f"[PACKET_BACKEND] Connection error: {e}")
            return None
    
    def send_data(self, session: object, data: bytes) -> bool:
        """
        Send data using existing packet system.
        
        Args:
            session: Active session object
            data: Raw bytes to transmit
            
        Returns:
            True if send successful
        """
        try:
            # Convert bytes to string for existing message system
            message = data.decode('utf-8', errors='ignore')
            
            # Import MessageType here to avoid circular import
            from models import MessageType
            
            # Use existing message processor logic
            result = self.message_processor.send_message(session, message, MessageType.DATA)
            
            if result:
                logging.debug(f"[PACKET_BACKEND] Sent {len(data)} bytes")
                return True
            else:
                logging.error("[PACKET_BACKEND] Send failed")
                return False
                
        except Exception as e:
            logging.error(f"[PACKET_BACKEND] Send error: {e}")
            return False
    
    def receive_data(self, session: object, timeout: int = 30) -> Optional[bytes]:
        """
        Receive data using existing packet system.
        
        Args:
            session: Active session object  
            timeout: Timeout in seconds
            
        Returns:
            Received bytes or None
        """
        try:
            # Use existing utilities for waiting for messages
            import utils
            from models import MessageType
            
            # Wait for data message using existing logic
            message = utils.wait_for_specific_message(
                self.connection_manager, session, MessageType.DATA, timeout
            )
            
            if message:
                # Convert string back to bytes
                return message.encode('utf-8')
            else:
                logging.debug("[PACKET_BACKEND] Receive timeout")
                return None
                
        except Exception as e:
            logging.error(f"[PACKET_BACKEND] Receive error: {e}")
            return None
    
    def disconnect(self, session: object) -> bool:
        """
        Disconnect session using existing logic.
        
        Args:
            session: Session to disconnect
            
        Returns:
            True if disconnect successful
        """
        try:
            # Use existing connection manager disconnect logic
            self.connection_manager.disconnect(session)
            self._update_status(BackendStatus.DISCONNECTED)
            
            logging.info("[PACKET_BACKEND] Disconnected session")
            return True
            
        except Exception as e:
            logging.error(f"[PACKET_BACKEND] Disconnect error: {e}")
            return False
    
    def is_connected(self, session: object) -> bool:
        """
        Check if session is connected using existing logic.
        
        Args:
            session: Session to check
            
        Returns:
            True if connected
        """
        try:
            # Check session state using existing models
            from models import ModemState
            
            if hasattr(session, 'state'):
                return session.state == ModemState.CONNECTED
            else:
                # Fallback check
                return self.connection_manager.tnc_connection is not None
                
        except Exception as e:
            logging.error(f"[PACKET_BACKEND] Connection check error: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get packet backend status using existing components.
        
        Returns:
            Dictionary with status information
        """
        try:
            status = {
                "backend_type": "packet",
                "status": self.status.value,
                "tnc_connected": self.connection_manager.tnc_connection is not None,
                "tnc_host": getattr(self.connection_manager, 'tnc_host', 'unknown'),
                "tnc_port": getattr(self.connection_manager, 'tnc_port', 'unknown'),
                "callsign": getattr(self.connection_manager, 'callsign', 'unknown'),
                "is_server": self.is_server
            }
            
            # Add connection type info if available
            try:
                import config
                status["connection_type"] = getattr(config, 'CONNECTION_TYPE', 'unknown')
                if hasattr(config, 'SERIAL_PORT'):
                    status["serial_port"] = config.SERIAL_PORT
                    status["serial_speed"] = config.SERIAL_SPEED
            except:
                pass
                
            return status
            
        except Exception as e:
            logging.error(f"[PACKET_BACKEND] Status error: {e}")
            return {
                "backend_type": "packet",
                "status": "error", 
                "error": str(e)
            }

# Register this backend with the factory
def register_packet_backend():
    """Register the packet backend with the factory."""
    from .backend_factory import BackendFactory
    BackendFactory.register_backend(BackendType.PACKET, PacketBackend)
    logging.info("[PACKET_BACKEND] Registered packet backend")

# Auto-register when module is imported
register_packet_backend()