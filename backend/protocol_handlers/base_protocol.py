"""
Base Protocol Handler Interface

Simple interface for NOSTR operations over different transports.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class ProtocolHandler(ABC):
    """Abstract base class for protocol handlers."""
    
    def __init__(self, backend_manager, config):
        self.backend_manager = backend_manager
        self.config = config
    
    @abstractmethod
    def send_nostr_request(self, session, request_data: dict) -> bool:
        """Send a NOSTR request (GET_NOTES, etc.)."""
        pass
    
    @abstractmethod  
    def receive_nostr_response(self, session, timeout: int = 30) -> Optional[dict]:
        """Receive NOSTR response data."""
        pass