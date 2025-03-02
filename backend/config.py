import pathlib
import configparser
from typing import List

config_path = pathlib.Path(__file__).parent.absolute() / "settings.ini"
client_callsign_path = pathlib.Path(__file__).parent.absolute() / "data/client_settings.ini"
server_callsign_path = pathlib.Path(__file__).parent.absolute() / "data/server_settings.ini"

config = configparser.ConfigParser()
config.read([config_path, client_callsign_path, server_callsign_path])

def update_config(section, option, value):
    """Update the settings in the appropriate INI file."""
    config.read(config_path)  # Always read settings.ini first

    if section == 'RADIO':
        if option == 'client_callsign':
            config_to_update = configparser.ConfigParser()
            config_to_update.read(client_callsign_path)
            config_to_update.set(section, option, str(value))
            with open(client_callsign_path, 'w') as f:
                config_to_update.write(f)
        elif option == 'server_callsign':
            config_to_update = configparser.ConfigParser()
            config_to_update.read(server_callsign_path)
            config_to_update.set(section, option, str(value))
            with open(server_callsign_path, 'w') as f:
                config_to_update.write(f)
        # Remove the [RADIO] section from settings.ini
        if config.has_section('RADIO'):
            config.remove_section('RADIO')
            with open(config_path, 'w') as f:
                config.write(f)
    else:  # For sections other than 'RADIO'
        config.set(section, option, str(value))
        with open(config_path, 'w') as f:
            config.write(f)

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

# Add new settings for relays list - server only pull in future!
def get_relay_list() -> List[str]:
    """Get list of relays from config."""
    relay_string = config.get('NOSTR', 'relays')
    return [relay.strip() for relay in relay_string.split(',')]

#Import from settings here:

CLIENT_HOST = config.get('TNC','CLIENT_HOST')
CLIENT_PORT = config.getint('TNC','CLIENT_PORT')
SERVER_HOST = config.get('TNC','SERVER_HOST')
SERVER_PORT = config.getint('TNC','SERVER_PORT')
C_CALLSIGN = parse_tuple(config.get('RADIO','CLIENT_CALLSIGN'))
S_CALLSIGN = parse_tuple(config.get('RADIO','SERVER_CALLSIGN'))
RETRY_COUNT = config.getint('GENERAL','SEND_RETRIES')
DISCONNECT_RETRY = config.getint('GENERAL', 'DISCONNECT_RETRY')
ACK_TIMEOUT = config.getint('GENERAL','ACK_TIMEOUT')
MAX_PACKET_SIZE = config.getint('GENERAL','MAX_PACKET_SIZE')
CONNECTION_TIMEOUT = config.getint('GENERAL','CONNECTION_TIMEOUT')
KEEP_ALIVE_INTERVAL = config.getint('GENERAL','KEEP_ALIVE_INTERVAL')
KEEP_ALIVE_RETRY_INTERVAL = config.getint('GENERAL','KEEP_ALIVE_RETRY_INTERVAL')
KEEP_ALIVE_FINAL_INTERVAL = config.getint('GENERAL','KEEP_ALIVE_FINAL_INTERVAL')
CONNECTION_ATTEMPT_TIMEOUT = config.getint('GENERAL', 'CONNECTION_ATTEMPT_TIMEOUT')
SHUTDOWN_TIMEOUT = config.getint('GENERAL', 'SHUTDOWN_TIMEOUT')
PACKET_SEND_DELAY = config.getfloat('GENERAL', 'PACKET_SEND_DELAY')
DISCONNECT_TIMEOUT = config.getint('GENERAL', 'DISCONNECT_TIMEOUT')
DISCONNECT_TIMEOUT = config.getint('GENERAL', 'DISCONNECT_TIMEOUT')
MISSING_PACKETS_TIMEOUT = config.getint('GENERAL', 'MISSING_PACKETS_TIMEOUT')
BAUD_RATE = config.getint('GENERAL', 'BAUD_RATE')
NO_ACK_TIMEOUT = config.getint('GENERAL', 'NO_ACK_TIMEOUT')
NO_PACKET_TIMEOUT = config.getint('GENERAL', 'NO_PACKET_TIMEOUT')
READY_TIMEOUT = config.getint('GENERAL', 'ready_timeout')
MISSING_PACKETS_THRESHOLD = config.getfloat('GENERAL', 'MISSING_PACKETS_THRESHOLD')
DEFAULT_NOTE_REQUEST_COUNT = config.getint('NOSTR', 'DEFAULT_NOTE_REQUEST_COUNT')
NOSTR_RELAYS = get_relay_list()
CONNECTION_STABILIZATION_DELAY = config.getfloat('GENERAL', 'CONNECTION_STABILIZATION_DELAY')