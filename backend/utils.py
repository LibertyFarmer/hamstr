import logging
import time
import config
import random
from models import MessageType

def wait_for_specific_message(core, session, expected_type, timeout=config.ACK_TIMEOUT):
    start_time = time.time()
    logging.info(f"Waiting for message type {expected_type} with timeout {timeout} seconds")
    while time.time() - start_time < timeout:
        source_callsign, message, msg_type = core.receive_message(session, timeout=0.1)
        if msg_type is not None:
            logging.info(f"Received: source={source_callsign}, type={msg_type}, message={message}")
            if msg_type == expected_type:
                logging.info(f"Received expected message type: {expected_type}")
                return True
            elif msg_type == MessageType.DISCONNECT:
                logging.info(f"Received DISCONNECT while waiting for {expected_type}")
                return False
        time.sleep(0.1)
    
    logging.warning(f"Timeout after {timeout} seconds while waiting for {expected_type}")
    return False

def wait_for_ack(core, session, timeout=config.ACK_TIMEOUT, resend_message=None, resend_type=None):
    start_time = time.time()
    resend_count = 0
    max_resends = 2
    ack_wait_start = time.time()
    
    # Add a small delay before starting to wait for ACK to give client time to process
    time.sleep(config.CONNECTION_STABILIZATION_DELAY)
    
    while time.time() - start_time < timeout:
        source_callsign, message, msg_type = core.receive_message(session, timeout=0.5)
        if msg_type == MessageType.ACK:
            # Check if the ACK contains a sequence number
            if message and "|" in message:
                _, seq_num = message.split("|", 1)
                logging.info(f"Received ACK with sequence number {seq_num} from {source_callsign}")
                session.last_activity = time.time()
                
                # Return True if this is the ACK we're waiting for
                return True
            else:
                logging.info(f"Received general ACK from {source_callsign}")
                session.last_activity = time.time()
                return True
                
        elif msg_type == MessageType.DISCONNECT:
            logging.info(f"Received DISCONNECT from {source_callsign}")
            core.handle_disconnect(session)
            return False
        elif msg_type is not None:
            logging.warning(f"Received unexpected message while waiting for ACK: {msg_type}")
        
        # Add a more patient retry mechanism
        if resend_message and resend_type and time.time() - ack_wait_start > (timeout / 3) and resend_count < max_resends:
            # Calculate wait time before retry - grows with each retry
            wait_time = config.CONNECTION_STABILIZATION_DELAY * (1 + resend_count)
            logging.info(f"Waiting {wait_time:.2f} seconds before retry attempt {resend_count + 1}")
            time.sleep(wait_time)
            
            # Then try resending
            logging.info(f"No ACK received yet, resending message (attempt {resend_count + 1})")
            core.send_single_packet(session, 0, 0, resend_message, resend_type)
            resend_count += 1
            ack_wait_start = time.time()  # Reset the ack wait timer
    
    logging.warning("ACK not received within timeout")
    return False