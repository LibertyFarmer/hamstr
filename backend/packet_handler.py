import logging
import time
import config
from models import MessageType
from ax25_kiss_utils import build_ax25_frame, kiss_wrap
from protocol_utils import calculate_crc32, estimate_transmission_time
from networking import send_frame
from socketio_logger import get_socketio_logger

# SocketIO logger
socketio_logger = get_socketio_logger()

class PacketHandler:
    def __init__(self, core):
        self.core = core

    def send_single_packet(self, session, seq_num, total_packets, packet, message_type):
        if not session.tnc_connection:
            socketio_logger.error("[TNC] TNC connection is closed. Cannot send packet.")
            logging.error("TNC connection is closed. Cannot send packet.")
            return False
        
        if message_type in [MessageType.ACK, MessageType.CONNECT, MessageType.CONNECT_ACK, 
                            MessageType.DATA_REQUEST, MessageType.DONE, MessageType.DONE_ACK, 
                            MessageType.RETRY, MessageType.DISCONNECT, MessageType.READY,
                            MessageType.PKT_MISSING]:
            # Control messages
            full_packet = f"{message_type.value}:{packet.decode()}"
        else:
            # Data messages
            header = f"{seq_num:04d}|{total_packets:04d}|{message_type.value}"
            content = f"{header}:{packet.decode()}"
            
            # Calculate checksum and append it to the content
            checksum = calculate_crc32(content.encode())
            full_packet = f"{content}|{checksum}"
    
        logging.debug(f"Sending packet: {full_packet}")
        
        ax25_frame = build_ax25_frame(self.core.callsign, session.remote_callsign, full_packet.encode())
        kiss_frame = kiss_wrap(ax25_frame)
        
        success = send_frame(session.tnc_connection, kiss_frame)
        if success:
            estimated_time = estimate_transmission_time(len(kiss_frame))
            socketio_logger.info(f"[CONTROL] Sending packet: Type={message_type.name}, Seq={seq_num}/{total_packets}, Estimated transmission time: {estimated_time:.2f} seconds")
            logging.info(f"Sending packet: Type={message_type.name}, Seq={seq_num}/{total_packets}")
            
            #socketio_logger.info(f"[PACKET] Estimated transmission time: {estimated_time:.2f} seconds")
            logging.info(f"Estimated transmission time: {estimated_time:.2f} seconds")
            
            # Add PTT delay adjustments after sending
            if message_type == MessageType.ACK:
                # Shorter delay for ACKs
                time.sleep(estimated_time + config.PTT_TAIL)
            elif message_type in [MessageType.CONNECT, MessageType.CONNECT_ACK, MessageType.READY]:
                # Longer delay for control messages
                time.sleep(estimated_time + config.PTT_ACK_SPACING)
            else:
                # Standard delay for data packets
                time.sleep(estimated_time + config.PTT_RX_DELAY)
        else:
            socketio_logger.error(f"[PACKET] Failed to send packet: Type={message_type.name}, Seq={seq_num}/{total_packets}")
            logging.error(f"Failed to send packet: Type={message_type.name}, Seq={seq_num}/{total_packets}")
        return success

    def split_message(self, message):
        max_packet_size = config.MAX_PACKET_SIZE - 15  # Account for headers
        return [message[i:i+max_packet_size] for i in range(0, len(message), max_packet_size)]

    def reassemble_response(self, response_parts, total_packets):
        reassembled = []
        missing_packets = []
        for i in range(1, total_packets + 1):
            if i in response_parts:
                reassembled.append(response_parts[i])
                logging.debug(f"Packet {i} content: {response_parts[i][:50]}...")  # Log first 50 chars
            else:
                missing_packets.append(i)
                reassembled.append(f"[MISSING PACKET {i}]")
        
        full_response = ''.join(reassembled)
        if missing_packets:
            socketio_logger.warning(f"[SYSTEM] Packets {missing_packets} are missing in the final reassembly")
            logging.warning(f"Packets {missing_packets} are missing in the final reassembly")
            logging.debug(f"Received packets: {sorted(response_parts.keys())}")
        else:
            socketio_logger.info("[SYSTEM] All packets successfully reassembled")
            logging.info("All packets successfully reassembled")
        logging.debug(f"Full reassembled response: {full_response}")
        return full_response

    def get_missing_packets(self, received_packets, total_packets):
        return [i for i in range(1, total_packets + 1) if i not in received_packets]

    def check_missing_packets(self, session):
        return set(range(1, session.total_packets + 1)) - session.acked_packets

    def handle_missing_packets_sender(self, session, missing_packets):
        if isinstance(missing_packets, str):
            try:
                _, missing_packets_str = missing_packets.split('|', 1)
                missing_packets = list(map(int, missing_packets_str.split('|')))
            except ValueError:
                socketio_logger.error("[SYSTEM] Invalid PKT_MISSING message format")
                logging.error("Invalid PKT_MISSING message format")
                return False
        
        logging.info(f"Handling missing packets: {missing_packets}")
        socketio_logger.info(f"[SYSTEM] Handling missing packets: {missing_packets}")
        
        if self.core.send_ready(session):
            if self.core.wait_for_ready(session, timeout=config.ACK_TIMEOUT * 2):
                for seq_num in missing_packets:
                    packet = self.get_packet(session, seq_num)
                    if packet:
                        if self.send_single_packet(session, seq_num, session.total_packets, packet, MessageType.RESPONSE):
                            if self.core.wait_for_ack(session):
                                socketio_logger.info(f"[SYSTEM] Successfully resent packet {seq_num}")
                                logging.info(f"Successfully resent packet {seq_num}")
                            else:
                                socketio_logger.warning(f"[SYSTEM] Failed to receive ACK for resent packet {seq_num}")
                                logging.warning(f"Failed to receive ACK for resent packet {seq_num}")
                                return False
                        else:
                            socketio_logger.error(f"[SYSTEM] Failed to resend packet {seq_num}")
                            logging.error(f"Failed to resend packet {seq_num}")
                            return False
                    else:
                        socketio_logger.error(f"[SYSTEM] Could not find packet {seq_num} for resending")
                        logging.error(f"Could not find packet {seq_num} for resending")
                        return False
                
                logging.info("All missing packets sent successfully")
                socketio_logger.info("[SYSTEM] All missing packets sent successfully")
                return True
            else:
                socketio_logger.error("[SYSTEM] Did not receive READY message from receiver")
                logging.error("Did not receive READY message from receiver")
                return False
        else:
            socketio_logger.error("[SYSTEM] Failed to send READY for missing packets")
            logging.error("Failed to send READY for missing packets")
            return False

    def get_packet(self, session, seq_num):
        if hasattr(session, 'sent_packets') and seq_num in session.sent_packets:
            return session.sent_packets[seq_num]
        return None
