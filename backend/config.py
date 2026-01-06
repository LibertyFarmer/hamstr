# config.py - Updated to handle NETWORK section and backend settings
import pathlib
import configparser
from typing import List

config_path = pathlib.Path(__file__).parent.absolute() / "settings.ini"
client_callsign_path = pathlib.Path(__file__).parent.absolute() / "data/client_settings.ini"
server_callsign_path = pathlib.Path(__file__).parent.absolute() / "data/server_settings.ini"

config = configparser.ConfigParser()
config.read([config_path, client_callsign_path, server_callsign_path])

server_config = configparser.ConfigParser()
server_config.read([config_path, server_callsign_path])

client_config = configparser.ConfigParser()
client_config.read([config_path, client_callsign_path])

def update_config(section, option, value):
    """Update the settings in the appropriate INI file."""
    
    if section == 'RADIO':
        if option == 'client_callsign' or option == 'CLIENT_CALLSIGN':
            # Handle client callsign - route to client_settings.ini
            config_to_update = configparser.ConfigParser()
            config_to_update.read(client_callsign_path)
            if not config_to_update.has_section('RADIO'):
                config_to_update.add_section('RADIO')
            config_to_update.set(section, 'client_callsign', str(value))
            with open(client_callsign_path, 'w') as f:
                config_to_update.write(f)
        elif option == 'hamstr_server' or option == 'HAMSTR_SERVER':
            # Handle target server callsign - route to client_settings.ini
            config_to_update = configparser.ConfigParser()
            config_to_update.read(client_callsign_path)
            if not config_to_update.has_section('RADIO'):
                config_to_update.add_section('RADIO')
            config_to_update.set(section, 'hamstr_server', str(value))
            with open(client_callsign_path, 'w') as f:
                config_to_update.write(f)
        elif option == 'SERVER_CALLSIGN':
            # Handle server callsign - route to server_settings.ini
            config_to_update = configparser.ConfigParser()
            config_to_update.read(server_callsign_path)
            if not config_to_update.has_section('RADIO'):
                config_to_update.add_section('RADIO')
            config_to_update.set(section, option, str(value))
            with open(server_callsign_path, 'w') as f:
                config_to_update.write(f)
    elif section == 'TNC':
        if option.startswith('CLIENT_') or option in ['client_host', 'client_port'] or option in ['connection_type', 'serial_port', 'serial_speed']:
            # Handle client TNC settings - route to client_settings.ini
            config_to_update = configparser.ConfigParser()
            config_to_update.read(client_callsign_path)
            if not config_to_update.has_section('TNC'):
                config_to_update.add_section('TNC')
            
            # Always convert to lowercase for storage (except serial settings)
            if option == 'client_host' or option == 'CLIENT_HOST':
                lower_option = 'client_host'
            elif option == 'client_port' or option == 'CLIENT_PORT':
                lower_option = 'client_port'
            elif option in ['connection_type', 'serial_port', 'serial_speed']:
                lower_option = option  # Keep as-is for new serial settings
            else:
                lower_option = option.lower()
                
            config_to_update.set(section, lower_option, str(value))
            with open(client_callsign_path, 'w') as f:
                config_to_update.write(f)
        elif option.startswith('SERVER_') or option in ['server_host', 'server_port', 'CONNECTION_TYPE', 'SERIAL_PORT', 'SERIAL_SPEED']:
            # Handle server TNC settings - route to server_settings.ini
            config_to_update = configparser.ConfigParser()
            config_to_update.read(server_callsign_path)
            if not config_to_update.has_section('TNC'):
                config_to_update.add_section('TNC')
            config_to_update.set(section, option, str(value))
            with open(server_callsign_path, 'w') as f:
                config_to_update.write(f)
    elif section == 'NETWORK':
        # NEW: Handle backend settings - route based on specific settings
        if option == 'backend_type':
            # Backend type goes to main settings.ini (shared setting)
            main_config = configparser.ConfigParser()
            main_config.read(config_path)
            if not main_config.has_section('NETWORK'):
                main_config.add_section('NETWORK')
            main_config.set(section, option, str(value))
            with open(config_path, 'w') as f:
                main_config.write(f)
        else:
            # Other NETWORK settings might be client/server specific in the future
            # For now, put them in main settings.ini
            main_config = configparser.ConfigParser()
            main_config.read(config_path)
            if not main_config.has_section('NETWORK'):
                main_config.add_section('NETWORK')
            main_config.set(section, option, str(value))
            with open(config_path, 'w') as f:
                main_config.write(f)
    elif section in ['VARA', 'RETICULUM', 'FLDIGI']:
        # NEW: Handle backend-specific settings - go to main settings.ini for now
        # Future: might split these between client/server configs
        main_config = configparser.ConfigParser()
        main_config.read(config_path)
        if not main_config.has_section(section):
            main_config.add_section(section)
        main_config.set(section, option, str(value))
        with open(config_path, 'w') as f:
            main_config.write(f)
    elif section == 'NOSTR':
        if option == 'RELAYS':
            # Handle NOSTR RELAYS - route to server_settings.ini
            config_to_update = configparser.ConfigParser()
            config_to_update.read(server_callsign_path)
            if not config_to_update.has_section('NOSTR'):
                config_to_update.add_section('NOSTR')
            config_to_update.set(section, option, str(value))
            with open(server_callsign_path, 'w') as f:
                config_to_update.write(f)
        elif option == 'DEFAULT_NOTE_REQUEST_COUNT' or option == 'default_note_request_count':
            # Handle client NOSTR settings - route to client_settings.ini
            config_to_update = configparser.ConfigParser()
            config_to_update.read(client_callsign_path)
            if not config_to_update.has_section('NOSTR'):
                config_to_update.add_section('NOSTR')
            config_to_update.set(section, 'default_note_request_count', str(value))
            with open(client_callsign_path, 'w') as f:
                config_to_update.write(f)
        else:
            # Other NOSTR settings go to main settings.ini
            main_config = configparser.ConfigParser()
            main_config.read(config_path)
            if not main_config.has_section(section):
                main_config.add_section(section)
            main_config.set(section, option, str(value))
            with open(config_path, 'w') as f:
                main_config.write(f)
    else:  # For main settings.ini only (GENERAL, PTT, etc.)
        # Only read and update the main settings file
        main_config = configparser.ConfigParser()
        main_config.read(config_path)
        if not main_config.has_section(section):
            main_config.add_section(section)
        main_config.set(section, option, str(value))
        with open(config_path, 'w') as f:
            main_config.write(f)

def parse_tuple(input):
    # Remove parentheses and split by comma
    parts = input.strip('()').split(',')
    if len(parts) != 2:
        return '', 0  # Default values if parsing fails
    callsign = parts[0].strip()
    try:
        ssid = int(parts[1].strip())
    except ValueError:
        ssid = 0  # Default to 0 if SSID is not a valid integer
    return callsign, ssid

def get_relay_list() -> List[str]:
    """Get list of relays from server config."""
    try:
        relay_string = server_config.get('NOSTR', 'RELAYS')
        return [relay.strip() for relay in relay_string.split(',')]
    except:
        # Fallback to main config if server config doesn't have relays
        try:
            relay_string = config.get('NOSTR', 'relays')
            return [relay.strip() for relay in relay_string.split(',')]
        except:
            return []

# General settings
try:
    SEND_RETRIES = config.getint('GENERAL', 'send_retries')
except (configparser.NoSectionError, configparser.NoOptionError):
    SEND_RETRIES = 3  # Default retries

try:
    DISCONNECT_RETRY = config.getint('GENERAL', 'disconnect_retry')
except (configparser.NoSectionError, configparser.NoOptionError):
    DISCONNECT_RETRY = 1  # Default disconnect retry

try:
    ACK_TIMEOUT = config.getint('GENERAL', 'ack_timeout')
except (configparser.NoSectionError, configparser.NoOptionError):
    ACK_TIMEOUT = 15  # Default ACK timeout in seconds

try:
    MAX_PACKET_SIZE = config.getint('GENERAL', 'max_packet_size')
except (configparser.NoSectionError, configparser.NoOptionError):
    MAX_PACKET_SIZE = 200  # Default max packet size in bytes

try:
    CONNECTION_TIMEOUT = config.getint('GENERAL', 'connection_timeout')
except (configparser.NoSectionError, configparser.NoOptionError):
    CONNECTION_TIMEOUT = 95  # Default connection timeout in seconds

try:
    CONNECTION_ATTEMPT_TIMEOUT = config.getint('GENERAL', 'connection_attempt_timeout')
except (configparser.NoSectionError, configparser.NoOptionError):
    CONNECTION_ATTEMPT_TIMEOUT = 10  # Default connection attempt timeout in seconds

try:
    KEEP_ALIVE_INTERVAL = config.getint('GENERAL', 'keep_alive_interval')
except (configparser.NoSectionError, configparser.NoOptionError):
    KEEP_ALIVE_INTERVAL = 20  # Default keep-alive interval in seconds

try:
    KEEP_ALIVE_RETRY_INTERVAL = config.getint('GENERAL', 'keep_alive_retry_interval')
except (configparser.NoSectionError, configparser.NoOptionError):
    KEEP_ALIVE_RETRY_INTERVAL = 5  # Default keep-alive retry interval in seconds

try:
    KEEP_ALIVE_FINAL_INTERVAL = config.getint('GENERAL', 'keep_alive_final_interval')
except (configparser.NoSectionError, configparser.NoOptionError):
    KEEP_ALIVE_FINAL_INTERVAL = 10  # Default final keep-alive interval in seconds

try:
    SHUTDOWN_TIMEOUT = config.getint('GENERAL', 'shutdown_timeout')
except (configparser.NoSectionError, configparser.NoOptionError):
    SHUTDOWN_TIMEOUT = 20  # Default shutdown timeout in seconds

try:
    PACKET_SEND_DELAY = config.getfloat('GENERAL', 'packet_send_delay')
except (configparser.NoSectionError, configparser.NoOptionError):
    PACKET_SEND_DELAY = 0.4  # Default packet send delay in seconds

try:
    DISCONNECT_TIMEOUT = config.getint('GENERAL', 'disconnect_timeout')
except (configparser.NoSectionError, configparser.NoOptionError):
    DISCONNECT_TIMEOUT = 5  # Default disconnect timeout in seconds

try:
    MISSING_PACKETS_TIMEOUT = config.getint('GENERAL', 'missing_packets_timeout')
except (configparser.NoSectionError, configparser.NoOptionError):
    MISSING_PACKETS_TIMEOUT = 50  # Default missing packets timeout in seconds

try:
    BAUD_RATE = config.getint('GENERAL', 'baud_rate')
except (configparser.NoSectionError, configparser.NoOptionError):
    BAUD_RATE = 300  # Default baud rate

try:
    NO_ACK_TIMEOUT = config.getint('GENERAL', 'no_ack_timeout')
except (configparser.NoSectionError, configparser.NoOptionError):
    NO_ACK_TIMEOUT = 40  # Default no ACK timeout in seconds

try:
    NO_PACKET_TIMEOUT = config.getint('GENERAL', 'no_packet_timeout')
except (configparser.NoSectionError, configparser.NoOptionError):
    NO_PACKET_TIMEOUT = 50  # Default no packet timeout in seconds

try:
    MISSING_PACKETS_THRESHOLD = config.getfloat('GENERAL', 'missing_packets_threshold')
except (configparser.NoSectionError, configparser.NoOptionError):
    MISSING_PACKETS_THRESHOLD = 0.5  # Default missing packets threshold

try:
    READY_TIMEOUT = config.getint('GENERAL', 'ready_timeout')
except (configparser.NoSectionError, configparser.NoOptionError):
    READY_TIMEOUT = 20  # Default READY timeout in seconds

try:
    CONNECTION_STABILIZATION_DELAY = config.getfloat('GENERAL', 'connection_stabilization_delay')
except (configparser.NoSectionError, configparser.NoOptionError):
    CONNECTION_STABILIZATION_DELAY = 1.0  # Default stabilization delay in seconds

# PTT settings
try:
    PTT_TX_DELAY = config.getfloat('PTT', 'tx_delay')
except (configparser.NoSectionError, configparser.NoOptionError):
    PTT_TX_DELAY = 0.25  # Default TX delay in seconds

try:
    PTT_RX_DELAY = config.getfloat('PTT', 'rx_delay')
except (configparser.NoSectionError, configparser.NoOptionError):
    PTT_RX_DELAY = 0.25  # Default RX delay in seconds

try:
    PTT_TAIL = config.getfloat('PTT', 'ptt_tail')
except (configparser.NoSectionError, configparser.NoOptionError):
    PTT_TAIL = 0.1  # Default PTT tail in seconds

try:
    PTT_ACK_SPACING = config.getfloat('PTT', 'ack_spacing')
except (configparser.NoSectionError, configparser.NoOptionError):
    PTT_ACK_SPACING = 0.5  # Default ACK spacing in seconds

# Add fallback values for any settings that may be missing
try:
    CONNECT_ACK_TIMEOUT = config.getint('GENERAL', 'connect_ack_timeout')
except (configparser.NoSectionError, configparser.NoOptionError):
    CONNECT_ACK_TIMEOUT = ACK_TIMEOUT  # Use ACK_TIMEOUT as fallback

try:
    MESSAGE_REQUEST_BUFFER = config.getint('GENERAL', 'message_request_buffer')
except (configparser.NoSectionError, configparser.NoOptionError):
    MESSAGE_REQUEST_BUFFER = 5  # Default buffer

try:
    PACKET_RESEND_DELAY = config.getfloat('GENERAL', 'packet_resend_delay')
except (configparser.NoSectionError, configparser.NoOptionError):
    PACKET_RESEND_DELAY = 0.3  # Default resend delay

# Backward compatibility alias
RETRY_COUNT = SEND_RETRIES

# Get NOSTR relays
NOSTR_RELAYS = get_relay_list()

# Force reload client config to get latest values
client_config.read([config_path, client_callsign_path])

# Client TNC connection settings
try:
    CONNECTION_TYPE = client_config.get('TNC', 'connection_type')
except:
    CONNECTION_TYPE = 'tcp'  # Default to TCP

try:
    SERIAL_PORT = client_config.get('TNC', 'serial_port')
except:
    SERIAL_PORT = 'COM3'  # Default Windows port

try:
    SERIAL_SPEED = client_config.getint('TNC', 'serial_speed')
except:
    SERIAL_SPEED = 57600  # Default baud rate

# Client settings from client_config
try:
    CLIENT_HOST = client_config.get('TNC','client_host')
except:
    CLIENT_HOST = config.get('TNC','client_host', fallback='localhost')

try:
    CLIENT_PORT = client_config.getint('TNC','client_port')
except:
    CLIENT_PORT = config.getint('TNC','client_port', fallback=8001)

try:
    C_CALLSIGN = parse_tuple(client_config.get('RADIO','client_callsign'))
except:
    C_CALLSIGN = parse_tuple(config.get('RADIO','client_callsign', fallback='(CALLSIGN, 0)'))

try:
    HAMSTR_SERVER = parse_tuple(client_config.get('RADIO','hamstr_server'))
except:
    HAMSTR_SERVER = ('SERVER', 0)  # Default only - no fallback to server settings

try:
    DEFAULT_NOTE_REQUEST_COUNT = client_config.getint('NOSTR', 'default_note_request_count')
except:
    DEFAULT_NOTE_REQUEST_COUNT = config.getint('NOSTR', 'default_note_request_count', fallback=1)

# Server TNC connection settings
try:
    SERVER_CONNECTION_TYPE = server_config.get('TNC', 'CONNECTION_TYPE')
except:
    SERVER_CONNECTION_TYPE = 'tcp'  # Default to TCP

try:
    SERVER_SERIAL_PORT = server_config.get('TNC', 'SERIAL_PORT')
except:
    SERVER_SERIAL_PORT = 'COM3'  # Default Windows port

try:
    SERVER_SERIAL_SPEED = server_config.getint('TNC', 'SERIAL_SPEED')
except:
    SERVER_SERIAL_SPEED = 57600  # Default baud rate

# Server settings from server_config
try:
    SERVER_HOST = server_config.get('TNC','SERVER_HOST')
except:
    SERVER_HOST = config.get('TNC','server_host', fallback='localhost')

try:
    SERVER_PORT = server_config.getint('TNC','SERVER_PORT')
except:
    SERVER_PORT = config.getint('TNC','server_port', fallback=8002)

try:
    S_CALLSIGN = parse_tuple(server_config.get('RADIO','SERVER_CALLSIGN'))
except:
    S_CALLSIGN = parse_tuple(config.get('RADIO','server_callsign', fallback='(SERVER, 0)'))

# NEW: Backend system configuration
try:
    # Try client config first, then server config, then main config
    BACKEND_TYPE = None
    if hasattr(client_config, 'has_section') and client_config.has_section('NETWORK'):
        BACKEND_TYPE = client_config.get('NETWORK', 'backend_type', fallback=None)
    
    if not BACKEND_TYPE and hasattr(server_config, 'has_section') and server_config.has_section('NETWORK'):
        BACKEND_TYPE = server_config.get('NETWORK', 'backend_type', fallback=None)
    
    if not BACKEND_TYPE:
        BACKEND_TYPE = config.get('NETWORK', 'backend_type', fallback='legacy')
        
except:
    BACKEND_TYPE = 'legacy'  # Safe default

# NEW: VARA settings (with safe defaults)
try:
    VARA_BANDWIDTH = config.getint('VARA', 'bandwidth', fallback=2300)
    VARA_ARQ_TIMEOUT = config.getint('VARA', 'arq_timeout', fallback=60)
    VARA_CHAT_MODE = config.get('VARA', 'chat_mode', fallback='ON')
    VARA_CONNECTION_TIMEOUT = config.getint('VARA', 'connection_timeout', fallback=30)
    VARA_HOST = config.get('VARA', 'vara_host', fallback='127.0.0.1')
except:
    # Fallback values if VARA section doesn't exist
    VARA_BANDWIDTH = 2300
    VARA_ARQ_TIMEOUT = 60
    VARA_CHAT_MODE = 'ON'
    VARA_CONNECTION_TIMEOUT = 30
    VARA_HOST = '127.0.0.1'

# VARA PTT settings - SEPARATE for client and server
# Client PTT settings
try:
    CLIENT_VARA_USE_PTT = client_config.getboolean('VARA', 'use_ptt', fallback=True)
except:
    CLIENT_VARA_USE_PTT = True

try:
    CLIENT_VARA_PTT_SERIAL_PORT = client_config.get('VARA', 'ptt_serial_port', fallback='COM10')
except:
    CLIENT_VARA_PTT_SERIAL_PORT = 'COM10'

try:
    CLIENT_VARA_PTT_SERIAL_BAUD = client_config.getint('VARA', 'ptt_serial_baud', fallback=38400)
except:
    CLIENT_VARA_PTT_SERIAL_BAUD = 38400

try:
    CLIENT_VARA_PTT_METHOD = client_config.get('VARA', 'ptt_method', fallback='BOTH')
except:
    CLIENT_VARA_PTT_METHOD = 'BOTH'

try:
    CLIENT_VARA_PRE_PTT_DELAY = client_config.getfloat('VARA', 'pre_ptt_delay', fallback=0.1)
except:
    CLIENT_VARA_PRE_PTT_DELAY = 0.1

try:
    CLIENT_VARA_POST_PTT_DELAY = client_config.getfloat('VARA', 'post_ptt_delay', fallback=0.1)
except:
    CLIENT_VARA_POST_PTT_DELAY = 0.1

# Server PTT settings
try:
    SERVER_VARA_USE_PTT = server_config.getboolean('VARA', 'use_ptt', fallback=True)
except:
    SERVER_VARA_USE_PTT = True

try:
    SERVER_VARA_PTT_SERIAL_PORT = server_config.get('VARA', 'ptt_serial_port', fallback='COM11')
except:
    SERVER_VARA_PTT_SERIAL_PORT = 'COM11'

try:
    SERVER_VARA_PTT_SERIAL_BAUD = server_config.getint('VARA', 'ptt_serial_baud', fallback=38400)
except:
    SERVER_VARA_PTT_SERIAL_BAUD = 38400

try:
    SERVER_VARA_PTT_METHOD = server_config.get('VARA', 'ptt_method', fallback='BOTH')
except:
    SERVER_VARA_PTT_METHOD = 'BOTH'

try:
    SERVER_VARA_PRE_PTT_DELAY = server_config.getfloat('VARA', 'pre_ptt_delay', fallback=0.1)
except:
    SERVER_VARA_PRE_PTT_DELAY = 0.1

try:
    SERVER_VARA_POST_PTT_DELAY = server_config.getfloat('VARA', 'post_ptt_delay', fallback=0.1)
except:
    SERVER_VARA_POST_PTT_DELAY = 0.1

# NEW: Reticulum settings (with safe defaults)
try:
    RETICULUM_INTERFACE_TYPE = config.get('RETICULUM', 'interface_type', fallback='kiss')
    RETICULUM_KISS_PORT = config.getint('RETICULUM', 'kiss_port', fallback=7300)
    RETICULUM_KISS_HOST = config.get('RETICULUM', 'kiss_host', fallback='localhost')
    RETICULUM_CONFIG_PATH = config.get('RETICULUM', 'reticulum_config_path', fallback='~/.reticulum')
    RETICULUM_ANNOUNCE_INTERVAL = config.getint('RETICULUM', 'announce_interval', fallback=300)
    RETICULUM_HOP_COUNT = config.getint('RETICULUM', 'hop_count', fallback=4)
    RETICULUM_IDENTITY_FILE = config.get('RETICULUM', 'identity_file', fallback='reticulum_identity')
except:
    # Fallback values if RETICULUM section doesn't exist
    RETICULUM_INTERFACE_TYPE = 'kiss'
    RETICULUM_KISS_PORT = 7300
    RETICULUM_KISS_HOST = 'localhost'
    RETICULUM_CONFIG_PATH = '~/.reticulum'
    RETICULUM_ANNOUNCE_INTERVAL = 300
    RETICULUM_HOP_COUNT = 4
    RETICULUM_IDENTITY_FILE = 'reticulum_identity'

# NEW: FLDIGI settings (with safe defaults)
try:
    FLDIGI_KISS_PORT = config.getint('FLDIGI', 'kiss_port', fallback=7342)
    FLDIGI_MODE = config.get('FLDIGI', 'mode', fallback='psk31')
    FLDIGI_ARQ_ENABLED = config.getboolean('FLDIGI', 'arq_enabled', fallback=False)
    FLDIGI_TIMING_MULTIPLIER = config.getfloat('FLDIGI', 'timing_multiplier', fallback=2.0)
    FLDIGI_CONNECTION_TIMEOUT = config.getint('FLDIGI', 'connection_timeout', fallback=45)
except:
    # Fallback values if FLDIGI section doesn't exist
    FLDIGI_KISS_PORT = 7342
    FLDIGI_MODE = 'psk31'
    FLDIGI_ARQ_ENABLED = False
    FLDIGI_TIMING_MULTIPLIER = 2.0
    FLDIGI_CONNECTION_TIMEOUT = 45