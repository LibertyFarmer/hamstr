"""
Factory pattern for creating the appropriate network backend
based on configuration settings.
"""

import logging
from .base_backend import BackendType, NetworkBackend

# Import will be added as we create each backend
# from .packet_backend import PacketBackend
# from .vara_backend import VARABackend
# from .reticulum_backend import ReticulumBackend
# from .fldigi_backend import FLDIGIBackend

class BackendFactory:
    """
    Factory class for creating network backends based on configuration.
    
    This centralizes backend creation and ensures proper initialization
    of the correct backend type.
    """
    
    # Registry of available backends (will be populated as we create them)
    _backend_registry = {
        # BackendType.PACKET: PacketBackend,
        # BackendType.VARA: VARABackend,
        # BackendType.RETICULUM: ReticulumBackend,
        # BackendType.FLDIGI: FLDIGIBackend,
    }
    
    @staticmethod
    def create_backend(backend_type: BackendType, config, is_server: bool = False, core_instance=None) -> NetworkBackend:
        """
        Create and return the appropriate backend instance.
        
        Args:
            backend_type: Type of backend to create
            config: Configuration object
            is_server: Whether this is a server instance
            core_instance: Reference to Core instance (required for packet backend)
            
        Returns:
            Initialized backend instance
            
        Raises:
            ValueError: If backend type is not supported
            ImportError: If required backend module is not available
        """
        
        # Handle legacy mode (temporary during transition)
        if backend_type == BackendType.LEGACY:
            logging.info("[FACTORY] Legacy mode selected - using original system")
            return None  # Signal to use original system
        
        # Check if backend is registered
        if backend_type not in BackendFactory._backend_registry:
            available_types = list(BackendFactory._backend_registry.keys())
            raise ValueError(
                f"Backend type '{backend_type.value}' is not supported. "
                f"Available types: {[bt.value for bt in available_types]}"
            )
        
        # Get the backend class
        backend_class = BackendFactory._backend_registry[backend_type]
        
        try:
            # Create backend - pass core_instance for packet backend
            if backend_type == BackendType.PACKET:
                backend_instance = backend_class(config, is_server, core_instance)
            else:
                backend_instance = backend_class(config, is_server)
            
            logging.info(f"[FACTORY] Created {backend_type.value} backend "
                        f"for {'server' if is_server else 'client'}")
            return backend_instance
            
        except Exception as e:
            logging.error(f"[FACTORY] Failed to create {backend_type.value} backend: {e}")
            raise
    
    @staticmethod
    def register_backend(backend_type: BackendType, backend_class):
        """
        Register a new backend type.
        
        This allows for dynamic registration of backends as they're implemented.
        
        Args:
            backend_type: The backend type enum
            backend_class: The backend class to register
        """
        BackendFactory._backend_registry[backend_type] = backend_class
        logging.info(f"[FACTORY] Registered backend: {backend_type.value}")
    
    @staticmethod
    def get_available_backends():
        """
        Get list of available backend types.
        
        Returns:
            List of BackendType enums that are available
        """
        return list(BackendFactory._backend_registry.keys())
    
    @staticmethod
    def parse_backend_type(backend_type_str: str) -> BackendType:
        """
        Parse backend type from string configuration.
        
        Args:
            backend_type_str: String representation of backend type
            
        Returns:
            BackendType enum
            
        Raises:
            ValueError: If backend type string is invalid
        """
        backend_type_str = backend_type_str.lower().strip()
        
        try:
            return BackendType(backend_type_str)
        except ValueError:
            valid_types = [bt.value for bt in BackendType]
            raise ValueError(
                f"Invalid backend type '{backend_type_str}'. "
                f"Valid types: {valid_types}"
            )

# Helper function for easy backend creation from config
def create_backend_from_config(config_module, is_server: bool = False, core_instance=None) -> NetworkBackend:
    """
    Convenience function to create backend directly from HAMSTR config system.
    
    Args:
        config_module: HAMSTR config module (imports config.py)
        is_server: Whether this is a server instance
        core_instance: Reference to Core instance (required for packet backend)
        
    Returns:
        Initialized backend instance or None for legacy mode
    """
    # Read backend type from appropriate config based on client/server
    try:
        if is_server:
            # Server reads from server_config first, then main config
            if hasattr(config_module, 'server_config') and config_module.server_config.has_section('NETWORK'):
                backend_type_str = config_module.server_config.get('NETWORK', 'backend_type', fallback='legacy')
                logging.info(f"[FACTORY] Server using server_config: {backend_type_str}")
            else:
                backend_type_str = config_module.config.get('NETWORK', 'backend_type', fallback='legacy')
                logging.info(f"[FACTORY] Server using main config: {backend_type_str}")
        else:
            # Client reads from client_config first, then main config  
            if hasattr(config_module, 'client_config') and config_module.client_config.has_section('NETWORK'):
                backend_type_str = config_module.client_config.get('NETWORK', 'backend_type', fallback='legacy')
                logging.info(f"[FACTORY] Client using client_config: {backend_type_str}")
            else:
                backend_type_str = config_module.config.get('NETWORK', 'backend_type', fallback='legacy')
                logging.info(f"[FACTORY] Client using main config: {backend_type_str}")
    except Exception as e:
        # Show the actual error instead of hiding it
        logging.error(f"[FACTORY] Config reading error: {e}")
        import traceback
        logging.error(f"[FACTORY] Traceback: {traceback.format_exc()}")
        backend_type_str = 'legacy'
        logging.info("[FACTORY] Defaulting to legacy mode due to config error")
    
    backend_type = BackendFactory.parse_backend_type(backend_type_str)
    return BackendFactory.create_backend(backend_type, config_module, is_server, core_instance)