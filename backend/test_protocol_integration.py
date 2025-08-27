"""
Test script to verify protocol manager integration with Core
"""

import sys
import logging

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_core_protocol_manager():
    """Test Core class with protocol manager"""
    try:
        print("Testing Core class with protocol manager...")
        
        # Import and create Core instance
        from core import Core
        
        # Test client instance
        print("Creating client Core instance...")
        client_core = Core(is_server=False)
        
        # Check if protocol manager was created
        if hasattr(client_core, 'protocol_manager') and client_core.protocol_manager:
            protocol_type = client_core.protocol_manager.get_protocol_type()
            print(f"✅ Client protocol manager: {protocol_type}")
        else:
            print("❌ Client protocol manager not created")
        
        # Test server instance  
        print("Creating server Core instance...")
        server_core = Core(is_server=True)
        
        # Check if protocol manager was created
        if hasattr(server_core, 'protocol_manager') and server_core.protocol_manager:
            protocol_type = server_core.protocol_manager.get_protocol_type()
            print(f"✅ Server protocol manager: {protocol_type}")
        else:
            print("❌ Server protocol manager not created")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing Core: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_core_protocol_manager()