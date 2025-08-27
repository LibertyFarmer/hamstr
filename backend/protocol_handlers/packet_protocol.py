"""
Packet Protocol Handler

For traditional transports (packet radio) - uses existing READY/ACK system.
Wraps legacy HAMSTR packet logic without modification.
"""

import logging
from typing import Optional, Dict, Any
from .base_protocol import ProtocolHandler


class PacketProtocol(ProtocolHandler):
    """Packet protocol for traditional packet radio."""
    
    def __init__(self, backend_manager, config, core_instance):
        """Initialize with reference to Core for existing methods."""
        super().__init__(backend_manager, config)
        self.core = core_instance  # Reference to Core for existing packet methods
    
    def send_nostr_request(self, session, request_data: dict) -> bool:
        """Send NOSTR request using existing packet protocol with READY/ACK."""
        try:
            logging.info("[PACKET] Sending request via packet protocol")
            
            # Convert to the format your existing system expects
            request_string = self._format_request_string(request_data)
            
            # Use your existing DATA_REQUEST system
            return self.core.message_processor.send_data_request(session, request_string)
            
        except Exception as e:
            logging.error(f"[PACKET] Error sending request: {e}")
            return False
    
    def receive_nostr_response(self, session, timeout: int = 30) -> Optional[dict]:
        """Receive NOSTR response using existing packet reconstruction."""
        try:
            logging.info("[PACKET] Waiting for response via packet protocol")
            
            # Use your existing response handling
            response_string = self.core.receive_full_response(session, timeout)
            
            if response_string:
                return {'data': response_string, 'protocol': 'packet'}
            else:
                return None
                
        except Exception as e:
            logging.error(f"[PACKET] Error receiving response: {e}")
            return None
    
    def _format_request_string(self, request_data: dict) -> str:
        """Convert request dict to the string format your system expects."""
        request_type = request_data.get('type', 'GET_NOTES')
        count = request_data.get('count', 2)
        params = request_data.get('params', '')
        
        if params:
            return f"{request_type} {count} {params}"
        else:
            return f"{request_type} {count}"