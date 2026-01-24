import logging
import time
import config
from models import MessageType, ModemState
from protocol_utils import calculate_crc32
from socketio_logger import get_socketio_logger


# SocketIO logger
socketio_logger = get_socketio_logger()


class MessageProcessor:
    def __init__(self, core):
        self.core = core

    def process_message(self, message, source_callsign):
        try:
            if ':' not in message:
                raise ValueError("Invalid message format")
            
            header, content = message.split(':', 1)
            header_parts = header.split('|')
            
            if len(header_parts) == 1:
                # Control message
                msg_type = MessageType(int(header_parts[0]))
                return source_callsign, content, msg_type
            elif len(header_parts) == 3:
                # Data message
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
                
                socketio_logger.info(f"[PACKET] Received message: Type={msg_type.name}, Seq={seq_num}/{total_packets}, Content={content[:50]}...")
                logging.info(f"Received message: Type={msg_type.name}, Seq={seq_num}/{total_packets}, Content={content[:50]}...")
                return source_callsign, f"{header}:{content}", msg_type
            else:
                raise ValueError("Invalid header format")
        except Exception as e:
            socketio_logger.error(f"[SYSTEM] Error processing message: {str(e)}")
            logging.error(f"Error processing message: {str(e)}")
            return source_callsign, None, None

    def send_message(self, session, message, message_type):
        socketio_logger.info(f"[PACKET] Sending message: {message_type} to {session.remote_callsign}")
        logging.info(f"Sending message: {message_type} to {session.remote_callsign}")
        session.state = ModemState.SENDING  
        
        if isinstance(message, str):
            message = message.encode('utf-8')
        
        packets = self.core.packet_handler.split_message(message)
        session.total_packets = len(packets)
        session.sent_packets = {}
        session.acked_packets = set()
        
        for seq_num, packet in enumerate(packets, 1):
            retry_count = 0
            while retry_count < config.RETRY_COUNT:
                if self.core.send_single_packet(session, seq_num, session.total_packets, packet, message_type):
                    session.sent_packets[seq_num] = packet
                    if message_type not in [MessageType.ACK, MessageType.CONNECT, MessageType.CONNECT_ACK, MessageType.DATA_REQUEST]:
                        if self.core.wait_for_ack(session):
                            session.acked_packets.add(seq_num)
                            break
                    else:
                        return True
                
                retry_count += 1
                if retry_count < config.RETRY_COUNT:
                    socketio_logger.warning(f"[PACKET] Attempt {retry_count} failed. Retrying in {config.ACK_TIMEOUT} seconds...")
                    logging.warning(f"Attempt {retry_count} failed. Retrying in {config.ACK_TIMEOUT} seconds...")
                    time.sleep(config.ACK_TIMEOUT)
            
            if retry_count == config.RETRY_COUNT:
                socketio_logger.warning(f"[PACKET] Failed to send packet {seq_num}/{session.total_packets} after {config.RETRY_COUNT} attempts. Moving to next packet.")
                logging.warning(f"Failed to send packet {seq_num}/{session.total_packets} after {config.RETRY_COUNT} attempts. Moving to next packet.")
        
        self.core.send_done(session)
        return self.core.wait_for_missing_packets(session)

    def send_data_request(self, session, request):
        logging.debug(f"Sending DATA_REQUEST: {request}")
        if self.send_message(session, request, MessageType.DATA_REQUEST):
            logging.debug("DATA_REQUEST sent, waiting for READY")
            if self.core.wait_for_specific_message(session, MessageType.READY):
                socketio_logger.info("[CLIENT] Received READY from server, sending READY")
                logging.info("Received READY from server, sending READY")
                if self.core.send_ready(session):
                    socketio_logger.info("[CONTROL] READY sent successfully")
                    logging.info("READY sent successfully")
                    return True
                else:
                    socketio_logger.error("[SYSTEM] Failed to send READY message")
                    logging.error("Failed to send READY message")
            else:
                socketio_logger.error("[SYSTEM] Failed to receive READY for DATA_REQUEST")
                logging.error("Failed to receive READY for DATA_REQUEST")
        else:
            socketio_logger.error("[SYSTEM] Failed to send DATA_REQUEST")
            logging.error("Failed to send DATA_REQUEST")
        return False

    def wait_for_data_request(self, session):
        start_time = time.time()
        while time.time() - start_time < config.CONNECTION_TIMEOUT:
            source_callsign, message, msg_type = self.core.receive_message(session)
            if msg_type == MessageType.DATA_REQUEST:
                return message
            time.sleep(0.1)
        socketio_logger.warning("[SYSTEM] Timeout while waiting for DATA_REQUEST")
        logging.warning("Timeout while waiting for DATA_REQUEST")
        return None
    
    def send_control_message(self, session, content, message_type):
        """Send a control message with retry logic"""
        logging.info(f"Sending control message: {content}")
        
        # Add a small delay before sending READY messages
        if message_type == MessageType.READY:
            time.sleep(config.CONNECTION_STABILIZATION_DELAY)
        
        for retry_count in range(config.RETRY_COUNT):
            if self.core.send_single_packet(session, 0, 0, content.encode(), message_type):
                logging.info(f"Control message {message_type.name} sent successfully")
                
                # Add a longer delay after READY messages
                if message_type == MessageType.READY:
                    time.sleep(config.CONNECTION_STABILIZATION_DELAY)
                    
                return True
            
            logging.warning(f"Failed to send {message_type.name}. Attempt {retry_count + 1} of {config.RETRY_COUNT}")
            if retry_count < config.RETRY_COUNT - 1:
                time.sleep(config.ACK_TIMEOUT / 2)  # Shorter delay for control messages
        
        logging.error(f"Failed to send {message_type.name} after {config.RETRY_COUNT} attempts")
        return False