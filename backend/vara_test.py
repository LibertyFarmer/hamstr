import socket
import sys
import time
import logging
import threading
import queue

# Configure logging for timestamps
logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s', datefmt='%H:%M:%S')

try:
    from ax25_kiss_utils import build_ax25_frame, kiss_wrap, kiss_unwrap, decode_ax25_callsign
except ImportError:
    logging.error("Error: Could not import ax25_kiss_utils.py.")
    sys.exit(1)

# --- Configuration Based on VARA Documentation ---
KISS_HOST = '127.0.0.1'

# Client VARA instance
CLIENT_COMMAND_PORT = 8300
CLIENT_DATA_PORT = 8301  

# Server VARA instance  
SERVER_COMMAND_PORT = 8400
SERVER_DATA_PORT = 8401  # Different port to avoid conflict

SOURCE_CALL = ('KK7AHK', 3)
DESTINATION_CALL = ('KK7AHK', 7)

def send_simple_command(sock, command):
    """Send a simple command to VARA and get response."""
    try:
        sock.sendall((command + '\r').encode('ascii'))
        sock.settimeout(3)
        response = sock.recv(1024).decode('ascii', errors='ignore').strip()
        logging.info(f"Command: {command} -> Response: {response}")
        return response
    except Exception as e:
        logging.error(f"Error sending command '{command}': {e}")
        return None

def vara_client():
    """VARA client using correct port configuration."""
    logging.info("VARA Client - Correct Ports")
    logging.info("---------------------------")

    command_sock = None
    data_sock = None

    try:
        # 1. Connect to client command port and establish connection
        command_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        command_sock.connect((KISS_HOST, CLIENT_COMMAND_PORT))
        logging.info("Connected to client command port")

        # Setup and connect
        time.sleep(1)
        send_simple_command(command_sock, f"MYCALL {SOURCE_CALL[0]}-{SOURCE_CALL[1]}")
        send_simple_command(command_sock, "BW2300")
        send_simple_command(command_sock, "CHAT ON")
        send_simple_command(command_sock, f"CONNECT {SOURCE_CALL[0]}-{SOURCE_CALL[1]} {DESTINATION_CALL[0]}-{DESTINATION_CALL[1]}")

        # Wait for connection
        connected = False
        start_time = time.time()
        while time.time() - start_time < 60 and not connected:
            try:
                command_sock.settimeout(2)
                data = command_sock.recv(1024)
                if data:
                    messages = data.decode('ascii', errors='ignore').strip()
                    for line in messages.split('\r'):
                        line = line.strip()
                        if line and line.startswith("CONNECTED"):
                            connected = True
                            logging.info("*** CONNECTION ESTABLISHED! ***")
                            break
            except socket.timeout:
                continue

        if not connected:
            logging.error("Failed to establish connection")
            return

        # 2. Connect to the SHARED data port (8301)
        logging.info("Waiting 5 seconds before connecting to data port...")
        time.sleep(5)
        
        logging.info(f"Connecting to SHARED data port at {KISS_HOST}:{CLIENT_DATA_PORT}...")
        data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_sock.settimeout(10)
        data_sock.connect((KISS_HOST, CLIENT_DATA_PORT))
        logging.info("Connected to data port successfully!")

        # 3. Send messages with keepalive
        print("\n=== READY TO SEND MESSAGES ===")
        last_activity = time.time()
        
        while True:
            try:
                # Send keepalive every 30 seconds
                if time.time() - last_activity > 30:
                    keepalive_msg = "KEEPALIVE"
                    ax25_frame = build_ax25_frame(SOURCE_CALL, DESTINATION_CALL, keepalive_msg)
                    kiss_frame = kiss_wrap(ax25_frame)
                    data_sock.sendall(kiss_frame)
                    logging.info("*** SENT KEEPALIVE ***")
                    last_activity = time.time()
                
                message = input("Message: ").strip()
                if message.lower() == 'quit':
                    break
                
                if message:
                    # Send via KISS protocol
                    ax25_frame = build_ax25_frame(SOURCE_CALL, DESTINATION_CALL, message)
                    kiss_frame = kiss_wrap(ax25_frame)
                    data_sock.sendall(kiss_frame)
                    logging.info(f"*** SENT: '{message}' ({len(kiss_frame)} bytes via KISS) ***")
                    last_activity = time.time()
                    
                    # Monitor for response
                    try:
                        data_sock.settimeout(3)
                        response_data = data_sock.recv(1024)
                        if response_data:
                            # Process KISS response
                            ax25_response = kiss_unwrap(response_data)
                            if ax25_response:
                                response_msg = ax25_response[16:].decode('utf-8', 'ignore').strip()
                                logging.info(f"*** RECEIVED: '{response_msg}' ***")
                                last_activity = time.time()
                    except socket.timeout:
                        pass
                        
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Error: {e}")
                break

    except Exception as e:
        logging.error(f"Client error: {e}")
    finally:
        if data_sock:
            data_sock.close()
        if command_sock:
            try:
                send_simple_command(command_sock, "DISCONNECT")
            except:
                pass
            command_sock.close()

def vara_server():
    """VARA server using correct port configuration."""
    logging.info("VARA Server - Correct Ports")
    logging.info("---------------------------")

    command_sock = None
    data_sock = None

    try:
        # 1. Connect to server command port and setup listening
        command_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        command_sock.connect((KISS_HOST, SERVER_COMMAND_PORT))
        logging.info("Connected to server command port")

        # Setup
        time.sleep(1)
        send_simple_command(command_sock, f"MYCALL {DESTINATION_CALL[0]}-{DESTINATION_CALL[1]}")
        send_simple_command(command_sock, "BW2300")
        send_simple_command(command_sock, "LISTEN ON")
        
        logging.info("*** SERVER READY - LISTENING ***")

        # Wait for client connection
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
                            logging.info("*** CLIENT CONNECTED! ***")
                            break
            except socket.timeout:
                continue

        # 2. Connect to the SHARED data port (8301) AFTER client connects
        logging.info("Client connected! Connecting to shared data port...")
        time.sleep(2)  # Let connection stabilize
        
        data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_sock.settimeout(10)
        data_sock.connect((KISS_HOST, SERVER_DATA_PORT))
        logging.info("Connected to shared data port successfully!")

        # 3. Monitor for data with status reporting
        logging.info("*** MONITORING FOR DATA ***")
        buffer = b''
        connection_start_time = time.time()
        last_status_report = time.time()
        messages_received = 0
        messages_sent = 0
        
        while True:
            # Show status report every 2 minutes
            if time.time() - last_status_report > 120:  # 2 minutes
                session_time = int(time.time() - connection_start_time)
                minutes = session_time // 60
                seconds = session_time % 60
                
                print(f"\n{'='*50}")
                print(f"SERVER STATUS - {minutes:02d}:{seconds:02d}")
                print(f"Messages Received: {messages_received}")
                print(f"Messages Sent: {messages_sent}")
                print(f"Status: LISTENING/CONNECTED")
                print(f"{'='*50}\n")
                
                last_status_report = time.time()
            
            # Check for incoming KISS data
            try:
                data_sock.settimeout(1)
                chunk = data_sock.recv(1024)
                if chunk:
                    buffer += chunk
                    logging.info(f"*** RECEIVED {len(chunk)} bytes ***")
                    
                    # Process KISS frames
                    while b'\xc0' in buffer:
                        fend_start = buffer.find(b'\xc0')
                        fend_end = buffer.find(b'\xc0', fend_start + 1)
                        
                        if fend_end == -1:
                            break
                        
                        kiss_frame = buffer[fend_start:fend_end + 1]
                        buffer = buffer[fend_end + 1:]
                        
                        ax25_frame = kiss_unwrap(kiss_frame)
                        if ax25_frame:
                            source_callsign = decode_ax25_callsign(ax25_frame, 7)
                            message = ax25_frame[16:].decode('utf-8', 'ignore').strip()
                            
                            logging.info("=" * 60)
                            logging.info(f"*** MESSAGE RECEIVED ***")
                            logging.info(f"From: {source_callsign}")
                            logging.info(f"Message: '{message}'")
                            logging.info("=" * 60)
                            messages_received += 1
                            
                            # Send response
                            response_msg = f"ACK: {message}"
                            response_ax25 = build_ax25_frame(DESTINATION_CALL, SOURCE_CALL, response_msg)
                            response_kiss = kiss_wrap(response_ax25)
                            data_sock.sendall(response_kiss)
                            logging.info(f"*** SENT ACK: '{response_msg}' ***")
                            messages_sent += 1
                            
            except socket.timeout:
                pass
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Data error: {e}")
                break

            # Check command port for real disconnect events
            try:
                command_sock.settimeout(0.1)
                cmd_data = command_sock.recv(1024)
                if cmd_data:
                    status = cmd_data.decode('ascii', errors='ignore').strip()
                    for line in status.split('\r'):
                        line = line.strip()
                        if line and line.startswith("DISCONNECTED"):
                            logging.info("*** REAL DISCONNECTION DETECTED ***")
                            return
            except socket.timeout:
                pass

    except Exception as e:
        logging.error(f"Server error: {e}")
    finally:
        if data_sock:
            data_sock.close()
        if command_sock:
            command_sock.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "client":
        vara_client()
    else:
        vara_server()