import logging
import time
import config
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

def wait_for_ack(core, session, timeout=config.ACK_TIMEOUT):
    start_time = time.time()
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
    logging.warning("ACK not received within timeout")
    return False