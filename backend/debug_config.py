#!/usr/bin/env python3
"""
Debug script to check how config is structured and what BACKEND_TYPE is set to.
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

def debug_config():
    """Debug the config system to see why NETWORK section isn't found"""
    
    try:
        import config
        
        print("=== CONFIG DEBUG ===")
        print(f"BACKEND_TYPE attribute: {getattr(config, 'BACKEND_TYPE', 'NOT FOUND')}")
        
        # Check if config has the ConfigParser objects
        if hasattr(config, 'config'):
            print(f"Main config object exists: {type(config.config)}")
            if config.config.has_section('NETWORK'):
                print("✅ Main config has NETWORK section")
                backend_type = config.config.get('NETWORK', 'backend_type', fallback='NOT FOUND')
                print(f"Main config backend_type: {backend_type}")
            else:
                print("❌ Main config missing NETWORK section")
                print(f"Available sections: {config.config.sections()}")
        
        if hasattr(config, 'server_config'):
            print(f"Server config object exists: {type(config.server_config)}")
            if config.server_config.has_section('NETWORK'):
                print("✅ Server config has NETWORK section")
                backend_type = config.server_config.get('NETWORK', 'backend_type', fallback='NOT FOUND')
                print(f"Server config backend_type: {backend_type}")
            else:
                print("❌ Server config missing NETWORK section")
                print(f"Server available sections: {config.server_config.sections()}")
        
        if hasattr(config, 'client_config'):
            print(f"Client config object exists: {type(config.client_config)}")
            if config.client_config.has_section('NETWORK'):
                print("✅ Client config has NETWORK section")
                backend_type = config.client_config.get('NETWORK', 'backend_type', fallback='NOT FOUND')
                print(f"Client config backend_type: {backend_type}")
            else:
                print("❌ Client config missing NETWORK section")
                print(f"Client available sections: {config.client_config.sections()}")
        
        # Test direct attribute access (what the current code expects)
        print(f"\nDirect attribute access:")
        print(f"config.BACKEND_TYPE = {getattr(config, 'BACKEND_TYPE', 'NOT FOUND')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Config debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_config()