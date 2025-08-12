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
    else:  # For main settings.ini only
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
    SERVER_HOST = config.get('TNC','SERVER_HOST', fallback='localhost')

try:
    SERVER_PORT = server_config.getint('TNC', 'SERVER_PORT')
except:
    SERVER_PORT = config.getint('TNC', 'SERVER_PORT', fallback=8002)

try:
    S_CALLSIGN = parse_tuple(server_config.get('RADIO','SERVER_CALLSIGN'))
except:
    S_CALLSIGN = parse_tuple(config.get('RADIO','SERVER_CALLSIGN', fallback='(SERVER, 0)'))

# Shared settings from main config
RETRY_COUNT = config.getint('GENERAL','send_retries')
DISCONNECT_RETRY = config.getint('GENERAL', 'disconnect_retry')
ACK_TIMEOUT = config.getint('GENERAL','ack_timeout')
MAX_PACKET_SIZE = config.getint('GENERAL','max_packet_size')
CONNECTION_TIMEOUT = config.getint('GENERAL','connection_timeout')
KEEP_ALIVE_INTERVAL = config.getint('GENERAL','keep_alive_interval')
KEEP_ALIVE_RETRY_INTERVAL = config.getint('GENERAL','keep_alive_retry_interval')
KEEP_ALIVE_FINAL_INTERVAL = config.getint('GENERAL','keep_alive_final_interval')
CONNECTION_ATTEMPT_TIMEOUT = config.getint('GENERAL', 'connection_attempt_timeout')
SHUTDOWN_TIMEOUT = config.getint('GENERAL', 'shutdown_timeout')
PACKET_SEND_DELAY = config.getfloat('GENERAL', 'packet_send_delay')
DISCONNECT_TIMEOUT = config.getint('GENERAL', 'disconnect_timeout')
MISSING_PACKETS_TIMEOUT = config.getint('GENERAL', 'missing_packets_timeout')
BAUD_RATE = config.getint('GENERAL', 'baud_rate')
NO_ACK_TIMEOUT = config.getint('GENERAL', 'no_ack_timeout')
NO_PACKET_TIMEOUT = config.getint('GENERAL', 'no_packet_timeout')
READY_TIMEOUT = config.getint('GENERAL', 'ready_timeout')
MISSING_PACKETS_THRESHOLD = config.getfloat('GENERAL', 'missing_packets_threshold')
CONNECTION_STABILIZATION_DELAY = config.getfloat('GENERAL', 'connection_stabilization_delay')

# Get NOSTR relays
NOSTR_RELAYS = get_relay_list()

# Load PTT-specific settings with default values if not found
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