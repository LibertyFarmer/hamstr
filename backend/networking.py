import socket
import time
import logging
import config
from ax25_kiss_utils import kiss_unwrap, decode_ax25_callsign, clean_message, kiss_wrap
from models import Session
from socketio_logger import get_socketio_logger
from protocol_utils import estimate_transmission_time

# Import serial support
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logging.warning("pyserial not available - serial TNC support disabled")

# SocketIO logger
socketio_logger = get_socketio_logger()

# Begin Networking Functions
def create_tnc_connection(host, port, timeout=5):
    """Create a connection to the TNC."""
    
    # Check if we should use serial instead of TCP
    connection_type = getattr(config, 'CONNECTION_TYPE', 'tcp').lower()
    
    if connection_type == 'serial' and SERIAL_AVAILABLE:
        return _create_serial_connection(timeout)
    else:
        return _create_tcp_connection(host, port, timeout)

def _create_tcp_connection(host, port, timeout=5):
    """Create a TCP connection to the TNC (original functionality)."""
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

def _create_serial_connection(timeout=5):
    """Create a serial connection to the TNC."""
    if not SERIAL_AVAILABLE:
        socketio_logger.error("[TNC] pyserial not available - cannot create serial connection")
        logging.error("pyserial not available - cannot create serial connection")
        return None
    
    # Get serial settings from config
    serial_port = getattr(config, 'SERIAL_PORT', 'COM3')
    serial_speed = getattr(config, 'SERIAL_SPEED', 57600)
    
    logging.debug(f"Attempting serial connection to TNC at {serial_port}:{serial_speed} [NETWORKING]")
    try:
        ser = serial.Serial(
            port=serial_port,
            baudrate=serial_speed,
            timeout=timeout,
            write_timeout=timeout
        )
        logging.debug(f"Connected to TNC at {serial_port}:{serial_speed} [NETWORKING]")
        socketio_logger.info(f"[TNC] Connected to serial TNC at {serial_port}:{serial_speed}")
        return ser
    except serial.SerialException as e:
        socketio_logger.error(f"[TNC] Serial connection error: {e}")
        logging.error(f"Serial connection error: {e}")
    except Exception as e:
        socketio_logger.error(f"[TNC] Error connecting to serial TNC: {e} [NETWORKING]")
        logging.error(f"Error connecting to serial TNC: {e} [NETWORKING]")
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
            sock = connection  # Assume it's already a connection object

        # Send frame - handle both socket and serial
        if hasattr(sock, 'sendall'):  # TCP socket
            sock.sendall(frame)
        elif hasattr(sock, 'write'):  # Serial connection
            sock.write(frame)
        else:
            # Fallback - try sendall first, then write
            try:
                sock.sendall(frame)
            except AttributeError:
                sock.write(frame)
                
        if not is_ack:
            time.sleep(len(frame) * delay_factor)
        logging.debug("Sent Data")
        return True
    except Exception as e:
        socketio_logger.error(f"[SYSTEM] Error sending frame: {e}")
        logging.error(f"Error sending frame: {e}")
        return False

def receive_packet(sock, timeout=0.1):
    if sock is None:
        return None, None

    # Check if connection is closed
    if hasattr(sock, '_closed') and sock._closed:
        return None, None
    elif hasattr(sock, 'is_open') and not sock.is_open:
        return None, None

    try:
        # Set timeout and receive data
        if hasattr(sock, 'settimeout'):  # TCP socket
            sock.settimeout(timeout)
            chunk = sock.recv(1024)
        elif hasattr(sock, 'timeout'):  # Serial connection
            sock.timeout = timeout
            chunk = sock.read(1024)
        else:
            # Fallback - assume socket-like
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
    except (socket.timeout, serial.SerialTimeoutException if SERIAL_AVAILABLE else socket.timeout):
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
        connection_type = getattr(config, 'CONNECTION_TYPE', 'tcp').lower()
        if connection_type == 'serial':
            serial_port = getattr(config, 'SERIAL_PORT', 'COM3')
            socketio_logger.error(f"[TNC] Failed to connect to serial TNC at {serial_port}")
            logging.error(f"Failed to connect to serial TNC at {serial_port}")
        else:
            socketio_logger.error(f"[TNC] Failed to connect to TNC at {host}:{port}")
            logging.error(f"Failed to connect to TNC at {host}:{port}")
        return None, None

    logging.debug(f"Connected to TNC for listening")

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
        # Close connection
        if hasattr(sock, 'close'):
            sock.close()
        logging.debug("Closed TNC connection")