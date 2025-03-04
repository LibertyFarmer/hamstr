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
    
    while time.time() - start_time < timeout:
        source_callsign, message, msg_type = core.receive_message(session, timeout=0.5)
        if msg_type == MessageType.ACK:
            logging.info(f"Received ACK from {source_callsign}")
            session.last_activity = time.time()
            return True
        elif msg_type == MessageType.DISCONNECT:
            logging.info(f"Received DISCONNECT from {source_callsign}")
            core.handle_disconnect(session)
            return False
        elif msg_type is not None:
            logging.warning(f"Received unexpected message while waiting for ACK: {msg_type}")
        
        # Add exponential backoff for retries
        if resend_message and resend_type and time.time() - start_time > (timeout / 3) * (resend_count + 1) and resend_count < max_resends:
            # Calculate backoff time - exponential with some randomness to prevent collisions
            backoff_time = (config.PTT_ACK_SPACING * (1.5 ** resend_count)) + (random.random() * 0.2)
            logging.info(f"Backing off for {backoff_time:.2f} seconds before retry {resend_count + 1}")
            time.sleep(backoff_time)
            
            # Add PTT TX delay before sending
            time.sleep(config.PTT_TX_DELAY)
            
            # Then resend
            core.send_single_packet(session, 0, 0, resend_message, resend_type)
            resend_count += 1
            
            # Add additional wait after sending to allow radio to switch back to receive
            time.sleep(config.PTT_RX_DELAY)
    
    logging.warning("ACK not received within timeout")
    return False