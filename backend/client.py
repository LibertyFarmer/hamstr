import logging
import signal
import time
import sqlite3
import json
from core import Core, ModemState, MessageType
import config
from threading import Lock
from socketio_logger import get_socketio_logger
from models import NoteRequestType
from protocol_utils import compress_nostr_data, decompress_nostr_data


# SocketIO logger
socketio_logger = get_socketio_logger()


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Client:
    def __init__(self, base_dir=None):
        self.core = Core(is_server=False, base_dir=base_dir)  # Pass base_dir to Core
        self.running = True
        self.session = None
        self.db_lock = Lock()

    def stop(self):
        self.running = False
        socketio_logger.info("[CLIENT] Client stopping...")
        logging.info("Client stopping...")

    def connect_and_send_request(self, server_callsign, request_type, count, additional_params=None):
        """
        Send a request with type to the server.
        
        Args:
            server_callsign: Tuple of (callsign, ssid)
            request_type: NoteRequestType enum value
            count: Number of notes to request
            additional_params: Optional string of additional parameters
        """
        if not self.session or self.session.state == ModemState.DISCONNECTED:
            socketio_logger.info(f"[CLIENT] Connecting to {server_callsign[0]}-{server_callsign[1]}...")
            
            self.session = self.core.connect(server_callsign)
            if not self.session:
                socketio_logger.error(f"[CLIENT] Failed to connect to server {server_callsign}")
                logging.error(f"Failed to connect to server {server_callsign}")
                return False, None
            
            # Log connection
            socketio_logger.info(f"[SESSION] CONNECTED to {server_callsign[0]}-{server_callsign[1]}")
            
            # Add stabilization delay only for PacketProtocol (DirectProtocol doesn't need it)
            if not hasattr(self.core, 'protocol_manager') or \
            self.core.protocol_manager.get_protocol_type() == 'PacketProtocol':
                time.sleep(config.CONNECTION_STABILIZATION_DELAY * 1.3)

        try:
            # For specific user requests, derive NPUB from stored NSEC
            if request_type == NoteRequestType.SPECIFIC_USER and additional_params is None:
                npub = self.core.get_npub()
                if not npub:
                    socketio_logger.error("[CLIENT] No NPUB available - please set up NOSTR key first")
                    return False, {
                        "success": False,
                        "message": "NOSTR key not set up"
                    }
                additional_params = npub

            # NEW: Route through protocol layer if available
            if hasattr(self.core, 'protocol_manager') and self.core.protocol_manager:
                socketio_logger.info("[CLIENT] Using protocol layer for request")
                logging.info(f"Using protocol layer: {self.core.protocol_manager.get_protocol_type()}")
                
                # Prepare request data for protocol layer
                request_data = {
                    'type': request_type.value,
                    'count': count
                }
                if additional_params:
                    request_data['params'] = additional_params
                
                # Send via protocol layer
                success = self.core.protocol_manager.send_nostr_request(self.session, request_data)
                
                if success:
                    # Receive response via protocol layer
                    print(f"DEBUG: About to call receive_nostr_response")
                    response = self.core.protocol_manager.receive_nostr_response(self.session, timeout=180)
                    print(f"DEBUG: Got response: {response}")
                    
                    if response:
                        # Handle response based on protocol type
                        if self.core.protocol_manager.get_protocol_type() == 'DirectProtocol':
                            # Direct protocol response
                            response_data = response.get('data', '')
                        else:
                            # Packet protocol response
                            response_data = response.get('data', '')
                        
                        if response_data:
                            try:
                                # Check if it's an error response
                                parsed_response = json.loads(response_data)
                                if not parsed_response.get('success', True):
                                    error_type = parsed_response.get('error_type')
                                    error_message = parsed_response.get('message')
                                    socketio_logger.error(f"[SERVER ERROR] Type: {error_type}, Message: {error_message}")
                                    if hasattr(self.core, 'backend_manager') and self.core.backend_manager:
                                        socketio_logger.info("[SESSION] Client initiating disconnect")
                                        self.core.backend_manager.disconnect(self.session)
                                        self.session = None
                                    return True, response_data
                            except json.JSONDecodeError:
                                pass  # Not an error response, continue normal processing
                            
                            # Decompress and return response
                            decompressed_response = decompress_nostr_data(response_data)
                            socketio_logger.info(f"[PACKET] Response received from server")
                            logging.info(f"Protocol response received: {len(decompressed_response)} chars")

                            # Direct disconnect flow: send ACK → wait for DONE → send DONE_ACK → wait for DISCONNECT → send DISCONNECT_ACK → close
                            if hasattr(self.core, 'backend_manager') and self.core.backend_manager:
                                protocol = self.core.protocol_manager
                                
                                # NEW: Send ACK after receiving full response
                                socketio_logger.info("[CONTROL] Sending ACK")
                                protocol.send_control_message(self.session, 'ACK')
                                
                                # 1. Wait for DONE from server
                                socketio_logger.info("[CONTROL] Waiting for DONE from server")
                                if protocol.wait_for_control_message(self.session, 'DONE', timeout=30):
                                    
                                    # 2. Send DONE_ACK
                                    socketio_logger.info("[CONTROL] Sending DONE_ACK")
                                    protocol.send_control_message(self.session, 'DONE_ACK')
                                    
                                    # 3. Wait for DISCONNECT from server
                                    socketio_logger.info("[CONTROL] Waiting for DISCONNECT from server")
                                    if protocol.wait_for_control_message(self.session, 'DISCONNECT', timeout=30):
                                        
                                        # 4. Send DISCONNECT_ACK
                                        socketio_logger.info("[CONTROL] Sending DISCONNECT_ACK")
                                        protocol.send_control_message(self.session, 'DISCONNECT_ACK')
                                        time.sleep(2)  # Give server time to receive
                                
                                # 5. Close connection
                                self.core.backend_manager.disconnect(self.session)
                                self.session = None
                                socketio_logger.info("[SESSION] Client disconnect complete")

                            return True, response_data

                        else:
                            socketio_logger.error("[CLIENT] Empty response from protocol layer")
                            return False, None
                    else:
                        socketio_logger.error("[CLIENT] No response from protocol layer")
                        return False, None
                else:
                    socketio_logger.error("[CLIENT] Protocol layer request failed")
                    return False, None
            
            else:
                # FALLBACK: Use existing legacy packet protocol
                socketio_logger.info("[CLIENT] Using legacy packet protocol")
                logging.info("No protocol manager - using legacy packet system")
                
                # Format request with space and pipe separation
                request = f"GET_NOTES {request_type.value}|{count}"
                if additional_params:
                    request = f"{request}|{additional_params}"
                    
                logging.info(f"Sending request: {request}")
                
                # Add significant delay before sending DATA_REQUEST
                time.sleep(config.CONNECTION_STABILIZATION_DELAY * 1.5)
                
                for attempt in range(config.RETRY_COUNT):
                    if self.core.send_data_request(self.session, request):
                        socketio_logger.info("[SESSION] DATA_REQUEST sent and READY state achieved")
                        logging.info("DATA_REQUEST sent and READY state achieved")
                        
                        # Use the core receive_response method
                        response = self.core.receive_response(self.session)
                        
                        if response:
                            try:
                                response_data = json.loads(response)
                                if not response_data.get('success', True):
                                    error_type = response_data.get('error_type')
                                    error_message = response_data.get('message')
                                    socketio_logger.error(f"[SERVER ERROR] Type: {error_type}, Message: {error_message}")
                                    return True, response
                            except json.JSONDecodeError:
                                pass  # Not an error response, continue normal processing
                            
                            decompressed_response = decompress_nostr_data(response)
                            socketio_logger.info(f"[CLIENT] JSON NOTE: {decompressed_response}")
                            logging.info(f"Server response: {decompressed_response}")
                            return True, response
                        else:
                            socketio_logger.error("[CLIENT] No response received from server")
                            logging.error("No response received from server")
                            break
                    else:
                        socketio_logger.warning(f"[SESSION] Failed to send request or achieve READY state. Attempt {attempt + 1} of {config.RETRY_COUNT}")
                        logging.warning(f"Failed to send request or achieve READY state. Attempt {attempt + 1} of {config.RETRY_COUNT}")
                        if attempt < config.RETRY_COUNT - 1:
                            time.sleep(config.ACK_TIMEOUT)
                else:
                    socketio_logger.error("[CLIENT] Failed to send request after all retry attempts")
                    logging.error("Failed to send request after all retry attempts")

        except Exception as e:
            socketio_logger.error(f"[SYSTEM] An error occurred during request: {e}")
            logging.error(f"An error occurred during request: {e}")
        finally:
            if self.session and self.session.state not in [ModemState.DISCONNECTING, ModemState.DISCONNECTED]:
                self.disconnect()

        return False, None
    
    def send_packet_ack(self, session, seq_num, max_retries=2):
        """Send an ACK for a specific packet with proper timing and retries."""
        # Add a small delay before sending ACK to ensure radio is ready
        time.sleep(config.CONNECTION_STABILIZATION_DELAY)
        
        # Use the sequence number in the ACK message
        ack_message = f"ACK|{seq_num:04d}"
        
        for retry in range(max_retries):
            success = self.core.message_processor.send_control_message(session, ack_message, MessageType.ACK)
            if success:
                # Add additional delay after sending ACK
                time.sleep(config.CONNECTION_STABILIZATION_DELAY)
                return True
            
            if retry < max_retries - 1:
                logging.warning(f"ACK send attempt {retry+1} failed, retrying...")
                time.sleep(config.CONNECTION_STABILIZATION_DELAY)
        
        logging.error(f"Failed to send ACK for packet {seq_num} after {max_retries} attempts")
        return False
        
    def connect_and_send_note(self, server_callsign, note):
        if not self.session or self.session.state == ModemState.DISCONNECTED:
            socketio_logger.info(f"[CLIENT] Connecting to {server_callsign[0]}-{server_callsign[1]}...")
            
            self.session = self.core.connect(server_callsign)
            if not self.session:
                socketio_logger.error(f"[CLIENT] Failed to connect to server {server_callsign}")
                logging.error(f"Failed to connect to server {server_callsign}")
                return False
            
            # Log connection
            socketio_logger.info(f"[SESSION] CONNECTED to {server_callsign[0]}-{server_callsign[1]}")
        
        try:
            socketio_logger.info("[CLIENT] Sending note")
            logging.info("Sending note")
            
            # Route through protocol layer if available
            if hasattr(self.core, 'protocol_manager') and self.core.protocol_manager:
                socketio_logger.info("[CLIENT] Using protocol layer for note")
                
                note_data = {'type': 'NOTE', 'content': note}
                success = self.core.protocol_manager.send_nostr_request(self.session, note_data)
                
                if success:
                    response = self.core.protocol_manager.receive_nostr_response(self.session, timeout=60)
                    if response and response.get('success'):
                        socketio_logger.info("[CLIENT] Note Published!")
                        
                        protocol = self.core.protocol_manager
                        
                        # Send DONE
                        socketio_logger.info("[CONTROL] Sending DONE")
                        protocol.send_control_message(self.session, 'DONE')
                        
                        # Wait for DONE_ACK
                        socketio_logger.info("[CONTROL] Waiting for DONE_ACK")
                        done_ack = protocol.receive_nostr_response(self.session, timeout=15)
                        if done_ack and done_ack.get('type') == 'DONE_ACK':
                            socketio_logger.info("[CONTROL] Received DONE_ACK")
                        else:
                            socketio_logger.warning("[CONTROL] No DONE_ACK received")
                        
                        time.sleep(1)  # Brief pause
                        
                        # Send DISCONNECT (don't wait for ACK - connection will close)
                        socketio_logger.info("[CONTROL] Sending DISCONNECT")
                        protocol.send_control_message(self.session, 'DISCONNECT')
                        socketio_logger.info("[CONTROL] Disconnect signal sent")
                        
                        time.sleep(2)  # Give it time to transmit
                        return True
                    else:
                        socketio_logger.error("[CLIENT] Failed to publish note")
                        return False
                else:
                    return False
            
            else:
                # FALLBACK: Old packet system (before protocol manager was added)
                if not self.core.send_ready(self.session) or not self.core.wait_for_ready(self.session):
                    socketio_logger.error("Failed to establish READY state")
                    return False
                if not self.core.send_note(self.session, note):
                    socketio_logger.error("[SYSTEM] Failed to send note")
                    return False
                response = self.core.wait_for_specific_message(self.session, MessageType.DONE_ACK, timeout=config.ACK_TIMEOUT)
                if response:
                    socketio_logger.info("[CONTROL] Received DONE_ACK, note transmission complete")
                    return True
                else:
                    socketio_logger.error("[CLIENT] Failed to receive DONE_ACK")
                    return False
        
        except Exception as e:
            socketio_logger.error(f"[SYSTEM] An error occurred during note sending: {e}")
            logging.error(f"An error occurred during note sending: {e}")
            return False
        finally:
            if self.session and self.session.state not in [ModemState.DISCONNECTING, ModemState.DISCONNECTED]:
                self.disconnect()

    def handle_missing_packets(self, session, missing_packets_message):
        _, missing_packets_str = missing_packets_message.split('|', 1)
        missing_packets = list(map(int, missing_packets_str.split('|')))
        socketio_logger.info(f"[PACKET] Handling missing packets: {missing_packets}")
        logging.info(f"Handling missing packets: {missing_packets}")
        
        for seq_num in missing_packets:
            if seq_num in session.sent_packets:
                packet = session.sent_packets[seq_num]
                retry_count = 0
                while retry_count < config.RETRY_COUNT:
                    # Use RESPONSE message type for note writing, NOTE for other cases
                    msg_type = MessageType.RESPONSE if session.is_note_writing else MessageType.NOTE
                    if self.core.send_single_packet(session, seq_num, session.total_packets, packet, msg_type):
                        if self.core.wait_for_ack(session):
                            socketio_logger.info(f"[PACKET] Successfully resent packet {seq_num}")
                            logging.info(f"Successfully resent packet {seq_num}")
                            break
                    retry_count += 1
                    if retry_count < config.RETRY_COUNT:
                        socketio_logger.warning(f"[PACKET] Failed to receive ACK for resent packet {seq_num}. Retrying...")
                        logging.warning(f"Failed to receive ACK for resent packet {seq_num}. Retrying...")
                        time.sleep(config.ACK_TIMEOUT)
                if retry_count == config.RETRY_COUNT:
                    socketio_logger.error(f"[PACKET] Failed to resend packet {seq_num} after {config.RETRY_COUNT} attempts")
                    logging.error(f"Failed to resend packet {seq_num} after {config.RETRY_COUNT} attempts")
                    return False
            else:
                socketio_logger.error(f"[SYSTEM] Missing packet {seq_num} not found in sent packets")
                logging.error(f"Missing packet {seq_num} not found in sent packets")
                return False
            
        socketio_logger.info("[PACKET] All missing packets resent successfully")
        logging.info("All missing packets resent successfully")
        return True

    def disconnect(self):
        socketio_logger.info("[SESSION] Client initiating disconnect [CLIENT_DISCONNECT]")
        logging.info("Client initiating disconnect [CLIENT_DISCONNECT]")
        if self.session and self.session.state != ModemState.DISCONNECTED:
            # Check if using DirectProtocol - use direct disconnect
            if hasattr(self.core, 'protocol_manager') and self.core.protocol_manager:
                if self.core.protocol_manager.get_protocol_type() == 'DirectProtocol':
                    self.core.backend_manager.disconnect(self.session)
                    self.session = None
                    socketio_logger.info("[SYSTEM] Client disconnect complete [CLIENT_DISCONNECT_COMPLETE]")
                    logging.info("Client disconnect complete [CLIENT_DISCONNECT_COMPLETE]")
                    return
            
            # Packet protocol disconnect
            if self.core.send_disconnect(self.session):
                if self.core.wait_for_ack(self.session, timeout=config.DISCONNECT_TIMEOUT):
                    socketio_logger.info("[CLIENT] Disconnect acknowledged by server")
                    logging.info("Disconnect acknowledged by server")
                else:
                    socketio_logger.warning("[SYSTEM] Did not receive ACK for DISCONNECT")
                    logging.warning("Did not receive ACK for DISCONNECT")
            else:
                socketio_logger.error("[SYSTEM] Failed to send DISCONNECT")
                logging.error("Failed to send DISCONNECT")
            self.core.cleanup_session(self.session)
        self.session = None
        socketio_logger.info("[SYSTEM] Client disconnect complete [CLIENT_DISCONNECT_COMPLETE]")
        logging.info("Client disconnect complete [CLIENT_DISCONNECT_COMPLETE]")

    def save_note(self, note):
        with self.db_lock:
            conn = sqlite3.connect('notes.db')
            c = conn.cursor()
            try:
                note_data = json.loads(note)
                c.execute("INSERT INTO notes (id, content, created_at) VALUES (?, ?, ?)",
                          (note_data['id'], note_data['content'], note_data['created_at']))
                conn.commit()
                socketio_logger.info(f"[SYSTEM] Note saved to local database: {note_data['id']}")
                logging.info(f"Note saved to local database: {note_data['id']}")
            except Exception as e:
                socketio_logger.error(f"[SYSTEM] Error saving note to database: {e}")
                logging.error(f"Error saving note to database: {e}")
            finally:
                conn.close()

    def get_recent_notes(self, limit=10):
        with self.db_lock:
            conn = sqlite3.connect('notes.db')
            c = conn.cursor()
            try:
                c.execute("SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,))
                notes = c.fetchall()
                return [{"id": note[0], "content": note[1], "created_at": note[2]} for note in notes]
            except Exception as e:
                socketio_logger.error(f"[SYSTEM] Error retrieving notes from database: {e}")
                logging.error(f"Error retrieving notes from database: {e}")
                return []
            finally:
                conn.close()

    def run(self):
        signal.signal(signal.SIGINT, lambda signum, frame: self.stop())
        signal.signal(signal.SIGTERM, lambda signum, frame: self.stop())

        try:
            while self.running:
                request = input("Enter your request (or 'quit' to exit): ")
                if request.lower() == 'quit':
                    break
                success, response = self.connect_and_send_request(config.S_CALLSIGN, request)
                if not success:
                    socketio_logger.error("[SYSTEM] Failed to process request")
                    logging.error("Failed to process request")
                else:
                    socketio_logger.info(f"[CONTROL] Received response: {response}")
                    logging.info(f"Received response: {response}")
        except Exception as e:
            socketio_logger.error(f"[SYSTEM] An error occurred: {e}")
            logging.error(f"An error occurred: {e}")
        finally:
            self.disconnect()
            socketio_logger.info("[CLIENT] Client has successfully stopped.")
            logging.info("Client stopped.")

if __name__ == "__main__":
    client = Client()
    client.run()