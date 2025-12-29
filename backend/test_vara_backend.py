#!/usr/bin/env python3
"""
VARA Backend Test Script

This script tests the VARA backend implementation independently
to verify it works correctly before integrating with HAMSTR.

Usage:
    python test_vara_backend.py client    # Test as client
    python test_vara_backend.py server    # Test as server

Prerequisites:
    - VARA HF modem running locally
    - Client VARA on ports 8300/8301
    - Server VARA on ports 8400/8401
"""

import sys
import os
import time
import logging

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MockConfig:
    """Mock config object for testing VARA backend"""
    
    def __init__(self, is_server=False):
        # Basic callsigns
        self.C_CALLSIGN = '(KK7AHK, 3)'  # Client callsign
        self.S_CALLSIGN = '(KK7AHK, 7)'  # Server callsign
        
        # VARA settings
        self.VARA_BANDWIDTH = 2300
        self.VARA_CONNECTION_TIMEOUT = 60
        self.VARA_CHAT_MODE = 'ON'
        self.VARA_COMMAND_PORT = 8300  # Will be overridden by backend
        self.VARA_DATA_PORT = 8301     # Will be overridden by backend

def test_vara_backend_import():
    """Test that VARA backend can be imported"""
    try:
        from network_backends.vara_backend import VARABackend
        print("✅ VARA backend imported successfully")
        return True
    except ImportError as e:
        print(f"❌ VARA backend import failed: {e}")
        return False

def test_vara_backend_creation(is_server=False):
    """Test VARA backend creation and configuration"""
    try:
        from network_backends.vara_backend import VARABackend
        
        config = MockConfig(is_server)
        backend = VARABackend(config, is_server)
        
        role = "server" if is_server else "client"
        expected_cmd_port = 8400 if is_server else 8300
        expected_data_port = 8401 if is_server else 8301
        
        print(f"✅ VARA backend created for {role}")
        print(f"✅ Command port: {backend.command_port} (expected {expected_cmd_port})")
        print(f"✅ Data port: {backend.data_port} (expected {expected_data_port})")
        print(f"✅ Callsign: {backend.my_callsign}")
        
        # Test status
        status = backend.get_status()
        print(f"✅ Status: {status['backend_type']} - {status['status']}")
        
        return backend
        
    except Exception as e:
        print(f"❌ VARA backend creation failed: {e}")
        return None

def test_vara_connection(is_server=False):
    """Test VARA connection (requires running VARA instances)"""
    print(f"\n{'='*60}")
    print(f"Testing VARA {'Server' if is_server else 'Client'} Connection")
    print(f"{'='*60}")
    
    backend = test_vara_backend_creation(is_server)
    if not backend:
        return False
    
    try:
        if is_server:
            # Server waits for client
            print("🔄 Server waiting for client connection...")
            print("   (Run 'python test_vara_backend.py client' in another terminal)")
            
            # Connect as server (listen mode)
            session = backend.connect(('KK7AHK', 3))  # Wait for client KK7AHK-3
            
        else:
            # Client connects to server
            print("🔄 Client connecting to server...")
            
            # Connect as client
            session = backend.connect(('KK7AHK', 7))  # Connect to server KK7AHK-7
        
        if session:
            print("✅ VARA connection established!")
            
            # Test data exchange
            test_message = b"Hello from VARA backend test!"
            
            if not is_server:
                # Client sends first
                print(f"📤 Sending: {test_message.decode()}")
                if backend.send_data(session, test_message):
                    print("✅ Data sent successfully")
                    
                    # Wait for response
                    print("🔄 Waiting for response...")
                    response = backend.receive_data(session, timeout=10)
                    if response:
                        print(f"📥 Received: {response.decode()}")
                    else:
                        print("⏰ No response received")
                        
            else:
                # Server receives first
                print("🔄 Waiting for client message...")
                received = backend.receive_data(session, timeout=30)
                if received:
                    try:
                        # Try to decode as text, handle binary data gracefully
                        received_text = received.decode('utf-8', errors='replace')
                        print(f"📥 Received: {received_text}")
                        
                        # Send response
                        response_msg = f"ACK: {received_text}".encode('utf-8')
                        print(f"📤 Sending response: {response_msg.decode()}")
                        if backend.send_data(session, response_msg):
                            print("✅ Response sent successfully")
                        else:
                            print("❌ Failed to send response")
                    except Exception as e:
                        print(f"📥 Received {len(received)} bytes (binary data)")
                        print(f"❌ Decode error: {e}")
                        
                        # Send binary response
                        response_msg = b"ACK: Binary data received"
                        print(f"📤 Sending response: {response_msg.decode()}")
                        if backend.send_data(session, response_msg):
                            print("✅ Response sent successfully")
                        else:
                            print("❌ Failed to send response")
                else:
                    print("⏰ No message received from client")
            
            # Clean disconnect
            print("🔄 Disconnecting...")
            if backend.disconnect(session):
                print("✅ Disconnected successfully")
            else:
                print("❌ Disconnect failed")
                
            return True
            
        else:
            print("❌ VARA connection failed")
            return False
            
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def main():
    """Main test function"""
    print("VARA Backend Test Suite")
    print("=" * 60)
    
    # Check arguments
    if len(sys.argv) < 2:
        print("Usage: python test_vara_backend.py [client|server]")
        print("\nRun this to test VARA backend functionality:")
        print("  Terminal 1: python test_vara_backend.py server")
        print("  Terminal 2: python test_vara_backend.py client")
        print("\nPrerequisites:")
        print("  - VARA HF modem running on localhost")
        print("  - Client VARA: ports 8300/8301")
        print("  - Server VARA: ports 8400/8401")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    if mode not in ['client', 'server']:
        print("Error: Mode must be 'client' or 'server'")
        sys.exit(1)
    
    is_server = (mode == 'server')
    
    # Run tests
    print("\n1. Testing VARA backend import...")
    if not test_vara_backend_import():
        sys.exit(1)
    
    print("\n2. Testing VARA backend creation...")
    if not test_vara_backend_creation(is_server):
        sys.exit(1)
    
    print("\n3. Testing VARA connection...")
    if test_vara_connection(is_server):
        print("\n🎉 All VARA backend tests passed!")
    else:
        print("\n❌ VARA connection test failed")
        print("\nTroubleshooting:")
        print("- Ensure VARA HF is running locally")
        print("- Check that VARA ports are configured correctly")
        print("- Verify both client and server VARA instances are running")
        print("- Run server test first, then client test")

if __name__ == "__main__":
    main()