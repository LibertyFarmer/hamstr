import logging
import time
import socket
import config
from models import Session, ModemState, MessageType
from networking import create_tnc_connection as networking_create_tnc_connection
from protocol_utils import parse_callsign
from socketio_logger import get_socketio_logger


# SocketIO logger
socketio_logger = get_socketio_logger()


def create_tnc_connection(host, port):
    """Create a connection to the TNC."""
    try:
        sock = networking_create_tnc_connection(host, port)
        if sock:
            socketio_logger.info(f"[TNC] Connected to TNC at {host}:{port}")
            logging.info(f"Connected to TNC at {host}:{port}")
            return sock
        else:
            socketio_logger.error(f"[TNC] Failed to connect to TNC at {host}:{port}")
            logging.error(f"Failed to connect to TNC at {host}:{port}")
            return None
    except Exception as e:
        socketio_logger.error(f"[TNC] Error connecting to TNC: {str(e)}")
        logging.error(f"Error connecting to TNC: {str(e)}")
        return None

def cleanup_session(session, sessions):
    """Clean up a session."""
    if session.id in sessions:
        sessions.pop(session.id, None)
        socketio_logger.info(f"[SESSION] Disconnected session: {session.id}")
        logging.info(f"Disconnected session: {session.id}")
        session.state = ModemState.DISCONNECTED

def reset_for_next_connection():
    """Reset the server for the next connection."""
    socketio_logger.info("[SYSTEM] Resetting server for next connection")
    logging.info("Resetting server for next connection")
    # Add any future necessary reset logic here


class ConnectionManager:
    def __init__(self, is_server, core):
        self.is_server = is_server
        self.core = core
        self.tnc_host = config.SERVER_HOST if is_server else config.CLIENT_HOST
        self.tnc_port = config.SERVER_PORT if is_server else config.CLIENT_PORT
        self.callsign = parse_callsign(config.S_CALLSIGN if is_server else config.C_CALLSIGN)
        self.tnc_connection = None
        logging.debug(f"ConnectionManager initialized for {'server' if is_server else 'client'} [CM]")

    def start(self):
        logging.debug("ConnectionManager start method called [CM]")
        self.tnc_connection = create_tnc_connection(self.tnc_host, self.tnc_port)
        if not self.tnc_connection:
            logging.error(f"Failed to connect to TNC at {self.tnc_host}:{self.tnc_port} [CM]")
            return False
        logging.debug(f"Started ConnectionManager with TNC at {self.tnc_host}:{self.tnc_port} [CM]")
        return True
    
    def stop(self):
        if not hasattr(self, '_stopped'):
            self._stopped = True
            if self.tnc_connection:
                try:
                    self.tnc_connection.shutdown(socket.SHUT_RDWR)
                    self.tnc_connection.close()
                except Exception as e:
                    socketio_logger.error(f"[TNC] Error closing TNC connection: {str(e)}")
                    logging.error(f"Error closing TNC connection: {str(e)}")
            self.tnc_connection = None
            logging.debug("ConnectionManager stopped [CM_STOP]")

    def connect(self, remote_callsign):
        if not self.start():
            socketio_logger.error("[TNC] Failed to start TNC connection")
            logging.error("Failed to start TNC connection")
            return None

        if not self.tnc_connection:
            socketio_logger.error("[TNC] NC connection is not established")
            logging.error("TNC connection is not established")
            return None

        session = self.create_session(remote_callsign)
        session.state = ModemState.CONNECTING
        session.tnc_connection = self.tnc_connection

        for attempt in range(config.RETRY_COUNT):
            socketio_logger.info(f"[NETWORKING] Connection attempt {attempt + 1}/{config.RETRY_COUNT}")
            logging.info(f"Connection attempt {attempt + 1}/{config.RETRY_COUNT}")
            if self.core.send_single_packet(session, 0, 0, "Connect Request".encode(), MessageType.CONNECT):
                socketio_logger.info(f"[SESSION] Sending CONNECTION REQUEST. Waiting for CONNECT_ACK...")
                logging.info(f"Sending CONNECTION REQUEST. Waiting for CONNECT_ACK...")
                if self.core.wait_for_specific_message(session, MessageType.CONNECT_ACK, timeout=config.CONNECTION_ATTEMPT_TIMEOUT):
                    # Add a significant delay after receiving CONNECT_ACK before sending ACK
                    time.sleep(config.CONNECTION_STABILIZATION_DELAY * 2)
                    
                    if self.core.send_ack(session):
                        session.state = ModemState.CONNECTED
                        socketio_logger.info(f"[SESSION] CONNECTED to {remote_callsign[0]}-{remote_callsign[1]}")
                        logging.info(f"CONNECTED to {remote_callsign[0]}-{remote_callsign[1]}")
                        
                        # Add another delay to let the ACK fully transmit
                        time.sleep(config.CONNECTION_STABILIZATION_DELAY * 2)
                        
                        return session
                    else:
                        socketio_logger.error("[CONTROL] Failed to send ACK")
                        logging.error("Failed to send ACK")
                else:
                    socketio_logger.warning(f"[SYSTEM] Timeout waiting for CONNECT_ACK on attempt {attempt + 1}")
                    logging.warning(f"Timeout waiting for CONNECT_ACK on attempt {attempt + 1}")
            else:
                socketio_logger.warning(f"[SYSTEM] Failed to send CONNECTION REQUEST on attempt {attempt + 1}")
                logging.warning(f"Failed to send CONNECTION REQUEST on attempt {attempt + 1}")
            
            if attempt < config.RETRY_COUNT - 1:
                socketio_logger.info(f"[SYSTEM] Retrying in {config.CONNECTION_ATTEMPT_TIMEOUT} seconds...")
                logging.info(f"Retrying in {config.CONNECTION_ATTEMPT_TIMEOUT} seconds...")
                time.sleep(config.CONNECTION_ATTEMPT_TIMEOUT)
        
        logging.error(f"Failed to connect to {remote_callsign} after {config.RETRY_COUNT} attempts")
        socketio_logger.error(f"[SYSTEM] Failed to connect to {remote_callsign} after {config.RETRY_COUNT} attempts")
        self.core.stop()
        return None
    
    def create_session(self, remote_callsign):
        """Create a new session."""
        parsed_callsign = parse_callsign(remote_callsign)
        session_id = f"{self.callsign[0]}-{parsed_callsign[0]}-{int(time.time())}"
        session = Session(session_id, parsed_callsign)
        session.tnc_connection = self.tnc_connection
        return session
    

    def initiate_disconnect(self, session):
        socketio_logger.info(f"[SESSION] Initiating disconnect for session: {session.id}")
        logging.info(f"Initiating disconnect for session: {session.id}")
        if session and session.state not in [ModemState.DISCONNECTING, ModemState.DISCONNECTED]:
            session.state = ModemState.DISCONNECTING
            try:
                if self.core.send_single_packet(session, 0, 0, "Disconnect".encode(), MessageType.DISCONNECT):
                    if self.core.wait_for_ack(session, timeout=config.DISCONNECT_TIMEOUT):
                        socketio_logger.info("[CONTROL] DISCONNECT ACK received")
                        logging.info("Disconnect acknowledged")
                    else:
                        socketio_logger.warning("[SYSTEM] Did not receive DISCONNECT ACK")
                        logging.warning("Did not receive ACK for DISCONNECT")
                else:
                    socketio_logger.error("[SYSTEM] Failed to send DISCONNECT")
                    logging.error("Failed to send DISCONNECT")
            except Exception as e:
                socketio_logger.error(f"Error during disconnect: {str(e)}")
                logging.error(f"Error during disconnect: {str(e)}")
            finally:
                self.cleanup_session(session)
        elif session:
            socketio_logger.info(f"[SESSION] Session {session.id} already disconnecting or disconnected")
            logging.info(f"Session {session.id} already disconnecting or disconnected")
    
    def disconnect(self, session):
        socketio_logger.info(f"[SESSION] Disconnecting session: {session.id}")
        logging.info(f"Disconnecting session: {session.id}")
        if session and session.state not in [ModemState.DISCONNECTING, ModemState.DISCONNECTED]:
            session.state = ModemState.DISCONNECTING
            self.cleanup_session(session)  # Actually clean up the session
        elif session:
            socketio_logger.info(f"[SESSION] Session {session.id} already disconnecting or disconnected")
            logging.info(f"Session {session.id} already disconnecting or disconnected")

    def handle_disconnect(self, session):
        socketio_logger.info(f"[SESSION] Handling disconnect for session: {session.id}")
        logging.info(f"Handling disconnect for session: {session.id}")
        self.cleanup_session(session)

    def handle_disconnect_request(self, session):
        socketio_logger.info(f"[SESSION] Handling disconnect request for session: {session.id}")
        logging.info(f"Handling disconnect request for session: {session.id}")
        if session and session.state not in [ModemState.DISCONNECTING, ModemState.DISCONNECTED]:
            session.state = ModemState.DISCONNECTING
            self.core.send_ack(session)
            self.cleanup_session(session)
        else:
            socketio_logger.info(f"[SYSTEM] Session {session.id} already disconnecting or disconnected")
            logging.info(f"Session {session.id} already disconnecting or disconnected")

    def cleanup_session(self, session):
        if session.id in self.core.sessions:
            self.core.sessions.pop(session.id, None)
            socketio_logger.info(f"[SESSION] Cleaned up session: {session.id}")
            logging.info(f"Cleaned up session: {session.id}")
        if session.tnc_connection:
            try:
                session.tnc_connection.close()
            except Exception as e:
                socketio_logger.error(f"[TNC] Error closing TNC connection: {str(e)}")
                logging.error(f"Error closing TNC connection: {str(e)}")
        session.state = ModemState.DISCONNECTED
        session.tnc_connection = None

    def reset_for_next_connection(self):
        logging.debug("ConnectionManager resetting for next connection [CM]")
        if not self.tnc_connection or self.tnc_connection._closed:
            logging.debug("Creating new TNC connection [CM]")
            self.tnc_connection = create_tnc_connection(self.tnc_host, self.tnc_port)
            if self.tnc_connection:
                socketio_logger.info(f"[TNC] Ready for new connections on {self.tnc_host}:{self.tnc_port} [CM]")
                logging.info(f"Ready for new connections on {self.tnc_host}:{self.tnc_port} [CM]")
        else:
            logging.debug("TNC connection already exists, ready for new connections [CM]")

    def handle_disconnect_request(self, session):
        socketio_logger.info(f"[SESSION] Handling disconnect request for session: {session.id}")
        logging.info(f"Handling disconnect request for session: {session.id}")
        if session and session.state not in [ModemState.DISCONNECTING, ModemState.DISCONNECTED]:
            session.state = ModemState.DISCONNECTING
            self.core.send_ack(session)
            self.cleanup_session(session)
        else:
            logging.info(f"[SYSTEM] Session {session.id} already disconnecting or disconnected")
            logging.info(f"Session {session.id} already disconnecting or disconnected")

    def handle_incoming_connection(self):
        connection_attempt_time = None
        current_connect_session = None
        
        while self.core.running:
            logging.debug("Waiting for incoming connection")
            session = None  # Initialize session variable at the beginning
            
            # Check for stale connection attempts
            if connection_attempt_time and current_connect_session:
                if time.time() - connection_attempt_time > 10:  # 10 second timeout for connection establishment
                    logging.info(f"Connection attempt timed out after 10 seconds, cleaning up")
                    try:
                        self.cleanup_session(current_connect_session)
                    except Exception as e:
                        logging.error(f"Error during connection timeout cleanup: {e}")
                        # Force cleanup even if exception occurred
                        if hasattr(self.core, 'sessions') and current_connect_session.id in self.core.sessions:
                            self.core.sessions.pop(current_connect_session.id, None)
                    finally:
                        # Always clear these variables to prevent getting stuck
                        connection_attempt_time = None
                        current_connect_session = None
                        logging.info("Connection tracking cleared after timeout")
            
            try:
                source_callsign, message, msg_type = self.core.receive_message(None, timeout=1.0)
                if source_callsign and msg_type == MessageType.CONNECT:
                    socketio_logger.info(f"[CONTROL] Received CONNECT request from {source_callsign}")
                    logging.info(f"Received CONNECT request from {source_callsign}")
                    session = self.create_session(source_callsign)
                    if not session:
                        socketio_logger.error(f"[SYSTEM] Failed to create session for {source_callsign}")
                        logging.error(f"Failed to create session for {source_callsign}")
                        continue
                        
                    # Track this connection attempt
                    connection_attempt_time = time.time()
                    current_connect_session = session
                    
                    # Add deliberate delay before sending CONNECT_ACK to allow client radio to switch modes
                    time.sleep(config.CONNECTION_STABILIZATION_DELAY)  # 250ms delay
                    
                    if self.core.send_single_packet(session, 0, 0, "Connection Accepted".encode(), MessageType.CONNECT_ACK):
                        # Add another small delay after sending to ensure packet is fully transmitted
                        time.sleep(config.CONNECTION_STABILIZATION_DELAY)  # 250ms delay
                        
                        # Modified wait_for_ack with resend logic for first packet
                        start_time = time.time()
                        ack_received = False
                        resend_count = 0
                        max_resends = 2
                        ack_timeout = config.ACK_TIMEOUT
                        pending_request = None
                        
                        while time.time() - start_time < ack_timeout and not ack_received:
                            source_callsign2, message2, msg_type2 = self.core.receive_message(session, timeout=0.5)
                            if msg_type2 == MessageType.ACK:
                                logging.info(f"Received ACK from {source_callsign2}")
                                session.last_activity = time.time()
                                ack_received = True
                                break
                            elif msg_type2 == MessageType.DATA_REQUEST:
                                # Consider a DATA_REQUEST as an implicit ACK during connection
                                logging.info(f"Received DATA_REQUEST from {source_callsign2} - treating as implicit ACK")
                                session.last_activity = time.time()
                                ack_received = True
                                
                                # Store this DATA_REQUEST for processing after connection is established
                                pending_request = message2
                                break
                            elif msg_type2 == MessageType.DISCONNECT:
                                logging.info(f"Received DISCONNECT from {source_callsign2}")
                                self.handle_disconnect(session)
                                break
                            elif msg_type2 is not None:
                                logging.warning(f"Received unexpected message while waiting for ACK: {msg_type2}")
                            
                            # Resend CONNECT_ACK if no response after 1/3 of timeout
                            if time.time() - start_time > (ack_timeout / 3) * (resend_count + 1) and resend_count < max_resends:
                                logging.info(f"No ACK received yet, resending CONNECT_ACK (attempt {resend_count + 1})")
                                time.sleep(config.CONNECTION_STABILIZATION_DELAY)  # Add delay before resending
                                self.core.send_single_packet(session, 0, 0, "Connection Accepted".encode(), MessageType.CONNECT_ACK)
                                resend_count += 1
                                # Add delay after resend
                                time.sleep(config.CONNECTION_STABILIZATION_DELAY)
                        
                        if ack_received:
                            session.state = ModemState.CONNECTED
                            parsed_callsign = parse_callsign(source_callsign)
                            socketio_logger.info(f"[SESSION] CONNECTED to {parsed_callsign[0]}-{parsed_callsign[1]}")
                            logging.info(f"CONNECTED to {parsed_callsign[0]}-{parsed_callsign[1]}")
                            
                            # If we received a DATA_REQUEST during handshake, store it in the session
                            if pending_request:
                                session.pending_request = pending_request
                                logging.info(f"Stored pending DATA_REQUEST for processing: {pending_request}")
                            
                            # Clear connection tracking since we're fully connected now
                            connection_attempt_time = None
                            current_connect_session = None
                            
                            return session
                        else:
                            socketio_logger.error(f"[SYSTEM] Failed to receive ACK for CONNECT_ACK from {source_callsign}")
                            logging.error(f"Failed to receive ACK for CONNECT_ACK from {source_callsign}")
                            # Make sure to clean up the session here
                            try:
                                self.cleanup_session(session)
                            except Exception as cleanup_error:
                                logging.error(f"Error during failed connection cleanup: {cleanup_error}")
                                # Force cleanup even if exception occurred
                                if hasattr(self.core, 'sessions') and session.id in self.core.sessions:
                                    self.core.sessions.pop(session.id, None)
                    else:
                        socketio_logger.error(f"[SYSTEM] Failed to send CONNECT_ACK to {source_callsign}")
                        logging.error(f"Failed to send CONNECT_ACK to {source_callsign}")
                        # Make sure to clean up the session here
                        try:
                            self.cleanup_session(session)
                        except Exception as cleanup_error:
                            logging.error(f"Error during failed connection cleanup: {cleanup_error}")
                            # Force cleanup even if exception occurred
                            if hasattr(self.core, 'sessions') and session.id in self.core.sessions:
                                self.core.sessions.pop(session.id, None)
                    
                    # Note: we don't disconnect here - we'll let the timeout handle it
                elif source_callsign and msg_type == MessageType.DATA_REQUEST:
                    socketio_logger.info(f"[CONTROL] Received DATA_REQUEST from {source_callsign}")
                    logging.info(f"Received DATA_REQUEST from {source_callsign}")
                    
                    # Try to find an existing session for this callsign
                    session = None
                    for existing_session in self.core.sessions.values():
                        if existing_session.remote_callsign == source_callsign:
                            session = existing_session
                            break
                    
                    # If no session found, create a new one and mark as connected
                    if not session:
                        logging.info(f"Creating new session for previous callsign {source_callsign}")
                        session = self.create_session(source_callsign)
                        if session:
                            session.state = ModemState.CONNECTED
                            self.core.sessions[session.id] = session
                            socketio_logger.info(f"[SESSION] Recreated session for {source_callsign[0]}-{source_callsign[1]}")
                    
                    if session and session.state == ModemState.CONNECTED:
                        # Add delay before sending READY
                        time.sleep(config.CONNECTION_STABILIZATION_DELAY)
                        
                        if self.core.send_ready(session):
                            # Add delay after sending READY
                            time.sleep(config.CONNECTION_STABILIZATION_DELAY)
                            
                            if self.core.wait_for_ready(session):
                                socketio_logger.info("[SYSTEM] Ready to send data")
                                logging.info("Ready to send data")
                                return session
                            else:
                                socketio_logger.error("[SYSTEM] Failed to receive READY from client")
                                logging.error("Failed to receive READY from client")
                                # Clean up the session
                                try:
                                    self.cleanup_session(session)
                                except Exception as cleanup_error:
                                    logging.error(f"Error during failed READY cleanup: {cleanup_error}")
                        else:
                            socketio_logger.error("[SYSTEM] Failed to send READY to client")
                            logging.error("Failed to send READY to client")
                            # Clean up the session
                            try:
                                self.cleanup_session(session)
                            except Exception as cleanup_error:
                                logging.error(f"Error during failed READY cleanup: {cleanup_error}")
                    else:
                        socketio_logger.error("[SYSTEM] Received DATA_REQUEST for non-connected session")
                        logging.error("Received DATA_REQUEST for non-existent or non-connected session")
                elif source_callsign and msg_type is not None:
                    logging.info(f"Received message: Type={msg_type}, Content={message[:50]}...")

                # Only check connection timeout if we have a valid session
                if session and hasattr(session, 'last_activity') and time.time() - session.last_activity > config.CONNECTION_TIMEOUT:
                    logging.info(f"Connection timeout for {session.remote_callsign}")
                    try:
                        self.cleanup_session(session)
                    except Exception as e:
                        logging.error(f"Error during session timeout cleanup: {e}")
                        # Force cleanup even if exception occurred
                        if hasattr(self.core, 'sessions') and session.id in self.core.sessions:
                            self.core.sessions.pop(session.id, None)
                    
                # Only disconnect if we have a valid session
                if not self.core.running and session:
                    logging.info("Server is shutting down, ending session")
                    try:
                        self.cleanup_session(session)
                    except Exception as e:
                        logging.error(f"Error during shutdown cleanup: {e}")

                time.sleep(0.1)  # Small delay to prevent tight loop
            except Exception as e:
                socketio_logger.error(f"Error in handle_incoming_connection: {str(e)}")
                logging.error(f"Error in handle_incoming_connection: {str(e)}")
                
                # If there was an error during a connection attempt, clean it up
                if connection_attempt_time and current_connect_session:
                    logging.info("Cleaning up after error during connection attempt")
                    try:
                        self.cleanup_session(current_connect_session)
                    except Exception as cleanup_error:
                        logging.error(f"Error during error-triggered cleanup: {cleanup_error}")
                        # Force cleanup even if exception occurred
                        if hasattr(self.core, 'sessions') and current_connect_session.id in self.core.sessions:
                            self.core.sessions.pop(current_connect_session.id, None)
                    finally:
                        connection_attempt_time = None
                        current_connect_session = None
                        logging.info("Connection tracking cleared after error")
                
            time.sleep(0.2)  # Small delay to prevent tight loop
        logging.debug("Exited handle_incoming_connection method")
        return None