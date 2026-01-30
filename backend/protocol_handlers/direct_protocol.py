"""
Direct Protocol Handler

For reliable transports (VARA, Reticulum) - sends content directly.
Uses DONE/DONE_ACK/DISCONNECT/DISCONNECT_ACK for clean shutdown.
"""

import json
import logging
import time
import sys
from typing import Optional, Dict, Any
from .base_protocol import ProtocolHandler
from socketio_logger import get_socketio_logger
import config

socketio_logger = get_socketio_logger()


class DirectProtocol(ProtocolHandler):
    """Direct protocol for reliable transports like VARA and Reticulum."""
    
    def send_control_message(self, session, msg_type: str) -> bool:
        """Send control message (DONE, DONE_ACK, DISCONNECT, DISCONNECT_ACK)."""
        try:
            control_data = json.dumps({'type': msg_type}).encode('utf-8')
            success = self.backend_manager.send_data(session, control_data)
            if success:
                # Wait for backend to finish transmitting
                # Increased timeout to prevent disconnects during slow fades
                self.wait_for_transmission_complete(session, timeout=60)
                logging.info(f"[DIRECT] Sent {msg_type}")
                sys.stdout.flush()
                socketio_logger.info(f"[CONTROL] Sent {msg_type}")
            return success
        except Exception as e:
            logging.error(f"[DIRECT] Error sending {msg_type}: {e}")
            sys.stdout.flush()
            return False
    
    def wait_for_control_message(self, session, expected_type: str, timeout: int = 60) -> bool:
        """Wait for specific control message."""
        try:
            # Use provided timeout (default increased to 60s)
            response = self.backend_manager.receive_data(session, timeout)
            if response:
                msg = json.loads(response.decode('utf-8'))
                if msg.get('type') == expected_type:
                    logging.info(f"[DIRECT] Received {expected_type}")
                    sys.stdout.flush()
                    socketio_logger.info(f"[CONTROL] Received {expected_type}")
                    return True
            return False
        except Exception as e:
            logging.error(f"[DIRECT] Error waiting for {expected_type}: {e}")
            sys.stdout.flush()
            return False
        
    def send_nostr_request(self, session, request_data: dict) -> bool:
        """Send NOSTR request directly as JSON."""
        try:
            json_data = json.dumps(request_data).encode('utf-8')
            request_type = request_data.get('type', 'Response Packet')
            
            if 'data' in request_data:
                socketio_logger.info(f"[CONTROL] Sending response")
            else:
                socketio_logger.info(f"[CONTROL] Sending {request_type} request")
            
            logging.info(f"[DIRECT] Sending: {request_type} ({len(json_data)} bytes)")
            sys.stdout.flush()
            success = self.backend_manager.send_data(session, json_data)
            
            if success:
                # Wait for backend to finish transmitting
                # CRITICAL: Increased to 120s. Large requests on slow links need time.
                self.wait_for_transmission_complete(session, timeout=120)
                socketio_logger.info(f"[CONTROL] Transmission complete")
            else:
                socketio_logger.error(f"[CONTROL] Transmission failed")
            
            return success
            
        except Exception as e:
            logging.error(f"[DIRECT] Error sending: {e}")
            sys.stdout.flush()
            socketio_logger.error(f"[CONTROL] Error: {e}")
            return False
        
    def wait_for_transmission_complete(self, session, timeout: int = 120) -> bool:
        """Wait for backend to finish transmitting data (for reliable transports)."""
        try:
            # Let the backend handle transmission completion
            if hasattr(self.backend_manager, '_backend'):
                backend = self.backend_manager._backend
                
                # Check for VARA-specific wait method
                if hasattr(backend, '_wait_for_vara_tx_complete'):
                    return backend._wait_for_vara_tx_complete(timeout)
                
                # Future proofing: Check for generic wait method (for Reticulum later)
                if hasattr(backend, 'wait_for_tx_complete'):
                    return backend.wait_for_tx_complete(timeout)
            
            # Fallback for backends without transmission complete checking (Reticulum currently)
            # This is safe because Reticulum handles buffering internally
            return True
            
        except Exception as e:
            logging.error(f"[DIRECT] Error waiting for transmission: {e}")
            return False
        
    def receive_nostr_response(self, session, timeout: int = 120) -> Optional[dict]:
        """Receive NOSTR response directly as JSON."""
        try:
            logging.debug(f"[DIRECT] Waiting for response (timeout: {timeout}s)")
            sys.stdout.flush()
            
            # FIX: Generic log message (was "via VARA")
            socketio_logger.info("[SYSTEM] Waiting for response from server...")
            
            response_data = self.backend_manager.receive_data(session, timeout)
            
            if response_data:
                response_dict = json.loads(response_data.decode('utf-8'))
                logging.info(f"[DIRECT] Received response ({len(response_data)} bytes)")
                sys.stdout.flush()
                
                if 'data' in response_dict:
                    socketio_logger.info(f"[PROGRESS] 100.00% complete")
                else:
                    socketio_logger.info(f"[CONTROL] Message received via Server")
                
                return response_dict
            else:
                logging.debug("[DIRECT] No response received")
                sys.stdout.flush()
                socketio_logger.warning("[SYSTEM] No response received, timeout")
                return None
                
        except Exception as e:
            logging.error(f"[DIRECT] Error receiving response: {e}")
            sys.stdout.flush()
            socketio_logger.error(f"[SYSTEM] Error receiving response: {e}")
            return None