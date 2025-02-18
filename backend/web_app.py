import config
import threading
import sqlite3
import json
import time
import uuid
import os
import logging
import importlib
from models import NoteRequestType, NoteType
from protocol_utils import compress_nostr_data, decompress_nostr_data
from socketio_logger import init_socketio, get_socketio_logger
from nostr_sdk import Keys, EventId, EventBuilder, Tag, Kind 
from nsec_storage import NSECStorage
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from client import Client


app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
socketio = init_socketio(app)
nsec_storage = NSECStorage(BASE_DIR)

#initiate radio process lock
radio_lock = threading.Lock()
radio_operation_in_progress = False


# Initialize Client()
client = Client(BASE_DIR)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
socketio_logger = get_socketio_logger()

# Make sure init_db is called at app startup

def init_db():
    db_path = os.path.join(BASE_DIR, 'data', 'notes.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        # Check if table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notes'")
        table_exists = c.fetchone() is not None
        
        if not table_exists:
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
            socketio_logger.info("[DATABASE] Successfully initialized database")
        else:
            # Check if stored_at column exists
            c.execute("PRAGMA table_info(notes)")
            columns = [col[1] for col in c.fetchall()]
            if 'stored_at' not in columns:
                c.execute("ALTER TABLE notes ADD COLUMN stored_at INTEGER")
                conn.commit()
                socketio_logger.info("[DATABASE] Added stored_at column to existing database")
    except Exception as e:
        socketio_logger.error(f"[DATABASE] Error initializing database: {e}")
    finally:
        conn.close()

# Make sure init_db is called at app startup
init_db()

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    notes = get_notes_from_db(page, limit)
    socketio_logger.debug(f"Notes being served... Page: {page}, Limit: {limit}")
    return jsonify(notes)

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

@app.route('/send_note', methods=['POST'])
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
                content = content + f"nostr:{note_bech32}"
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

        thread = threading.Thread(target=request_notes_thread)
        thread.start()
        thread.join(timeout=config.CONNECTION_TIMEOUT)

        if thread.is_alive():
            socketio_logger.error("[CLIENT] Request timeout")
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

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    try:
        if request.method == 'POST':
            data = request.json
            for key, value in data.items():
                if key in setting_sections:
                    section, option = setting_sections[key]
                    if option.lower().endswith('_callsign'):
                        # Handle callsign objects
                        callsign_value = f"({value['callsign']}, {value['ssid']})"
                        config.update_config(section, option, callsign_value)
                    else:
                        config.update_config(section, option, str(value))

            reload_config()
            return jsonify({"message": "Settings updated and applied successfully!"})

        reload_config()
        settings_dict = {}
        for section in config.config.sections():
            for option in config.config.options(section):
                key = f"{section.upper()}_{option.upper()}"
                value = config.config.get(section, option)

                if option.lower().endswith('_callsign'):
                    # Parse callsign tuples
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
        return jsonify({"error": str(e)}), 500
    
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

if __name__ == '__main__':

    socketio.run(app, debug=True, host='0.0.0.0', allow_unsafe_werkzeug=True)