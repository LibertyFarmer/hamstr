"""
Test script for the HAMSTR modular backend system.

This script helps verify that the backend system is working correctly
without affecting the existing HAMSTR functionality.

Usage:
    python test_backend_system.py [backend_type]
    
Examples:
    python test_backend_system.py legacy    # Test legacy mode
    python test_backend_system.py packet    # Test packet backend
"""

import sys
import os
import logging
import tempfile
import configparser

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def create_test_config(backend_type="legacy"):
    """Create a test configuration."""
    config = configparser.ConfigParser()
    
    # Basic sections
    config.add_section('NETWORK')
    config.set('NETWORK', 'backend_type', backend_type)
    
    config.add_section('TNC')
    config.set('TNC', 'connection_type', 'tcp')
    config.set('TNC', 'client_host', 'localhost')
    config.set('TNC', 'client_port', '8001')
    config.set('TNC', 'server_host', 'localhost') 
    config.set('TNC', 'server_port', '8002')
    
    config.add_section('RADIO')
    config.set('RADIO', 'client_callsign', '(TEST, 1)')
    config.set('RADIO', 'server_callsign', '(TEST, 2)')
    
    # VARA settings
    config.add_section('VARA')
    config.set('VARA', 'client_command_port', '8300')
    config.set('VARA', 'client_data_port', '8301')
    config.set('VARA', 'server_command_port', '8400')
    config.set('VARA', 'server_data_port', '8401')
    
    return config

def test_backend_imports():
    """Test that backend modules can be imported."""
    print("Testing backend imports...")
    
    try:
        from network_backends import NetworkBackendManager, BackendType, get_available_backends
        print("✅ Backend imports successful")
        
        available = get_available_backends()
        print(f"✅ Available backends: {[bt.value for bt in available]}")
        return True
        
    except ImportError as e:
        print(f"❌ Backend import failed: {e}")
        return False

def test_backend_factory():
    """Test backend factory functionality."""
    print("\nTesting backend factory...")
    
    try:
        from network_backends.backend_factory import BackendFactory, create_backend_from_config
        from network_backends.base_backend import BackendType
        
        # Test factory registry
        available_backends = BackendFactory.get_available_backends()
        print(f"✅ Factory has {len(available_backends)} registered backends")
        
        # Test parsing
        backend_type = BackendFactory.parse_backend_type("packet")
        print(f"✅ Parsed 'packet' as {backend_type}")
        
        return True
        
    except Exception as e:
        print(f"❌ Factory test failed: {e}")
        return False

def test_legacy_mode():
    """Test legacy mode functionality."""
    print("\nTesting legacy mode...")
    
    try:
        config = create_test_config("legacy")
        
        from network_backends import NetworkBackendManager
        
        manager = NetworkBackendManager(config, is_server=False)
        
        if manager.is_legacy_mode():
            print("✅ Legacy mode correctly detected")
            
            status = manager.get_status()
            print(f"✅ Legacy status: {status}")
            return True
        else:
            print("❌ Legacy mode not detected")
            return False
            
    except Exception as e:
        print(f"❌ Legacy mode test failed: {e}")
        return False

def test_packet_backend():
    """Test packet backend (if available)."""
    print("\nTesting packet backend...")
    
    try:
        config = create_test_config("packet")
        
        from network_backends import NetworkBackendManager
        from network_backends.base_backend import BackendType
        
        manager = NetworkBackendManager(config, is_server=False)
        
        if not manager.is_legacy_mode():
            print("✅ Packet backend mode detected")
            
            status = manager.get_status()
            print(f"✅ Packet backend status: {status}")
            
            # Test that it's the right type
            if status.get('backend_type') == 'packet':
                print("✅ Correct backend type")
                return True
            else:
                print(f"❌ Wrong backend type: {status.get('backend_type')}")
                return False
        else:
            print("❌ Packet backend not initialized")
            return False
            
    except Exception as e:
        print(f"❌ Packet backend test failed: {e}")
        return False

def test_core_integration():
    """Test Core class integration with backend system."""
    print("\nTesting Core integration...")
    
    try:
        # This would require the actual Core class and dependencies
        # For now, just test that the imports work
        
        # Simulate what Core would do
        config = create_test_config("legacy")
        
        # Test backend availability detection
        from network_backends import get_backend_info
        info = get_backend_info()
        print(f"✅ Backend info: {info}")
        
        return True
        
    except Exception as e:
        print(f"❌ Core integration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("HAMSTR Backend System Test")
    print("=" * 40)
    
    backend_type = sys.argv[1] if len(sys.argv) > 1 else "legacy"
    print(f"Testing with backend_type: {backend_type}")
    
    tests = [
        test_backend_imports,
        test_backend_factory,
        test_legacy_mode,
        test_core_integration
    ]
    
    # Add packet backend test if requested
    if backend_type == "packet":
        tests.append(test_packet_backend)
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Backend system is ready.")
        return 0
    else:
        print("❌ Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())