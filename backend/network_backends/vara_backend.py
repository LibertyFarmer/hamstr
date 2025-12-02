"""
VARA Backend - VARA HF modem backend for HAMSTR modular system.

This backend implements the NetworkBackend interface using proven VARA patterns
from vara_test.py while maintaining compatibility with existing HAMSTR functionality.
"""

import socket
import logging
import time
import threading
import json
from typing import Optional, Dict, Any, Tuple
from .base_backend import NetworkBackend, BackendType, BackendStatus

# Import logging
from socketio_logger import get_socketio_logger
socketio_logger = get_socketio_logger()

# Import existing HAMSTR utilities (don't modify these)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from ax25_kiss_utils import build_ax25_frame, kiss_wrap, kiss_unwrap, decode_ax25_callsign

# Force immediate log flushing for real-time output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
# Force stdout to be unbuffered
sys.stdout.reconfigure(line_buffering=True)

class VARASession:
    """
    VARA session management.
    
    Encapsulates the dual-socket VARA connection and session state.
    Compatible with legacy HAMSTR Session interface.
    """
    
    def __init__(self, command_socket, data_socket, remote_callsign: tuple):
        self.command_socket = command_socket
        self.data_socket = data_socket
        self.remote_callsign = remote_callsign
        self.connected = True
        self.last_activity = time.time()
        self._lock = threading.Lock()
        self._receive_buffers = {}  # session_key -> bytes buffer
        self._json_buffers = {}     # session_key -> bytes buffer

        # Legacy compatibility attributes that HAMSTR expects
        self.id = f"{remote_callsign[0]}-{remote_callsign[1]}"
        self.tnc_connection = data_socket  # Point to data socket for compatibility
        
        # Additional legacy compatibility
        from models import ModemState
        self.state = ModemState.CONNECTED
    
    def update_activity(self):
        """Update last activity timestamp"""
        with self._lock:
            self.last_activity = time.time()
    
    def is_active(self, timeout: int = 120) -> bool:
        """Check if session is still active based on recent activity"""
        with self._lock:
            return (time.time() - self.last_activity) < timeout


class VARABackend(NetworkBackend):
    """
    VARA HF modem backend implementation.
    
    Implements high-performance VARA protocol using proven patterns from vara_test.py
    while maintaining compatibility with HAMSTR's KISS data transfer system.
    """
    
    def __init__(self, config, is_server: bool):
        """
        Initialize VARA backend.
        
        Args:
            config: Configuration module with VARA settings
            is_server: True if server instance, False for client
        """
        super().__init__(config, is_server)
        
        # Get VARA configuration
        self._setup_vara_config(config)
        
        # Session management
        self._active_sessions: Dict[str, VARASession] = {}
        
        # VARA connection state
        self._vara_ready = False
        self._listening_command_socket = None  # Keep command socket open for server
        
        # Try to initialize VARA (non-fatal if VARA not running yet)
        self._initialize_vara()
        
        logging.info(f"[VARA_BACKEND] Initialized VARA backend for {'server' if is_server else 'client'}")
        logging.info(f"[VARA_BACKEND] Command port: {self.command_port}, Data port: {self.data_port}")
        if not self._vara_ready:
            logging.info(f"[VARA_BACKEND] VARA not ready during init - will retry during first connection")
        
    def _initialize_vara(self):
        """Initialize VARA with our callsign and basic settings"""
        try:
            # Parse our callsign
            local_call, local_ssid = self._parse_callsign(self.my_callsign)
            
            # Connect to VARA command port
            command_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            command_sock.connect((self.vara_host, self.command_port))
            
            # VARA setup sequence
            time.sleep(1.0)  # Give VARA time to be ready
            
            # 1. Set bandwidth first (this works)
            if not self._send_vara_command(command_sock, f"BW{self.bandwidth}"):
                logging.warning("[VARA_BACKEND] Failed to set VARA bandwidth")
                
            # 2. Set our callsign 
            callsign_cmd = f"MYCALL {local_call}-{local_ssid}"
            if not self._send_vara_command(command_sock, callsign_cmd):
                logging.warning(f"[VARA_BACKEND] Failed to set VARA callsign: {callsign_cmd}")
                command_sock.close()
                return
                    
            logging.info(f"[VARA_BACKEND] Set VARA callsign to {local_call}-{local_ssid}")
                
            # 3. Set chat mode
            if not self._send_vara_command(command_sock, f"CHAT {self.chat_mode}"):
                logging.warning("[VARA_BACKEND] Failed to set VARA chat mode")
            
            # 4. Server-specific: Start listening and KEEP socket open
            if self.is_server:
                if self._send_vara_command(command_sock, "LISTEN ON"):
                    logging.info(f"[VARA_BACKEND] Server VARA listening for connections")
                    # KEEP the command socket open for server listening
                    self._listening_command_socket = command_sock
                    self._vara_ready = True
                else:
                    logging.warning("[VARA_BACKEND] Failed to start VARA listening")
                    command_sock.close()
            else:
                # Client doesn't need persistent command socket
                logging.info(f"[VARA_BACKEND] Client VARA ready for connections")
                self._vara_ready = True
                command_sock.close()
            
        except Exception as e:
            logging.info(f"[VARA_BACKEND] VARA not ready during initialization: {e}")
            logging.info(f"[VARA_BACKEND] Will attempt VARA setup during first connection")
            # Not fatal - VARA might not be running yet
        
    def _setup_vara_config(self, config):
        """Setup VARA configuration from config module"""
        try:
            # Get VARA settings from main config
            self.vara_host = getattr(config, 'VARA_HOST', '127.0.0.1')
            self.bandwidth = getattr(config, 'VARA_BANDWIDTH', 2300)
            self.connection_timeout = getattr(config, 'VARA_CONNECTION_TIMEOUT', 30)
            self.chat_mode = getattr(config, 'VARA_CHAT_MODE', 'ON')
            
            # Set ports based on role - server always uses 8400/8401, client uses 8300/8301
            if self.is_server:
                self.command_port = 8400  # Server VARA command port
                self.data_port = 8401     # Server VARA data port
                # Use server callsign
                server_callsign = getattr(config, 'S_CALLSIGN', '(TEST, 2)')
                self.my_callsign = server_callsign
                logging.info(f"[VARA_BACKEND] Server using callsign: {server_callsign}")
            else:
                self.command_port = 8300  # Client VARA command port  
                self.data_port = 8301     # Client VARA data port
                # Use client callsign
                client_callsign = getattr(config, 'C_CALLSIGN', '(TEST, 1)')
                self.my_callsign = client_callsign
                logging.info(f"[VARA_BACKEND] Client using callsign: {client_callsign}")
            
            logging.info(f"[VARA_BACKEND] Config - Role: {'server' if self.is_server else 'client'}, "
                        f"Callsign: {self.my_callsign}, Ports: {self.command_port}/{self.data_port}")
            
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Config setup error: {e}")
            # Use hard-coded fallback values based on role
            self.vara_host = '127.0.0.1'
            self.bandwidth = 2300
            self.connection_timeout = 30
            self.chat_mode = 'ON'
            
            if self.is_server:
                self.command_port = 8400
                self.data_port = 8401
                self.my_callsign = '(TEST, 2)'
            else:
                self.command_port = 8300
                self.data_port = 8301
                self.my_callsign = '(TEST, 1)'
    
    def _send_vara_command(self, sock: socket.socket, command: str) -> Optional[str]:
        """
        Send command to VARA and get response (from vara_test.py pattern).
        
        Args:
            sock: Command socket
            command: VARA command to send
            
        Returns:
            Response string if successful, None if error
        """
        try:
            sock.sendall((command + '\r').encode('ascii'))
            sock.settimeout(5)
            response = sock.recv(1024).decode('ascii', errors='ignore').strip()
            logging.debug(f"[VARA_BACKEND] Command: {command} -> Response: {response}")
            return response
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Command '{command}' failed: {e}")
            return None
    
    def _parse_callsign(self, callsign_str: str) -> Tuple[str, int]:
        """Parse callsign string to (call, ssid) tuple"""
        try:
            # Clean up the string first - remove extra quotes
            clean_str = str(callsign_str).strip().strip("'\"")
            
            # Handle formats like "(KK7AHK, 7)" or "KK7AHK-7"
            if clean_str.startswith('(') and clean_str.endswith(')'):
                # Parse tuple format
                inner_str = clean_str.strip('()')
                parts = [p.strip().strip("'\"") for p in inner_str.split(',')]
                return (parts[0], int(parts[1]))
            elif '-' in clean_str:
                # Parse hyphen format
                parts = clean_str.split('-')
                return (parts[0], int(parts[1]))
            else:
                # No SSID specified
                return (clean_str, 0)
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Callsign parse error for '{callsign_str}': {e}")
            # Try to extract just the call letters as fallback
            try:
                import re
                match = re.search(r'([A-Z0-9]+)', str(callsign_str))
                if match:
                    return (match.group(1), 0)
            except:
                pass
            return ('UNKNOWN', 0)
    
    def connect(self, remote_callsign: tuple) -> Optional[VARASession]:
        """
        Establish VARA connection with remote station.
        
        Args:
            remote_callsign: Tuple of (callsign, ssid)
            
        Returns:
            VARASession if successful, None if failed
        """
        self._update_status(BackendStatus.CONNECTING)
        
        # Parse callsigns
        local_call, local_ssid = self._parse_callsign(self.my_callsign)
        remote_call, remote_ssid = remote_callsign
        
        # Session key for tracking
        session_key = f"{remote_call}-{remote_ssid}"
        
        command_sock = None
        data_sock = None
        
        try:
            if self.is_server:
                # SERVER: Reuse existing listening command socket
                if not self._listening_command_socket:
                    raise Exception("Server not initialized - VARA listening socket not available")
                
                command_sock = self._listening_command_socket
                logging.info(f"[VARA_BACKEND] Server waiting for incoming connection...")
                
                # Wait for client connection on existing listening socket (no timeout - wait forever)
                connected = False
                while not connected:
                    try:
                        command_sock.settimeout(2)
                        data = command_sock.recv(1024)
                        if data:
                            messages = data.decode('ascii', errors='ignore').strip()
                            for line in messages.split('\r'):
                                line = line.strip()
                                if line and line.startswith("CONNECTED"):
                                    connected = True
                                    logging.info(f"[VARA_BACKEND] Client connected!")
                                    break
                    except socket.timeout:
                        continue
                
                if not connected:
                    raise Exception("Timeout waiting for client connection")
                    
            else:
                # CLIENT: Create new command socket and connect
                logging.info(f"[VARA_BACKEND] Connecting to VARA command port {self.vara_host}:{self.command_port}")
                command_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                command_sock.connect((self.vara_host, self.command_port))
                
                # Setup VARA configuration
                time.sleep(1)  # Let connection stabilize
                
                if not self._send_vara_command(command_sock, f"MYCALL {local_call}-{local_ssid}"):
                    raise Exception("Failed to set MYCALL")
                    
                if not self._send_vara_command(command_sock, f"BW{self.bandwidth}"):
                    raise Exception("Failed to set bandwidth")
                    
                if not self._send_vara_command(command_sock, f"CHAT {self.chat_mode}"):
                    raise Exception("Failed to set chat mode")
                
                # Connect to server
                connect_cmd = f"CONNECT {local_call}-{local_ssid} {remote_call}-{remote_ssid}"
                if not self._send_vara_command(command_sock, connect_cmd):
                    raise Exception("Failed to send CONNECT command")
                
                # Wait for connection confirmation
                logging.info(f"[VARA_BACKEND] Waiting for connection to {remote_call}-{remote_ssid}")
                connected = False
                start_time = time.time()
                while time.time() - start_time < self.connection_timeout and not connected:
                    try:
                        command_sock.settimeout(2)
                        data = command_sock.recv(1024)
                        if data:
                            messages = data.decode('ascii', errors='ignore').strip()
                            for line in messages.split('\r'):
                                line = line.strip()
                                if line and line.startswith("CONNECTED"):
                                    connected = True
                                    logging.info(f"[VARA_BACKEND] Connected to {remote_call}-{remote_ssid}")
                                    break
                    except socket.timeout:
                        continue
                
                if not connected:
                    raise Exception(f"Failed to connect to {remote_call}-{remote_ssid}")
            
            # Both client and server: Connect to data port
            logging.info(f"[VARA_BACKEND] Connecting to data port {self.vara_host}:{self.data_port}")
            data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_sock.settimeout(10)
            data_sock.connect((self.vara_host, self.data_port))
            
            # Create session object
            # CRITICAL: Server passes None for command socket to avoid closing the listening socket
            # Client passes the actual command socket
            if self.is_server:
                session = VARASession(None, data_sock, ('ANY', 0))
                logging.info("[VARA_BACKEND] Server session created (listening socket preserved)")
            else:
                session = VARASession(command_sock, data_sock, remote_callsign)
                logging.info(f"[VARA_BACKEND] Client session created for {remote_call}-{remote_ssid}")
            
            self._active_sessions[session_key] = session
            
            self._update_status(BackendStatus.CONNECTED)
            logging.info(f"[VARA_BACKEND] VARA connection established with {remote_call}-{remote_ssid}")
            
            return session
            
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Connection failed: {e}")
            self._update_status(BackendStatus.ERROR)
            
            # Cleanup on failure
            if data_sock:
                try:
                    data_sock.close()
                except:
                    pass
            
            # Only close command socket if it's a client connection (not the server's listening socket)
            if command_sock and not self.is_server:
                try:
                    self._send_vara_command(command_sock, "DISCONNECT")
                    command_sock.close()
                except:
                    pass
            
            return None
    
    def send_data(self, session: VARASession, data: bytes) -> bool:
        """
        Send data via VARA using KISS protocol.
        
        Args:
            session: Active VARA session
            data: Raw bytes to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not session or not session.connected:
                logging.error("[VARA_BACKEND] No active session for sending data")
                socketio_logger.error("[CONTROL] No active session")
                return False
            
            # Parse local and remote callsigns for AX.25 frame
            local_call, local_ssid = self._parse_callsign(self.my_callsign)
            
            # Build AX.25 frame using existing HAMSTR utilities
            ax25_frame = build_ax25_frame(
                (local_call, local_ssid),
                session.remote_callsign,
                data
            )
            
            # Wrap in KISS protocol
            kiss_frame = kiss_wrap(ax25_frame)
            
            # Log transmission with socketio
            socketio_logger.info(f"[CONTROL] Sending via VARA ({len(data)} bytes)")
            logging.debug(f"[VARA_BACKEND] Sending {len(data)} bytes payload, {len(kiss_frame)} bytes KISS frame")
            
            # Send via VARA data port
            session.data_socket.sendall(kiss_frame)
            session.update_activity()
            
            logging.debug(f"[VARA_BACKEND] Sent {len(data)} bytes via VARA/KISS")
            return True
            
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Send failed: {e}")
            socketio_logger.error(f"[CONTROL] Send failed: {e}")
            session.connected = False
            return False
    
    def receive_data(self, session: VARASession, timeout: int = 30) -> Optional[bytes]:
        """
        Receive data from VARA using KISS protocol with continuous monitoring.
        Uses persistent buffers across calls to handle split messages.
        
        Args:
            session: Active VARA session
            timeout: Total timeout in seconds
            
        Returns:
            Received bytes if successful, None if timeout/error
        """
        try:
            if not session or not session.connected:
                logging.error("[VARA_BACKEND] No active session for receiving data")
                return None
            
            # Get session key for persistent buffers
            session_key = f"{session.remote_callsign[0]}-{session.remote_callsign[1]}"
            
            # Use persistent buffers for this session (survives across calls)
            if not hasattr(self, '_receive_buffers'):
                self._receive_buffers = {}
                self._json_buffers = {}
            
            if session_key not in self._receive_buffers:
                self._receive_buffers[session_key] = b''
                self._json_buffers[session_key] = b''
            
            buffer = self._receive_buffers[session_key]
            json_buffer = self._json_buffers[session_key]
            
            logging.debug(f"[VARA_BACKEND] Starting receive with {timeout}s timeout, existing buffer: {len(buffer)} bytes, json: {len(json_buffer)} bytes")
            
            start_time = time.time()
            
            # Continuously monitor data port
            while time.time() - start_time < timeout:
                try:
                    # Check for incoming data with 1-second timeout
                    session.data_socket.settimeout(1)
                    chunk = session.data_socket.recv(1024)
                    
                    if not chunk:
                        # Connection closed
                        session.connected = False
                        logging.warning("[VARA_BACKEND] Connection closed")
                        # Clear buffers on disconnect
                        if session_key in self._receive_buffers:
                            del self._receive_buffers[session_key]
                            del self._json_buffers[session_key]
                        return None
                    
                    buffer += chunk
                    socketio_logger.info(f"[PACKET] Receiving data via VARA...")
                    #logging.info(f"[VARA_BACKEND] *** RAW CHUNK ({len(chunk)} bytes): {chunk[:100]}")
                    #logging.info(f"[VARA_BACKEND] *** BUFFER SIZE: {len(buffer)} bytes")
                    
                    # Process complete KISS frames
                    while b'\xc0' in buffer:
                        fend_start = buffer.find(b'\xc0')
                        fend_end = buffer.find(b'\xc0', fend_start + 1)
                        
                        if fend_end == -1:
                            # Incomplete frame, keep buffering
                            logging.debug("[VARA_BACKEND] Incomplete KISS frame, waiting for more data")
                            break
                        
                        # Extract complete KISS frame
                        kiss_frame = buffer[fend_start:fend_end + 1]
                        buffer = buffer[fend_end + 1:]
                        
                       # logging.info(f"[VARA_BACKEND] *** KISS FRAME ({len(kiss_frame)} bytes): {kiss_frame[:50]}")
                        
                        # Unwrap KISS to get AX.25 frame
                        ax25_frame = kiss_unwrap(kiss_frame)
                        if ax25_frame and len(ax25_frame) > 17:
                          #  logging.info(f"[VARA_BACKEND] *** AX25 FRAME ({len(ax25_frame)} bytes): {ax25_frame[:50]}")
                            
                            # Skip AX.25 header (16 bytes) + control byte (1 byte) = 17 bytes
                            payload = ax25_frame[17:]
                            json_buffer += payload
                            
                           # logging.info(f"[VARA_BACKEND] *** PAYLOAD ({len(payload)} bytes): {payload[:100]}")
                           # logging.info(f"[VARA_BACKEND] *** JSON BUFFER ({len(json_buffer)} bytes): {json_buffer[:100]}")
                            
                            # Try to decode as complete JSON
                            try:
                                json_str = json_buffer.decode('utf-8')
                                # Validate it's complete JSON
                                import json as json_module
                                json_module.loads(json_str)
                                
                                session.update_activity()
                                socketio_logger.info(f"[PACKET] Received complete message ({len(json_buffer)} bytes)")
                                logging.info(f"[VARA_BACKEND] *** COMPLETE JSON MESSAGE: {json_str}")
                                
                                # Clear buffers on success
                                self._receive_buffers[session_key] = b''
                                self._json_buffers[session_key] = b''
                                
                                return json_buffer
                                
                            except UnicodeDecodeError as e:
                                logging.debug(f"[VARA_BACKEND] Unicode decode error (buffering): {e}")
                                continue
                            except json_module.JSONDecodeError as e:
                                logging.debug(f"[VARA_BACKEND] Incomplete JSON (buffering): {e}")
                                continue
                        else:
                            logging.debug(f"[VARA_BACKEND] AX25 frame too short or invalid: {len(ax25_frame) if ax25_frame else 0} bytes")
                        
                except socket.timeout:
                    # 1-second timeout - check if session still active
                    elapsed = time.time() - start_time
                    logging.debug(f"[VARA_BACKEND] Socket timeout, elapsed: {elapsed:.1f}s/{timeout}s")
                    
                    if not session.is_active():
                        logging.warning("[VARA_BACKEND] Session inactive")
                        session.connected = False
                        # Clear buffers on disconnect
                        if session_key in self._receive_buffers:
                            del self._receive_buffers[session_key]
                            del self._json_buffers[session_key]
                        return None
                        
                    # Save buffers and continue
                    self._receive_buffers[session_key] = buffer
                    self._json_buffers[session_key] = json_buffer
                    continue
            
            # Timeout - save buffers for next call
            self._receive_buffers[session_key] = buffer
            self._json_buffers[session_key] = json_buffer
            
            logging.debug(f"[VARA_BACKEND] Receive timeout after {timeout}s, buffer: {len(buffer)} bytes, json_buffer: {len(json_buffer)} bytes")
            return None
            
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Receive error: {e}")
            import traceback
            logging.error(traceback.format_exc())
            session.connected = False
            return None
        
    def _wait_for_vara_tx_complete(self, timeout: int = 60) -> bool:
        """
        Wait for VARA to finish transmitting (BUSY FALSE).
        
        Args:
            timeout: Max seconds to wait
            
        Returns:
            True if transmission complete, False if timeout
        """
        if not self.is_server:
            # Client doesn't have persistent command socket
            return True
        
        try:
            if not self._listening_command_socket:
                return True
            
            logging.info("[VARA_BACKEND] Waiting for VARA transmission to complete...")
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    self._listening_command_socket.settimeout(0.5)
                    data = self._listening_command_socket.recv(1024)
                    if data:
                        messages = data.decode('ascii', errors='ignore').strip()
                        for line in messages.split('\r'):
                            if 'BUSY FALSE' in line or 'PTT FALSE' in line:
                                logging.info("[VARA_BACKEND] VARA transmission complete")
                                return True
                except socket.timeout:
                    continue
            
            logging.warning("[VARA_BACKEND] Timeout waiting for VARA TX complete")
            return False
            
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Error waiting for TX complete: {e}")
            return False
    
    def _check_disconnection(self, session: VARASession) -> bool:
        """
        Check command socket for disconnection events.
        Server uses listening socket, client uses session socket.
        """
        try:
            # Server: check the listening socket, Client: check session socket
            if self.is_server:
                if not self._listening_command_socket:
                    return True
                check_socket = self._listening_command_socket
            else:
                if not session.command_socket:
                    return True
                check_socket = session.command_socket
            
            check_socket.settimeout(0.1)
            cmd_data = check_socket.recv(1024)
            if cmd_data:
                status = cmd_data.decode('ascii', errors='ignore').strip()
                for line in status.split('\r'):
                    line = line.strip()
                    if line and line.startswith("DISCONNECTED"):
                        logging.info("[VARA_BACKEND] VARA disconnection detected")
                        return True
            return False
        except socket.timeout:
            return False
        except Exception as e:
            logging.debug(f"[VARA_BACKEND] Disconnect check error: {e}")
            return False  # Don't assume disconnected on error
        
    def _restart_vara_listening(self):
        """Restart VARA listening after session ends (server only)."""
        if not self.is_server:
            return
        
        try:
            # Close old listening socket if it exists
            if self._listening_command_socket:
                try:
                    self._listening_command_socket.close()
                except:
                    pass
            
            # Reconnect to VARA command port
            logging.info("[VARA_BACKEND] Reconnecting to VARA command port...")
            command_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            command_sock.connect((self.vara_host, self.command_port))
            
            time.sleep(1)
            
            # Wait for VARA to fully disconnect the previous session
            logging.info("[VARA_BACKEND] Waiting for VARA to complete disconnect...")
            disconnected = False
            start_wait = time.time()
            while time.time() - start_wait < 5 and not disconnected:
                try:
                    command_sock.settimeout(0.5)
                    data = command_sock.recv(1024)
                    if data:
                        messages = data.decode('ascii', errors='ignore').strip()
                        for line in messages.split('\r'):
                            if 'DISCONNECTED' in line or 'BUSY FALSE' in line:
                                disconnected = True
                                logging.info("[VARA_BACKEND] VARA disconnect confirmed")
                                break
                except socket.timeout:
                    continue
            
            # Give VARA a moment to reset
            time.sleep(0.5)
            
            # Reconfigure VARA
            local_call, local_ssid = self._parse_callsign(self.my_callsign)
            self._send_vara_command(command_sock, f"MYCALL {local_call}-{local_ssid}")
            self._send_vara_command(command_sock, f"BW{self.bandwidth}")
            self._send_vara_command(command_sock, f"CHAT {self.chat_mode}")
            self._send_vara_command(command_sock, "LISTEN ON")
            
            # Update listening socket
            self._listening_command_socket = command_sock
            self._vara_ready = True
            
            logging.info("[VARA_BACKEND] VARA listening restarted successfully")
            return True
            
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Failed to restart VARA listening: {e}")
            self._vara_ready = False
            return False
    
    def disconnect(self, session: VARASession) -> bool:
        """Disconnect session and clean up sockets."""
        logging.info(f"[VARA_BACKEND] disconnect() called for {session.remote_callsign}")
        try:
            session_key = f"{session.remote_callsign[0]}-{session.remote_callsign[1]}"
            
            # Close data socket
            if session.data_socket:
                try:
                    session.data_socket.close()
                    logging.info("[VARA_BACKEND] Data socket closed")
                except:
                    pass
                session.data_socket = None
            
            # CRITICAL: For server, DON'T close command socket - it's the listening socket!
            # For client, close the session's command socket
            if not self.is_server and session.command_socket:
                try:
                    session.command_socket.close()
                    logging.info("[VARA_BACKEND] Client command socket closed")
                except:
                    pass
                session.command_socket = None
            else:
                # Server: Just null out the session reference
                session.command_socket = None
                logging.info("[VARA_BACKEND] Server session ended, listening socket will be restarted")
            
            # Clear buffers
            if hasattr(self, '_receive_buffers') and session_key in self._receive_buffers:
                del self._receive_buffers[session_key]
            if hasattr(self, '_json_buffers') and session_key in self._json_buffers:
                del self._json_buffers[session_key]
            
            # Remove from active sessions
            if session_key in self._active_sessions:
                del self._active_sessions[session_key]
            
            session.connected = False
            self._update_status(BackendStatus.DISCONNECTED)
            
            # Server: Restart VARA listening for next connection
            if self.is_server:
                self._restart_vara_listening()
            
            logging.info(f"[VARA_BACKEND] Disconnected from {session.remote_callsign}")
            return True
            
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Disconnect error: {e}")
            return False
    
    def is_connected(self, session: VARASession) -> bool:
        """
        Check if VARA session is still connected.
        
        Args:
            session: Session to check
            
        Returns:
            True if connected, False otherwise
        """
        if not session:
            return False
            
        # Check session state and activity
        if not session.connected or not session.is_active():
            return False
        
        # Quick check for disconnection events
        if self._check_disconnection(session):
            session.connected = False
            return False
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get VARA backend status information.
        
        Returns:
            Dictionary with status details
        """
        try:
            status = {
                "backend_type": "vara",
                "status": self.status.value,
                "is_server": self.is_server,
                "command_port": self.command_port,
                "data_port": self.data_port,
                "vara_host": self.vara_host,
                "bandwidth": self.bandwidth,
                "chat_mode": self.chat_mode,
                "my_callsign": self.my_callsign,
                "active_sessions": len(self._active_sessions),
                "vara_ready": self._vara_ready
            }
            
            # Add session details
            if self._active_sessions:
                sessions = []
                for key, session in self._active_sessions.items():
                    sessions.append({
                        "remote_callsign": f"{session.remote_callsign[0]}-{session.remote_callsign[1]}",
                        "connected": session.connected,
                        "last_activity": session.last_activity,
                        "active": session.is_active()
                    })
                status["sessions"] = sessions
            
            return status
            
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Status error: {e}")
            return {
                "backend_type": "vara",
                "status": "error",
                "error": str(e)
            }
    
    def get_backend_type(self) -> BackendType:
        """Return the backend type"""
        return BackendType.VARA


# Register this backend with the factory
def register_vara_backend():
    """Register the VARA backend with the factory."""
    from .backend_factory import BackendFactory
    BackendFactory.register_backend(BackendType.VARA, VARABackend)
    logging.info("[VARA_BACKEND] Registered VARA backend")

# Auto-register when module is imported
register_vara_backend()