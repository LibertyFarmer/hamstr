#!/usr/bin/env python3

import sys
import threading
import time
import logging
import queue
from datetime import datetime
from typing import Optional
import os
import platform
import glob
import re

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QGridLayout, QPushButton, QLabel, 
                               QTextEdit, QGroupBox, QFrame, QSplitter, QDialog,
                               QFormLayout, QLineEdit, QSpinBox, QPlainTextEdit,
                               QCheckBox, QStatusBar, QMenuBar, QMessageBox, QComboBox)

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QAction

import config

def get_available_serial_ports():
    """Cross-platform function to detect available serial ports."""
    ports = []
    
    system = platform.system()
    
    if system == "Windows":
        # Windows - only detect actually available COM ports
        try:
            import serial.tools.list_ports
            available_ports = serial.tools.list_ports.comports()
            ports = [port.device for port in available_ports]
        except ImportError:
            # Fallback if pyserial is not available - try common ports
            for i in range(1, 20):
                port_name = f"COM{i}"
                try:
                    import serial
                    test_port = serial.Serial(port_name, timeout=0.1)
                    test_port.close()
                    ports.append(port_name)
                except:
                    pass
    elif system == "Linux":
        # Linux serial devices - only existing ones
        possible_patterns = [
            '/dev/ttyUSB*',
            '/dev/ttyACM*', 
            '/dev/ttyAMA*',
            '/dev/serial/by-id/*'
        ]
        for pattern in possible_patterns:
            ports.extend(glob.glob(pattern))
    elif system == "Darwin":  # macOS
        # macOS serial devices - only existing ones
        possible_patterns = [
            '/dev/cu.usbserial*',
            '/dev/cu.usbmodem*',
            '/dev/cu.SLAB_USBtoUART*',
            '/dev/cu.wchusbserial*'
        ]
        for pattern in possible_patterns:
            ports.extend(glob.glob(pattern))
    
    # Remove duplicates and sort
    ports = list(set(ports))
    ports.sort()
    
    # If no ports found, add some common defaults as placeholders
    if not ports:
        if system == "Windows":
            ports = ["COM3", "COM4", "COM5"]
        elif system == "Linux":
            ports = ["/dev/ttyUSB0", "/dev/ttyACM0"]
        elif system == "Darwin":
            ports = ["/dev/cu.usbserial", "/dev/cu.SLAB_USBtoUART"]
    
    return ports

# Custom signal emitter for thread-safe GUI updates
class LogSignals(QObject):
    new_log = Signal(str, str, str)  # timestamp, level, message
    server_status_changed = Signal(bool)  # running state
    server_started = Signal()
    
class UILogHandler(logging.Handler):
    def __init__(self, signals):
        super().__init__()
        self.signals = signals
        
    def emit(self, record):
        try:
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            level = record.levelname
            message = record.getMessage()
            
            self.signals.new_log.emit(timestamp, level, message)
            
            if 'Server is running' in message:
                self.signals.server_started.emit()
                
        except Exception:
            pass

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HAMSTR Server Settings")
        self.setModal(True)
        self.setFixedSize(600, 500)
        self.setStyleSheet("QLabel { font-weight: bold; }")
        
        layout = QFormLayout()

        # Server Callsign and SSID
        callsign_layout = QHBoxLayout()
        
        self.callsign_input = QLineEdit()
        self.callsign_input.setMaxLength(6)
        self.callsign_input.setPlaceholderText("KK7AHK")
        self.callsign_input.setFixedWidth(80)
        self.callsign_input.textChanged.connect(self.validate_callsign)
        
        dash_label = QLabel("-")
        dash_label.setStyleSheet("font-weight: bold; color: #6b7280;")
        dash_label.setFixedWidth(15)
        dash_label.setAlignment(Qt.AlignCenter)
        
        self.ssid_combo = QComboBox()
        self.ssid_combo.setFixedWidth(50)
        for i in range(16):
            self.ssid_combo.addItem(str(i))
        
        callsign_layout.addWidget(self.callsign_input)
        callsign_layout.addWidget(dash_label)
        callsign_layout.addWidget(self.ssid_combo)
        callsign_layout.addStretch()
        
        layout.addRow("Server Callsign:", callsign_layout)
        
        # TNC Connection Type Selector
        self.connection_type_combo = QComboBox()
        self.connection_type_combo.addItem("TCP", "tcp")
        self.connection_type_combo.addItem("Serial", "serial")
        self.connection_type_combo.currentIndexChanged.connect(self.on_connection_type_changed)
        layout.addRow("TNC Connection Type:", self.connection_type_combo)
        
        # TCP Settings Group
        self.tcp_group = QWidget()
        tcp_layout = QFormLayout()
        
        self.host_input = QLineEdit()
        tcp_layout.addRow("TNC Host:", self.host_input)
        
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        tcp_layout.addRow("TNC Port:", self.port_input)
        
        self.tcp_group.setLayout(tcp_layout)
        layout.addRow(self.tcp_group)
        
        # Serial Settings Group  
        self.serial_group = QWidget()
        serial_layout = QFormLayout()
        
        self.serial_port_combo = QComboBox()
        self.serial_port_combo.setEditable(True)  # Allow custom entries
        self.refresh_serial_ports()
        serial_layout.addRow("Serial Port:", self.serial_port_combo)
        
        # Add refresh button for serial ports
        refresh_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Ports")
        refresh_btn.clicked.connect(self.refresh_serial_ports)
        refresh_btn.setMaximumWidth(100)
        refresh_layout.addWidget(refresh_btn)
        refresh_layout.addStretch()
        serial_layout.addRow("", refresh_layout)
        
        self.serial_speed_combo = QComboBox()
        serial_speeds = ["1200", "9600", "19200", "38400", "57600", "115200"]
        self.serial_speed_combo.addItems(serial_speeds)
        self.serial_speed_combo.setCurrentText("57600")  # Default
        serial_layout.addRow("Serial Speed:", self.serial_speed_combo)
        
        self.serial_group.setLayout(serial_layout)
        layout.addRow(self.serial_group)
        
        # NOSTR Relays
        self.relays_input = QPlainTextEdit()
        self.relays_input.setMaximumHeight(100)
        self.relays_input.setPlaceholderText("wss://relay.nostr.band/,wss://relay.damus.io")
        layout.addRow("NOSTR Relays:", self.relays_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.cancel_btn = QPushButton("Cancel")
        
        # Style buttons
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        
        self.save_btn.clicked.connect(self.save_settings)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addRow(button_layout)
        self.setLayout(layout)
        
        # Load current settings
        self.load_current_settings()

    def refresh_serial_ports(self):
        """Refresh the list of available serial ports."""
        current_text = self.serial_port_combo.currentText()
        self.serial_port_combo.clear()
        
        ports = get_available_serial_ports()
        self.serial_port_combo.addItems(ports)
        
        # Try to restore previous selection
        index = self.serial_port_combo.findText(current_text)
        if index >= 0:
            self.serial_port_combo.setCurrentIndex(index)

    def on_connection_type_changed(self):
        """Handle TNC connection type change."""
        connection_type = self.connection_type_combo.currentData()
        
        if connection_type == "tcp":
            self.tcp_group.setVisible(True)
            self.serial_group.setVisible(False)
        else:  # serial
            self.tcp_group.setVisible(False)
            self.serial_group.setVisible(True)
            # Auto-refresh serial ports when switching to serial
            self.refresh_serial_ports()

    def load_current_settings(self):
        """Load current settings from config."""
        try:
            # Load callsign
            callsign_str = config.server_config.get('RADIO', 'SERVER_CALLSIGN', fallback='(CALLSIGN, 7)')
            callsign, ssid = config.parse_tuple(callsign_str)
            self.callsign_input.setText(callsign)
            self.ssid_combo.setCurrentText(str(ssid))
            
            # Load connection type
            connection_type = config.server_config.get('TNC', 'CONNECTION_TYPE', fallback='tcp').lower()
            index = self.connection_type_combo.findData(connection_type)
            if index >= 0:
                self.connection_type_combo.setCurrentIndex(index)
            
            # Load TCP settings
            host = config.server_config.get('TNC', 'SERVER_HOST', fallback='localhost')
            self.host_input.setText(host)
            
            port = config.server_config.getint('TNC', 'SERVER_PORT', fallback=8002)
            self.port_input.setValue(port)
            
            # Auto-refresh serial ports on dialog load
            self.refresh_serial_ports()
            
            # Load serial settings
            serial_port = config.server_config.get('TNC', 'SERIAL_PORT', fallback='COM3')
            index = self.serial_port_combo.findText(serial_port)
            if index >= 0:
                self.serial_port_combo.setCurrentIndex(index)
            else:
                # Add the configured port if it's not in the list
                self.serial_port_combo.addItem(serial_port)
                self.serial_port_combo.setCurrentText(serial_port)
            
            serial_speed = config.server_config.get('TNC', 'SERIAL_SPEED', fallback='57600')
            index = self.serial_speed_combo.findText(str(serial_speed))
            if index >= 0:
                self.serial_speed_combo.setCurrentIndex(index)
            
            # Load relays
            try:
                relays = config.server_config.get('NOSTR', 'RELAYS', fallback='')
                self.relays_input.setPlainText(relays)
            except:
                self.relays_input.setPlainText('wss://relay.nostr.band/,wss://relay.damus.io')
            
            # Trigger connection type change to show/hide appropriate controls
            self.on_connection_type_changed()
            
        except Exception as e:
            print(f"Error loading settings: {e}")
            # Set fallback values
            self.callsign_input.setText('CALLSIGN')
            self.ssid_combo.setCurrentText('7')
            self.host_input.setText('localhost')
            self.port_input.setValue(8002)

    def validate_callsign(self, text):
        """Validate callsign input - only letters and numbers."""
        cleaned = ''.join(c.upper() for c in text if c.isalnum())
        if cleaned != text.upper():
            self.callsign_input.setText(cleaned)

    def save_settings(self):
        """Save settings using config.update_config."""
        try:
            # Get and validate callsign
            callsign = self.callsign_input.text().strip().upper()
            ssid = int(self.ssid_combo.currentText())
            
            if not callsign or len(callsign) < 3:
                QMessageBox.warning(self, "Invalid Callsign", "Callsign must be at least 3 characters.")
                return
            
            # Format callsign as tuple string
            callsign_tuple = f"({callsign}, {ssid})"
            
            # Get connection type
            connection_type = self.connection_type_combo.currentData()
            
            # Save settings using existing config.update_config function
            config.update_config('RADIO', 'SERVER_CALLSIGN', callsign_tuple)
            config.update_config('TNC', 'CONNECTION_TYPE', connection_type)
            
            if connection_type == "tcp":
                config.update_config('TNC', 'SERVER_HOST', self.host_input.text().strip())
                config.update_config('TNC', 'SERVER_PORT', str(self.port_input.value()))
            else:  # serial
                config.update_config('TNC', 'SERIAL_PORT', self.serial_port_combo.currentText())
                config.update_config('TNC', 'SERIAL_SPEED', self.serial_speed_combo.currentText())
            
            config.update_config('NOSTR', 'RELAYS', self.relays_input.toPlainText().strip())
            
            # Reload config
            import importlib
            importlib.reload(config)
            
            # Show success message but DON'T close dialog
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            logging.info("Server settings updated via GUI")
            
            # Stay in the dialog - do NOT call self.accept()
            
        except Exception as e:
            print(f"Error saving settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

class ServerThread(QThread):
    def __init__(self, signals):
        super().__init__()
        self.signals = signals
        self.server = None
        self.running = True
        
    def run(self):
        try:
            from server import Server
            
            # Custom server wrapper to avoid signal handler issues
            class ThreadedServer:
                def __init__(self):
                    self.server = Server()
                    self.running = True
                    
                def run(self):
                    logging.info("Server is starting...")
                    if not self.server.core.start():
                        logging.error("Failed to start server. Exiting.")
                        return

                    logging.info("Server is running...")
                    
                    try:
                        while self.running and self.server.running:
                            logging.info("Waiting for incoming connections...")
                            try:
                                session = self.server.core.handle_incoming_connection()
                                if session:
                                    try:
                                        self.server.handle_connected_session(session)
                                    except Exception as e:
                                        logging.error(f"Error handling session: {e}")
                                    finally:
                                        logging.info("Session ended, resetting for next connection")
                                        self.server.core.reset_for_next_connection()
                                else:
                                    logging.info("Connection attempt failed or timed out, resetting for next connection")
                                    self.server.core.reset_for_next_connection()
                                
                                self.server.cleanup_inactive_sessions()
                            except Exception as e:
                                logging.error(f"Error in connection handling: {e}")
                                self.server.core.reset_for_next_connection()
                                
                            time.sleep(0.1)
                            
                    except Exception as e:
                        logging.error(f"Server error: {e}")
                    finally:
                        logging.info("Server stopped.")
                        
                def stop(self):
                    self.running = False
                    if self.server:
                        self.server.stop()
            
            self.server = ThreadedServer()
            self.server.run()
            
        except Exception as e:
            logging.error(f"Failed to start server: {e}")
            
    def stop_server(self):
        self.running = False
        if self.server:
            self.server.stop()
        self.quit()
        self.wait()

class HamstrServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.signals = LogSignals()
        self.server_thread = None
        self.server_running = False
        self.debug_mode = False
        self.start_time = None
        
        # Connection tracking
        self.connection_state = 'DISCONNECTED'  # DISCONNECTED, CONNECTING, CONNECTED, DISCONNECTING
        self.connected_callsign = None
        self.current_activity = 'Idle'
        
        self.setup_logging()
        self.init_ui()
        self.setup_signals()
        self.setup_timer()
        
        # Test logging immediately
        logging.info("HAMSTR Server UI initialized successfully")
        
    def setup_logging(self):
        """Setup logging to capture server logs"""
        self.log_handler = UILogHandler(self.signals)
        
        # Get root logger and add our handler
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Add console handler for debugging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Add our UI handler
        root_logger.addHandler(self.log_handler)
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("HAMSTR Server Control Panel")
        self.setGeometry(100, 100, 1000, 750)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("HAMSTR Server UI Ready")
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Top section - Control cards
        self.create_control_section(main_layout)
        
        # Bottom section - Logs
        self.create_log_section(main_layout)
        
        # Apply modern styling
        self.apply_styling()
        
    def create_menu_bar(self):
        """Create menu bar with settings"""
        menubar = self.menuBar()
        
        # Settings menu
        settings_menu = menubar.addMenu('&Settings')
        
        settings_action = QAction('&Server Settings...', self)
        settings_action.triggered.connect(self.open_settings)
        settings_menu.addAction(settings_action)
        
        settings_menu.addSeparator()
        
        exit_action = QAction('&Exit', self)
        exit_action.triggered.connect(self.close)
        settings_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu('&Help')
        about_action = QAction('&About HAMSTR...', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_control_section(self, main_layout):
        """Create the top control section with modern cards"""
        # Control cards in a grid
        control_frame = QFrame()
        control_layout = QGridLayout()
        control_frame.setLayout(control_layout)
        
        # Server Control Card
        control_group = QGroupBox("🔧 Server Control")
        control_group.setFixedHeight(140)
        control_group_layout = QVBoxLayout()
        
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ Start Server")
        self.stop_btn = QPushButton("⏹ Stop Server")
        
        # Simplified button styling without transform
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:disabled {
                background-color: #d1d5db;
                color: #9ca3af;
            }
        """)
        
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
            QPushButton:disabled {
                background-color: #d1d5db;
                color: #9ca3af;
            }
        """)
        
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        
        control_group_layout.addLayout(button_layout)
        control_group.setLayout(control_group_layout)
        
        # Server Status Card
        status_group = QGroupBox("📊 Server Status")
        status_group.setFixedHeight(140)
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("Server: Stopped")
        self.status_label.setStyleSheet("color: #ef4444; font-weight: 600; font-size: 16px;")
        
        self.uptime_label = QLabel("Uptime: 00:00:00")
        self.uptime_label.setStyleSheet("color: #6b7280; font-size: 14px;")
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.uptime_label)
        status_layout.addStretch()
        status_group.setLayout(status_layout)
        
        # Activity Status Card
        activity_group = QGroupBox("⚡ Current Activity")
        activity_group.setFixedHeight(140)
        activity_layout = QVBoxLayout()
        
        self.activity_label = QLabel("Server not running")
        self.activity_label.setStyleSheet("color: #6b7280; font-size: 14px;")
        
        activity_layout.addWidget(self.activity_label)
        activity_layout.addStretch()
        activity_group.setLayout(activity_layout)
        
        # Connection Status Card
        connection_group = QGroupBox("📡 Connection Status")
        connection_group.setFixedHeight(140)
        connection_layout = QVBoxLayout()
        
        self.connection_label = QLabel("Disconnected")
        self.connection_label.setStyleSheet("color: #ef4444; font-weight: 600; font-size: 14px;")
        
        connection_layout.addWidget(self.connection_label)
        connection_layout.addStretch()
        connection_group.setLayout(connection_layout)
        
        # Add cards to grid - 2x2 layout
        control_layout.addWidget(control_group, 0, 0)
        control_layout.addWidget(status_group, 0, 1)
        control_layout.addWidget(activity_group, 1, 0)
        control_layout.addWidget(connection_group, 1, 1)
        
        main_layout.addWidget(control_frame)
        
    def create_log_section(self, main_layout):
        """Create the log section with modern styling"""
        log_group = QGroupBox("🖥️ Server Logs")
        log_layout = QVBoxLayout()
        
        # Log controls
        log_controls = QHBoxLayout()
        
        self.debug_checkbox = QCheckBox("Debug Mode")
        self.debug_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: 600;
                color: #374151;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #d1d5db;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
        """)
        self.debug_checkbox.stateChanged.connect(self.toggle_debug_mode)
        
        self.clear_btn = QPushButton("🗑️ Clear Logs")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_logs)
        self.clear_btn.setMaximumWidth(120)
        
        log_controls.addWidget(self.debug_checkbox)
        log_controls.addStretch()
        log_controls.addWidget(self.clear_btn)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("SF Mono", 10) if sys.platform == "darwin" else QFont("Consolas", 10))
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #f8fafc;
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                padding: 12px;
                selection-background-color: #3b82f6;
            }
        """)
        
        log_layout.addLayout(log_controls)
        log_layout.addWidget(self.log_display)
        log_group.setLayout(log_layout)
        
        main_layout.addWidget(log_group)
        
    def apply_styling(self):
        """Apply modern styling to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f1f5f9;
            }
            QGroupBox {
                font-weight: 600;
                font-size: 14px;
                border: 2px solid #e5e7eb;
                border-radius: 12px;
                margin-top: 1ex;
                padding-top: 12px;
                background-color: white;
                color: #374151;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                color: #1f2937;
                background-color: white;
            }
            QMenuBar {
                background-color: white;
                border-bottom: 1px solid #e5e7eb;
                padding: 4px;
            }
            QMenuBar::item {
                padding: 8px 12px;
                border-radius: 6px;
            }
            QMenuBar::item:selected {
                background-color: #f3f4f6;
            }
            QStatusBar {
                background-color: white;
                border-top: 1px solid #e5e7eb;
                color: #6b7280;
                font-size: 12px;
            }
        """)
        
    def setup_signals(self):
        """Connect signals to slots"""
        self.signals.new_log.connect(self.add_log_entry)
        self.signals.server_status_changed.connect(self.update_server_status)
        self.signals.server_started.connect(self.on_server_started)
        
    def setup_timer(self):
        """Setup timer for UI updates"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(350)  # Update every 350ms
        
    def start_server(self):
        """Start the HAMSTR server"""
        if self.server_running:
            return
            
        try:
            logging.info("Starting server from UI...")
            
            self.server_thread = ServerThread(self.signals)
            self.server_thread.start()
            
            self.server_running = True
            self.start_time = datetime.now()
            
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            
            self.status_bar.showMessage("Starting server...")
            logging.info("Server thread started successfully")
            
        except Exception as e:
            error_msg = f"Failed to start server: {str(e)}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            
    def stop_server(self):
        """Stop the HAMSTR server"""
        if not self.server_running:
            return
            
        try:
            logging.info("Stopping server from UI...")
            
            if self.server_thread:
                self.server_thread.stop_server()
                
            self.server_running = False
            self.start_time = None
            
            # Reset connection tracking
            self.connection_state = 'DISCONNECTED'
            self.connected_callsign = None
            self.current_activity = 'Idle'
            
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            
            self.status_bar.showMessage("Server stopped")
            logging.info("Server stopped successfully")
            
            # Update displays
            self.update_connection_display()
            self.update_activity_display()
            
        except Exception as e:
            error_msg = f"Error stopping server: {str(e)}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            
    def add_log_entry(self, timestamp, level, message):
        """Add a log entry to the display and parse for connection/activity updates"""
        try:
            # Parse the message for connection status and activity
            self.parse_log_for_status(message)
            
            # Filter based on debug mode
            if not self.debug_mode and level == 'DEBUG':
                return
                
            # Color coding with modern colors
            colors = {
                'ERROR': '#ef4444',
                'WARNING': '#f59e0b',
                'INFO': '#3b82f6',
                'DEBUG': '#6b7280'
            }
            color = colors.get(level, '#000000')
            
            # Format message with better styling
            if self.debug_mode:
                formatted_msg = f'<span style="color: {color}; font-weight: 500">[{timestamp}] [{level}]</span> <span style="color: #374151">{message}</span>'
            else:
                formatted_msg = f'<span style="color: {color}; font-weight: 500">[{timestamp}]</span> <span style="color: #374151">{message}</span>'
                
            self.log_display.append(formatted_msg)
            
            # Auto-scroll to bottom
            scrollbar = self.log_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
        except Exception as e:
            print(f"Error adding log entry: {e}")
            
    def parse_log_for_status(self, message):
        """Parse log messages to extract connection status and current activity"""
        msg_lower = message.lower()
        
        # Connection Status Parsing
        if 'received connect request from' in msg_lower:
            # Extract callsign from message like "Received CONNECT request from KK7AHK"
            match = re.search(r'from ([A-Z0-9]+)', message, re.IGNORECASE)
            if match:
                self.connected_callsign = f"{match.group(1)}-0"
                self.connection_state = 'CONNECTING'
                self.current_activity = f'Connecting to {self.connected_callsign}'
        
        elif 'connected to' in msg_lower:
            # Handle "CONNECTED to KK7AHK-0" messages
            match = re.search(r'connected to ([A-Z0-9]+-\d+)', message, re.IGNORECASE)
            if match:
                self.connected_callsign = match.group(1)
                self.connection_state = 'CONNECTED'
                self.current_activity = 'Connection established'
        
        elif 'handling session for' in msg_lower:
            self.connection_state = 'CONNECTED'
            self.current_activity = 'Session active'
            
        elif 'received disconnect message' in msg_lower:
            self.connection_state = 'DISCONNECTING'
            self.current_activity = 'Disconnecting...'
            
        elif 'session ended' in msg_lower:
            self.connection_state = 'DISCONNECTED'
            self.connected_callsign = None
            self.current_activity = 'Session closed'
        
        # Detailed Activity Parsing from the log flow
        
        # Initial connection handshake
        elif 'sending packet: type=connect_ack' in msg_lower:
            self.current_activity = 'Sending connection acknowledgment'
        elif 'received ack from' in msg_lower:
            self.current_activity = 'Connection confirmed'
            
        # Data request handling (client requesting from server)
        elif 'received data_request:' in message:
            # Extract request type like "GET_NOTES 1|1|..."
            if 'GET_NOTES' in message:
                self.current_activity = 'Received notes request'
            elif 'SEARCH' in message:
                self.current_activity = 'Received search request'
            else:
                self.current_activity = 'Processing data request'
        
        # Note publishing handling (client sending to server)
        elif 'received message: type=note' in msg_lower:
            # Extract packet info like "Seq=0001/0002"
            match = re.search(r'seq=(\d+)/(\d+)', message, re.IGNORECASE)
            if match:
                self.current_activity = f'Receiving note packet {match.group(1)}/{match.group(2)}'
        elif 'received packet' in msg_lower and 'for note' in msg_lower:
            # Extract packet progress like "Received packet 1/2 for NOTE"
            match = re.search(r'received packet (\d+)/(\d+) for note', message, re.IGNORECASE)
            if match:
                self.current_activity = f'Received note packet {match.group(1)}/{match.group(2)}'
        elif 'all note packets received' in msg_lower:
            self.current_activity = 'All note packets received'
        elif 'received done from client' in msg_lower:
            self.current_activity = 'Note transfer completed'
        elif 'processing received note' in msg_lower:
            self.current_activity = 'Processing received note'
        elif 'processing standard note type' in msg_lower:
            self.current_activity = 'Processing STANDARD note'
        elif 'nostr note received for publishing' in msg_lower:
            self.current_activity = 'Publishing note to NOSTR'
            
        # NOSTR operations
        elif 'getting following list for' in msg_lower:
            self.current_activity = 'Fetching following list'
        elif 'found' in msg_lower and 'followed accounts' in msg_lower:
            # Extract number like "Found 412 followed accounts"
            match = re.search(r'found (\d+) followed accounts', message, re.IGNORECASE)
            if match:
                self.current_activity = f'Found {match.group(1)} followed accounts'
        elif 'fetching notes from' in msg_lower and 'followed accounts' in msg_lower:
            match = re.search(r'fetching notes from (\d+)', message, re.IGNORECASE)
            if match:
                self.current_activity = f'Fetching notes from {match.group(1)} accounts'
        elif 'step 3: awaiting events' in msg_lower:
            self.current_activity = 'Awaiting NOSTR events'
        elif 'step 4: got events, processing' in msg_lower:
            self.current_activity = 'Processing received events'
        elif 'step 5: processing' in msg_lower and 'events' in msg_lower:
            match = re.search(r'processing (\d+) events', message, re.IGNORECASE)
            if match:
                self.current_activity = f'Processing {match.group(1)} events'
        elif 'processed event' in msg_lower:
            match = re.search(r'processed event (\d+)', message, re.IGNORECASE)
            if match:
                self.current_activity = f'Processed event {match.group(1)}'
        elif 'step 6: processed' in msg_lower and 'successfully' in msg_lower:
            self.current_activity = 'Events processed successfully'
        elif 'step 7: final formatted result' in msg_lower:
            self.current_activity = 'Formatting response'
            
        # Response transmission
        elif 'about to send response' in msg_lower:
            self.current_activity = 'Preparing to send response'
        elif 'sending packet: type=response, seq=' in msg_lower:
            # Extract packet progress like "Seq=1/2"
            match = re.search(r'seq=(\d+)/(\d+)', message, re.IGNORECASE)
            if match:
                self.current_activity = f'Sending response packet {match.group(1)}/{match.group(2)}'
        elif 'sent packet' in msg_lower and 'progress:' in msg_lower:
            # Extract progress like "Progress: 50.00%"
            match = re.search(r'progress: ([\d.]+)%', message, re.IGNORECASE)
            if match:
                progress = float(match.group(1))
                self.current_activity = f'Response transmission {progress:.0f}% complete'
        elif 'sending control message: done' in msg_lower:
            self.current_activity = 'Sending completion signal'
        elif 'response sent successfully' in msg_lower:
            self.current_activity = 'Response sent successfully'
            
        # Lightning/Zap operations
        elif 'zap request received' in msg_lower:
            self.current_activity = 'Processing Lightning zap'
        elif 'generating lightning invoice' in msg_lower:
            self.current_activity = 'Generating Lightning invoice'
        elif 'sending invoice' in msg_lower:
            self.current_activity = 'Sending Lightning invoice'
        elif 'payment received' in msg_lower:
            self.current_activity = 'Payment confirmed'
        elif 'publishing zap receipt' in msg_lower:
            self.current_activity = 'Publishing zap receipt'
            
        # Search operations
        elif 'search request:' in msg_lower:
            self.current_activity = 'Processing search request'
        elif 'searching nostr for' in msg_lower:
            self.current_activity = 'Searching NOSTR'
        elif 'search completed' in msg_lower:
            self.current_activity = 'Search completed'
            
        # Cleanup and reset
        elif 'resetting for next connection' in msg_lower:
            self.current_activity = 'Resetting for next connection'
        elif 'waiting for incoming connections' in msg_lower:
            if self.server_running and self.connection_state == 'DISCONNECTED':
                self.current_activity = 'Waiting for connections'
            
        # Error handling
        elif 'error' in msg_lower and 'handling' not in msg_lower:
            self.current_activity = 'Error occurred'
        elif 'failed' in msg_lower:
            self.current_activity = 'Operation failed'
        elif 'timeout' in msg_lower:
            self.current_activity = 'Connection timeout'
            
        # Update the UI immediately
        self.update_connection_display()
        self.update_activity_display()
        
    def update_connection_display(self):
        """Update connection status display with colors"""
        if self.connection_state == 'DISCONNECTED':
            self.connection_label.setText("Disconnected")
            self.connection_label.setStyleSheet("color: #ef4444; font-weight: 600; font-size: 14px;")
        elif self.connection_state == 'CONNECTING':
            if self.connected_callsign:
                self.connection_label.setText(f"Connecting to {self.connected_callsign}")
            else:
                self.connection_label.setText("Connecting...")
            self.connection_label.setStyleSheet("color: #f59e0b; font-weight: 600; font-size: 14px;")
        elif self.connection_state == 'CONNECTED':
            if self.connected_callsign:
                self.connection_label.setText(f"Connected to {self.connected_callsign}")
            else:
                self.connection_label.setText("Connected")
            self.connection_label.setStyleSheet("color: #10b981; font-weight: 600; font-size: 14px;")
        elif self.connection_state == 'DISCONNECTING':
            if self.connected_callsign:
                self.connection_label.setText(f"Disconnecting from {self.connected_callsign}")
            else:
                self.connection_label.setText("Disconnecting...")
            self.connection_label.setStyleSheet("color: #f59e0b; font-weight: 600; font-size: 14px;")
            
    def update_activity_display(self):
        """Update current activity display"""
        if not self.server_running:
            self.activity_label.setText("Server not running")
            self.activity_label.setStyleSheet("color: #6b7280; font-size: 14px;")
        else:
            self.activity_label.setText(self.current_activity)
            
            # Color code based on activity type
            if 'error' in self.current_activity.lower():
                color = '#ef4444'  # red
            elif any(word in self.current_activity.lower() for word in ['connecting', 'disconnecting', 'preparing']):
                color = '#f59e0b'  # orange
            elif any(word in self.current_activity.lower() for word in ['connected', 'ready', 'established']):
                color = '#10b981'  # green
            elif any(word in self.current_activity.lower() for word in ['sending', 'receiving', 'processing']):
                color = '#3b82f6'  # blue
            else:
                color = '#6b7280'  # gray
                
            self.activity_label.setStyleSheet(f"color: {color}; font-size: 14px;")
        
    def update_server_status(self, running):
        """Update server status display"""
        if running:
            self.status_label.setText("Server: Running")
            self.status_label.setStyleSheet("color: #10b981; font-weight: 600; font-size: 16px;")
            if self.connection_state == 'DISCONNECTED':
                self.current_activity = 'Waiting for connections'
        else:
            self.status_label.setText("Server: Stopped")
            self.status_label.setStyleSheet("color: #ef4444; font-weight: 600; font-size: 16px;")
            # Reset connection state when server stops
            self.connection_state = 'DISCONNECTED'
            self.connected_callsign = None
            self.current_activity = 'Idle'
            
        # Update displays
        self.update_connection_display()
        self.update_activity_display()
            
    def on_server_started(self):
        """Handle server started signal"""
        self.status_bar.showMessage("Server started successfully", 3000)
        self.signals.server_status_changed.emit(True)
        
    def update_ui(self):
        """Update UI elements periodically"""
        # Update uptime
        if self.start_time and self.server_running:
            uptime = datetime.now() - self.start_time
            uptime_str = str(uptime).split('.')[0]
            self.uptime_label.setText(f"Uptime: {uptime_str}")
        else:
            self.uptime_label.setText("Uptime: 00:00:00")
            
    def toggle_debug_mode(self, state):
        """Toggle debug mode"""
        self.debug_mode = state == Qt.CheckState.Checked.value
        self.clear_logs()
        logging.info(f"Debug mode {'enabled' if self.debug_mode else 'disabled'}")
        
    def clear_logs(self):
        """Clear the log display"""
        self.log_display.clear()
        logging.info("Logs cleared")
        
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Handle settings save
            self.status_bar.showMessage("Settings saved successfully", 3000)
            logging.info("Settings dialog saved")
            
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About HAMSTR", 
                         "HAMSTR Server Control Panel\n\n"
                         "NOSTR over Ham Radio\n"
                         "Version 1.0\n\n"
                         "Created by Liberty Farmer")
            
    def closeEvent(self, event):
        """Handle application close"""
        if self.server_running:
            reply = QMessageBox.question(self, 'Close Application', 
                                       'Server is running. Stop server and exit?',
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_server()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

def main():
    """Main entry point"""
    print("HAMSTR Server UI is Ready to go")
    
    app = QApplication(sys.argv)
    app.setApplicationName("HAMSTR Server Control")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("HAMSTR")
    
    # Remove deprecated high DPI settings - PySide6 handles this automatically
    
    window = HamstrServerGUI()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()