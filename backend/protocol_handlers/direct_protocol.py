"""
Direct Protocol Handler

For reliable transports (VARA, Reticulum) - sends content directly.
No READY/ACK handshakes needed since transport provides reliability.
"""

import json
import logging
from typing import Optional, Dict, Any
from .base_protocol import ProtocolHandler
from socketio_logger import get_socketio_logger

socketio_logger = get_socketio_logger()


class DirectProtocol(ProtocolHandler):
    """Direct protocol for reliable transports like VARA."""
    
    def send_nostr_request(self, session, request_data: dict) -> bool:
        """Send NOSTR request directly as JSON."""
        try:
            # Convert to JSON bytes
            json_data = json.dumps(request_data).encode('utf-8')
            
            # Determine request type for logging
            request_type = request_data.get('type', 'UNKNOWN')
            
            # Match packet system logging style
            if 'data' in request_data:
                # This is a response from server
                socketio_logger.info(f"[CONTROL] Sending response via VARA")
            else:
                # This is a request from client
                socketio_logger.info(f"[CONTROL] Sending {request_type} request via VARA")
            
            logging.info(f"[DIRECT] Sending: {request_type} ({len(json_data)} bytes)")
            
            # Send directly via backend
            success = self.backend_manager.send_data(session, json_data)
            
            if success:
                socketio_logger.info(f"[CONTROL] Transmission complete")
            else:
                socketio_logger.error(f"[CONTROL] Transmission failed")
            
            return success
            
        except Exception as e:
            logging.error(f"[DIRECT] Error sending: {e}")
            socketio_logger.error(f"[CONTROL] Error: {e}")
            return False
    
    def receive_nostr_response(self, session, timeout: int = 30) -> Optional[dict]:
        """Receive NOSTR response directly as JSON."""
        try:
            logging.debug(f"[DIRECT] Waiting for response (timeout: {timeout}s)")
            socketio_logger.info("[SYSTEM] Waiting for response via VARA...")
            
            # Receive data directly from backend
            response_data = self.backend_manager.receive_data(session, timeout)
            
            if response_data:
                response_dict = json.loads(response_data.decode('utf-8'))
                logging.info(f"[DIRECT] Received response ({len(response_data)} bytes)")
                
                # Check if this is server response with data
                if 'data' in response_dict:
                    socketio_logger.info(f"[PACKET] Response received from server")
                    socketio_logger.info(f"[PROGRESS] 100.00% complete")
                else:
                    socketio_logger.info(f"[CONTROL] Message received via VARA")
                
                return response_dict
            else:
                logging.debug("[DIRECT] No response received")
                socketio_logger.warning("[SYSTEM] No response received, timeout")
                return None
                
        except Exception as e:
            logging.error(f"[DIRECT] Error receiving response: {e}")
            socketio_logger.error(f"[SYSTEM] Error receiving response: {e}")
            return None