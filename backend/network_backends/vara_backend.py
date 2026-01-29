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
import re
from typing import Optional, Dict, Any, Tuple
from .base_backend import NetworkBackend, BackendType, BackendStatus
from ptt_controller import PTTController

# Import logging
from socketio_logger import get_socketio_logger
socketio_logger = get_socketio_logger()

# Import existing HAMSTR utilities
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from ax25_kiss_utils import build_ax25_frame, kiss_wrap, kiss_unwrap, decode_ax25_callsign

# Force immediate log flushing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
sys.stdout.reconfigure(line_buffering=True)

class VARASession:
    def __init__(self, command_socket, data_socket, remote_callsign: tuple):
        self.command_socket = command_socket
        self.data_socket = data_socket
        self.remote_callsign = remote_callsign
        self.connected = True
        self.last_activity = time.time()
        self._lock = threading.Lock()
        self._receive_buffers = {}
        self._json_buffers = {}
        self.id = f"{remote_callsign[0]}-{remote_callsign[1]}"
        self.tnc_connection = data_socket
        from models import ModemState
        self.state = ModemState.CONNECTED
    
    def update_activity(self):
        with self._lock:
            self.last_activity = time.time()
    
    def is_active(self, timeout: int = 120) -> bool:
        with self._lock:
            return (time.time() - self.last_activity) < timeout

class VARABackend(NetworkBackend):
    def __init__(self, config, is_server: bool):
        logging.info(f"[VARA_BACKEND] __init__ called - is_server={is_server}")
        super().__init__(config, is_server)
        self._setup_vara_config(config)
        self._active_sessions: Dict[str, VARASession] = {}
        self._vara_ready = False
        self._listening_command_socket = None
        self._ptt_monitor_thread = None
        self._vara_messages = []
        self._message_lock = threading.Lock()
        self._last_buffer_level = 0
        self._last_buffer_change_time = time.time()
        self._is_transmitting = False

        self.ptt = None
        if self.is_server:
            use_ptt = getattr(config, 'SERVER_VARA_USE_PTT', True)
            test_mode = getattr(config, 'VARA_TEST_MODE', False)
            ptt_port = getattr(config, 'SERVER_VARA_PTT_SERIAL_PORT', 'COM11')
            ptt_baud = getattr(config, 'SERVER_VARA_PTT_SERIAL_BAUD', 38400)
            ptt_method = getattr(config, 'SERVER_VARA_PTT_METHOD', 'BOTH')
            pre_delay = getattr(config, 'SERVER_VARA_PRE_PTT_DELAY', 0.1)
            post_delay = getattr(config, 'SERVER_VARA_POST_PTT_DELAY', 0.1)
        else:
            use_ptt = getattr(config, 'CLIENT_VARA_USE_PTT', True)
            test_mode = getattr(config, 'VARA_TEST_MODE', False)
            ptt_port = getattr(config, 'CLIENT_VARA_PTT_SERIAL_PORT', 'COM10')
            ptt_baud = getattr(config, 'CLIENT_VARA_PTT_SERIAL_BAUD', 38400)
            ptt_method = getattr(config, 'CLIENT_VARA_PTT_METHOD', 'BOTH')
            pre_delay = getattr(config, 'CLIENT_VARA_PRE_PTT_DELAY', 0.1)
            post_delay = getattr(config, 'CLIENT_VARA_POST_PTT_DELAY', 0.1)

        if test_mode:
            logging.info("[VARA_BACKEND] *** TEST MODE ENABLED *** - Bypassing physical PTT")
            self.ptt = None
        elif use_ptt:
            try:
                self.ptt = PTTController(port=ptt_port, baud=ptt_baud, method=ptt_method, pre_delay=pre_delay, post_delay=post_delay)
                if self.ptt.connect():
                    logging.info(f"[VARA_BACKEND] PTT enabled on {ptt_port}")
                else:
                    logging.warning("[VARA_BACKEND] PTT enabled but connection failed")
                    self.ptt = None
            except Exception as e:
                logging.error(f"[VARA_BACKEND] PTT initialization failed: {e}")
                self.ptt = None
        else:
            logging.info("[VARA_BACKEND] PTT disabled - VARA FM or VOX mode")
        
        try:
            self._initialize_vara()
        except Exception as e:
            logging.warning(f"[VARA_BACKEND] Initial VARA setup failed (will retry): {e}")
        
    def _initialize_vara(self):
        """
        Initialize VARA connection.
        Robust version: Retries configuration if modem is busy (Polite Wait).
        """
        try:
            local_call, local_ssid = self._parse_callsign(self.my_callsign)
            
            if self._listening_command_socket:
                try: self._listening_command_socket.close()
                except: pass
                self._listening_command_socket = None

            command_sock = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    command_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    command_sock.connect((self.vara_host, self.command_port))
                    break
                except Exception as e:
                    logging.warning(f"[VARA_BACKEND] Init attempt {attempt+1} failed: {e}")
                    time.sleep(1.0)
            
            if not command_sock:
                raise Exception("Could not connect to VARA Command Port after retries")

            # NO ABORT. Just connect and wait if needed.
            command_sock.settimeout(5)
            time.sleep(0.5)
            
            # --- CONFIGURATION RETRY LOOP ---
            # If VARA is cleaning up previous session, BW command will fail. 
            # We retry politely until it accepts.
            config_success = False
            for i in range(5):
                if self._send_vara_command(command_sock, f"BW{self.bandwidth}"):
                    config_success = True
                    break
                else:
                    logging.warning(f"[VARA_BACKEND] VARA busy, waiting for idle state (attempt {i+1})...")
                    time.sleep(2.0) # Wait 2s before retrying
            
            if not config_success:
                logging.warning("[VARA_BACKEND] Failed to set Bandwidth after retries, proceeding anyway...")

            callsign_cmd = f"MYCALL {local_call}-{local_ssid}"
            if not self._send_vara_command(command_sock, callsign_cmd):
                command_sock.close()
                return
            
            if not self._send_vara_command(command_sock, f"CHAT {self.chat_mode}"):
                logging.warning("[VARA_BACKEND] Failed to set VARA chat mode")
            
            if self.is_server:
                if self._send_vara_command(command_sock, "LISTEN ON"):
                    logging.info(f"[VARA_BACKEND] Server VARA listening for connections")
                    self._listening_command_socket = command_sock
                    self._vara_ready = True
                    
                    if self._ptt_monitor_thread and self._ptt_monitor_thread.is_alive():
                        pass
                    
                    self._ptt_monitor_thread = threading.Thread(
                        target=self._monitor_vara_ptt,
                        daemon=True,
                        name="VARA-PTT-Monitor"
                    )
                    self._ptt_monitor_thread.start()
                    logging.info("[VARA_BACKEND] Monitor thread started")
                else:
                    command_sock.close()
            else:
                self._vara_ready = True
                command_sock.close()
            
        except Exception as e:
            logging.error(f"[VARA_BACKEND] VARA initialization error: {e}")
            self._vara_ready = False
            raise e

    def _monitor_vara_ptt(self):
        logging.info("[VARA_PTT] Monitor thread starting")
        buffer_pattern = re.compile(r'BUFFER (\d+)')
        
        while self._vara_ready and self._listening_command_socket:
            try:
                self._listening_command_socket.settimeout(1.0)
                data = self._listening_command_socket.recv(1024)
                
                if data:
                    raw_msg = data.decode('ascii', errors='ignore').strip()
                    for line in raw_msg.split('\r'):
                        line = line.strip()
                        if not line: continue
                        
                        with self._message_lock:
                            self._vara_messages.append(line)
                        
                        buffer_match = buffer_pattern.search(line)
                        if buffer_match:
                            current_buffer = int(buffer_match.group(1))
                            if current_buffer != self._last_buffer_level:
                                self._last_buffer_level = current_buffer
                                self._last_buffer_change_time = time.time()

                        if line == 'PTT ON':
                            self._is_transmitting = True
                            logging.info("[VARA_PTT] *** PTT ON ***")
                            socketio_logger.info("[CONTROL] ⚡ PTT ON")
                            if self.ptt and not self.ptt.is_keyed: self.ptt.key()
                        
                        elif line == 'PTT OFF':
                            self._is_transmitting = False
                            self._last_buffer_level = 0
                            self._last_buffer_change_time = time.time()
                            logging.info("[VARA_PTT] *** PTT OFF ***")
                            socketio_logger.info("[CONTROL] ⚡ PTT OFF")
                            if self.ptt and self.ptt.is_keyed: self.ptt.unkey()
                else:
                    logging.warning("[VARA_PTT] Socket returned empty data (Remote Close)")
                    break
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                logging.error(f"[VARA_PTT] Unexpected monitor error: {e}")
                break
        
        self._vara_ready = False
        logging.info("[VARA_PTT] Monitor stopped")

    def _wait_for_vara_message(self, search_string: str, timeout: float = 30) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            with self._message_lock:
                for msg in self._vara_messages:
                    if search_string in msg:
                        self._vara_messages.clear()
                        return True
            time.sleep(0.1)
        return False
        
    def _setup_vara_config(self, config):
        try:
            self.vara_host = getattr(config, 'VARA_HOST', '127.0.0.1')
            self.bandwidth = getattr(config, 'VARA_BANDWIDTH', 2300)
            self.connection_timeout = getattr(config, 'VARA_CONNECTION_TIMEOUT', 30)
            self.chat_mode = getattr(config, 'VARA_CHAT_MODE', 'ON')
            
            if self.is_server:
                self.command_port = 8400
                self.data_port = 8401
                self.my_callsign = getattr(config, 'S_CALLSIGN', '(TEST, 2)')
            else:
                self.command_port = 8300
                self.data_port = 8301
                self.my_callsign = getattr(config, 'C_CALLSIGN', '(TEST, 1)')
            
            logging.info(f"[VARA_BACKEND] Config - Role: {'server' if self.is_server else 'client'}, Callsign: {self.my_callsign}")
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Config setup error: {e}")
            self.vara_host = '127.0.0.1'
            self.command_port = 8400 if self.is_server else 8300
            self.data_port = 8401 if self.is_server else 8301
            self.my_callsign = '(TEST, 2)' if self.is_server else '(TEST, 1)'

    def _send_vara_command(self, sock: socket.socket, command: str) -> Optional[str]:
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
        try:
            clean_str = str(callsign_str).strip().strip("'\"")
            if clean_str.startswith('(') and clean_str.endswith(')'):
                inner_str = clean_str.strip('()')
                parts = [p.strip().strip("'\"") for p in inner_str.split(',')]
                return (parts[0], int(parts[1]))
            elif '-' in clean_str:
                parts = clean_str.split('-')
                return (parts[0], int(parts[1]))
            else:
                return (clean_str, 0)
        except:
            return ('UNKNOWN', 0)
    
    def connect(self, remote_callsign: tuple) -> Optional[object]:
        if self.is_server:
            # Self-Healing: Check if monitor died
            monitor_dead = (self._ptt_monitor_thread is None) or (not self._ptt_monitor_thread.is_alive())
            if monitor_dead or not self._vara_ready or not self._listening_command_socket:
                logging.warning("[VARA_BACKEND] Server backend in bad state. Re-initializing...")
                try:
                    self._initialize_vara()
                except Exception as e:
                    logging.error(f"[VARA_BACKEND] Failed to heal connection: {e}")
                    return None

        self._update_status(BackendStatus.CONNECTING)
        local_call, local_ssid = self._parse_callsign(self.my_callsign)
        
        if self.is_server:
            remote_call, remote_ssid = "ANY", 0
        else:
            remote_call, remote_ssid = remote_callsign
        
        command_sock = None
        data_sock = None
        
        try:
            if self.is_server:
                if not self._listening_command_socket: raise Exception("Server not initialized")
                logging.info(f"[VARA_BACKEND] Server waiting for incoming connection...")
                
                connected = False
                incoming_callsign_str = None
                
                while not connected:
                    if not self._vara_ready:
                        logging.error("[VARA_BACKEND] Monitor died while waiting. Aborting.")
                        return None
                    with self._message_lock:
                        for msg in list(self._vara_messages):
                            if msg.startswith("CONNECTED"):
                                connected = True
                                logging.info(f"[VARA_BACKEND] Connection detected: {msg}")
                                parts = msg.split()
                                if len(parts) >= 3: incoming_callsign_str = parts[2]
                                elif len(parts) >= 2: incoming_callsign_str = parts[1]
                                self._vara_messages.clear()
                                break
                    if not connected: time.sleep(0.1)

                if incoming_callsign_str:
                    remote_call, remote_ssid = self._parse_callsign(incoming_callsign_str)
            else:
                # Client Connect
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        command_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        command_sock.settimeout(5)
                        command_sock.connect((self.vara_host, self.command_port))
                        break
                    except:
                        if command_sock: command_sock.close()
                        time.sleep(2)
                
                if not command_sock: raise Exception("Failed to connect to VARA HF")
                
                time.sleep(0.5)
                self._send_vara_command(command_sock, f"MYCALL {local_call}-{local_ssid}")
                self._send_vara_command(command_sock, f"BW{self.bandwidth}")
                self._send_vara_command(command_sock, f"CHAT {self.chat_mode}")
                
                connect_cmd = f"CONNECT {local_call}-{local_ssid} {remote_call}-{remote_ssid}"
                if not self._send_vara_command(command_sock, connect_cmd): raise Exception("Failed to send CONNECT")
                
                self._listening_command_socket = command_sock
                self._vara_ready = True
                with self._message_lock: self._vara_messages.clear()
                
                if not self._ptt_monitor_thread or not self._ptt_monitor_thread.is_alive():
                    self._ptt_monitor_thread = threading.Thread(target=self._monitor_vara_ptt, daemon=True)
                    self._ptt_monitor_thread.start()

                if not self._wait_for_vara_message("CONNECTED", timeout=self.connection_timeout):
                    raise Exception(f"Failed to connect to {remote_call}-{remote_ssid}")

            logging.info(f"[VARA_BACKEND] Connecting to data port...")
            data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_sock.settimeout(10)
            data_sock.connect((self.vara_host, self.data_port))
            
            session_key = f"{remote_call}-{remote_ssid}"
            if self.is_server:
                session = VARASession(None, data_sock, (remote_call, remote_ssid))
            else:
                session = VARASession(command_sock, data_sock, remote_callsign)
            
            self._active_sessions[session_key] = session
            self._update_status(BackendStatus.CONNECTED)
            return session
            
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Connection failed: {e}")
            self._update_status(BackendStatus.ERROR)
            if not self.is_server and command_sock: command_sock.close()
            if data_sock: data_sock.close()
            raise

    def send_data(self, session: VARASession, data: bytes) -> bool:
        try:
            if not session or not session.connected: return False
            local_call, local_ssid = self._parse_callsign(self.my_callsign)
            ax25_frame = build_ax25_frame((local_call, local_ssid), session.remote_callsign, data)
            kiss_frame = kiss_wrap(ax25_frame)
            
            socketio_logger.info(f"[CONTROL] Sending via VARA ({len(data)} bytes)")
            session.data_socket.sendall(kiss_frame)
            session.update_activity()
            self._last_buffer_change_time = time.time()
            return True
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Send failed: {e}")
            session.connected = False
            return False

    def receive_data(self, session: VARASession, timeout: int = 30) -> Optional[bytes]:
        try:
            if not session or not session.connected: return None
            session_key = f"{session.remote_callsign[0]}-{session.remote_callsign[1]}"
            
            if not hasattr(self, '_receive_buffers'): self._receive_buffers = {}
            if not hasattr(self, '_json_buffers'): self._json_buffers = {}
            if session_key not in self._receive_buffers:
                self._receive_buffers[session_key] = b''
                self._json_buffers[session_key] = b''
            
            buffer = self._receive_buffers[session_key]
            json_buffer = self._json_buffers[session_key]
            
            last_activity_time = time.time()
            logging.debug(f"[VARA_BACKEND] Starting receive (Idle Timeout: {timeout}s)")
            
            while time.time() - last_activity_time < timeout:
                try:
                    session.data_socket.settimeout(1.0)
                    chunk = session.data_socket.recv(1024)
                    if not chunk:
                        session.connected = False
                        del self._receive_buffers[session_key]
                        del self._json_buffers[session_key]
                        return None
                    
                    last_activity_time = time.time()
                    buffer += chunk
                    socketio_logger.info(f"[PACKET] Receiving data via VARA...")
                    
                    while b'\xc0' in buffer:
                        fend_start = buffer.find(b'\xc0')
                        fend_end = buffer.find(b'\xc0', fend_start + 1)
                        if fend_end == -1: break
                        
                        kiss_frame = buffer[fend_start:fend_end + 1]
                        buffer = buffer[fend_end + 1:]
                        ax25_frame = kiss_unwrap(kiss_frame)
                        
                        if ax25_frame and len(ax25_frame) > 17:
                            payload = ax25_frame[17:]
                            json_buffer += payload
                            try:
                                json_str = json_buffer.decode('utf-8')
                                import json as json_module
                                json_module.loads(json_str)
                                session.update_activity()
                                socketio_logger.info(f"[PACKET] Received complete message ({len(json_buffer)} bytes)")
                                self._receive_buffers[session_key] = b''
                                self._json_buffers[session_key] = b''
                                return json_buffer
                            except: continue
                except socket.timeout:
                    if not session.is_active():
                        session.connected = False
                        return None
                    continue
            
            self._receive_buffers[session_key] = buffer
            self._json_buffers[session_key] = json_buffer
            return None
        except Exception as e:
            logging.error(f"[VARA_BACKEND] Receive error: {e}")
            session.connected = False
            return None
        
    def _wait_for_vara_tx_complete(self, timeout: int = 60) -> bool:
        if not self.is_server: return True
        if not self._listening_command_socket: return True
        
        logging.info("[VARA_BACKEND] Waiting for VARA transmission to complete (Smart Wait)...")
        stall_timeout = 60
        start_wait = time.time()
        
        while True:
            if self._check_disconnection(None): return False
            if not self._is_transmitting:
                if self._last_buffer_level == 0:
                    logging.info("[VARA_BACKEND] VARA transmission complete (PTT OFF + Buffer 0)")
                    return True
            
            time_since_change = time.time() - self._last_buffer_change_time
            if time_since_change > stall_timeout:
                logging.warning(f"[VARA_BACKEND] VARA TX Stalled! No buffer movement for {stall_timeout}s")
                return False
            if time.time() - start_wait > 300:
                logging.warning("[VARA_BACKEND] VARA TX timed out (Safety Limit)")
                return False
            time.sleep(0.1)

    def _check_disconnection(self, session) -> bool:
        with self._message_lock:
            for msg in self._vara_messages:
                if "DISCONNECTED" in msg: return True
        return False
        
    def _restart_vara_listening(self):
        if not self.is_server: return
        try:
            if self._listening_command_socket:
                # Give VARA a moment to breathe after disconnect
                time.sleep(1.5)
                self._listening_command_socket.sendall(b"LISTEN ON\r")
                return True
        except:
            self._vara_ready = False
            return False
    
    def disconnect(self, session: VARASession) -> bool:
        try:
            session_key = f"{session.remote_callsign[0]}-{session.remote_callsign[1]}"
            if self.ptt: 
                try: self.ptt.unkey()
                except: pass
            
            if session.data_socket:
                try: session.data_socket.close()
                except: pass
            
            if not self.is_server and session.command_socket:
                try: session.command_socket.close()
                except: pass
                self._vara_ready = False
                if self._ptt_monitor_thread: 
                    self._ptt_monitor_thread.join(timeout=2)
                self._ptt_monitor_thread = None
                self._listening_command_socket = None
            
            if session_key in self._active_sessions:
                del self._active_sessions[session_key]
            
            session.connected = False
            self._update_status(BackendStatus.DISCONNECTED)
            
            if self.is_server:
                # Polite Disconnect: Tell VARA to disconnect, then wait before restarting listener
                if self._listening_command_socket:
                    try: 
                        logging.info("[VARA_BACKEND] Sending DISCONNECT to VARA modem...")
                        self._listening_command_socket.sendall(b"DISCONNECT\r")
                    except Exception as e:
                        logging.warning(f"[VARA_BACKEND] Failed to send DISCONNECT command: {e}")
                
                self._restart_vara_listening()
            return True
        except:
            return False

    def cleanup(self):
        try:
            for key in list(self._active_sessions.keys()):
                self.disconnect(self._active_sessions[key])
            
            self._vara_ready = False
            if self.is_server and self._listening_command_socket:
                try:
                    self._listening_command_socket.sendall(b"LISTEN OFF\r")
                    self._listening_command_socket.close()
                except: pass
                self._listening_command_socket = None
            
            if self._ptt_monitor_thread and self._ptt_monitor_thread.is_alive():
                self._ptt_monitor_thread.join(timeout=2)
            
            if self.ptt: self.ptt.disconnect()
        except: pass
    
    def is_connected(self, session: VARASession) -> bool:
        return session and session.connected and session.is_active() and not self._check_disconnection(session)
    
    def get_status(self) -> Dict[str, Any]:
        return {"backend_type": "vara", "status": self.status.value, "sessions": len(self._active_sessions)}
    
    def get_backend_type(self) -> BackendType:
        return BackendType.VARA

def register_vara_backend():
    from .backend_factory import BackendFactory
    BackendFactory.register_backend(BackendType.VARA, VARABackend)

register_vara_backend()