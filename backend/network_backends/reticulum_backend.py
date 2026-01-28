"""
Reticulum Backend - Reticulum Network Stack backend for HAMSTR modular system.

This backend implements the NetworkBackend interface using Reticulum Network Stack
for encrypted mesh networking over LoRa, packet radio, and other transports.

Key Features:
- Encrypted, self-routing mesh network communication
- Link-based reliable connections
- Automatic Resource handling for large transfers (>200 bytes)
- Deterministic server discovery via grid squares
- Connect-per-operation pattern (keeps airwaves clear)
"""

import RNS
import os
import logging
import time
import threading
import json
from typing import Optional, Dict, Any
from .base_backend import NetworkBackend, BackendType, BackendStatus

# Import logging
from socketio_logger import get_socketio_logger
socketio_logger = get_socketio_logger()

# Force immediate log flushing
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
sys.stdout.reconfigure(line_buffering=True)


class ReticulumSession:
    """
    Reticulum session management.
    
    Wraps RNS.Link with HAMSTR session interface.
    Compatible with legacy HAMSTR Session interface.
    """
    
    def __init__(self, link: RNS.Link, remote_grid: str):
        self.link = link
        self.remote_grid = remote_grid
        self.connected = True
        self.last_activity = time.time()
        self._receive_buffer = bytearray()
        self._receive_event = threading.Event()
        self._lock = threading.Lock()
        
        # Legacy compatibility attributes that HAMSTR expects
        self.id = f"reticulum-{remote_grid}"

        # Have to add Dummy callsign for legacy compatibility
        self.remote_callsign = ("RETICULUM", 0)  
        
        # Additional legacy compatibility
        from models import ModemState
        self.state = ModemState.CONNECTED
        
        logging.info(f"[RETICULUM_SESSION] Created session for {remote_grid}")
    
    def update_activity(self):
        """Update last activity timestamp"""
        with self._lock:
            self.last_activity = time.time()
    
    def is_active(self, timeout: int = 120) -> bool:
        """Check if session is still active based on recent activity"""
        with self._lock:
            return (time.time() - self.last_activity) < timeout
    
    def append_data(self, data: bytes):
        """Append received data to buffer (called by packet callback)"""
        with self._lock:
            self._receive_buffer.extend(data)
            self._receive_event.set()
    
    def get_received_data(self, timeout: float) -> Optional[bytes]:
        """Wait for and retrieve received data"""
        if self._receive_event.wait(timeout):
            with self._lock:
                data = bytes(self._receive_buffer)
                self._receive_buffer.clear()
                self._receive_event.clear()
                return data
        return None


class ReticulumBackend(NetworkBackend):
    """
    Reticulum Network Stack backend implementation.
    
    Implements encrypted mesh networking using Reticulum Network Stack (RNS).
    Supports LoRa, packet radio, and other transports configured via Reticulum's config.
    """
    
    def __init__(self, config, is_server: bool):
        """
        Initialize Reticulum backend.
        
        Args:
            config: Configuration module with Reticulum settings
            is_server: True if server instance, False for client
        """
        logging.info(f"[RETICULUM_BACKEND] __init__ called - is_server={is_server}")
        super().__init__(config, is_server)
        
        # Get Reticulum configuration
        self._setup_reticulum_config(config)
        
        # Session management
        self._active_sessions: Dict[str, ReticulumSession] = {}
        self._session_lock = threading.Lock()
        
        # Shutdown flag for clean exit
        self._shutting_down = False
        
        # Reticulum state
        self._reticulum = None
        self._identity = None
        self._destination = None
        self._server_destination_hash = None
        
        # SAFE MTU: Reticulum packets have a hard limit (usually ~500 bytes).
        # We set this to 200 to be safe on LoRa and force larger data into Resources.
        self.packet_mtu = 200
        
        # Initialize Reticulum
        self._initialize_reticulum()
        
        # Start server announcement if server
        if self.is_server:
            self._start_announcing()
        
        logging.info("[RETICULUM_BACKEND] Initialization complete")
    
    def _setup_reticulum_config(self, config):
        """Setup Reticulum configuration from config module"""
        try:
            if self.is_server:
                # Server configuration
                self.server_grid = getattr(config, 'RETICULUM_SERVER_GRID', None)
                self.announce_interval = getattr(config, 'RETICULUM_ANNOUNCE_INTERVAL', 21600)
                self.reticulum_config_dir = getattr(config, 'RETICULUM_SERVER_CONFIG_DIR', None)
                
                if not self.server_grid:
                    logging.warning("[RETICULUM_BACKEND] No server_grid configured - using default DM34")
                    self.server_grid = "DM34"
                
                logging.info(f"[RETICULUM_BACKEND] Server config - Grid: {self.server_grid}, "
                        f"Announce interval: {self.announce_interval}s, "
                        f"Config dir: {self.reticulum_config_dir}")
            else:
                # Client configuration
                self.hamstr_server_hash = getattr(config, 'RETICULUM_HAMSTR_SERVER_HASH', None)
                self.hamstr_server_pubkey = getattr(config, 'RETICULUM_HAMSTR_SERVER_PUBKEY', None)
                self.hamstr_server_grid = getattr(config, 'RETICULUM_HAMSTR_SERVER_GRID', None)
                self.connection_timeout = getattr(config, 'RETICULUM_CONNECTION_TIMEOUT', 60)
                self.keepalive_interval = getattr(config, 'RETICULUM_KEEPALIVE_INTERVAL', 0)
                self.reticulum_config_dir = getattr(config, 'RETICULUM_CONFIG_DIR', None)
                
                if not self.hamstr_server_hash:
                    logging.warning("[RETICULUM_BACKEND] No hamstr_server_hash configured")
                if not self.hamstr_server_pubkey:
                    logging.warning("[RETICULUM_BACKEND] No hamstr_server_pubkey configured")
                
                logging.info(f"[RETICULUM_BACKEND] Client config - Server hash: {self.hamstr_server_hash[:16] if self.hamstr_server_hash else 'None'}..., "
                        f"Timeout: {self.connection_timeout}s, "
                        f"Config dir: {self.reticulum_config_dir}")
                
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Config setup error: {e}")
            import traceback
            logging.error(traceback.format_exc())
            # Fallback values
            if self.is_server:
                self.server_grid = "DM34"
                self.announce_interval = 21600
            else:
                self.hamstr_server_hash = None
                self.hamstr_server_pubkey = None
                self.hamstr_server_grid = None
                self.connection_timeout = 60
                self.keepalive_interval = 0
            self.reticulum_config_dir = None
    
    def _initialize_reticulum(self):
        """Initialize Reticulum instance and identity"""
        try:
            socketio_logger.info("[RETICULUM] Initializing Reticulum Network Stack...")
            
            # Initialize Reticulum with config directory (expand ~ properly!)
            if self.reticulum_config_dir:
                expanded_dir = os.path.expanduser(self.reticulum_config_dir)
            else:
                if self.is_server:
                    expanded_dir = os.path.expanduser("~/.reticulum_server")
                else:
                    expanded_dir = os.path.expanduser("~/.reticulum")
            
            # Check if we're in main thread
            import threading
            is_main_thread = threading.current_thread() is threading.main_thread()
            
            # Check if Reticulum singleton already exists with SAME config dir
            existing_instance = None
            try:
                existing_instance = RNS.Reticulum._Reticulum__instance
                
                # Only reuse if same config directory
                if existing_instance and hasattr(existing_instance, 'configdir'):
                    if existing_instance.configdir != expanded_dir:
                        logging.info(f"[RETICULUM_BACKEND] Existing instance uses different config ({existing_instance.configdir}), forcing new instance")
                        # Clear singleton to force new instance with our config
                        RNS.Reticulum._Reticulum__instance = None
                        existing_instance = None
            except Exception:
                pass
            
            if existing_instance:
                # Reuse existing instance (same config dir)
                logging.info("[RETICULUM_BACKEND] Reusing existing Reticulum instance")
                self._reticulum = existing_instance
            elif not is_main_thread:
                # We're in a background thread - initialize without signal handlers
                logging.info("[RETICULUM_BACKEND] Not in main thread, initializing without signal handlers")
                
                import signal as signal_module
                original_signal = signal_module.signal
                signal_module.signal = lambda *args, **kwargs: None
                
                try:
                    self._reticulum = RNS.Reticulum(configdir=expanded_dir)
                    logging.info(f"[RETICULUM_BACKEND] Using config dir: {expanded_dir} (no signal handlers)")
                finally:
                    signal_module.signal = original_signal
            else:
                # Main thread - initialize normally
                self._reticulum = RNS.Reticulum(configdir=expanded_dir)
                logging.info(f"[RETICULUM_BACKEND] Using config dir: {expanded_dir}")
            
            # Load or create identity
            self._load_or_create_identity()
            
            # Create destination
            self._create_destination()
            
            socketio_logger.info("[RETICULUM] Reticulum initialized successfully")
            self.status = BackendStatus.DISCONNECTED
            
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Initialization failed: {e}")
            socketio_logger.error(f"[RETICULUM] Initialization failed: {e}")
            import traceback
            logging.error(traceback.format_exc())
            self.status = BackendStatus.ERROR
            raise
    
    def _load_or_create_identity(self):
        """Load existing identity or create new one"""
        try:
            # Identity file path - ALWAYS in backend/data/ directory
            if self.is_server:
                identity_filename = "reticulum_server_identity"
            else:
                identity_filename = "reticulum_client_identity"
            
            # Get the backend directory (where this file is)
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            identity_path = os.path.join(backend_dir, "data", identity_filename)
            
            if os.path.exists(identity_path):
                self._identity = RNS.Identity.from_file(identity_path)
                logging.info(f"[RETICULUM_BACKEND] Loaded existing identity from {identity_path}")
            else:
                self._identity = RNS.Identity()
                os.makedirs(os.path.dirname(identity_path), exist_ok=True)
                self._identity.to_file(identity_path)
                logging.info(f"[RETICULUM_BACKEND] Created new identity at {identity_path}")
            
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Identity error: {e}")
            import traceback
            logging.error(traceback.format_exc())
            raise
        
    def _create_destination(self):
        """Create destination for incoming connections (server) or prepare for outbound (client)"""
        try:
            if self.is_server:
                # Server: Create IN destination (persistent address)
                self._destination = RNS.Destination(
                    self._identity,
                    RNS.Destination.IN,
                    RNS.Destination.SINGLE,
                    "hamstr",
                    "server"
                )
                
                # Store hash for easy access
                self._server_destination_hash = RNS.hexrep(self._destination.hash, delimit=False)
                
                # Export public key for distribution
                public_key_hex = self._identity.get_public_key().hex()
                
                logging.info(f"[RETICULUM_BACKEND] Server destination created")
                logging.info(f"[RETICULUM_BACKEND] Destination hash: {self._server_destination_hash}")
                logging.info(f"[RETICULUM_BACKEND] Public key: {public_key_hex}")
                
                # Log to console prominently for easy copying
                print("\n" + "="*70)
                print("HAMSTR RETICULUM SERVER")
                print("="*70)
                print(f"Destination Hash: {self._server_destination_hash}")
                print(f"Public Key: {public_key_hex}")
                if self.server_grid:
                    print(f"Grid Square: {self.server_grid} (metadata only)")
                print("\n⚠️  PUBLISH BOTH HASH AND PUBLIC KEY TO YOUR DIRECTORY!")
                print("="*70 + "\n")
                
                # Set link established callback for incoming connections
                self._destination.set_link_established_callback(self._server_link_established)
                
                # Announce immediately
                self._destination.announce()
                logging.info("[RETICULUM_BACKEND] Announced destination")
                
            else:
                # Client: Will create OUT destination when connecting
                logging.info("[RETICULUM_BACKEND] Client mode - destination will be created on connect")
                
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Destination creation error: {e}")
            raise
    
    def _server_link_established(self, link):
        """Callback when client connects to server"""
        logging.info(f"[RETICULUM_BACKEND] *** CALLBACK TRIGGERED *** Client connecting!")
        
        try:
            link_hash = RNS.hexrep(link.hash, delimit=False)
            logging.info(f"[RETICULUM_BACKEND] Client connected: {link_hash}")
            socketio_logger.info("[RETICULUM] Client connecting...")
            
            # Configure callbacks & strategies (THIS WAS THE FIX)
            self._configure_link_callbacks(link)
            
            # Create session for this incoming Link
            session = ReticulumSession(link, "CLIENT")  # Use "CLIENT" as remote_grid placeholder
            
            # Store session
            with self._session_lock:
                session_key = f"reticulum-{link_hash[:8]}"
                session.id = session_key
                self._active_sessions[session_key] = session
            
            logging.info(f"[RETICULUM_BACKEND] Session created: {session_key}")
            
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Link established callback error: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    def _server_packet_received(self, data, packet):
        """Callback when server receives packet"""
        try:
            logging.info(f"[RETICULUM_BACKEND] Server received packet: {len(data)} bytes")
            
            # Find session for this link
            link = packet.link
            with self._session_lock:
                for session in self._active_sessions.values():
                    if session.link == link:
                        session.append_data(data)
                        session.update_activity()
                        return
            
            logging.warning("[RETICULUM_BACKEND] Received packet but no matching session found")
            
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Packet received error: {e}")
    
    def _start_announcing(self):
        """Start periodic announcement (server only)"""
        if not self.is_server:
            return
        
        def announce_loop():
            while True:
                try:
                    self._destination.announce()
                    logging.info(f"[RETICULUM_BACKEND] Announced destination")
                    time.sleep(self.announce_interval)
                except Exception as e:
                    logging.error(f"[RETICULUM_BACKEND] Announce error: {e}")
                    time.sleep(60)  # Retry after 1 minute on error
        
        announce_thread = threading.Thread(target=announce_loop, daemon=True)
        announce_thread.start()
        logging.info(f"[RETICULUM_BACKEND] Started announcement thread (interval: {self.announce_interval}s)")
    
    def _configure_link_callbacks(self, link):
        """
        Apply standard callbacks and RESOURCE STRATEGIES to a link.
        Used by both Client (on connect) and Server (on incoming).
        """
        # 1. Packet Callback (Small data)
        link.set_packet_callback(self._packet_received_callback)
        if self.is_server:
            link.set_packet_callback(self._server_packet_received)
        else:
            link.set_packet_callback(self._client_packet_received)
        
        # 2. Resource Strategy (Large data > 200 bytes)
        # CRITICAL: We must accept resources, or large transfers will be ignored.
        link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
        link.set_resource_callback(self._on_resource_concluded)
        link.set_resource_started_callback(self._on_resource_started)
        link.set_resource_concluded_callback(self._on_resource_concluded)

        # 3. Windowing (Congestion Control)
        # Removed invalid set_packet_window call
        # Reticulum handles basic packet windowing internally. 
        # For large resources, we handle it in send_data using resource.window = 1

    def connect(self, remote_callsign: tuple) -> Optional[ReticulumSession]:
        """
        Establish connection to remote station.
        
        For CLIENT: Connect to server using hash and public key from config
        For SERVER: Wait for incoming Link (via callback)
        """
        
        try:
            # SERVER MODE: Wait for incoming connection via callback
            if self.is_server:
                logging.info("[RETICULUM_BACKEND] Server waiting for incoming Link...")
                socketio_logger.info("[RETICULUM] Waiting for incoming connection...")
                
                # Block checking for incoming connections (created by callback)
                check_interval = 0.5
                
                while True:
                    # Check shutdown flag
                    if self._shutting_down:
                        return None
                    
                    # Check if a session was created by the _server_link_established callback
                    with self._session_lock:
                        if self._active_sessions:
                            # Found a session! Return the first one
                            session = list(self._active_sessions.values())[0]
                            logging.info(f"[RETICULUM_BACKEND] Accepted incoming connection")
                            socketio_logger.info("[SESSION] Client connected")
                            return session
                    
                    time.sleep(check_interval)
            
            # CLIENT MODE: Connect to server using hash and public key
            server_hash = self.hamstr_server_hash
            server_pubkey = self.hamstr_server_pubkey
            
            if not server_hash or not server_pubkey:
                logging.error("[RETICULUM_BACKEND] Missing server hash or public key in client_settings.ini")
                socketio_logger.error("[RETICULUM] Missing server configuration")
                return None
            
            socketio_logger.info(f"[RETICULUM] Connecting to server...")
            logging.info(f"[RETICULUM_BACKEND] Connecting to {server_hash[:16]}...")
            
            try:
                # Convert hex strings to bytes
                destination_hash = bytes.fromhex(server_hash)
                public_key_bytes = bytes.fromhex(server_pubkey)
                
                # Reconstruct server Identity from public key
                server_identity = RNS.Identity()
                server_identity.load_public_key(public_key_bytes)
                
            except Exception as e:
                logging.error(f"[RETICULUM_BACKEND] Failed to load Identity: {e}")
                socketio_logger.error("[RETICULUM] Failed to process server identity")
                return None
            
            # Create outbound destination
            try:
                outbound_destination = RNS.Destination(
                    server_identity,
                    RNS.Destination.OUT,
                    RNS.Destination.SINGLE,
                    "hamstr",
                    "server"
                )
            except Exception as e:
                logging.error(f"[RETICULUM_BACKEND] Failed to create outbound destination: {e}")
                return None
            
            # REQUEST PATH TO DESTINATION
            if not RNS.Transport.has_path(destination_hash):
                logging.info("[RETICULUM_BACKEND] No path to destination, requesting...")
                socketio_logger.info("[RETICULUM] Finding path to server...")
                RNS.Transport.request_path(destination_hash)
                
                # Wait for path
                path_timeout = 30
                start = time.time()
                while not RNS.Transport.has_path(destination_hash):
                    if time.time() - start > path_timeout:
                        logging.error("[RETICULUM_BACKEND] Path request timeout")
                        socketio_logger.error("[RETICULUM] Cannot find path to server")
                        return None
                    time.sleep(0.1)
                
                logging.info("[RETICULUM_BACKEND] Path established to server")
            
            # Establish Link
            socketio_logger.info("[RETICULUM] Establishing link...")
            logging.info("[RETICULUM_BACKEND] Creating Link to server...")
            
            try:
                link = RNS.Link(outbound_destination)
            except Exception as e:
                logging.error(f"[RETICULUM_BACKEND] Failed to create Link: {e}")
                return None
            
            # Wait for Link establishment
            link_timeout = self.connection_timeout
            start_time = time.time()
            
            while time.time() - start_time < link_timeout:
                if self._shutting_down:
                    link.teardown()
                    return None
                
                if link.status == RNS.Link.ACTIVE:
                    socketio_logger.info("[SESSION] CONNECTED")
                    logging.info("[RETICULUM_BACKEND] Link established successfully")
                    break
                elif link.status == RNS.Link.CLOSED:
                    logging.error("[RETICULUM_BACKEND] Link closed during establishment")
                    socketio_logger.error("[RETICULUM] Link establishment failed")
                    return None
                time.sleep(0.1)
            else:
                socketio_logger.error("[RETICULUM] Link establishment timeout")
                logging.error(f"[RETICULUM_BACKEND] Link timeout after {link_timeout}s")
                link.teardown()
                return None
            
            # Create session
            session = ReticulumSession(link, server_hash[:16])
            
            # Configure strategies (THIS IS WHERE THE FIX WAS APPLIED)
            self._configure_link_callbacks(link)
            
            # Store session
            with self._session_lock:
                session_key = f"reticulum-{server_hash[:8]}"
                self._active_sessions[session_key] = session
            
            self.status = BackendStatus.CONNECTED
            return session
            
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Connection failed: {e}")
            socketio_logger.error(f"[RETICULUM] Connection failed: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None
    
    def _client_packet_received(self, data, packet):
        """Callback when client receives packet"""
        try:
            logging.info(f"[RETICULUM_BACKEND] Client received packet: {len(data)} bytes")
            
            # Find session for this link
            link = packet.link
            with self._session_lock:
                for session in self._active_sessions.values():
                    if session.link == link:
                        session.append_data(data)
                        session.update_activity()
                        return
            
            logging.warning("[RETICULUM_BACKEND] Received packet but no matching session found")
            
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Packet received error: {e}")
            
    def _packet_received_callback(self, data, packet):
        """Generic fallback packet callback"""
        # Handled by specific server/client callbacks
        pass
    
    def send_data(self, session: ReticulumSession, data: bytes) -> bool:
        """
        Send raw application data to remote station.
        
        This is our CUSTOM method that wraps Reticulum's packet sending:
        - Creates RNS.Packet with data
        - Sends via packet.send()
        - Reticulum automatically handles Resources for large transfers
        - Progress tracking via Resource callbacks
        
        Args:
            session: Active Reticulum session
            data: Raw bytes to transmit
            
        Returns:
            True if send successful, False otherwise
        """
        try:
            if not session or not session.connected:
                logging.error("[RETICULUM_BACKEND] No active session for sending data")
                return False
            
            if not session.link or session.link.status != RNS.Link.ACTIVE:
                logging.error("[RETICULUM_BACKEND] Link not active")
                return False
            
            data_size = len(data)
            logging.info(f"[RETICULUM_BACKEND] Sending {data_size} bytes")
            
            # --- CRITICAL FIX: Explicit Split Logic ---
            if data_size <= self.packet_mtu:
                # Small Data -> Packet
                packet = RNS.Packet(session.link, data)
                packet.send()
                session.update_activity()
                return True
            else:
                # Large Data -> Resource
                socketio_logger.info(f"[RETICULUM] Starting resource transfer ({data_size} bytes)...")
                
                resource = RNS.Resource(data, session.link)
                
                # --- CRITICAL FIX: Window = 1 for LoRa Stability ---
                # This forces Reticulum to wait for an ACK for every segment.
                resource.window = 1
                
                # Set progress monitoring
                # Note: These are set on the link for *incoming*, but here we just rely on Reticulum
                # to send the resource. We don't need to manually attach callbacks to the *Link* for *outgoing*
                
                return True
            
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Send error: {e}")
            socketio_logger.error(f"[RETICULUM] Send error: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False
    
    def _on_resource_started(self, resource):
        """Callback when large transfer starts"""
        try:
            total_size = resource.total_size
            logging.info(f"[RETICULUM_BACKEND] Resource transfer started: {total_size} bytes")
            socketio_logger.info(f"[RETICULUM] Transferring {total_size} bytes...")
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Resource started callback error: {e}")
    
    def _on_resource_progress(self, resource):
        """Callback for transfer progress updates"""
        try:
            progress = resource.get_progress()
            percent = int(progress * 100)
            
            # Throttle logging - only log every 10%
            if percent % 10 == 0:
                logging.info(f"[RETICULUM_BACKEND] Transfer progress: {percent}%")
                socketio_logger.info(f"[PROGRESS] Transfer: {percent}%")
                
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Resource progress callback error: {e}")
    
    def _on_resource_concluded(self, resource):
        """Callback when transfer completes"""
        try:
            if resource.status == RNS.Resource.COMPLETE:
                # --- CRITICAL FIX: Actually Read the Data ---
                data = resource.data.read()
                logging.info(f"[RETICULUM_BACKEND] Resource finished. Read {len(data)} bytes.")
                socketio_logger.info("[RETICULUM] Large transfer received.")
                
                # Find the session and inject data so DirectProtocol sees it
                with self._session_lock:
                    for session in self._active_sessions.values():
                        if session.link == resource.link:
                            session.append_data(data)
                            session.update_activity()
                            return
            else:
                logging.warning(f"[RETICULUM_BACKEND] Resource failed status: {resource.status}")
                
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Resource concluded callback error: {e}")
    
    def receive_data(self, session: ReticulumSession, timeout: int = 30) -> Optional[bytes]:
        """
        Receive raw application data from remote station.
        
        Waits for packet callback to populate the receive buffer,
        then returns the data.
        
        Args:
            session: Active Reticulum session
            timeout: Total timeout in seconds
            
        Returns:
            Received bytes if successful, None if timeout/error
        """
        try:
            if not session or not session.connected:
                logging.error("[RETICULUM_BACKEND] No active session for receiving data")
                return None
            
            logging.info(f"[RETICULUM_BACKEND] Waiting for data (timeout: {timeout}s)...")
            # socketio_logger.info("[RETICULUM] Waiting for response...")
            
            # Wait for data via the session's event-based system
            data = session.get_received_data(timeout)
            
            if data:
                logging.info(f"[RETICULUM_BACKEND] Received {len(data)} bytes")
                socketio_logger.info(f"[RETICULUM] Response received ({len(data)} bytes)")
                session.update_activity()
                return data
            else:
                logging.warning(f"[RETICULUM_BACKEND] Receive timeout after {timeout}s")
                # socketio_logger.error("[RETICULUM] Receive timeout")
                return None
                
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Receive error: {e}")
            socketio_logger.error(f"[RETICULUM] Receive error: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None
    
    def disconnect(self, session: ReticulumSession) -> bool:
        """
        Close connection gracefully.
        
        Args:
            session: Session to close
            
        Returns:
            True if disconnect successful
        """
        try:
            if not session:
                logging.warning("[RETICULUM_BACKEND] No session to disconnect")
                return False
            
            socketio_logger.info("[RETICULUM] Disconnecting...")
            logging.info(f"[RETICULUM_BACKEND] Disconnecting session: {session.id}")
            
            # Mark session as disconnected
            session.connected = False
            
            # Teardown Link gracefully
            if session.link:
                try:
                    session.link.teardown()
                    logging.info("[RETICULUM_BACKEND] Link teardown initiated")
                    
                    # Wait briefly for clean teardown
                    timeout = 5.0
                    start_time = time.time()
                    while time.time() - start_time < timeout:
                        if session.link.status == RNS.Link.CLOSED:
                            logging.info("[RETICULUM_BACKEND] Link closed cleanly")
                            break
                        time.sleep(0.1)
                    
                except Exception as e:
                    logging.warning(f"[RETICULUM_BACKEND] Link teardown error: {e}")
            
            # Remove from active sessions
            with self._session_lock:
                session_key = session.id
                if session_key in self._active_sessions:
                    del self._active_sessions[session_key]
                    logging.info(f"[RETICULUM_BACKEND] Removed session: {session_key}")
            
            socketio_logger.info("[SESSION] DISCONNECTED")
            logging.info("[RETICULUM_BACKEND] Disconnect complete")
            
            # Update status if no active sessions
            with self._session_lock:
                if not self._active_sessions:
                    self.status = BackendStatus.DISCONNECTED
            
            return True
            
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Disconnect error: {e}")
            socketio_logger.error(f"[RETICULUM] Disconnect error: {e}")
            return False
    
    def get_status(self) -> BackendStatus:
        """Get current backend status"""
        return self.status
    
    def get_backend_type(self) -> BackendType:
        """Return the backend type"""
        return BackendType.RETICULUM
    
    def is_connected(self, session: ReticulumSession) -> bool:
        """
        Check if session is still connected.
        
        Args:
            session: Session to check
            
        Returns:
            True if connected, False otherwise
        """
        if not session:
            return False
        
        # Check session state
        if not session.connected:
            return False
        
        # Check Link status
        if not session.link or session.link.status != RNS.Link.ACTIVE:
            session.connected = False
            return False
        
        # Check if session is still active (hasn't timed out)
        if not session.is_active(timeout=120):
            logging.warning("[RETICULUM_BACKEND] Session inactive timeout")
            session.connected = False
            return False
        
        return True
    
    def cleanup(self):
        """Cleanup all resources"""
        try:
            # SET SHUTDOWN FLAG FIRST
            self._shutting_down = True
            logging.info("[RETICULUM_BACKEND] Cleaning up...")
            
            # Disconnect all active sessions
            with self._session_lock:
                for session in list(self._active_sessions.values()):
                    try:
                        self.disconnect(session)
                    except Exception as e:
                        logging.error(f"[RETICULUM_BACKEND] Error disconnecting session: {e}")
                self._active_sessions.clear()
            
            # Deregister destination before teardown
            if self._destination:
                try:
                    RNS.Transport.deregister_destination(self._destination)
                    logging.info("[RETICULUM_BACKEND] Destination deregistered")
                except Exception as e:
                    logging.debug(f"[RETICULUM_BACKEND] Destination deregister: {e}")
                self._destination = None
            
            # Properly teardown Reticulum instance
            if self._reticulum:
                try:
                    RNS.Reticulum.exit_handler()
                    logging.info("[RETICULUM_BACKEND] Reticulum instance torn down")
                except Exception as e:
                    logging.debug(f"[RETICULUM_BACKEND] Exit handler: {e}")
                
                self._reticulum = None
            
            logging.info("[RETICULUM_BACKEND] Cleanup complete")
            
        except Exception as e:
            logging.error(f"[RETICULUM_BACKEND] Cleanup error: {e}")


# Register this backend with the factory
def register_reticulum_backend():
    """Register the Reticulum backend with the factory."""
    from .backend_factory import BackendFactory
    BackendFactory.register_backend(BackendType.RETICULUM, ReticulumBackend)
    logging.info("[RETICULUM_BACKEND] Registered Reticulum backend")

# Auto-register when module is imported
register_reticulum_backend()