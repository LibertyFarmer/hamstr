"""
Base abstract interface for all network backends in HAMSTR.
This defines the contract that all protocol backends must implement.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any

class BackendType(Enum):
    """Supported backend types for radio protocols"""
    LEGACY = "legacy"      # Original system (for transition period)
    PACKET = "packet"      # Full TNC packet system with AX.25 KISS
    VARA = "vara"          # VARA HF modem with KISS data transfer
    RETICULUM = "reticulum"  # Reticulum mesh networking (raw data)
    FLDIGI = "fldigi"      # FLDIGI digital modes with KISS

class BackendStatus(Enum):
    """Backend connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting" 
    CONNECTED = "connected"
    ERROR = "error"

class NetworkBackend(ABC):
    """
    Abstract base class for all network backends.
    
    Each backend handles a different radio protocol while providing
    a unified interface to the rest of the HAMSTR system.
    """
    
    def __init__(self, config, is_server: bool):
        """
        Initialize the backend.
        
        Args:
            config: Configuration object with settings
            is_server: True if this is server instance, False for client
        """
        self.config = config
        self.is_server = is_server
        self.status = BackendStatus.DISCONNECTED
        self._connection = None
        
    @abstractmethod
    def connect(self, remote_callsign: tuple) -> Optional[object]:
        """
        Establish connection to remote station.
        
        Args:
            remote_callsign: Tuple of (callsign, ssid)
            
        Returns:
            Session object if successful, None if failed
        """
        pass
        
    @abstractmethod
    def send_data(self, session: object, data: bytes) -> bool:
        """
        Send raw application data to remote station.
        
        Args:
            session: Active session object
            data: Raw bytes to transmit
            
        Returns:
            True if send successful, False otherwise
        """
        pass
        
    @abstractmethod
    def receive_data(self, session: object, timeout: int = 30) -> Optional[bytes]:
        """
        Receive raw application data from remote station.
        
        Args:
            session: Active session object
            timeout: Timeout in seconds
            
        Returns:
            Received bytes if successful, None if timeout/error
        """
        pass
        
    @abstractmethod
    def disconnect(self, session: object) -> bool:
        """
        Close connection gracefully.
        
        Args:
            session: Session to disconnect
            
        Returns:
            True if disconnect successful
        """
        pass
        
    @abstractmethod
    def is_connected(self, session: object) -> bool:
        """
        Check if session is still connected.
        
        Args:
            session: Session to check
            
        Returns:
            True if connected, False otherwise
        """
        pass
        
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Get backend-specific status information.
        
        Returns:
            Dictionary with status details for monitoring/debugging
        """
        pass
    
    # Common helper methods that backends can use
    def _update_status(self, new_status: BackendStatus):
        """Update backend status and log the change"""
        if self.status != new_status:
            old_status = self.status
            self.status = new_status
            self._log_status_change(old_status, new_status)
    
    def _log_status_change(self, old_status: BackendStatus, new_status: BackendStatus):
        """Log status changes for debugging"""
        import logging
        logging.info(f"[BACKEND] {self.__class__.__name__} status: {old_status.value} → {new_status.value}")
    
    def get_backend_type(self) -> BackendType:
        """Get the type of this backend"""
        # This will be overridden in each concrete backend
        raise NotImplementedError("Backend must implement get_backend_type()")