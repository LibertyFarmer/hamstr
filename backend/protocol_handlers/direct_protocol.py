"""
Direct Protocol Handler

For reliable transports (VARA, Reticulum) - sends content directly.
No READY/ACK handshakes needed since transport provides reliability.
"""

import json
import logging
from typing import Optional, Dict, Any
from .base_protocol import ProtocolHandler


class DirectProtocol(ProtocolHandler):
    """Direct protocol for reliable transports like VARA."""
    
    def send_nostr_request(self, session, request_data: dict) -> bool:
        """Send NOSTR request directly as JSON."""
        try:
            # Convert to JSON bytes
            json_data = json.dumps(request_data).encode('utf-8')
            
            logging.info(f"[DIRECT] Sending request: {request_data.get('type')} ({len(json_data)} bytes)")
            
            # Send directly via backend (no packet protocol)
            return self.backend_manager.send_data(session, json_data)
            
        except Exception as e:
            logging.error(f"[DIRECT] Error sending request: {e}")
            return False
    
    def receive_nostr_response(self, session, timeout: int = 30) -> Optional[dict]:
        """Receive NOSTR response directly as JSON."""
        try:
            logging.info(f"[DIRECT] Waiting for response (timeout: {timeout}s)")
            
            # Receive data directly from backend
            response_data = self.backend_manager.receive_data(session, timeout)
            
            if response_data:
                response_dict = json.loads(response_data.decode('utf-8'))
                logging.info(f"[DIRECT] Received response ({len(response_data)} bytes)")
                return response_dict
            else:
                logging.warning("[DIRECT] No response received")
                return None
                
        except Exception as e:
            logging.error(f"[DIRECT] Error receiving response: {e}")
            return None