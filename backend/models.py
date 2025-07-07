from enum import Enum
import time


class MessageType(Enum):
    DATA_REQUEST = 1
    RESPONSE = 2
    ACK = 3
    CONNECT = 4
    CONNECT_ACK = 5
    DISCONNECT = 6
    KEEP_ALIVE = 7
    CONNECTION_EXPIRED = 8
    NOTIFICATION = 9
    READY = 10
    DONE = 11
    DONE_ACK = 12
    RETRY = 13
    PKT_MISSING = 14
    NOTE = 15
    ZAP_REQUEST = 16
    ZAP_RESPONSE = 17

# New SessionState enum
class SessionState(Enum):
    IDLE = 0
    CONNECTING = 1
    CONNECTED = 2
    DATA_PREP = 3
    SENDING = 4
    RECEIVING = 5
    ACKNOWLEDGING = 6
    ERROR = 7
    DISCONNECTING = 8
    DONE_ACK = 9
    DISCONNECTED = 10
    WAITING_FOR_MISSING = 11  

# Existing ModemState enum (keep this as is)
class ModemState(Enum):
    IDLE = 0
    CONNECTING = 1
    CONNECTED = 2
    DATA_PREP = 3
    SENDING = 4
    RECEIVING = 5
    ACKNOWLEDGING = 6
    ERROR = 7
    DISCONNECTING = 8
    DONE_ACK = 9
    DISCONNECTED = 10

#Note types to save bandwidth

class NoteType(Enum):
    STANDARD = 1  # Regular note
    REPLY = 2     # Direct reply 
    QUOTE = 3     # Quote reply
    REPOST = 4    # Boost/repost

#Request types to save bandwidth
class NoteRequestType(Enum):
    FOLLOWING = 1    # Get notes from following list
    SPECIFIC_USER = 2  # Current functionality - specific npub
    GLOBAL = 3      # Global feed
    SEARCH_TEXT = 4     # Search by text content
    SEARCH_HASHTAG = 5  # Search by hashtag
    SEARCH_USER = 6    # Search by npub/name
    TEST_ERROR = 99    # For testing error responses


# NWC Responses to save bandwidth
class NWCResponseCode(Enum):
    SUCCESS = 0
    INSUFFICIENT_BALANCE = 1  
    RECIPIENT_NOT_FOUND = 2
    INVOICE_EXPIRED = 3
    PAYMENT_TIMEOUT = 4
    WALLET_OFFLINE = 5
    AMOUNT_TOO_LOW = 6
    AMOUNT_TOO_HIGH = 7
    RATE_LIMITED = 8
    INVALID_RECIPIENT = 9
    
    # Only use double digits if we need more codes later
    NETWORK_ERROR = 10
    UNKNOWN_ERROR = 99

NWC_ERROR_MESSAGES = {
    NWCResponseCode.SUCCESS: {"text": "⚡ Zap sent successfully!", "type": "success"},
    NWCResponseCode.INSUFFICIENT_BALANCE: {"text": "❌ Insufficient wallet balance", "type": "error"},
    NWCResponseCode.RECIPIENT_NOT_FOUND: {"text": "❌ Recipient Lightning address not found", "type": "error"},
    NWCResponseCode.INVOICE_EXPIRED: {"text": "❌ Lightning invoice expired", "type": "error"},
    NWCResponseCode.PAYMENT_TIMEOUT: {"text": "❌ Payment timed out", "type": "error"},
    NWCResponseCode.WALLET_OFFLINE: {"text": "❌ Wallet is offline", "type": "error"},
    NWCResponseCode.AMOUNT_TOO_LOW: {"text": "❌ Amount too low (minimum required)", "type": "error"},
    NWCResponseCode.AMOUNT_TOO_HIGH: {"text": "❌ Amount exceeds maximum limit", "type": "error"},
    NWCResponseCode.RATE_LIMITED: {"text": "❌ Too many requests, try again later", "type": "error"},
    NWCResponseCode.INVALID_RECIPIENT: {"text": "❌ Invalid Lightning address", "type": "error"},
    NWCResponseCode.NETWORK_ERROR: {"text": "❌ Network connection error", "type": "error"},
    NWCResponseCode.UNKNOWN_ERROR: {"text": "❌ Zap failed (unknown error)", "type": "error"}
}

class Session:
    def __init__(self, session_id, remote_callsign):
        self.id = session_id
        self.remote_callsign = remote_callsign
        self.state = SessionState.IDLE
        self.modem_state = ModemState.IDLE
        self.last_activity = time.time()
        self.received_packets = {}
        self.expected_seq_num = 1
        self.total_packets = 0
        self.sent_packets = {}
        self.tnc_connection = None
        self.is_note_writing = False
        self.note_type = None  # Track type of note being sent
        self.reply_context = None  # Store note_id and pubkey for replies