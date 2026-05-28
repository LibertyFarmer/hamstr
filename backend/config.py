# config.py
# Role-based config loader. Set HAMSTR_ROLE env var before importing:
#   os.environ['HAMSTR_ROLE'] = 'client'  # in web_app.py
#   os.environ['HAMSTR_ROLE'] = 'server'  # in server_ui.py
# Each role reads only its own settings file. settings.ini is a silent
# read-only fallback for existing installs and will be removed in a future version.

import os
import pathlib
import configparser
import shutil
import logging
from typing import List

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_base = pathlib.Path(__file__).parent.absolute()
_data = _base / "data"

_client_ini   = _data / "client_settings.ini"
_client_tmpl  = _data / "client_settings.ini.template"
_server_ini   = _data / "server_settings.ini"
_server_tmpl  = _data / "server_settings.ini.template"
_legacy_ini   = _base / "settings.ini"   # read-only fallback, never written

# ---------------------------------------------------------------------------
# Auto-provision: copy template → ini on first run
# ---------------------------------------------------------------------------
for _ini, _tmpl in [(_client_ini, _client_tmpl), (_server_ini, _server_tmpl)]:
    if not _ini.exists():
        if _tmpl.exists():
            shutil.copy(_tmpl, _ini)
            logging.info(f"[CONFIG] Created {_ini.name} from template")
        else:
            _ini.touch()
            logging.warning(f"[CONFIG] Template missing, created empty {_ini.name}")

# ---------------------------------------------------------------------------
# Role detection
# ---------------------------------------------------------------------------
ROLE = os.environ.get('HAMSTR_ROLE', 'client')

# ---------------------------------------------------------------------------
# Load configs
# Each loads legacy settings.ini first (lower priority), then its own file
# (higher priority) so existing installs keep working during transition.
# ---------------------------------------------------------------------------
client_config = configparser.ConfigParser()
client_config.read([_legacy_ini, _client_ini])

server_config = configparser.ConfigParser()
server_config.read([_legacy_ini, _server_ini])

# Active config for this process
_cfg     = client_config if ROLE == 'client' else server_config
_ini_path = _client_ini  if ROLE == 'client' else _server_ini

# Legacy alias — some modules do `config.config.get(...)` after importing
config = _cfg

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _g(section, option, fallback=None, cast=str):
    """Get a value from the active config with a typed fallback."""
    try:
        raw = _cfg.get(section, option)
        if cast is bool:
            return raw.strip().lower() in ('true', '1', 'yes')
        return cast(raw)
    except Exception:
        return fallback


# ---------------------------------------------------------------------------
# GENERAL — packet protocol timing
# ---------------------------------------------------------------------------
ACK_TIMEOUT                  = _g('GENERAL', 'ack_timeout',                  15,   int)
SEND_RETRIES                 = _g('GENERAL', 'send_retries',                  3,    int)
DISCONNECT_RETRY             = _g('GENERAL', 'disconnect_retry',              1,    int)
MAX_PACKET_SIZE              = _g('GENERAL', 'max_packet_size',               200,  int)
CONNECTION_TIMEOUT           = _g('GENERAL', 'connection_timeout',            120,  int)
CONNECTION_ATTEMPT_TIMEOUT   = _g('GENERAL', 'connection_attempt_timeout',    10,   int)
KEEP_ALIVE_INTERVAL          = _g('GENERAL', 'keep_alive_interval',           20,   int)
KEEP_ALIVE_RETRY_INTERVAL    = _g('GENERAL', 'keep_alive_retry_interval',     5,    int)
KEEP_ALIVE_FINAL_INTERVAL    = _g('GENERAL', 'keep_alive_final_interval',     10,   int)
SHUTDOWN_TIMEOUT             = _g('GENERAL', 'shutdown_timeout',              20,   int)
PACKET_SEND_DELAY            = _g('GENERAL', 'packet_send_delay',             0.4,  float)
DISCONNECT_TIMEOUT           = _g('GENERAL', 'disconnect_timeout',            5,    int)
MISSING_PACKETS_TIMEOUT      = _g('GENERAL', 'missing_packets_timeout',       50,   int)
BAUD_RATE                    = _g('GENERAL', 'baud_rate',                     300,  int)
NO_ACK_TIMEOUT               = _g('GENERAL', 'no_ack_timeout',                40,   int)
NO_PACKET_TIMEOUT            = _g('GENERAL', 'no_packet_timeout',             50,   int)
MISSING_PACKETS_THRESHOLD    = _g('GENERAL', 'missing_packets_threshold',     0.5,  float)
READY_TIMEOUT                = _g('GENERAL', 'ready_timeout',                 20,   int)
CONNECTION_STABILIZATION_DELAY = _g('GENERAL', 'connection_stabilization_delay', 1.1, float)

# Extra GENERAL values read by various modules
CONNECT_ACK_TIMEOUT   = _g('GENERAL', 'connect_ack_timeout',   ACK_TIMEOUT, int)
MESSAGE_REQUEST_BUFFER = _g('GENERAL', 'message_request_buffer', 5,          int)
PACKET_RESEND_DELAY   = _g('GENERAL', 'packet_resend_delay',    0.3,        float)

# Backward-compat alias
RETRY_COUNT = SEND_RETRIES

# ---------------------------------------------------------------------------
# PTT (legacy packet PTT timing)
# ---------------------------------------------------------------------------
PTT_TX_DELAY   = _g('PTT', 'tx_delay',    0.25, float)
PTT_RX_DELAY   = _g('PTT', 'rx_delay',    0.25, float)
PTT_TAIL       = _g('PTT', 'ptt_tail',    0.1,  float)
PTT_ACK_SPACING = _g('PTT', 'ack_spacing', 0.5,  float)

# ---------------------------------------------------------------------------
# NETWORK — backend selection
# ---------------------------------------------------------------------------
BACKEND_TYPE = _g('NETWORK', 'backend_type', 'packet')

# ---------------------------------------------------------------------------
# TNC / RADIO (client-side names)
# ---------------------------------------------------------------------------
CONNECTION_TYPE = _g('TNC', 'connection_type', 'tcp')
SERIAL_PORT     = _g('TNC', 'serial_port',     'COM3')
SERIAL_SPEED    = _g('TNC', 'serial_speed',    57600, int)

# Client TNC address
CLIENT_HOST = _g('TNC', 'client_host', 'localhost')
CLIENT_PORT = _g('TNC', 'client_port', 8001, int)

# Server TNC address (read by server-side networking code)
SERVER_HOST = _g('TNC', 'server_host', 'localhost')
SERVER_PORT = _g('TNC', 'server_port', 8002, int)

# Server TNC serial (uppercase keys from server template)
SERVER_CONNECTION_TYPE = _g('TNC', 'connection_type', 'tcp')
SERVER_SERIAL_PORT     = _g('TNC', 'serial_port',     'COM3')
SERVER_SERIAL_SPEED    = _g('TNC', 'serial_speed',    57600, int)

# ---------------------------------------------------------------------------
# Callsigns
# ---------------------------------------------------------------------------
def parse_tuple(raw: str):
    """Parse '(CALLSIGN, SSID)' → (str, int). Returns ('', 0) on failure."""
    try:
        parts = raw.strip().strip('()').split(',')
        return parts[0].strip(), int(parts[1].strip())
    except Exception:
        return '', 0

def _callsign(section, option, fallback='(CALLSIGN, 0)'):
    raw = _g(section, option, fallback)
    return parse_tuple(raw)

C_CALLSIGN   = _callsign('RADIO', 'client_callsign')
HAMSTR_SERVER = _callsign('RADIO', 'hamstr_server',   '(SERVER, 0)')
S_CALLSIGN   = _callsign('RADIO', 'server_callsign',  '(SERVER, 0)')

# ---------------------------------------------------------------------------
# NOSTR
# ---------------------------------------------------------------------------
DEFAULT_NOTE_REQUEST_COUNT = _g('NOSTR', 'default_note_request_count', 2, int)

def get_relay_list() -> List[str]:
    """Return relay list from active config."""
    raw = _g('NOSTR', 'relays', 'wss://relay.nostr.band/,wss://relay.damus.io')
    return [r.strip() for r in raw.split(',') if r.strip()]

NOSTR_RELAYS = get_relay_list()

# ---------------------------------------------------------------------------
# VARA
# ---------------------------------------------------------------------------
VARA_HOST               = _g('VARA', 'vara_host',           '127.0.0.1')
VARA_BANDWIDTH          = _g('VARA', 'bandwidth',            2300, int)
VARA_ARQ_TIMEOUT        = _g('VARA', 'arq_timeout',          60,   int)
VARA_CHAT_MODE          = _g('VARA', 'chat_mode',            'ON')
VARA_CONNECTION_TIMEOUT = _g('VARA', 'connection_timeout',   30,   int)
VARA_TEST_MODE          = _g('VARA', 'vara_test_mode',       False, bool)

# Port numbers — each template already has the correct defaults per role
VARA_COMMAND_PORT = _g('VARA', 'command_port', 8300 if ROLE == 'client' else 8400, int)
VARA_DATA_PORT    = _g('VARA', 'data_port',    8301 if ROLE == 'client' else 8401, int)

# Convenience aliases used by existing code
CLIENT_VARA_COMMAND_PORT = VARA_COMMAND_PORT if ROLE == 'client' else _g('VARA', 'command_port', 8300, int)
CLIENT_VARA_DATA_PORT    = VARA_DATA_PORT    if ROLE == 'client' else _g('VARA', 'data_port',    8301, int)
SERVER_VARA_COMMAND_PORT = VARA_COMMAND_PORT if ROLE == 'server' else _g('VARA', 'command_port', 8400, int)
SERVER_VARA_DATA_PORT    = VARA_DATA_PORT    if ROLE == 'server' else _g('VARA', 'data_port',    8401, int)

# PTT — read from active config; both CLIENT_ and SERVER_ aliases point to same values
_VARA_USE_PTT         = _g('VARA', 'use_ptt',          True,    bool)
_VARA_PTT_PORT        = _g('VARA', 'ptt_serial_port',  'COM3')
_VARA_PTT_BAUD        = _g('VARA', 'ptt_serial_baud',  38400,   int)
_VARA_PTT_METHOD      = _g('VARA', 'ptt_method',       'BOTH')
_VARA_PRE_PTT_DELAY   = _g('VARA', 'pre_ptt_delay',    0.1,     float)
_VARA_POST_PTT_DELAY  = _g('VARA', 'post_ptt_delay',   0.1,     float)

CLIENT_VARA_USE_PTT         = _VARA_USE_PTT
CLIENT_VARA_PTT_SERIAL_PORT = _VARA_PTT_PORT
CLIENT_VARA_PTT_SERIAL_BAUD = _VARA_PTT_BAUD
CLIENT_VARA_PTT_METHOD      = _VARA_PTT_METHOD
CLIENT_VARA_PRE_PTT_DELAY   = _VARA_PRE_PTT_DELAY
CLIENT_VARA_POST_PTT_DELAY  = _VARA_POST_PTT_DELAY

SERVER_VARA_USE_PTT         = _VARA_USE_PTT
SERVER_VARA_PTT_SERIAL_PORT = _VARA_PTT_PORT
SERVER_VARA_PTT_SERIAL_BAUD = _VARA_PTT_BAUD
SERVER_VARA_PTT_METHOD      = _VARA_PTT_METHOD
SERVER_VARA_PRE_PTT_DELAY   = _VARA_PRE_PTT_DELAY
SERVER_VARA_POST_PTT_DELAY  = _VARA_POST_PTT_DELAY

# ---------------------------------------------------------------------------
# RETICULUM
# ---------------------------------------------------------------------------
RETICULUM_CONFIG_DIR         = _g('RETICULUM', 'reticulum_config_dir', None)
RETICULUM_SERVER_CONFIG_DIR  = RETICULUM_CONFIG_DIR   # same file per role

RETICULUM_HAMSTR_SERVER_HASH   = _g('RETICULUM', 'hamstr_server_hash',   None)
RETICULUM_HAMSTR_SERVER_PUBKEY = _g('RETICULUM', 'hamstr_server_pubkey', None)
RETICULUM_HAMSTR_SERVER_GRID   = _g('RETICULUM', 'hamstr_server_grid',   None)
RETICULUM_CONNECTION_TIMEOUT   = _g('RETICULUM', 'connection_timeout',   60,    int)
RETICULUM_KEEPALIVE_INTERVAL   = _g('RETICULUM', 'keepalive_interval',   0,     int)

RETICULUM_SERVER_GRID          = _g('RETICULUM', 'server_grid',          None)
RETICULUM_ANNOUNCE_INTERVAL    = _g('RETICULUM', 'announce_interval',    21600, int)

# ---------------------------------------------------------------------------
# FLDIGI
# ---------------------------------------------------------------------------
FLDIGI_HOST = _g('FLDIGI', 'fldigi_host', 'localhost')
FLDIGI_PORT = _g('FLDIGI', 'fldigi_port', 7342 if ROLE == 'client' else 7343, int)

# ---------------------------------------------------------------------------
# Config update — writes to the role-appropriate file only
# ---------------------------------------------------------------------------
def _write(ini_path: pathlib.Path, section: str, option: str, value: str):
    """Read → modify → write a single settings file."""
    cfg = configparser.ConfigParser()
    cfg.read(ini_path)
    if not cfg.has_section(section):
        cfg.add_section(section)
    cfg.set(section, option.lower(), str(value))
    with open(ini_path, 'w') as f:
        cfg.write(f)

def update_client_config(section: str, option: str, value):
    _write(_client_ini, section, option, str(value))

def update_server_config(section: str, option: str, value):
    _write(_server_ini, section, option, str(value))

def update_config(section: str, option: str, value):
    """Backward-compat: writes to the active role's settings file."""
    _write(_ini_path, section, option, str(value))

def reload_config():
    """Re-read the active ini file into the active ConfigParser."""
    _cfg.read([_legacy_ini, _ini_path])