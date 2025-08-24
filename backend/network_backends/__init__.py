"""
HAMSTR Network Backends Module

This module provides a modular backend system for different radio protocols.
Each backend implements the NetworkBackend interface while providing 
protocol-specific functionality.

Available Backends:
- PacketBackend: Full TNC packet system (wraps existing HAMSTR logic)
- VARABackend: VARA HF modem with KISS data transfer  
- ReticulumBackend: Reticulum mesh networking
- FLDIGIBackend: FLDIGI digital modes

Usage:
    from network_backends import NetworkBackendManager
    
    # Create backend manager (auto-detects from config)
    manager = NetworkBackendManager(config, is_server=False)
    
    # Connect and communicate
    session = manager.connect(('KK7AHK', 7))
    if session:
        manager.send_data(session, b"Hello World")
        response = manager.receive_data(session)
        manager.disconnect(session)
"""

__version__ = "1.0.0"
__author__ = "HAMSTR Development Team"

# Import main classes for easy access
from .base_backend import NetworkBackend, BackendType, BackendStatus
from .backend_factory import BackendFactory, create_backend_from_config
from .backend_manager import NetworkBackendManager

# Import and register available backends
try:
    from .packet_backend import PacketBackend
    PACKET_AVAILABLE = True
except ImportError as e:
    PACKET_AVAILABLE = False
    import logging
    logging.warning(f"[BACKENDS] PacketBackend not available: {e}")

# VARA Backend - NEW!
try:
    from .vara_backend import VARABackend
    VARA_AVAILABLE = True
except ImportError as e:
    VARA_AVAILABLE = False
    import logging
    logging.warning(f"[BACKENDS] VARABackend not available: {e}")

# Future backends - commented out until implemented
# try:
#     from .reticulum_backend import ReticulumBackend
#     RETICULUM_AVAILABLE = True
# except ImportError:
#     RETICULUM_AVAILABLE = False

# try:
#     from .fldigi_backend import FLDIGIBackend
#     FLDIGI_AVAILABLE = True
# except ImportError:
#     FLDIGI_AVAILABLE = False

# These will be uncommented as we add each backend
RETICULUM_AVAILABLE = False
FLDIGI_AVAILABLE = False

# Export main interface
__all__ = [
    'NetworkBackend',
    'BackendType', 
    'BackendStatus',
    'BackendFactory',
    'NetworkBackendManager',
    'create_backend_from_config'
]

def get_available_backends():
    """Get list of available backend types."""
    available = []
    if PACKET_AVAILABLE:
        available.append(BackendType.PACKET)
    if VARA_AVAILABLE:
        available.append(BackendType.VARA)
    if RETICULUM_AVAILABLE:
        available.append(BackendType.RETICULUM)
    if FLDIGI_AVAILABLE:
        available.append(BackendType.FLDIGI)
    return available

def get_backend_info():
    """Get information about backend availability."""
    return {
        'packet': PACKET_AVAILABLE,
        'vara': VARA_AVAILABLE, 
        'reticulum': RETICULUM_AVAILABLE,
        'fldigi': FLDIGI_AVAILABLE,
        'total_available': len(get_available_backends())
    }