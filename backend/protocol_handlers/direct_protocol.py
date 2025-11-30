"""
Direct Protocol Handler

For reliable transports (VARA, Reticulum) - sends content directly.
Uses DONE/DONE_ACK/DISCONNECT/DISCONNECT_ACK for clean shutdown.
"""

import json
import logging
import time
from typing import Optional, Dict, Any
from .base_protocol import ProtocolHandler
from socketio_logger import get_socketio_logger

socketio_logger = get_socketio_logger()


class DirectProtocol(ProtocolHandler):
    """Direct protocol for reliable transports like VARA."""
    
    def send_control_message(self, session, msg_type: str) -> bool:
        """Send control message (DONE, DONE_ACK, DISCONNECT, DISCONNECT_ACK)."""
        try:
            control_data = json.dumps({'type': msg_type}).encode('utf-8')
            success = self.backend_manager.send_data(session, control_data)
            if success:
                logging.info(f"[DIRECT] Sent {msg_type}")
                socketio_logger.info(f"[CONTROL] Sent {msg_type}")
            return success
        except Exception as e:
            logging.error(f"[DIRECT] Error sending {msg_type}: {e}")
            return False
    
    def wait_for_control_message(self, session, expected_type: str, timeout: int = 30) -> bool:
        """Wait for specific control message."""
        try:
            response = self.backend_manager.receive_data(session, timeout)
            if response:
                msg = json.loads(response.decode('utf-8'))
                if msg.get('type') == expected_type:
                    logging.info(f"[DIRECT] Received {expected_type}")
                    socketio_logger.info(f"[CONTROL] Received {expected_type}")
                    return True
            return False
        except Exception as e:
            logging.error(f"[DIRECT] Error waiting for {expected_type}: {e}")
            return False
    
    def send_nostr_request(self, session, request_data: dict) -> bool:
        """Send NOSTR request directly as JSON."""
        try:
            json_data = json.dumps(request_data).encode('utf-8')
            request_type = request_data.get('type', 'UNKNOWN')
            
            if 'data' in request_data:
                socketio_logger.info(f"[CONTROL] Sending response via VARA")
            else:
                socketio_logger.info(f"[CONTROL] Sending {request_type} request via VARA")
            
            logging.info(f"[DIRECT] Sending: {request_type} ({len(json_data)} bytes)")
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
            
            response_data = self.backend_manager.receive_data(session, timeout)
            
            if response_data:
                response_dict = json.loads(response_data.decode('utf-8'))
                logging.info(f"[DIRECT] Received response ({len(response_data)} bytes)")
                
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