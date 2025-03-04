import logging
import time
import config
from models import Session, ModemState, MessageType
from ax25_kiss_utils import build_ax25_frame, kiss_wrap, clean_message, kiss_unwrap, decode_ax25_callsign
from networking import create_tnc_connection, receive_packet, send_frame
from protocol_utils import calculate_crc32, parse_callsign, estimate_transmission_time
from connection_manager import ConnectionManager
from packet_handler import PacketHandler
from message_processor import MessageProcessor
from utils import wait_for_specific_message, wait_for_ack
import utils
from socketio_logger import get_socketio_logger
from nsec_storage import NSECStorage

# Regular logger
logger = logging.getLogger(__name__)

# SocketIO logger
socketio_logger = get_socketio_logger()


MINIMUM_CHECKSUM_LENGTH = 8  # Minimum length of a message that should include a checksum

class Core:
    def __init__(self, is_server, base_dir=None):
        self.is_server = is_server
        self.tnc_host = config.SERVER_HOST if is_server else config.CLIENT_HOST
        self.tnc_port = config.SERVER_PORT if is_server else config.CLIENT_PORT
        self.callsign = parse_callsign(config.S_CALLSIGN if is_server else config.C_CALLSIGN)
        self.connection_manager = ConnectionManager(is_server, self)
        self.packet_handler = PacketHandler(self)
        self.message_processor = MessageProcessor(self)
        self.sessions = {}
        self.tnc_connection = None
        self.running = True
        self.acked_packets = set()
        if not is_server and base_dir:
            self.nsec_storage = NSECStorage(base_dir)

    def start(self):
        return self.connection_manager.start()

    def stop(self):
        if not hasattr(self, '_stopped'):
            self._stopped = True
            self.running = False
            if self.connection_manager:
                self.connection_manager.stop()
            logging.debug("Core stopped [CORE_STOP]")
        else:
            logging.debug("Core stop called again, but already stopped [CORE_STOP_AGAIN]")

    def connect(self, remote_callsign):
        return self.connection_manager.connect(remote_callsign)

    def create_session(self, remote_callsign):
        return self.connection_manager.create_session(remote_callsign)

    def send_single_packet(self, session, seq_num, total_packets, packet, message_type):
        return self.packet_handler.send_single_packet(session, seq_num, total_packets, packet, message_type)

    def send_ack(self, session, seq_num=None):
        ack_message = f"ACK{f'|{seq_num:04d}' if seq_num is not None else ''}"
        return self.message_processor.send_control_message(session, ack_message, MessageType.ACK)

    def send_message(self, session, message, message_type):
        return self.message_processor.send_message(session, message, message_type)
    
    def wait_for_specific_message(self, session, expected_type, timeout=config.ACK_TIMEOUT):
        return wait_for_specific_message(self, session, expected_type, timeout)
    
    def wait_for_ack(self, session, timeout=config.ACK_TIMEOUT):
        return wait_for_ack(self, session, timeout)
    
    def disconnect(self, session):
        self.connection_manager.disconnect(session)

    def get_nsec(self):
        # Get NSEC for client operations
        if self.is_server:
            return None
        return self.nsec_storage.get_nsec()

    def wait_for_disconnect_ack(self, session, timeout=config.DISCONNECT_TIMEOUT):
        start_time = time.time()
        while time.time() - start_time < timeout:
            source_callsign, message, msg_type = self.receive_message(session, timeout=0.5)
            if msg_type == MessageType.DISCONNECT_ACK:
                socketio_logger.info(f"Received Disconnect ACK from {source_callsign}") 
                logging.info("Received DISCONNECT_ACK")
                return True
        socketio_logger.warning("Timeout waiting for DISCONNECT_ACK") 
        logging.warning("Timeout waiting for DISCONNECT_ACK")
        return False

    def receive_message(self, session, timeout=None):
        start_time = time.time()
        last_log_time = start_time
        tnc_connection = session.tnc_connection if session else self.connection_manager.tnc_connection
        
        while timeout is None or time.time() - start_time < timeout:
            source_callsign, ax25_frame = receive_packet(tnc_connection, timeout=0.1)
            if ax25_frame:
                try:
                    message = clean_message(ax25_frame)
                    decoded_message = message.decode('utf-8', errors='ignore')
                    
                    if ':' not in decoded_message:
                        raise ValueError("Invalid message format")
                    
                    header, content = decoded_message.split(':', 1)
                    
                    if header.isdigit():
                        # It's a control message
                        msg_type = MessageType(int(header))
                        socketio_logger.info(f"[CONTROL] Received control: Type={msg_type.name}, Content={content}")
                        logging.info(f"Received control message: Type={msg_type.name}, Content={content}")
                        return source_callsign, content, msg_type
                    else:
                        # It's a data message
                        header_parts = header.split('|')
                        if len(header_parts) != 3:
                            socketio_logger.error("[PACKET] Invalid header format for data message")
                            raise ValueError("Invalid header format for data message")
                        
                        seq_num, total_packets, msg_type_str = header_parts
                        msg_type = MessageType(int(msg_type_str))
                        
                        # Separate content and checksum
                        if '|' in content:
                            content, received_checksum = content.rsplit('|', 1)
                        else:
                            socketio_logger.warning("[PACKET] No checksum found in data message")
                            logging.warning("No checksum found in data message")
                            return source_callsign, None, MessageType.RETRY
                        
                        # Verify checksum
                        calculated_checksum = calculate_crc32(f"{header}:{content}".encode())
                        if calculated_checksum != received_checksum:
                            socketio_logger.warning(f"[PACKET] Checksum mismatch. Calculated: {calculated_checksum}, Received: {received_checksum}")
                            logging.warning(f"Checksum mismatch. Calculated: {calculated_checksum}, Received: {received_checksum}")
                            return source_callsign, None, MessageType.RETRY
                        
                        socketio_logger.info(f"[PACKET] Received Message: Type={msg_type.name}, Seq={seq_num}/{total_packets}")
                        logging.info(f"Received message: Type={msg_type.name}, Seq={seq_num}/{total_packets}")
                        logging.debug(f"Full packet content: {content}")
                        return source_callsign, f"{header}:{content}", msg_type
                    
                except Exception as e:
                    socketio_logger.error(f"[PACKET] Error processing message: {str(e)}")
                    logging.error(f"Error processing message: {str(e)}")
                    if session:
                        self.request_retry(session, source_callsign)
            
            current_time = time.time()
            if current_time - last_log_time >= 5:
                logging.debug("No message received within the last 5 seconds")
                last_log_time = current_time
        
        return None, None, None

    def process_message(self, message, source_callsign):
        return self.message_processor.process_message(message, source_callsign)

    def request_retry(self, session, source_callsign):
        if session is None:
            socketio_logger.error("[SYSTEM] Cannot request retry: No active session")
            logging.error("Cannot request retry: No active session")
            return
        retry_message = "RETRY"
        self.send_single_packet(session, 0, 0, retry_message.encode(), MessageType.RETRY)
        socketio_logger.info(f"[SYSTEM] Sent RETRY request to {source_callsign}")
        logging.info(f"Sent RETRY request to {source_callsign}")

    def split_message(self, message):
        return self.packet_handler.split_message(message)

    def handle_incoming_connection(self):
        return self.connection_manager.handle_incoming_connection()

    def send_data_request(self, session, request):
        return self.message_processor.send_data_request(session, request)
        
    def send_ready(self, session):
        logging.info("Sending READY message")
        return self.message_processor.send_control_message(session, "READY", MessageType.READY)
    

    def wait_for_ready(self, session, timeout=config.READY_TIMEOUT):
        """Wait for a READY message from the remote station"""
        start_time = time.time()
        retries = 0
        max_retries = 2  # Maximum number of internal retries
        
        while time.time() - start_time < timeout and retries < max_retries:
            source_callsign, message, msg_type = self.receive_message(session, timeout=0.5)
            
            if msg_type == MessageType.READY:
                logging.info("Received READY message")
                session.last_activity = time.time()  # Update activity timestamp
                
                # Add delay after receiving READY
                time.sleep(config.CONNECTION_STABILIZATION_DELAY)
                return True
            elif msg_type == MessageType.DATA_REQUEST:
                # Also accept DATA_REQUEST as an alternative to READY in some cases
                logging.info("Received DATA_REQUEST (accepting as READY equivalent)")
                session.last_activity = time.time()
                
                # Add delay after receiving DATA_REQUEST
                time.sleep(config.CONNECTION_STABILIZATION_DELAY)
                return True
            elif msg_type == MessageType.DISCONNECT:
                logging.info("Received DISCONNECT while waiting for READY")
                self.handle_disconnect(session)
                return False  # Return immediately when DISCONNECT is received
            elif msg_type is not None:
                logging.warning(f"Received unexpected message type {msg_type} while waiting for READY")
            
            # Check if we've spent enough time waiting to try a retry
            if time.time() - start_time > (timeout / 2) and retries == 0:
                # Try to resend our own READY as a prompting measure
                logging.info("No READY received yet, sending our own READY as a prompt")
                time.sleep(config.CONNECTION_STABILIZATION_DELAY)  # Add delay before sending
                self.send_ready(session)
                retries += 1
                time.sleep(config.CONNECTION_STABILIZATION_DELAY)  # Add delay after sending
        
        socketio_logger.warning("[SYSTEM] READY message not received within timeout")
        logging.warning("READY message not received within timeout")
        return False

    def wait_for_data_request(self, session):
        return self.message_processor.wait_for_data_request(session)
    
    def send_note(self, session, note):
        logging.info("Preparing to send note")
        success = self.message_processor.send_message(session, note, MessageType.NOTE)
        if success:
            socketio_logger.info("Note sent successfully, sending DONE")
            logging.info("Note sent successfully, sending DONE")
            if self.send_done(session):
                logging.info("DONE sent")
                socketio_logger.info("[PACKET] DONE packet sent")
                return True
            else:
                socketio_logger.error("Failed to send DONE")
                logging.error("Failed to send DONE")
        return False

    def send_response(self, session, response):
        packets = self.split_message(response.encode())
        total_packets = len(packets)
        session.total_packets = total_packets
        session.sent_packets = {}
        session.acked_packets = set()
        
        for seq_num, packet in enumerate(packets, 1):
            retries = 0
            ack_received = False
            while retries < config.RETRY_COUNT and not ack_received:
                if self.send_single_packet(session, seq_num, total_packets, packet, MessageType.RESPONSE):
                    session.sent_packets[seq_num] = packet
                    
                    # Wait longer for ACK on first packet, which seems to be problematic
                    ack_timeout = config.ACK_TIMEOUT * (2 if seq_num == 1 else 1)
                    
                    # Add a small delay before starting to listen for ACK
                    time.sleep(config.CONNECTION_STABILIZATION_DELAY)
                    
                    start_time = time.time()
                    while time.time() - start_time < ack_timeout:
                        source_callsign, message, msg_type = self.core.receive_message(session, timeout=0.5)
                        if msg_type == MessageType.ACK and message:
                            try:
                                # Check if this is an ACK for our packet
                                if "|" in message:
                                    _, ack_seq = message.split("|", 1)
                                    if int(ack_seq) == seq_num:
                                        session.acked_packets.add(seq_num)
                                        progress = (len(session.acked_packets) / total_packets) * 100
                                        socketio_logger.info(f"[PACKET] Sent packet {seq_num}/{total_packets} - Progress: {progress:.2f}%")
                                        logging.info(f"Sent packet {seq_num}/{total_packets} - Progress: {progress:.2f}%")
                                        ack_received = True
                                        break
                            except (ValueError, IndexError):
                                # If we can't parse the ACK, assume it's not for us
                                pass
                        elif msg_type == MessageType.DISCONNECT:
                            logging.info("Received DISCONNECT while waiting for ACK")
                            self.core.handle_disconnect(session)
                            return False
                    
                    if ack_received:
                        break
                        
                    socketio_logger.warning(f"[CONTROL] Failed to receive ACK for packet {seq_num}")
                    logging.warning(f"Failed to receive ACK for packet {seq_num}")
                else:
                    socketio_logger.warning(f"[CONTROL] Failed to send packet {seq_num}")
                    logging.warning(f"Failed to send packet {seq_num}")
                    
                retries += 1
                if retries < config.RETRY_COUNT:
                    socketio_logger.info(f"[PACKET] Retrying to send packet {seq_num}. Attempt {retries + 1}")
                    logging.info(f"Retrying to send packet {seq_num}. Attempt {retries + 1}")
                    time.sleep(config.ACK_TIMEOUT)
            
            if retries == config.RETRY_COUNT and not ack_received:
                socketio_logger.error(f"[PACKET] Failed to send packet {seq_num} after {config.RETRY_COUNT} attempts.")
                logging.error(f"Failed to send packet {seq_num} after {config.RETRY_COUNT} attempts.")
        
        # After sending all packets (or attempting to), send DONE
        self.core.send_done(session)
        
        # Wait for DONE_ACK or handle PKT_MISSING
        start_time = time.time()
        while time.time() - start_time < config.CONNECTION_TIMEOUT:
            source_callsign, message, msg_type = self.core.receive_message(session, timeout=1.0)
            if msg_type == MessageType.DONE_ACK:
                socketio_logger.info("[CONTROL] Received DONE_ACK")
                logging.info("Received DONE_ACK")
                return True
            elif msg_type == MessageType.PKT_MISSING:
                socketio_logger.info(f"[CONTROL] Received PKT_MISSING request: {message}")
                logging.info(f"Received PKT_MISSING request: {message}")
                try:
                    # Handle empty or malformed PKT_MISSING messages
                    if not message or "|" not in message or len(message.split("|", 1)[1].strip()) == 0:
                        socketio_logger.error("[SYSTEM] Empty or malformed PKT_MISSING message")
                        logging.error("Empty or malformed PKT_MISSING message")
                        # Send DONE_ACK to allow client to continue
                        self.core.send_single_packet(session, 0, 0, "DONE_ACK".encode(), MessageType.DONE_ACK)
                        return True
                        
                    if self.core.packet_handler.handle_missing_packets_sender(session, message):
                        socketio_logger.info("[CONTROL] Missing packets sent successfully")
                        logging.info("Missing packets sent successfully")
                        self.core.send_done(session)  # Send DONE again after resending missing packets
                    else:
                        socketio_logger.error("[CONTROL] Failed to send missing packets")
                        logging.error("Failed to send missing packets")
                        return False
                except Exception as e:
                    socketio_logger.error(f"[SYSTEM] Error handling PKT_MISSING: {str(e)}")
                    logging.error(f"Error handling PKT_MISSING: {str(e)}")
                    # Send DONE_ACK to allow client to continue
                    self.core.send_single_packet(session, 0, 0, "DONE_ACK".encode(), MessageType.DONE_ACK)
                    return True
        
        logging.warning("Did not receive DONE_ACK or PKT_MISSING within timeout")
        socketio_logger.warning("[SYSTEM] Did not receive DONE_ACK or PKT_MISSING within timeout")
        return False
        
    def handle_incomplete_transmission(self, session):
        socketio_logger.info("[SYSTEM] Handling incomplete transmission")
        logging.info("Handling incomplete transmission")
        self.send_done(session)  # Send DONE even if not all packets were sent successfully
        start_time = time.time()
        while time.time() - start_time < config.ACK_TIMEOUT:
            source_callsign, message, msg_type = self.receive_message(session, timeout=1.0)
            if msg_type == MessageType.DONE_ACK:
                socketio_logger.info("[CONTROL] Received DONE_ACK, ending transmission")
                logging.info("Received DONE_ACK, ending transmission")
                self.connection_manager.handle_disconnect(session)
                return
            elif msg_type == MessageType.PKT_MISSING:
                socketio_logger.info(f"[CONTROL] Received PKT_MISSING request: {message}")
                logging.info(f"Received PKT_MISSING request: {message}")
                if self.handle_missing_packets_sender(session, message):
                    start_time = time.time()  # Reset timer after handling missing packets
                else:
                    socketio_logger.error("Failed to handle missing packets request")
                    logging.error("Failed to handle missing packets request")
                    self.connection_manager.handle_disconnect(session)
                    return
        # If no DONE_ACK received, force disconnect
        socketio_logger.warning("[SYSTEM] No DONE_ACK received, forcing disconnect...")
        logging.warning("No DONE_ACK received, forcing disconnect")
        self.connection_manager.handle_disconnect(session)


    def wait_for_done_ack_and_disconnect(self, session):
        start_time = time.time()
        while time.time() - start_time < config.ACK_TIMEOUT:
            source_callsign, message, msg_type = self.receive_message(session, timeout=1.0)
            
            if msg_type == MessageType.DONE_ACK:
                socketio_logger.info("[CONTROL] Received DONE_ACK")
                logging.info("Received DONE_ACK")
                self.disconnect(session)
                return True
            elif msg_type == MessageType.PKT_MISSING:
                socketio_logger.info(f"[CONTROL] Received PKT_MISSING request: {message}")
                logging.info(f"Received PKT_MISSING request: {message}")
                if self.handle_missing_packets_sender(session, message):
                    # Reset the timer after handling missing packets
                    start_time = time.time()
                else:
                    return False
        
        logging.warning("Timeout waiting for DONE_ACK")
        socketio_logger.warning("[SYSTEM] Timeout waiting for DONE_ACK")
        return False

        
    def wait_for_done_ack_or_missing(self, session):
        start_time = time.time()
        while time.time() - start_time < config.ACK_TIMEOUT:
            source_callsign, message, msg_type = self.receive_message(session, timeout=1.0)
            
            if msg_type == MessageType.DONE_ACK:
                socketio_logger.info("[CONTROL] Received DONE_ACK")
                logging.info("Received DONE_ACK")
                # Wait for potential disconnect message
                disconnect_wait_start = time.time()
                while time.time() - disconnect_wait_start < config.DISCONNECT_TIMEOUT:
                    _, _, disconnect_msg_type = self.receive_message(session, timeout=1.0)
                    if disconnect_msg_type == MessageType.DISCONNECT:
                        socketio_logger.info("[CONTROL] Received DISCONNECT after DONE_ACK")
                        logging.info("Received DISCONNECT after DONE_ACK")
                        self.handle_disconnect(session)
                        return True
                socketio_logger.warning("[SYSTEM] No DISCONNECT received after DONE_ACK, ending transmission")
                logging.warning("No DISCONNECT received after DONE_ACK, ending transmission")
                return True
            elif msg_type == MessageType.PKT_MISSING:
                socketio_logger.info(f"[CONTROL] Received PKT_MISSING request: {message}")
                logging.info(f"Received PKT_MISSING request: {message}")
                if self.connection_manager.handle_disconnect(session):
                    # Reset the timer after handling missing packets
                    start_time = time.time()
                else:
                    return False
            elif msg_type == MessageType.DISCONNECT:
                socketio_logger.info("[CONTROL] Received DISCONNECT while waiting for DONE_ACK")
                logging.info("Received DISCONNECT while waiting for DONE_ACK")
                self.connection_manager.handle_disconnect(session)
                return False
            
        socketio_logger.warning("[SYSTEM] Timeout waiting for DONE_ACK")
        logging.warning("Timeout waiting for DONE_ACK")
        return False

    def check_missing_packets(self, session):
        return set(range(1, session.total_packets + 1)) - session.acked_packets

    def handle_missing_packets_sender(self, session, missing_packets):
        return self.packet_handler.handle_missing_packets_sender(session, missing_packets)
    
    def send_done(self, session):
        return self.message_processor.send_control_message(session, "DONE", MessageType.DONE)
    
    def receive_done_ack(self, session, timeout=config.ACK_TIMEOUT):
        start_time = time.time()
        while time.time() - start_time < timeout:
            source_callsign, message, msg_type = self.receive_message(session, timeout=0.5)
            if msg_type == MessageType.DONE_ACK:
                socketio_logger.info(f"[CONTROL] Received DONE_ACK from {source_callsign}")
                logging.info(f"Received DONE_ACK from {source_callsign}")
                return True
            elif msg_type == MessageType.DISCONNECT:
                socketio_logger.info(f"[CONTROL] Received DISCONNECT from {source_callsign}")
                logging.info(f"Received DISCONNECT from {source_callsign}")
                self.handle_disconnect(session)
                return False
        socketio_logger.warning("[SYSTEM] DONE_ACK not received within timeout")
        logging.warning("DONE_ACK not received within timeout")
        return False
    
    def receive_done_ack(self, session, timeout=config.ACK_TIMEOUT):
        start_time = time.time()
        while time.time() - start_time < timeout:
            source_callsign, message, msg_type = self.receive_message(session, timeout=0.5)
            if msg_type == MessageType.DONE_ACK:
                socketio_logger.info(f"[CONTROL] Received DONE_ACK from {source_callsign}")
                logging.info(f"Received DONE_ACK from {source_callsign}")
                return True
        socketio_logger.warning("[SYSTEM] DONE_ACK not received within timeout")
        logging.warning("DONE_ACK not received within timeout")
        return False
    
    def handle_disconnect(self, session):
        self.connection_manager.handle_disconnect(session)

    def receive_response(self, session):
        start_time = time.time()
        response_parts = {}
        total_packets = None
        last_packet_time = start_time
        
        def update_packet(seq_num, content):
            response_parts[seq_num] = content
            logging.info(f"Updated packet {seq_num}. Total packets received: {len(response_parts)}")

        def check_missing_packets():
            if total_packets is None:
                return set()
            return set(range(1, total_packets + 1)) - set(response_parts.keys())

        while time.time() - start_time < config.CONNECTION_TIMEOUT:
            current_time = time.time()
            if current_time - last_packet_time > config.NO_PACKET_TIMEOUT:
                socketio_logger.warning(f"[PACKET] No packets received for {config.NO_PACKET_TIMEOUT} seconds.")
                logging.warning(f"No packets received for {config.NO_PACKET_TIMEOUT} seconds.")
                if total_packets is not None and total_packets > 0:
                    ratio = len(response_parts) / total_packets
                    if ratio >= config.MISSING_PACKETS_THRESHOLD:
                        socketio_logger.info(f"[PACKET] More than {config.MISSING_PACKETS_THRESHOLD*100}% of packets received. Attempting to request missing packets.")
                        logging.info(f"More than {config.MISSING_PACKETS_THRESHOLD*100}% of packets received. Attempting to request missing packets.")
                        missing = check_missing_packets()
                        if self.request_missing_packets(session, missing, update_packet):
                            last_packet_time = time.time()  # Reset the packet timeout
                            continue
                socketio_logger.warning("[SYSTEM] Disconnecting due to timeout.")
                logging.info("Disconnecting due to timeout.")
                self.disconnect(session)
                break

            source_callsign, message, msg_type = self.receive_message(session, timeout=1.0)
            
            if msg_type == MessageType.RESPONSE:
                last_packet_time = time.time()  # Reset the packet timeout
                try:
                    header, content = message.split(':', 1)
                    seq_num, total, _ = header.split('|')
                    seq_num = int(seq_num)
                    total = int(total)
                    
                    if total_packets is None:
                        total_packets = total
                    
                    update_packet(seq_num, content)
                    socketio_logger.info(f"[CONTROL] Sending control: Type=ACK")
                    self.send_ack(session, seq_num)
                    
                    progress = (len(response_parts) / total_packets) * 100
                    socketio_logger.info(f"[PROGRESS] {progress:.2f}% complete")
                    logging.info(f"Received packet {seq_num}/{total_packets} - Progress: {progress:.2f}%")
                except ValueError as e:
                    socketio_logger.error(f"[SYSTEM] Error parsing response message: {e}")
                    logging.error(f"Error parsing response message: {e}")
                    continue
                
            elif msg_type == MessageType.DONE:
                missing = check_missing_packets()
                if not missing:
                    socketio_logger.info("[CONTROL] Received DONE message & all packets are accounted for")
                    logging.info("Received DONE message and all packets are present")
                    full_response = self.reassemble_response(response_parts, total_packets)
                    self.send_single_packet(session, 0, 0, "DONE_ACK".encode(), MessageType.DONE_ACK)
                    return full_response
                else:
                    socketio_logger.warning(f"[SYSTEM] Received DONE but missing packets: {missing}")
                    logging.warning(f"Received DONE but missing packets: {missing}")
                    if self.request_missing_packets(session, missing, update_packet):
                        last_packet_time = time.time()  # Reset the packet timeout
                        continue  # Continue the loop to receive the missing packets
                    else:
                        socketio_logger.error("Failed to retrieve missing packets")
                        logging.error("Failed to retrieve missing packets")
                        break
            
            elif msg_type == MessageType.DISCONNECT:
                socketio_logger.info("[CONTROL] Received DISCONNECT message")
                logging.info("Received DISCONNECT message")
                self.send_ack(session)
                socketio_logger.info(f"[SYSTEM] Sending control: Type=ACK, disconnecting...")
                self.handle_disconnect(session)
                break
            
            elif msg_type is None:
                continue

        # Handle incomplete response
        if total_packets is not None and len(response_parts) < total_packets:
            socketio_logger.warning(f"[SYSTEM] Received incomplete response. Got {len(response_parts)} out of {total_packets} packets.")
            logging.warning(f"Received incomplete response. Got {len(response_parts)} out of {total_packets} packets.")
            missing = check_missing_packets()
            if self.request_missing_packets(session, missing, update_packet):
                logging.info("[SYSTEM] Successfully retrieved missing packets after timeout")
                logging.info("Successfully retrieved missing packets after timeout")
            else:
                socketio_logger.error("[SYSTEM] Failed to retrieve all missing packets after timeout")
                logging.error("Failed to retrieve all missing packets after timeout")

        if total_packets is None:
            return None
        return self.reassemble_response(response_parts, total_packets)
    
    def handle_data_transfer_end(self, session):
        if session.state == ModemState.CONNECTED:
            socketio_logger.info("[SYSTEM] Data transfer completed, initiating disconnect")
            logging.info("Data transfer completed, initiating disconnect as receiver")
            self.connection_manager.initiate_disconnect(session)

    def reassemble_response(self, response_parts, total_packets):
        return self.packet_handler.reassemble_response(response_parts, total_packets)

    def get_missing_packets(self, received_packets, total_packets):
        return self.packet_handler.get_missing_packets(received_packets, total_packets)
    
    def request_missing_packets(self, session, missing_packets, update_packet_func):
        # Add check for empty missing packets list
        if not missing_packets:
            logging.warning("Empty missing packets list, not sending PKT_MISSING")
            return True  # Return true since there's nothing missing
            
        request = f"PKT_MISSING|{'|'.join(map(str, missing_packets))}"
        if self.send_single_packet(session, 0, 0, request.encode(), MessageType.PKT_MISSING):
            if self.wait_for_ready(session, timeout=config.ACK_TIMEOUT * 2):
                if self.send_ready(session):
                    start_time = time.time()
                    while missing_packets and time.time() - start_time < config.CONNECTION_TIMEOUT:
                        source_callsign, message, msg_type = self.receive_message(session, timeout=1.0)
                        if msg_type == MessageType.RESPONSE:
                            try:
                                header, content = message.split(':', 1)
                                seq_num, total, _ = header.split('|')
                                seq_num = int(seq_num)
                                
                                if seq_num in missing_packets:
                                    update_packet_func(seq_num, content)
                                    missing_packets.remove(seq_num)
                                    self.send_ack(session, seq_num)
                                    socketio_logger.info(f"[PACKET] Received missing packet {seq_num}")
                                    logging.info(f"Received missing packet {seq_num}")
                                
                                if not missing_packets:
                                    socketio_logger.info("[SYSTEM] All missing packets received")
                                    logging.info("All missing packets received")
                                    return True
                            except ValueError as e:
                                socketio_logger.error(f"[SYSTEM] Error parsing response message: {e}")
                                logging.error(f"Error parsing response message: {e}")
                                continue
                        elif msg_type == MessageType.DONE:
                            if not missing_packets:
                                socketio_logger.info("[SYSTEM] All missing packets received")
                                logging.info("All missing packets received")
                                return True
                            else:
                                socketio_logger.warning(f"[SYSTEM] Received DONE but still missing packets: {missing_packets}")
                                logging.warning(f"Received DONE but still missing packets: {missing_packets}")
                                return False
                    
                    if missing_packets:
                        socketio_logger.warning(f"[SYSTEM] Timeout while waiting for missing packets: {missing_packets}")
                        logging.warning(f"Timeout while waiting for missing packets: {missing_packets}")
                        return False
                    return True
                else:
                    socketio_logger.error("[SYSTEM] Failed to send READY for missing packets")
                    logging.error("Failed to send READY for missing packets")
            else:
                socketio_logger.error("[SYSTEM] Did not receive READY from sender")
                logging.error("Did not receive READY from sender")
        logging.error("Failed to request missing packets")
        socketio_logger.error("[SYSTEM] Failed to request missing packets")
        return False

    def get_packet(self, session, seq_num):
        # Implement this method to retrieve a specific packet
        # This is a placeholder implementation
        if hasattr(session, 'sent_packets') and seq_num in session.sent_packets:
            return session.sent_packets[seq_num]
        return None
    
    def wait_for_missing_packets(self, session):
        start_time = time.time()
        while time.time() - start_time < config.MISSING_PACKETS_TIMEOUT:
            source_callsign, message, msg_type = self.receive_message(session, timeout=1.0)
            if msg_type == MessageType.PKT_MISSING:
                self.packet_handler.handle_missing_packets_sender(session, message)
                return True
            elif msg_type == MessageType.DONE_ACK:
                socketio_logger.info("[CONTROL] Received DONE_ACK, ending transmission")
                logging.info("Received DONE_ACK, ending transmission")
                return True
        
        missing_packets = self.check_missing_packets(session)
        if missing_packets:
            socketio_logger.info(f"[SYSTEM] Timeout waiting for missing packets request. Missing packets: {missing_packets}")
            logging.info(f"Timeout waiting for missing packets request. Missing packets: {missing_packets}")
        else:
            socketio_logger.info("[SYSTEM] All packets acknowledged. Ending transmission.")
            logging.info("All packets acknowledged. Ending transmission.")
        
        return False

    def send_disconnect(self, session):
        socketio_logger.info(f"[CONTROL] Sending DISCONNECT for session: {session.id}")
        logging.info(f"Sending DISCONNECT for session: {session.id}")
        return self.message_processor.send_control_message(session, "Disconnect", MessageType.DISCONNECT)


    def cleanup_session(self, session):
        if session.id in self.sessions:
            self.sessions.pop(session.id, None)
            socketio_logger.info(f"[SYSTEM] Disconnected session: {session.id}")
            logging.info(f"Disconnected session: {session.id}")
            session.state = ModemState.DISCONNECTED
        if self.is_server:
            # For server, don't close TNC connection, just reset for next client
            self.reset_for_next_connection()
        else:
            self.stop()  # For client, stop the core

    def reset_for_next_connection(self):
        socketio_logger.info("[SYSTEM] Resetting for next connection")
        logging.info("Resetting for next connection")
        self.sessions.clear()
        if self.is_server:
            self.connection_manager.reset_for_next_connection()
        else:
            self.connection_manager.stop()
            self.connection_manager = ConnectionManager(self.is_server, self)
            self.connection_manager.start()
    
    def check_missing_packets(self, session):
        return self.packet_handler.check_missing_packets(session)