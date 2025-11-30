"""
Protocol Manager

Routes NOSTR operations to appropriate protocol based on backend type.
Simple: reliable transports use DirectProtocol, unreliable use PacketProtocol.
"""

import logging
import sys
import os
from typing import Optional, Dict, Any

# Fix relative import issue
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from network_backends.base_backend import BackendType

from .direct_protocol import DirectProtocol
from .packet_protocol import PacketProtocol


class ProtocolManager:
    """Manages protocol selection for NOSTR operations."""
    
    # Simple mapping: reliable vs unreliable transports
    PROTOCOL_MAP = {
        BackendType.VARA: DirectProtocol,       # VARA is reliable
        BackendType.RETICULUM: DirectProtocol,  # Reticulum is reliable  
        BackendType.FLDIGI: DirectProtocol,     # FLDIGI modes are reliable
        BackendType.PACKET: PacketProtocol,     # Traditional packet needs READY/ACK
    }
    
    def __init__(self, backend_manager, config, core_instance):
        """Initialize protocol manager."""
        self.backend_manager = backend_manager
        self.config = config
        self.core = core_instance
        self._current_handler = None
        
        self._initialize_protocol_handler()
    
    def _initialize_protocol_handler(self):
        """Initialize the appropriate protocol handler."""
        backend_type = self.backend_manager.get_backend_type()
        handler_class = self.PROTOCOL_MAP.get(backend_type, PacketProtocol)
        
        # Create handler instance
        if handler_class == PacketProtocol:
            self._current_handler = handler_class(self.backend_manager, self.config, self.core)
        else:
            self._current_handler = handler_class(self.backend_manager, self.config)
        
        protocol_name = handler_class.__name__
        logging.info(f"[PROTOCOL_MGR] Using {protocol_name} for {backend_type.value}")

    def send_control_message(self, session, msg_type: str) -> bool:
        """Forward control message to underlying protocol handler."""
        if hasattr(self._current_handler, 'send_control_message'):
            return self._current_handler.send_control_message(session, msg_type)
        return False

    def wait_for_control_message(self, session, expected_type: str, timeout: int = 30) -> bool:
        """Forward control message wait to underlying protocol handler."""
        if hasattr(self._current_handler, 'wait_for_control_message'):
            return self._current_handler.wait_for_control_message(session, expected_type, timeout)
        return False
    
    def get_protocol_type(self) -> str:
        """Get current protocol type name."""
        return self._current_handler.__class__.__name__
    
    def send_nostr_request(self, session, request_data: dict) -> bool:
        """Route request to appropriate protocol."""
        return self._current_handler.send_nostr_request(session, request_data)
    
    def receive_nostr_response(self, session, timeout: int = 30) -> Optional[dict]:
        """Route response to appropriate protocol."""
        return self._current_handler.receive_nostr_response(session, timeout)