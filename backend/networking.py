import socket
import time
import logging
import config
from ax25_kiss_utils import kiss_unwrap, decode_ax25_callsign, clean_message, kiss_wrap
from models import Session
from socketio_logger import get_socketio_logger
from protocol_utils import estimate_transmission_time


# SocketIO logger
socketio_logger = get_socketio_logger()

# Begin Networking Functions
def create_tnc_connection(host, port, timeout=5):
    """Create a connection to the TNC."""
    logging.debug(f"Attempting to connect to TNC at {host}:{port} [NETWORKING]")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        logging.debug(f"Connected to TNC at {host}:{port} [NETWORKING]")
        return sock
    except ConnectionRefusedError:
        socketio_logger.error(f"[TNC] Error connecting to TNC: Connection refused on port {port}. [NETWORKING.PY]")
        logging.error(f"Error connecting to TNC: Connection refused on port {port}. [NETWORKING.PY]")
    except socket.timeout:
        socketio_logger.error(f"[TNC] Error connecting to TNC: Connection timed out. [NETWORKING]")
        logging.error(f"Error connecting to TNC: Connection timed out. [NETWORKING]")
    except Exception as e:
        socketio_logger.error(f"[TNC] Error connecting to TNC: {e} [NETWORKING]")
        logging.error(f"Error connecting to TNC: {e} [NETWORKING]")
    return None

def send_frame(connection, frame, is_ack=False, delay_factor=0.001):
    """Send a frame to the TNC and optionally wait for confirmation."""
    try:
        if isinstance(connection, Session):
            if not connection.tnc_connection:
                socketio_logger.error("[TNC] No TNC connection available for sending frame")
                logging.error("No TNC connection available for sending frame")
                return False
            sock = connection.tnc_connection
        else:
            sock = connection  # Assume it's already a socket object

        # Add a small delay before transmission to allow radio PTT to engage
        time.sleep(config.CONNECTION_STABILIZATION_DELAY)
        
        # Send the data
        sock.sendall(frame)
        
        # Calculate transmission time based on frame size and baud rate
        # Add small buffer for radio tail and for receiver to be ready
        transmission_time = estimate_transmission_time(len(frame))
        
        # Use longer delay for ACKs to ensure they're received
        if is_ack:
            time.sleep(transmission_time * 1.5)
        else:
            time.sleep(transmission_time)
            
        logging.debug("Sent Data")
        return True
    except Exception as e:
        socketio_logger.error(f"[SYSTEM] Error sending frame: {e}")
        logging.error(f"Error sending frame: {e}")
        return False

def receive_packet(sock, timeout=0.1):
    if sock is None or sock._closed:
        return None, None

    try:
        sock.settimeout(timeout)
        chunk = sock.recv(1024)
        if chunk:
            logging.debug(f"Received chunk: {chunk}")
            start = chunk.find(b'\xc0')
            end = chunk.find(b'\xc0', start + 1)

            if start != -1 and end != -1:
                kiss_frame = chunk[start:end+1]

                if not kiss_frame or len(kiss_frame) < 3:
                    socketio_logger.warning("[SYSTEM] Received an empty or malformed KISS frame. Ignoring...")
                    logging.warning("Received an empty or malformed KISS frame. Ignoring...")
                    return None, None

                ax25_frame = kiss_unwrap(kiss_frame)
                if ax25_frame:
                    source_callsign = decode_ax25_callsign(ax25_frame, 7)
                    logging.debug(f"Decoded AX.25 frame from {source_callsign}")
                    return source_callsign, ax25_frame
    except socket.timeout:
        pass
    except ConnectionResetError:
        socketio_logger.info("[TNC] Connection was reset by peer")
        logging.info("Connection was reset by peer")
        return None, None
    except AttributeError:
        socketio_logger.info("[TNC] Socket has been closed")
        logging.info("Socket has been closed")
        return None, None
    except OSError as e:
        if e.errno == 10038:  # "An operation was attempted on something that is not a socket"
            socketio_logger.info("[TNC] Socket has been closed")
            logging.info("Socket has been closed")
        else:
            socketio_logger.error(f"[TNC] Error receiving packet: {str(e)}")
            logging.error(f"Error receiving packet: {str(e)}")
        return None, None
    except Exception as e:
        socketio_logger.error(f"[TNC] Unexpected error receiving packet: {str(e)}")
        logging.error(f"Unexpected error receiving packet: {str(e)}")
        return None, None

    return None, None

def listen_for_packets(host, port, timeout=0.1, max_retries=3):
    sock = create_tnc_connection(host, port)
    if not sock:
        socketio_logger.error(f"[TNC] Failed to connect to TNC at {host}:{port}")
        logging.error(f"Failed to connect to TNC at {host}:{port}")
        return None, None

    logging.debug(f"Connected to TNC at {host}:{port}")

    try:
        start_time = time.time()
        while time.time() - start_time < timeout * max_retries:
            logging.debug(f"Attempting to receive packet, time left: {timeout * max_retries - (time.time() - start_time):.2f}s")
            source_callsign, ax25_frame = receive_packet(sock, timeout)
            if source_callsign and ax25_frame:
                logging.debug(f"Received packet from {source_callsign}")
                return source_callsign, ax25_frame
            time.sleep(0.1)

        logging.debug("No packets received within timeout period")
        return None, None
    finally:
        sock.close()
        logging.debug("Closed TNC connection")