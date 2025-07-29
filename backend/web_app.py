import config
import threading
import sqlite3
import json
import time
import uuid
import os
import logging
import importlib
from models import NoteRequestType, NoteType, MessageType, ZapType
from protocol_utils import compress_nostr_data, decompress_nostr_data, parse_callsign
from socketio_logger import init_socketio, get_socketio_logger
from nostr_sdk import Keys, EventId, EventBuilder, Tag, Kind 
from nsec_storage import NSECStorage
from nwc_storage import NWCStorage
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from client import Client


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), 'frontend', 'build')

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
socketio = init_socketio(app)
nsec_storage = NSECStorage(BASE_DIR)
nwc_storage = NWCStorage(BASE_DIR)

#initiate radio process lock
radio_lock = threading.Lock()
radio_operation_in_progress = False


# Initialize Client()
client = Client(BASE_DIR)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
socketio_logger = get_socketio_logger()

# Setup db init on app startup

def init_db():
    db_path = os.path.join(BASE_DIR, 'data', 'notes.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS notes
                     (id TEXT PRIMARY KEY,
                      content TEXT,
                      created_at INTEGER,
                      pubkey TEXT,
                      display_name TEXT,
                      lud16 TEXT,
                      is_local INTEGER,
                      stored_at INTEGER)''')
        conn.commit()
    except Exception as e:
        socketio_logger.error(f"[DATABASE] Error initializing database: {e}")
    finally:
        conn.close()

# Call the initialize database function at startup!!
init_db()


# API Routes
@app.route('/api/notes')
def get_notes():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    notes = get_notes_from_db(page, limit)
    response = jsonify(notes)
    socketio_logger.info(f"[API] Returning notes response: {response.get_data(as_text=True)}")
    return response


def get_notes_from_db(page=1, limit=10):
    offset = (page - 1) * limit
    db_path = os.path.join(BASE_DIR, 'data', 'notes.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # First get total count
    c.execute("SELECT COUNT(*) FROM notes WHERE is_local = 0")
    total_count = c.fetchone()[0]
    
    # Then get paginated results
    c.execute("""
        SELECT id, content, created_at, pubkey, display_name, lud16, is_local 
        FROM notes 
        WHERE is_local = 0 
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    """, (limit, offset))
    
    notes = c.fetchall()
    conn.close()
    
    has_more = (offset + limit) < total_count
    
    return {
        "notes": [{
            "id": note[0],
            "content": note[1],
            "created_at": note[2],
            "pubkey": note[3],
            "display_name": note[4],
            "lud16": note[5],
            "formatted_date": datetime.fromtimestamp(note[2]).strftime('%Y-%m-%d %H:%M:%S')
        } for note in notes],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_count,
            "has_more": has_more
        }
    }

def check_radio_status(operation_type):
    global radio_operation_in_progress
    if radio_operation_in_progress:
        socketio_logger.error(f"[CLIENT] Failed to {operation_type} - radio operation in progress")
        return True
    return False

@app.route('/api/send_note', methods=['POST'])
def send_note():
    global radio_operation_in_progress
    
    if radio_operation_in_progress:
        socketio_logger.info("[SYSTEM] Cannot send note - radio operation in progress")
        return jsonify({
            "success": False, 
            "message": "Cannot send note - radio operation in progress"
        }), 500

    try:
        data = request.get_json()
        socketio_logger.info("[DEBUG] Parsed JSON data: %s", data)
    except Exception as e:
        socketio_logger.error("[DEBUG] JSON parse error: %s", str(e))
        return jsonify({
            "success": False,
            "message": "Invalid request format"
        }), 400

    content = data.get('content', '')
    hashtags = data.get('hashtags', [])
    note_type = NoteType(data.get('note_type', NoteType.STANDARD.value))
    
    try:
        nsec = nsec_storage.get_nsec()
        if not nsec:
            socketio_logger.error("[CLIENT] No NSEC available - please set up NOSTR key first")
            return jsonify({
                "success": False,
                "message": "NSEC key not found. Please set up your NOSTR key first."
            }), 400
            
        socketio_logger.info("[CLIENT] Creating signed note...")
        keys = Keys.parse(nsec)
        
        # Create tags array
        tags = []
        
        # Add hashtags if present
        for hashtag in hashtags:
            tag = Tag.parse(["t", hashtag])
            tags.append(tag)
            
        # Handle different note types
        if note_type == NoteType.REPOST:
            if not data.get('repost_id'):
                return jsonify({
                    "success": False,
                    "message": "Repost requires note ID"
                }), 400
                
            if not data.get('repost_pubkey'):
                return jsonify({
                    "success": False,
                    "message": "Repost requires author's pubkey"
                }), 400
                
            # Add e-tag for reposted note
            e_tag = Tag.parse(["e", data['repost_id']])
            tags.append(e_tag)
            
            # Add p-tag for original author
            p_tag = Tag.parse(["p", data['repost_pubkey']])
            tags.append(p_tag)
            
            # Use Kind 6 for reposts
            builder = EventBuilder(
                kind=Kind(6),
                content=content,
                tags=tags
            )
            
        elif note_type == NoteType.QUOTE:
            if not data.get('reply_to'):
                return jsonify({
                    "success": False,
                    "message": "Quote requires note ID"
                }), 400
                    
            if not data.get('reply_pubkey'):
                return jsonify({
                    "success": False,
                    "message": "Quote requires author's pubkey"
                }), 400

            try:
                # Convert hex note ID to proper bech32 format
                event_id = EventId.from_hex(data['reply_to'])
                note_bech32 = event_id.to_bech32()
                
                # Add the bech32 reference to the existing content
                content = content + f"\nnostr:{note_bech32}"
                socketio_logger.info(f"[CLIENT] Quote content formatted: {content}")
                
                # Add quote-specific tags
                e_tag = Tag.parse(["e", data['reply_to'], "", "mention"])
                q_tag = Tag.parse(["q", data['reply_to']])  # Add q tag for explicit quote
                p_tag = Tag.parse(["p", data['reply_pubkey'], "", "mention"])
                tags.extend([e_tag, p_tag, q_tag])

                builder = EventBuilder(
                    kind=Kind(1),
                    content=content,
                    tags=tags
                )
            except Exception as e:
                socketio_logger.error(f"[CLIENT] Error processing quote: {str(e)}")
                return jsonify({
                    "success": False,
                    "message": f"Error formatting quote: {str(e)}"
                }), 500
                    
        elif note_type == NoteType.REPLY:
            if not data.get('reply_to'):
                return jsonify({
                    "success": False,
                    "message": "Reply requires note ID"
                }), 400
                
            if not data.get('reply_pubkey'):
                return jsonify({
                    "success": False,
                    "message": "Reply requires author's pubkey"
                }), 400
            
            # Add e-tag with NIP-10 reply marker
            e_tag = Tag.parse(["e", data['reply_to'], "", "reply"])
            tags.append(e_tag)
            
            # Add p-tag for the original note's author
            p_tag = Tag.parse(["p", data['reply_pubkey']])
            tags.append(p_tag)
            
            builder = EventBuilder(
                kind=Kind(1),
                content=content,
                tags=tags
            )
            
        else:
            # Standard note
            builder = EventBuilder(
                kind=Kind(1),
                content=content,
                tags=tags
            )

        signed_note = builder.to_event(keys)
        note_json = signed_note.as_json()
        
        compressed_note = compress_nostr_data(note_json)
        socketio_logger.info("[CLIENT] Note compressed, preparing to send")
        result_container = []
        def send_note_thread():
            global radio_operation_in_progress
            with radio_lock:
                radio_operation_in_progress = True
                try:
                    success = client.connect_and_send_note(config.S_CALLSIGN, compressed_note)
                    result_container.append(success)
                finally:
                    radio_operation_in_progress = False

        thread = threading.Thread(target=send_note_thread)
        thread.start()
        thread.join(timeout=config.CONNECTION_TIMEOUT)

        if thread.is_alive():
            socketio_logger.error("[CLIENT] Failed to send note - operation timed out")
            return jsonify({
                "success": False, 
                "message": "Failed to connect to TNC - operation timed out"
            }), 500

        if not result_container or not result_container[0]:
            socketio_logger.error("[CLIENT] Failed to send note - TNC connection failed")
            return jsonify({
                "success": False,
                "message": "Failed to connect to TNC"
            }), 500

        return jsonify({
            "success": True,
            "message": "Note sent successfully"
        }), 200

    except Exception as e:
        socketio_logger.error(f"[SYSTEM] Error signing/sending note: {e}")
        return jsonify({
            "success": False,
            "message": f"Error processing note: {str(e)}"
        }), 500

@app.route('/request_notes/<int:count>', methods=['POST'])
def request_notes(count):
    global radio_operation_in_progress
    
    if check_radio_status("request notes"):
        return jsonify({
            "success": False, 
            "message": "Failed to request notes - radio operation in progress"
        }), 500
        
    ALLOWED_REQUEST_TYPES = {
        NoteRequestType.SPECIFIC_USER.value,
        NoteRequestType.FOLLOWING.value,
        NoteRequestType.GLOBAL.value,
        NoteRequestType.SEARCH_TEXT.value,
        NoteRequestType.SEARCH_HASHTAG.value,
        NoteRequestType.SEARCH_USER.value
    }

    try:
        nsec = nsec_storage.get_nsec()
        if not nsec:
            socketio_logger.error("[CLIENT] NSEC key not found")
            return jsonify({
                "success": False,
                "message": "NSEC key not found. Please set up your NOSTR key first."
            }), 400
            
        keys = Keys.parse(nsec)
        own_pubkey = keys.public_key().to_hex()
        
        request_data = request.get_json()
        request_type_value = request_data.get('requestType', NoteRequestType.SPECIFIC_USER.value)
        search_text = request_data.get('searchText', '')
        
        if request_type_value not in ALLOWED_REQUEST_TYPES:
            socketio_logger.error(f"[SYSTEM] Invalid request type: {request_type_value}")
            return jsonify({
                "success": False,
                "message": "Invalid request type"
            }), 400
            
        request_type = NoteRequestType(request_type_value)
        
        # Determine additional parameters based on request type
        if request_type == NoteRequestType.SPECIFIC_USER:
            additional_params = own_pubkey
            socketio_logger.info(f"[SYSTEM] Requesting own notes using pubkey: {own_pubkey}")
        elif request_type == NoteRequestType.FOLLOWING:
            additional_params = own_pubkey
            socketio_logger.info(f"[SYSTEM] Requesting following feed for pubkey: {own_pubkey}")
        elif request_type in [NoteRequestType.SEARCH_USER, NoteRequestType.SEARCH_TEXT, NoteRequestType.SEARCH_HASHTAG]:
            additional_params = search_text
            socketio_logger.info(f"[SYSTEM] Requesting {request_type.name} search for term: {search_text}")
        else:  # GLOBAL
            additional_params = None
            socketio_logger.info("[SYSTEM] Requesting global feed")

        # Calculate a dynamic timeout based on the number of notes requested
        # More notes = longer timeout
        dynamic_timeout = max(config.CONNECTION_TIMEOUT, count * 60)  # At least 60s per note
        
        # Store original timeout to restore later
        original_timeout = config.CONNECTION_TIMEOUT
        # Temporarily override the timeout
        config.CONNECTION_TIMEOUT = dynamic_timeout
        
        socketio_logger.info(f"[SYSTEM] Using extended timeout of {dynamic_timeout} seconds for {count} notes")
        
        result_container = []
        def request_notes_thread():
            global radio_operation_in_progress
            with radio_lock:
                radio_operation_in_progress = True
                try:
                    success, response = client.connect_and_send_request(
                        config.S_CALLSIGN, 
                        request_type,
                        count,
                        additional_params=additional_params
                    )
                    result_container.append((success, response))
                finally:
                    radio_operation_in_progress = False
                    # Restore original timeout
                    config.CONNECTION_TIMEOUT = original_timeout

        thread = threading.Thread(target=request_notes_thread)
        thread.start()
        thread.join(timeout=dynamic_timeout + 30)  # Allow extra time for thread cleanup

        if thread.is_alive():
            # Thread is still running after timeout
            socketio_logger.error("[CLIENT] Request timeout")
            # Restore original timeout
            config.CONNECTION_TIMEOUT = original_timeout
            return jsonify({
                "success": False,
                "message": "Failed to connect to TNC - operation timed out"
            }), 500

        if not result_container:
            socketio_logger.error("[CLIENT] Failed to connect to TNC")
            return jsonify({
                "success": False,
                "message": "Failed to connect to TNC"
            }), 500

        success, response = result_container[0]
        if not success:
            return jsonify({
                "success": False,
                "message": "Failed to connect to TNC"
            }), 500

        if response:
            try:
                # Decompress the response
                decompressed_response = decompress_nostr_data(response)
                response_data = json.loads(decompressed_response)
                socketio_logger.info(f"[DEBUG] Parsed response data: {response_data.get('success')}")
                
                if not response_data.get('success', True):
                    error_type = response_data.get('error_type')
                    error_message = response_data.get('message')
                    socketio_logger.error(f"[SERVER ERROR] Type: {error_type}, Message: {error_message}")
                    return jsonify(response_data), 400
                    
                socketio_logger.info("[DEBUG] About to process received notes")
                process_received_notes(decompressed_response)
                socketio_logger.info("[DEBUG] Finished processing notes")
                
                try:
                    notes_data = get_notes_from_db(1, count)  # Get fresh notes from DB
                    return jsonify({
                        "success": True,
                        "message": f"Retrieved {count} notes successfully",
                        "data": notes_data
                    }), 200
                except Exception as e:
                    socketio_logger.error(f"[CLIENT] Error getting updated notes: {str(e)}")
                    return jsonify({
                        "success": True,
                        "message": "Notes received but refresh failed",
                        "data": response_data
                    }), 200
            except Exception as e:
                socketio_logger.error(f"[CLIENT] Error processing response: {str(e)}")
                return jsonify({
                    "success": False,
                    "message": "Error processing response"
                }), 500
        else:
            return jsonify({
                "success": False,
                "message": "No response received from TNC"
            }), 500

    except Exception as e:
        socketio_logger.error(f"[CLIENT] Error in request_notes: {str(e)}")
        # Make sure to restore original timeout if there was an exception
        if 'original_timeout' in locals():
            config.CONNECTION_TIMEOUT = original_timeout
        return jsonify({
            "success": False,
            "message": "Failed to connect to TNC"
        }), 500

def create_note(content):
    return {
        "id": str(uuid.uuid4()),
        "content": content,
        "created_at": int(time.time()),
        "pubkey": "default_pubkey",  # Replace with actual pubkey when implemented
        "referenced_events": "[]",
        "p": "",
        "root": ""
    }

def save_note(note, is_local=False):
    db_path = os.path.join(BASE_DIR, 'data', 'notes.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    max_retries = 5
    for _ in range(max_retries):
        try:
            c.execute("""INSERT INTO notes 
                         (id, content, created_at, pubkey, referenced_events, p, root, is_local) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                      (note.get('id', str(uuid.uuid4())),
                       note.get('content', ''),
                       note.get('created_at', int(time.time())),
                       note.get('pubkey', ''),
                       json.dumps(note.get('referenced_events', [])),
                       note.get('p', ''),
                       note.get('root', ''),
                       int(is_local)))
            conn.commit()
            break
        except sqlite3.IntegrityError:
            note['id'] = str(uuid.uuid4())  # Generate a new UUID and retry
    else:
        socketio_logger.error(f"Failed to save note after {max_retries} attempts")
        logging.error(f"Failed to save note after {max_retries} attempts")
    conn.close()

# Note Handinlg API
def process_received_notes(response):
    try:
        data = json.loads(response)
        logging.debug(f"Parsed JSON data: {data}")
        
        if isinstance(data, dict) and 'events' in data:
            notes = data['events']
        elif isinstance(data, list):
            notes = data
        else:
            logging.error(f"Unexpected data structure: {data}")
            return

        base_timestamp = int(time.time())
        db_path = os.path.join(BASE_DIR, 'data', 'notes.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        try:
            for i, note in enumerate(notes):
                # Add a small increment (milliseconds) to each note's stored_at time
                current_timestamp = base_timestamp + i
                
                logging.debug(f"Processing note: {note}")
                c.execute("""INSERT OR REPLACE INTO notes 
                            (id, content, created_at, pubkey, display_name, lud16, is_local, stored_at) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                         (note.get('id'),
                          note.get('content'),
                          note.get('created_at'),
                          note.get('pubkey', ''),
                          note.get('display_name', ''),
                          note.get('lud16', ''),
                          0,  # 0 for not local
                          current_timestamp))
            conn.commit()
            socketio_logger.info(f"[CLIENT] Processed {len(notes)} notes")
            logging.info(f"Processed {len(notes)} notes")
        except Exception as e:
            socketio_logger.error(f"[DATABASE] Error saving notes: {e}")
            logging.error(f"Error saving notes: {e}")
        finally:
            conn.close()
            
    except json.JSONDecodeError:
        socketio_logger.error("[SYSTEM] Error decoding received notes")
        logging.error("Error decoding received notes")
    except Exception as e:
        socketio_logger.error(f"[SYSTEM] Error processing received notes: {str(e)}")
        logging.error(f"Error processing received notes: {str(e)}")

# Store section info dynamically
setting_sections = {}

def reload_config():
    """ Reload the settings by reloading the config module """
    importlib.reload(config)

#Settings Route(s)

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    try:
        if request.method == 'POST':
            data = request.json
            
            for key, value in data.items():
                if key in setting_sections:
                    section, option = setting_sections[key]
                    
                    # Handle callsign objects - use existing tuple format like server_ui.py
                    if (option.lower().endswith('_callsign') or 
                        option.lower() == 'hamstr_server'):
                        # Convert frontend format to config tuple format (same as server_ui.py)
                        if isinstance(value, dict):
                            callsign_tuple = f"({value['callsign']}, {value['ssid']})"
                        elif isinstance(value, list) and len(value) == 2:
                            callsign_tuple = f"({value[0]}, {value[1]})"
                        else:
                            continue
                        config.update_config(section, option, callsign_tuple)
                    else:
                        config.update_config(section, option, str(value))

            reload_config()
            return jsonify({"message": "Settings updated and applied successfully!"})

        # GET method
        reload_config()
        settings_dict = {}
        for section in config.config.sections():
            for option in config.config.options(section):
                key = f"{section.upper()}_{option.upper()}"
                value = config.config.get(section, option)

                # Handle callsign parsing - both _callsign AND hamstr_server  
                if (option.lower().endswith('_callsign') or 
                    option.lower() == 'hamstr_server'):
                    callsign, ssid = config.parse_tuple(value)
                    value = [callsign, ssid]
                elif value.isdigit():
                    value = int(value)
                elif value.replace('.', '', 1).isdigit():
                    value = float(value)

                settings_dict[key] = value
                setting_sections[key] = (section, option)

        return jsonify(settings_dict)

    except Exception as e:
        print(f"Error handling settings request: {e}")
        import traceback
        traceback.print_exc()  # Print full traceback
        return jsonify({"error": str(e)}), 500
    
#Secure NSEC Handling API

@app.route('/api/nsec', methods=['GET', 'POST', 'DELETE'])
def manage_nsec():
    if request.method == 'POST':
        nsec = request.json.get('nsec')
        if not nsec:
            return jsonify({'success': False, 'message': 'NSEC is required'}), 400
        
        # Validate NSEC format
        if not nsec.startswith('nsec1'):
            return jsonify({'success': False, 'message': 'Invalid NSEC format'}), 400
            
        success = nsec_storage.store_nsec(nsec)
        return jsonify({
            'success': success,
            'message': 'NSEC stored successfully' if success else 'Failed to store NSEC'
        })
        
    elif request.method == 'GET':
        has_nsec = nsec_storage.has_nsec()
        return jsonify({
            'success': True,
            'has_nsec': has_nsec
        })
        
    elif request.method == 'DELETE':
        success = nsec_storage.clear_nsec()
        return jsonify({
            'success': success,
            'message': 'NSEC cleared successfully' if success else 'Failed to clear NSEC'
        })

# Clear Notes function

@app.route('/api/clear_notes', methods=['POST'])
def clear_notes():
    try:
        db_path = os.path.join(BASE_DIR, 'data', 'notes.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("DELETE FROM notes")
        conn.commit()
        conn.close()
        socketio_logger.info("[DATABASE] Successfully cleared notes database")
        return jsonify({
            "success": True,
            "message": "Notes database cleared successfully"
        })
    except Exception as e:
        socketio_logger.error(f"[DATABASE] Error clearing database: {e}")
        return jsonify({
            "success": False,
            "message": f"Error clearing database: {str(e)}"
        }), 500

#--- Begin Zap and NWC ----

@app.route('/api/nwc', methods=['GET', 'POST', 'DELETE'])
def manage_nwc():
    """Manage NWC connection (similar to NSEC management)."""
    if request.method == 'POST':
        data = request.get_json()
        nwc_uri = data.get('nwc_uri')
        
        if not nwc_uri:
            return jsonify({'success': False, 'message': 'NWC URI is required'}), 400
        
        # Validate NWC URI format
        if not nwc_uri.startswith('nostr+walletconnect://'):
            return jsonify({'success': False, 'message': 'Invalid NWC URI format'}), 400
            
        success = nwc_storage.store_nwc_connection(nwc_uri)
        return jsonify({
            'success': success,
            'message': 'NWC connection stored successfully' if success else 'Failed to store NWC connection'
        })
        
    elif request.method == 'GET':
        has_nwc = nwc_storage.has_nwc_connection()
        connection_info = None
        
        if has_nwc:
            connection = nwc_storage.get_nwc_connection()
            if connection:
                # Return safe info (no secrets)
                connection_info = {
                    'relay': connection.get('relay'),
                    'wallet_pubkey_preview': connection.get('wallet_pubkey', '')[:8] + '...',
                    'connected': True
                }
        
        return jsonify({
            'success': True,
            'has_nwc': has_nwc,
            'connection_info': connection_info
        })
        
    elif request.method == 'DELETE':
        success = nwc_storage.clear_nwc_connection()
        return jsonify({
            'success': success,
            'message': 'NWC connection cleared successfully' if success else 'Failed to clear NWC connection'
        })

@app.route('/api/test_nwc', methods=['POST'])
def test_nwc_connection():
    """Test NWC connection while online (for setup phase)."""
    try:
        data = request.get_json()
        nwc_uri = data.get('nwc_uri')
        
        if not nwc_uri:
            return jsonify({'success': False, 'message': 'NWC URI is required'}), 400
        
        # Test the connection with real wallet communication
        test_result = nwc_storage.test_nwc_connection(nwc_uri)
        
        # If test is successful, store the connection
        if test_result.get('success'):
            socketio_logger.info(f"[NWC] Connection test passed, storing connection")
            
            store_success = nwc_storage.store_nwc_connection(nwc_uri)
            if store_success:
                test_result['stored'] = True
                test_result['message'] = test_result.get('message', 'Connected!') + ' Connection stored securely.'
                socketio_logger.info(f"[NWC] Connection stored successfully")
            else:
                test_result['stored'] = False
                test_result['message'] = 'Connection successful but failed to store securely'
                socketio_logger.error(f"[NWC] Failed to store connection")
        else:
            socketio_logger.error(f"[NWC] Connection test failed, not storing")
            test_result['stored'] = False
        
        return jsonify(test_result)
        
    except Exception as e:
        socketio_logger.error(f"[NWC] Error testing connection: {e}")
        return jsonify({
            'success': False,
            'message': f'Connection test failed: {str(e)}',
            'stored': False
        }), 500

@app.route('/api/send_zap', methods=['POST'])
def send_zap():
    """Send zap request via ham radio using new kind 9734 flow."""
    global radio_operation_in_progress
    
    if radio_operation_in_progress:
        socketio_logger.info("[SYSTEM] Cannot send zap - radio operation in progress")
        return jsonify({
            "success": False, 
            "message": "Cannot send zap - radio operation in progress"
        }), 500

    try:
        data = request.get_json()
        socketio_logger.info("[DEBUG] Parsed zap JSON data: %s", data)
    except Exception as e:
        socketio_logger.error("[DEBUG] JSON parse error: %s", str(e))
        return jsonify({
            "success": False,
            "message": "Invalid request format"
        }), 400

    # Extract zap data
    recipient_lud16 = data.get('recipient_lud16', '')
    amount_sats = data.get('amount_sats', 0)
    message = data.get('message', '')
    zap_type = data.get('zap_type', 1)  # Default to NOTE_ZAP
    note_id = data.get('note_id')  # For note zaps
    recipient_pubkey = data.get('recipient_pubkey', '')
    
    # Validate inputs
    if not recipient_lud16:
        socketio_logger.error("[CLIENT] No recipient Lightning address provided")
        return jsonify({
            "success": False,
            "message": "Recipient Lightning address is required"
        }), 400
    
    if amount_sats <= 0:
        socketio_logger.error("[CLIENT] Invalid zap amount")
        return jsonify({
            "success": False,
            "message": "Zap amount must be greater than 0"
        }), 400
    
    if not recipient_pubkey:
        socketio_logger.error("[CLIENT] No recipient pubkey provided")
        return jsonify({
            "success": False,
            "message": "Recipient pubkey is required"
        }), 400
    
    # Check for NWC connection
    if not nwc_storage.has_nwc_connection():
        socketio_logger.error("[CLIENT] No NWC connection available")
        return jsonify({
            "success": False,
            "message": "No Lightning wallet connected. Please setup NWC connection first."
        }), 400

    try:
        # Get NWC relay for packet transmission
        nwc_relay = nwc_storage.get_nwc_relay_url()
        if not nwc_relay:
            socketio_logger.error("[CLIENT] Failed to get NWC relay URL")
            return jsonify({
                "success": False,
                "message": "Invalid NWC connection - missing relay"
            }), 400
        
        # Get NSEC for signing the zap note
        nsec = nsec_storage.get_nsec()
        if not nsec:
            socketio_logger.error("[CLIENT] No NSEC available for signing zap note")
            return jsonify({
                "success": False,
                "message": "NOSTR key required to sign zap note"
            }), 400
        
        # Create kind 9734 zap note
        keys = Keys.parse(nsec)
        
        # Build zap note tags
        tags = [
            Tag.parse(["amount", str(amount_sats * 1000)]),  # Amount in millisats
            Tag.parse(["lnaddr", recipient_lud16]),           # Lightning address
            Tag.parse(["p", recipient_pubkey])                # Recipient pubkey
        ]
        
        # Add note reference for note zaps
        if zap_type == ZapType.NOTE_ZAP and note_id:
            tags.append(Tag.parse(["e", note_id]))
        
        # Add NWC relay for server processing
        tags.append(Tag.parse(["relay", nwc_relay]))

        # Create and sign the kind 9734 event
        builder = EventBuilder(Kind(9734), message, tags)
        signed_event = builder.to_event(keys)
        
        # Convert to JSON and compress for transmission
        zap_note_json = signed_event.as_json()
        compressed_note = compress_nostr_data(zap_note_json)
     
        socketio_logger.info(f"[CLIENT] Preparing to send kind 9734 zap note: {amount_sats} sats to {recipient_lud16}")
        
        # Use existing radio infrastructure
        radio_operation_in_progress = True
        result_container = [None]
        
        def radio_operation():
            nonlocal result_container
            try:
                client = Client(BASE_DIR)
                server_callsign = parse_callsign(config.HAMSTR_SERVER)
                
                socketio_logger.info("[CLIENT] Sending kind 9734 zap note via ZAP_KIND9734_REQUEST")
                
                session = client.core.connect(server_callsign)
                if session:
                    # PHASE 1: KIND 9734 → LIGHTNING INVOICE (working flow)
                    # Step 1: Send zap note packets + DONE
                    success = client.core.message_processor.send_message(session, compressed_note, MessageType.ZAP_KIND9734_REQUEST)
                    
                    if success:
                        socketio_logger.info("[CLIENT] Zap packets and DONE sent successfully")
                        
                        # Step 2: Wait for server READY (server is ready to send invoice)
                        if client.core.wait_for_specific_message(session, MessageType.READY):
                            socketio_logger.info("[CLIENT] Received READY from server, sending READY")
                            
                            # Step 3: Send client READY (client is ready to receive invoice)
                            if client.core.send_ready(session):
                                socketio_logger.info("[CLIENT] READY sent, waiting for invoice response")
                                
                                # Step 4: Wait for invoice response (ORIGINAL WORKING METHOD)
                                response = client.core.receive_response(session)
                                if response:
                                    # Decompress and show the invoice
                                    decompressed_response = decompress_nostr_data(response)
                                    socketio_logger.info(f"[CLIENT] Received invoice response: {decompressed_response}")
                                
                                    # Parse and show just the invoice
                                    try:
                                        invoice_data = json.loads(decompressed_response)
                                        if invoice_data.get('success') and 'invoice' in invoice_data:
                                            lightning_invoice = invoice_data['invoice']
                                            socketio_logger.info(f"[CLIENT] Lightning Invoice: {lightning_invoice}")
                                            
                                            # PHASE 2B: CREATE NWC PAYMENT COMMAND
                                            socketio_logger.info(f"[CLIENT] Creating encrypted NWC payment command")
                                            
                                            # Import the NWC command creation function
                                            from nostr import create_nwc_payment_command
                                            
                                            # Create encrypted payment command
                                            nwc_command = create_nwc_payment_command(nwc_storage, lightning_invoice)
                                            
                                            if nwc_command:
                                                # PHASE 2C: SEND NWC COMMAND VIA RADIO
                                                socketio_logger.info(f"[CLIENT] Sending NWC payment command via radio")
                                                
                                                # Compress the NWC command for transmission
                                                compressed_nwc_command = compress_nostr_data(nwc_command)
                                                
                                                # Step 6: Send client READY (client ready to send NWC command)
                                                if client.core.send_ready(session):
                                                    socketio_logger.info("[CLIENT] Sent READY for NWC command transmission")
                                                    
                                                    # Step 7: Wait for server READY (server ready to receive NWC command)
                                                    if client.core.wait_for_specific_message(session, MessageType.READY):
                                                        socketio_logger.info("[CLIENT] Server READY received, sending NWC command")
                                                        
                                                        # Step 8: Send encrypted NWC payment command
                                                        nwc_success = client.core.message_processor.send_message(
                                                            session, compressed_nwc_command, MessageType.NWC_PAYMENT_REQUEST
                                                        )
                                                        
                                                        if nwc_success:
                                                            socketio_logger.info("[CLIENT] NWC command sent, waiting for payment response")
                                                            
                                                            # Wait for payment response from server
                                                            if client.core.wait_for_specific_message(session, MessageType.READY, timeout=30):
                                                                socketio_logger.info("[CLIENT] Server READY received for payment response")
                                                                if client.core.send_ready(session):
                                                                    socketio_logger.info("[CLIENT] Sent READY for payment response")
                                                                    payment_response = client.core.receive_response(session)
                                                                else:
                                                                    payment_response = None
                                                                    socketio_logger.error("[CLIENT] Failed to send READY for payment response")
                                                            else:
                                                                payment_response = None  
                                                                socketio_logger.error("[CLIENT] Server not ready for payment response")
                                                            
                                                            if payment_response:
                                                                try:
                                                                    # Parse payment response
                                                                    decompressed_payment = decompress_nostr_data(payment_response)
                                                                    payment_result = json.loads(decompressed_payment)
                                                                    
                                                                    if payment_result.get("success"):
                                                                        socketio_logger.info("[CLIENT] ⚡ Zap payment successful!")
                                                                        result_container[0] = {
                                                                            "success": True,
                                                                            "message": "⚡ Zap sent successfully!",
                                                                            "preimage": payment_result.get("preimage")
                                                                        }
                                                                    else:
                                                                        error_msg = payment_result.get("error", "Payment failed")
                                                                        socketio_logger.error(f"[CLIENT] Payment failed: {error_msg}")
                                                                        result_container[0] = {
                                                                            "success": False,
                                                                            "message": f"Payment failed: {error_msg}"
                                                                        }
                                                                        
                                                                except Exception as e:
                                                                    socketio_logger.error(f"[CLIENT] Error parsing payment response: {e}")
                                                                    result_container[0] = {
                                                                        "success": False,
                                                                        "message": "Error processing payment response"
                                                                    }
                                                            else:
                                                                socketio_logger.error("[CLIENT] No payment response received")
                                                                result_container[0] = {
                                                                    "success": False,
                                                                    "message": "Payment timeout - no response from wallet"
                                                                }
                                                        else:
                                                            socketio_logger.error("[CLIENT] Failed to send NWC command")
                                                            result_container[0] = {
                                                                "success": False,
                                                                "message": "Failed to send payment command"
                                                            }
                                                    else:
                                                        socketio_logger.error("[CLIENT] Server not ready for NWC command")
                                                        result_container[0] = {
                                                            "success": False,
                                                            "message": "Server not ready for payment"
                                                        }
                                                else:
                                                    socketio_logger.error("[CLIENT] Failed to send READY for NWC command")
                                                    result_container[0] = {
                                                        "success": False,
                                                        "message": "Failed to initiate payment sequence"
                                                    }
                                            else:
                                                socketio_logger.error(f"[CLIENT] Failed to create NWC payment command")
                                                result_container[0] = {
                                                    "success": False, 
                                                    "message": "Failed to create payment command"
                                                }
                                        else:
                                            error_msg = invoice_data.get("message", "Invoice generation failed")
                                            result_container[0] = {
                                                "success": False,
                                                "message": f"Invoice generation failed: {error_msg}"
                                            }
                                    except Exception as e:
                                        socketio_logger.error(f"[CLIENT] Error parsing invoice: {e}")
                                        result_container[0] = {
                                            "success": False,
                                            "message": f"Error parsing invoice: {str(e)}"
                                        }
                                else:
                                    result_container[0] = {
                                        "success": False,
                                        "message": "No response received from server"
                                    }
                            else:
                                socketio_logger.error("[CLIENT] Failed to send READY")
                                result_container[0] = {"success": False, "message": "Failed to respond to server"}
                        else:
                            socketio_logger.error("[CLIENT] Did not receive READY from server")
                            result_container[0] = {"success": False, "message": "Server not ready"}
                    else:
                        socketio_logger.error("[CLIENT] Failed to send zap packets")
                        result_container[0] = {"success": False, "message": "Failed to send zap packets"}
                    
                    # Always disconnect at the end
                    client.core.disconnect(session)
                else:
                    socketio_logger.error("[CLIENT] Failed to connect to server")
                    result_container[0] = {"success": False, "message": "Failed to connect to server"}
                    
            except Exception as e:
                socketio_logger.error(f"[CLIENT] Radio operation error: {e}")
                result_container[0] = {"success": False, "message": f"Radio error: {str(e)}"}
        
    except Exception as e:
        socketio_logger.error(f"[CLIENT] Error creating zap note: {e}")
        return jsonify({
            "success": False,
            "message": f"Error creating zap note: {str(e)}"
        }), 500
    finally:
        radio_operation_in_progress = False

        radio_thread = threading.Thread(target=radio_operation)
    radio_thread.start()
    radio_thread.join(timeout=180)  # Or whatever timeout you had

    if radio_thread.is_alive():
        result_container[0] = {"success": False, "message": "Radio operation timeout"}

    return jsonify(result_container[0] or {"success": False, "message": "Unknown error"})
        
# Static file routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':

    socketio.run(app, debug=True, host='0.0.0.0', allow_unsafe_werkzeug=True)