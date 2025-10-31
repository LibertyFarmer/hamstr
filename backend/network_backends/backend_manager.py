"""
NetworkBackendManager - Main coordinator for the modular backend system.

This class provides a unified interface to the rest of HAMSTR while
managing the underlying protocol-specific backends.
"""

import logging
from typing import Optional, Dict, Any
from .base_backend import NetworkBackend, BackendType, BackendStatus
from .backend_factory import BackendFactory, create_backend_from_config

class NetworkBackendManager:
    """
    Main manager for network backends.
    
    This class acts as a facade that provides a clean interface to
    the rest of the HAMSTR system while managing the protocol-specific
    backend implementations.
    """
    
    def __init__(self, config_module, is_server: bool = False, core_instance=None):
        """
        Initialize the backend manager.
        
        Args:
            config_module: HAMSTR config module (imports config.py)
            is_server: True if this is server instance, False for client
        """
        self.config_module = config_module
        self.is_server = is_server
        self.core_instance = core_instance  # <-- NEW LINE
        self.current_backend = None
        self.active_sessions = {}
       
        
        # Initialize the backend based on configuration
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Initialize the appropriate backend based on configuration."""
        try:
            self.current_backend = create_backend_from_config(self.config_module, self.is_server, self.core_instance)
            
            if self.current_backend is None:
                logging.info("[BACKEND_MGR] Legacy mode - no backend created")
            else:
                # If packet backend, inject core reference
                if self.current_backend.get_backend_type() == BackendType.PACKET:
                    if self.core_instance:
                        self.current_backend.core = self.core_instance
                        self.current_backend.connection_manager = self.core_instance.connection_manager
                        self.current_backend.packet_handler = self.core_instance.packet_handler
                        self.current_backend.message_processor = self.core_instance.message_processor
                        logging.info("[BACKEND_MGR] Injected Core references into PacketBackend")
                    else:
                        logging.warning("[BACKEND_MGR] PacketBackend created without core_instance")
                
                backend_type = self.current_backend.get_backend_type()
                logging.info(f"[BACKEND_MGR] Initialized with {backend_type.value} backend")
                
        except Exception as e:
            logging.error(f"[BACKEND_MGR] Failed to initialize backend: {e}")
            self.current_backend = None
            raise
    
    def is_legacy_mode(self) -> bool:
        """Check if we're running in legacy mode (original system)."""
        return self.current_backend is None
    
    def connect(self, remote_callsign: tuple) -> Optional[object]:
        """
        Establish connection to remote station.
        
        Args:
            remote_callsign: Tuple of (callsign, ssid)
            
        Returns:
            Session object if successful, None if failed
        """
        if self.is_legacy_mode():
            raise RuntimeError("Backend manager is in legacy mode - should not be called")
        
        try:
            session = self.current_backend.connect(remote_callsign)
            if session:
                # Track the session
                session_id = getattr(session, 'id', str(id(session)))
                self.active_sessions[session_id] = session
                logging.info(f"[BACKEND_MGR] Connected to {remote_callsign} via {self.current_backend.get_backend_type().value}")
            return session
            
        except Exception as e:
            logging.error(f"[BACKEND_MGR] Connection failed: {e}")
            return None
    
    def send_data(self, session: object, data: bytes) -> bool:
        """
        Send data via the current backend.
        
        Args:
            session: Active session object
            data: Raw bytes to transmit
            
        Returns:
            True if send successful
        """
        if self.is_legacy_mode():
            raise RuntimeError("Backend manager is in legacy mode - should not be called")
        
        try:
            return self.current_backend.send_data(session, data)
        except Exception as e:
            logging.error(f"[BACKEND_MGR] Send failed: {e}")
            return False
    
    def receive_data(self, session: object, timeout: int = 30) -> Optional[bytes]:
        """
        Receive data via the current backend.
        
        Args:
            session: Active session object
            timeout: Timeout in seconds
            
        Returns:
            Received bytes or None
        """
        if self.is_legacy_mode():
            raise RuntimeError("Backend manager is in legacy mode - should not be called")
        
        try:
            return self.current_backend.receive_data(session, timeout)
        except Exception as e:
            logging.error(f"[BACKEND_MGR] Receive failed: {e}")
            return None
    
    def disconnect(self, session: object) -> bool:
        """
        Disconnect a session.
        
        Args:
            session: Session to disconnect
            
        Returns:
            True if disconnect successful
        """
        if self.is_legacy_mode():
            raise RuntimeError("Backend manager is in legacy mode - should not be called")
        
        try:
            result = self.current_backend.disconnect(session)
            
            # Remove from active sessions
            session_id = getattr(session, 'id', str(id(session)))
            self.active_sessions.pop(session_id, None)
            
            logging.info(f"[BACKEND_MGR] Disconnected session via {self.current_backend.get_backend_type().value}")
            return result
            
        except Exception as e:
            logging.error(f"[BACKEND_MGR] Disconnect failed: {e}")
            return False
    
    def is_connected(self, session: object) -> bool:
        """
        Check if session is connected.
        
        Args:
            session: Session to check
            
        Returns:
            True if connected
        """
        if self.is_legacy_mode():
            raise RuntimeError("Backend manager is in legacy mode - should not be called")
        
        try:
            return self.current_backend.is_connected(session)
        except Exception as e:
            logging.error(f"[BACKEND_MGR] Connection check failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status information.
        
        Returns:
            Dictionary with status details
        """
        if self.is_legacy_mode():
            return {
                "mode": "legacy",
                "backend_type": "original_system",
                "status": "active",
                "active_sessions": 0
            }
        
        try:
            backend_status = self.current_backend.get_status()
            
            # Add manager-level information
            status = {
                "mode": "modular",
                "backend_type": self.current_backend.get_backend_type().value,
                "backend_status": backend_status,
                "active_sessions": len(self.active_sessions),
                "session_ids": list(self.active_sessions.keys())
            }
            
            return status
            
        except Exception as e:
            logging.error(f"[BACKEND_MGR] Status check failed: {e}")
            return {
                "mode": "modular", 
                "backend_type": "unknown",
                "status": "error",
                "error": str(e)
            }
    
    def switch_backend(self, new_backend_type: BackendType) -> bool:
        """
        Switch to a different backend at runtime.
        
        Args:
            new_backend_type: New backend type to switch to
            
        Returns:
            True if switch successful
            
        Note:
            This will disconnect all active sessions
        """
        if self.is_legacy_mode():
            logging.warning("[BACKEND_MGR] Cannot switch from legacy mode")
            return False
        
        try:
            # Disconnect all active sessions
            for session in list(self.active_sessions.values()):
                self.disconnect(session)
            
            # Create new backend
            old_backend_type = self.current_backend.get_backend_type()
            self.current_backend = BackendFactory.create_backend(new_backend_type, self.config_module, self.is_server)
            
            logging.info(f"[BACKEND_MGR] Switched from {old_backend_type.value} to {new_backend_type.value}")
            return True
            
        except Exception as e:
            logging.error(f"[BACKEND_MGR] Backend switch failed: {e}")
            return False
    
    def cleanup(self):
        """Cleanup all resources."""
        if not self.is_legacy_mode():
            # Disconnect all sessions
            for session in list(self.active_sessions.values()):
                self.disconnect(session)
            
            logging.info("[BACKEND_MGR] Cleanup completed")

    def get_backend_type(self) -> BackendType:
        """
        Get the type of the current backend.
        
        Returns:
            BackendType enum of current backend
        """
        if self.is_legacy_mode():
            return BackendType.PACKET  # Default for legacy mode
        
        return self.current_backend.get_backend_type()