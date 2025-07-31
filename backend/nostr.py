import re
import json
import logging
import asyncio
import time
import requests
import aiohttp
from datetime import timedelta
from models import NoteRequestType, NoteType
from config import NOSTR_RELAYS
from nostr_sdk import Client, Filter, Kind, EventSource, PublicKey, Keys, Event, Metadata, Alphabet, SingleLetterTag

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# REGEX PATTERN CHECKS

MENTION_PATTERNS = [
    r'nostr:npub[a-zA-Z0-9]{58}',  # nostr:npub format
    r'npub[a-zA-Z0-9]{58}',        # plain npub format
    r'nostr:nprofile[a-zA-Z0-9]+', # nostr:nprofile format
    r'nprofile[a-zA-Z0-9]+'        # plain nprofile format
]


def clean_content(content):
    """Replace image & video URLs with [placeholder]"""
    import re
    # Match common image URLs and Markdown image syntax
    image_pattern = r'!\[.*?\]\(.*?\)|\b(https?:\/\/[^\s]+\.(?:jpg|jpeg|png|gif|webp))\b'
    # Match common video URLs and formats
    video_pattern = r'\b(https?:\/\/[^\s]+\.(?:mp4|webm|mov|avi|mkv))\b'
    
    # First replace images
    content = re.sub(image_pattern, '[image]', content)
    # Then replace videos
    content = re.sub(video_pattern, '[video]', content)
    return content

async def get_display_name(client, pubkey):
    """Get display name for a pubkey from Kind 0 event."""
    try:
        # Create filter for profile data (Kind 0)
        profile_filter = (Filter()
                        .authors([pubkey])
                        .kind(Kind(0))
                        .limit(1))
        
        source = EventSource.relays(timedelta(seconds=.5))
        profile_events = await client.get_events_of([profile_filter], source)
        
        if profile_events:
            event = profile_events[0]
            profile_data = json.loads(event.as_json())
            content = json.loads(profile_data.get('content', '{}'))
            
            # Get all possible name fields
            display_name = content.get('display_name')
            name = content.get('name')
            lud16 = content.get('lud16')
            
            if display_name and display_name != name:
                return display_name, lud16
            elif name:
                return name, lud16
            
        # If no profile found or no name fields, convert pubkey to npub
        npub = Keys.parse_public_key(pubkey.to_hex()).to_bech32()
        return npub, None
        
    except Exception as e:
        logging.error(f"Error getting display name: {e}")
        # Return pubkey in npub format as fallback
        try:
            npub = pubkey.to_bech32()
            return npub, None
        except:
            return pubkey.to_hex(), None

async def get_following_list(client, public_key):
    """Get list of users that this public key follows."""
    logging.info(f"Getting following list for: {public_key}")
    
    try:
        # Make sure relays are connected with a longer timeout
        await client.add_relays(NOSTR_RELAYS)
        await client.connect()
        
        # Retry loop for contact list
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                contact_filter = (Filter()
                               .authors([public_key])
                               .kind(Kind(3))
                               .limit(1))
                
                source = EventSource.relays(timedelta(seconds=2 * (attempt + 1)))  # Increase timeout with each attempt
                contacts = await client.get_events_of([contact_filter], source)
                
                if contacts:
                    contact_event = contacts[0]
                    contact_data = json.loads(contact_event.as_json())
                    
                    followed_keys = []
                    for tag in contact_data.get('tags', []):
                        if len(tag) >= 2 and tag[0] == 'p':
                            try:
                                followed_key = PublicKey.from_hex(tag[1])
                                followed_keys.append(followed_key)
                            except Exception as e:
                                logging.error(f"Error parsing pubkey {tag[1]}: {e}")
                                continue
                                
                    logging.info(f"Found {len(followed_keys)} followed accounts")
                    return followed_keys
            except Exception as e:
                logging.error(f"Error on attempt {attempt+1}: {e}")
                if attempt < max_attempts - 1:
                    logging.info(f"Retrying contact list fetch...")
                    await asyncio.sleep(1)  # Small delay before retry
        
        logging.info("No contact list found after retry")
        return []
        
    except Exception as e:
        logging.error(f"Error getting following list: {e}")
        return []

async def get_recent_notes(npub_hex, number, request_type=None):
    client = Client()
    
    logging.info(f"Step 1: Starting get_recent_notes for public key: {npub_hex}")
    logging.info(f"Request type received: {request_type}")
    
    try:
        await client.add_relays(NOSTR_RELAYS)
        await client.connect()
        
        try:
            logging.info(f"Step 2: Getting {number} Recent Posts from relays...")
            source = EventSource.relays(timedelta(seconds=1))

            if request_type == NoteRequestType.FOLLOWING:
                # For following, we need the caller's public key
                public_key = PublicKey.from_hex(npub_hex)
                followed_keys = await get_following_list(client, public_key)
                if not followed_keys:
                    return json.dumps({
                        "success": True,
                        "events": [],
                        "message": "No followed accounts found"
                    })
                logging.info(f"Fetching notes from {len(followed_keys)} followed accounts")
                filter = (Filter()
                         .authors(followed_keys)
                         .kind(Kind(1))
                         .limit(number))
            elif request_type == NoteRequestType.GLOBAL:
                # For global, we don't need any public key
                filter = (Filter()
                         .kind(Kind(1))
                         .limit(number))
            elif request_type == NoteRequestType.SEARCH_USER:
                # Handle name or npub search
                search_term = npub_hex.lower()  # npub_hex contains our search term here
                if search_term.startswith('npub1'):
                    try:
                        public_key = PublicKey.from_bech32(search_term)
                        filter = (Filter()
                                .authors([public_key])
                                .kind(Kind(1))
                                .limit(number))
                    except Exception as e:
                        logging.error(f"Invalid NPUB format: {e}")
                        return json.dumps({
                            "success": False,
                            "events": [],
                            "message": "Invalid NPUB format"
                        })
                else:
                    # Search by name in profiles (Kind 0)
                    try:
                        # First get recent active users (kind 1 text notes from last 3 months)
                        from nostr_sdk import Timestamp
                        
                        current_time = Timestamp.now()
                        three_months_ago = Timestamp.from_secs(int(time.time()) - (90 * 24 * 60 * 60))
                        
                        active_filter = (Filter()
                                        .kind(Kind(1))
                                        .since(three_months_ago)
                                        .limit(1000))
                        
                        logging.info(f"Getting active users since: {three_months_ago.as_secs()}")
                        active_events = await client.get_events_of([active_filter], source)
                        
                        # Get unique active pubkeys and convert them to PublicKey objects
                        active_pubkeys = set()
                        for event in active_events:
                            event_data = json.loads(event.as_json())
                            pubkey = event_data.get('pubkey')
                            if pubkey:
                                active_pubkeys.add(PublicKey.from_hex(pubkey))
                        
                        logging.info(f"Found {len(active_pubkeys)} active users to search through")
                        
                        # Now get profiles for these active users
                        profile_filter = (Filter()
                                        .kind(Kind(0))
                                        .authors(list(active_pubkeys)))
                        
                        logging.info(f"Searching profiles of active users with term: {search_term}")
                        profiles = await client.get_events_of([profile_filter], source)
                        matching_pubkeys = []
                        
                        for profile in profiles:
                            try:
                                profile_json = profile.as_json()
                                profile_data = json.loads(profile_json)
                                content = json.loads(profile_data.get('content', '{}'))
                                
                                # Get both name and display_name according to NIPs 01 and 24
                                name = str(content.get('name', '')).lower()
                                display_name = str(content.get('display_name', '')).lower()
                                
                                logging.info(f"Examining profile - name: {name}, display_name: {display_name}")
                                
                                # Search in both fields
                                if (search_term.lower() in name or 
                                    search_term.lower() in display_name):
                                    logging.info(f"Found matching profile: {display_name or name}")
                                    matching_pubkeys.append(profile.public_key)
                                    
                            except (json.JSONDecodeError, AttributeError) as e:
                                logging.error(f"Error parsing profile: {e}")
                                continue
                        
                        if not matching_pubkeys:
                            logging.info("No matching profiles found")
                            return json.dumps({
                                "success": True,
                                "events": [],
                                "message": "No users found matching the search term"
                            })
                        
                        logging.info(f"Found {len(matching_pubkeys)} matching profiles")
                        filter = (Filter()
                                .authors(matching_pubkeys)
                                .kind(Kind(1))
                                .limit(number))
                    except Exception as e:
                        logging.error(f"Error in name search: {e}")
                        return json.dumps({
                            "success": False,
                            "events": [],
                            "message": f"Error searching for user: {str(e)}"
                        })
            else:
                # Default behavior (SPECIFIC_USER)
                public_key = PublicKey.from_hex(npub_hex)
                filter = (Filter()
                         .authors([public_key])
                         .kind(Kind(1))
                         .limit(number))

            logging.info("Step 3: Awaiting events...")
            events = await client.get_events_of([filter], source)
            logging.info("Step 4: Got events, processing...")
            
            event_list = []
            count = 0
            
            events_to_process = list(events) if not isinstance(events, list) else events
            logging.info(f"Step 5: Processing {len(events_to_process)} events")
            
            for event in events_to_process:
                if count >= number:
                    break
                try:
                    event_json = event.as_json()
                    event_data = json.loads(event_json)
                    
                    # Process mentions in the note
                    event_data = await process_mentions_in_note(client, event_data)
                    
                    # Get display name for the note author
                    if 'pubkey' in event_data:
                        author_pubkey = PublicKey.from_hex(event_data['pubkey'])
                        display_name, lud16 = await get_display_name(client, author_pubkey)
                        
                        stripped_event = {
                            'id': event_data['id'],
                            'content': clean_content(event_data.get('content', '')),
                            'created_at': event_data.get('created_at'),
                            'pubkey': event_data['pubkey'],  # Always include hex pubkey
                        }

                        # Add display_name if it exists
                        if display_name:
                            stripped_event['display_name'] = display_name

                        # Add lightning address if available
                        if lud16:
                            stripped_event['lud16'] = lud16
                        
                        event_list.append(stripped_event)
                        count += 1
                        logging.info(f"Processed event {count} with display name: {display_name}")
                        
                except Exception as e:
                    logging.error(f"Error processing event {count + 1}: {e}")
                    continue
                
            logging.info(f"Step 6: Processed {len(event_list)} events successfully")
            
            response = {
                "success": True,
                "events": event_list
            }
            
            result = json.dumps(response, indent=2)
            logging.info(f"Step 7: Final formatted result: {result}")
            return result
                
        except Exception as e:
            logging.error(f"Error in main try block: {e}")
            response = {
                "success": False,
                "events": [],
                "message": f"Error fetching NOSTR events: {str(e)}"
            }
            result = json.dumps(response, indent=2)
            logging.error(f"Error response: {result}")
            return result
        
    finally:
        logging.info("Step 8: Disconnecting client")
        await client.disconnect()

def run_get_recent_notes(npub_hex, count, request_type=None):
    """Wrapper to run the async get_recent_notes in an event loop."""
    try:
        logging.info(f"Running get_recent_notes with request type: {request_type}")
        result = asyncio.run(get_recent_notes(npub_hex, count, request_type))
        if result is None:
            return json.dumps({
                "success": False,
                "events": [],
                "message": "No events returned"
            })
        return result
    except Exception as e:
        logging.error(f"Error in run_get_recent_notes: {e}")
        return json.dumps({
            "success": False,
            "events": [],
            "message": f"Error: {str(e)}"
        })
    

async def search_user_notes(search_term, number):
    """Search for users by name or npub and return their recent notes."""
    client = Client()
    
    logging.info(f"Searching for user: {search_term}")
    try:
        await client.add_relays(NOSTR_RELAYS)
        await client.connect()
        
        source = EventSource.relays(timedelta(seconds=.5))
        is_npub_search = search_term.lower().startswith('npub')
        
        if is_npub_search:
            try:
                # Direct NPUB lookup
                logging.info("Performing NPUB search")
                public_key = Keys.parse_public_key(search_term)
                filter = (Filter()
                         .authors([public_key])
                         .kind(Kind(1))
                         .limit(number))
                events = await client.get_events_of([filter], source)
            except Exception as e:
                logging.error(f"Invalid NPUB format: {e}")
                return json.dumps({
                    "success": False,
                    "events": [],
                    "message": "Invalid NPUB format"
                })
        else:
            # Search by name in profiles (Kind 0)
            try:
                # Create filters for name search in content
                search_term_filter = f'{{"content": "{search_term}"}}'
                profile_filter = (Filter()
                                .kind(Kind(0))
                                .search(search_term)  # This will search the content field
                                .limit(50))  # We can use a smaller limit since results are pre-filtered
                
                logging.info(f"Searching profiles with term: {search_term}")
                profiles = await client.get_events_of([profile_filter], source)
                matching_pubkeys = []
                
                for profile in profiles:
                    try:
                        profile_json = profile.as_json()
                        profile_data = json.loads(profile_json)
                        content_data = json.loads(profile_data.get('content', '{}'))
                        
                        name = str(content_data.get('name', '')).lower()
                        display_name = str(content_data.get('display_name', '')).lower()
                        
                        # Verify match (the relay might return fuzzy matches)
                        if (search_term.lower() in name or 
                            search_term.lower() in display_name):
                            logging.info(f"Found matching profile: {display_name or name}")
                            matching_pubkeys.append(profile.public_key)
                            
                    except (json.JSONDecodeError, AttributeError) as e:
                        logging.error(f"Error parsing profile: {e}")
                        continue
                
                if not matching_pubkeys:
                    return json.dumps({
                        "success": True,
                        "events": [],
                        "message": "No users found matching the search term"
                    })
                
                # Get notes from matching users
                notes_filter = (Filter()
                              .authors(matching_pubkeys)
                              .kind(Kind(1))
                              .limit(number))
                events = await client.get_events_of([notes_filter], source)
            except Exception as e:
                logging.error(f"Error in name search: {e}")
                return json.dumps({
                    "success": False,
                    "events": [],
                })
        
        # Process events using existing event processing logic
        event_list = []
        for event in events:
            try:
                event_data = json.loads(event.as_json())
                author_pubkey = PublicKey.from_hex(event_data['pubkey'])
                display_name, lud16 = await get_display_name(client, author_pubkey)
                
                stripped_event = {
                    'id': event_data['id'],
                    'content': clean_content(event_data.get('content', '')),
                    'created_at': event_data.get('created_at'),
                    'display_name': display_name,
                }
                
                if lud16:
                    stripped_event['lud16'] = lud16
                
                event_list.append(stripped_event)
                
            except Exception as e:
                logging.error(f"Error processing event: {e}")
                continue
        
        return json.dumps({
            "success": True,
            "events": event_list,
            "message": f"Found {len(event_list)} notes from matching users"
        })
        
    except Exception as e:
        logging.error(f"Error in search_user_notes: {e}")
        return json.dumps({
            "success": False,
            "events": [],
            "message": f"Error: {str(e)}"
        })
    finally:
        await client.disconnect()

def search_nostr(request_type, number, search_text=None):
    """Search NOSTR notes using different methods based on request type."""
    logging.info(f"Searching NOSTR: type={request_type.name}, query={search_text}")
    
    if request_type == NoteRequestType.SEARCH_TEXT:
        try:
            params = {
                'query': search_text,
                'kind': 1,
                'limit': number,
                'sort': 'time',
                'order': 'descending'
            }
            
            logging.info(f"[SEARCH] Querying nostr.wine API for text: {search_text}")
            start_time = time.time()
            response = requests.get('https://api.nostr.wine/search', params=params, timeout=5.0)
            api_time = time.time() - start_time
            logging.info(f"[SEARCH] API response time: {api_time:.2f} seconds")
            
            if response.status_code == 200:
                response_json = response.json()
                results = response_json.get('data', [])  # Get the data array
                logging.info(f"[SEARCH] Found {len(results)} initial results")

                # If no results, return early
                if not results:
                    return json.dumps({
                        "success": True,
                        "events": [],
                        "message": "No matching notes found"
                    })

                # Create async function to process results
                async def process_results():
                    client = Client()
                    try:
                        await client.add_relays(NOSTR_RELAYS)
                        await client.connect()
                        
                        events = []
                        for result in results:
                            try:
                                # Get author's pubkey
                                author_pubkey = PublicKey.from_hex(result.get('pubkey'))
                                # Get display name and lightning address
                                display_name, lud16 = await get_display_name(client, author_pubkey)
                                
                                # Create standardized event
                                stripped_event = {
                                    'id': result.get('id'),
                                    'content': clean_content(result.get('content', '')),
                                    'created_at': result.get('created_at'),
                                    'pubkey': result.get('pubkey')  # Always include hex pubkey
                                }

                                # Add display name if available
                                if display_name:
                                    stripped_event['display_name'] = display_name
                                    
                                # Add lightning address if available
                                if lud16:
                                    stripped_event['lud16'] = lud16
                                    
                                events.append(stripped_event)
                                logging.info(f"[SEARCH] Processed note from: {display_name or author_pubkey.to_bech32()}")
                                
                            except Exception as e:
                                logging.error(f"[SEARCH] Error processing result: {e}")
                                continue
                                
                        return events
                    finally:
                        await client.disconnect()

                # Run async processing
                events = asyncio.run(process_results())
                
                pagination = response_json.get('pagination', {})
                total_found = pagination.get('total_records', 0)
                
                return json.dumps({
                    "success": True,
                    "events": events
                })
            else:
                logging.error(f"[SEARCH] API request failed with status {response.status_code}")
                return json.dumps({
                    "success": False,
                    "events": [],
                    "message": "Search API request failed"
                })
                
        except Exception as e:
            logging.error(f"[SEARCH] Error performing text search: {e}")
            return json.dumps({
                "success": False,
                "events": [],
                "message": f"Error searching notes: {str(e)}"
            })
            
    elif request_type == NoteRequestType.SEARCH_HASHTAG:
        try:
            # Split and clean hashtags (remove # if present and ensure lowercase)
            clean_tags = [tag.strip().lower().lstrip('#') for tag in search_text.split(',')]
            logging.info(f"[SEARCH] Searching for hashtags: {clean_tags}")

            async def process_hashtag_search():
                client = Client()
                try:
                    await client.add_relays(NOSTR_RELAYS)
                    await client.connect()
                    
                    # Create filter for notes with any of the hashtags
                    tag_filter = Filter().kind(Kind(1)).limit(number)
                    
                    # Add each hashtag to the filter
                    for tag in clean_tags:
                        tag_filter = tag_filter.custom_tag(SingleLetterTag.lowercase(Alphabet.T), [tag])
                    
                    source = EventSource.relays(timedelta(seconds=.5))
                    events = await client.get_events_of([tag_filter], source)
                    
                    event_list = []
                    for event in events:
                        try:
                            event_data = json.loads(event.as_json())
                            author_pubkey = PublicKey.from_hex(event_data['pubkey'])
                            
                            # Get author's display name and lightning address
                            display_name, lud16 = await get_display_name(client, author_pubkey)
                            
                            # Create standardized event
                            stripped_event = {
                                'id': event_data['id'],
                                'content': clean_content(event_data.get('content', '')),
                                'created_at': event_data.get('created_at'),
                                'pubkey': event_data['pubkey']  # Always include hex pubkey
                            }

                            # Add display name if available
                            if display_name:
                                stripped_event['display_name'] = display_name
                                
                            # Add lightning address if available
                            if lud16:
                                stripped_event['lud16'] = lud16
                                
                            event_list.append(stripped_event)
                            logging.info(f"[SEARCH] Processed hashtag note from: {display_name or author_pubkey.to_bech32()}")
                            
                        except Exception as e:
                            logging.error(f"[SEARCH] Error processing hashtag result: {e}")
                            continue
                            
                    return event_list
                finally:
                    await client.disconnect()

            events = asyncio.run(process_hashtag_search())
            
            # Add this check for empty events
            if not events:
                # Format tags for message
                tag_list = [f"#{tag}" for tag in clean_tags]
                tag_message = ", ".join(tag_list)
                return json.dumps({
                    "success": True,
                    "events": [],
                    "message": f"No notes found with hashtags: {tag_message}"
                })
            
            return json.dumps({
                "success": True,
                "events": events
            })
        except Exception as e:
            logging.error(f"[SEARCH] Error performing hashtag search: {e}")
            return json.dumps({
                "success": False,
                "events": [],
                "message": f"Error searching hashtags: {str(e)}"
            })
        
def get_notes_from_search(search_term, number):
    """Get notes from nostr.wine search API."""
    try:
        params = {
            'query': search_term,
            'kind': 1,  # Only search text notes
            'limit': number,
            'sort': 'time',  # Get most recent matches
            'order': 'descending'
        }
        
        logging.info(f"[SEARCH] Querying nostr.wine API for: {search_term}")
        response = requests.get('https://api.nostr.wine/search', params=params)
        
        if response.status_code == 200:
            results = response.json()
            
            # Format the results to match our standard note format
            events = []
            for result in results:
                stripped_event = {
                    'id': result.get('id'),
                    'content': clean_content(result.get('content', '')),
                    'created_at': result.get('created_at'),
                    'pubkey': result.get('pubkey')
                }
                events.append(stripped_event)
            
            return json.dumps({
                "success": True,
                "events": events,
                "message": f"Found {len(events)} matching notes"
            })
        else:
            logging.error(f"[SEARCH] API request failed with status {response.status_code}")
            return json.dumps({
                "success": False,
                "events": [],
                "message": "Search API request failed"
            })
            
    except Exception as e:
        logging.error(f"[SEARCH] Error performing search: {e}")
        return json.dumps({
            "success": False,
            "events": [],
            "message": f"Error searching notes: {str(e)}"
        })

async def async_publish_note(note_json):
    """Publish a note to configured relays."""
    client = Client()
    
    try:
        # Parse the event
        event = Event.from_json(note_json)
        
        # Verify the event before publishing
        if not event.verify():
            logging.error("[PUBLISH] Note failed verification")
            return False
            
        logging.info(f"[PUBLISH] Publishing note to {len(NOSTR_RELAYS)} relays...")
        
        # Connect to relays
        await client.add_relays(NOSTR_RELAYS)
        await client.connect()
        
        # Send the event
        output = await client.send_event(event)
        
        # Log the output details
        logging.info(f"[PUBLISH] Event ID: {event.id().to_hex()}")
        
        # Just log that we sent it since we can't check output details yet
        logging.info("[PUBLISH] Note sent to relays")
        
        # Return true if we got this far without exceptions
        return True
            
    except Exception as e:
        logging.error(f"[PUBLISH] Error publishing note: {e}")
        return False
    finally:
        await client.disconnect()

def publish_note(note):
    """Publish received note to relays."""
    logging.info(f"NOSTR note received for publishing")
    try:
        note_data = json.loads(note)
        note_type = NoteType(note_data.get('note_type', NoteType.STANDARD.value))
        success = asyncio.run(async_publish_note(note))
        logging.info(f"Published {note_type.name} note to relays: {success}")
        return success
    except Exception as e:
        logging.error(f"[PUBLISH] Error in publish_note: {e}")
        return False

# Create NWC payment command and send encrypted

def create_nwc_payment_command(nwc_storage, lightning_invoice):
    """
    Create NWC payment command using nwc_utils.tryToPayInvoice() directly.
    """
    try:
        # Get NWC connection data
        connection_data = nwc_storage.get_nwc_connection()
        if not connection_data:
            logging.error("[NWC] No stored NWC connection")
            return None
       
        # Import nwc_utils functions
        try:
            from nwc_utils import processNWCstring, tryToPayInvoice
        except ImportError as e:
            logging.error(f"[NWC] Failed to import nwc_utils: {e}")
            return None
       
        # Convert stored connection data directly to nwc_obj format
        # (no need to reconstruct URI just to parse it again)
        from nwc_utils import processNWCstring
        from nostr_sdk import Keys
        
        nwc_obj = {
            'wallet_pubkey': connection_data['wallet_pubkey'],
            'relay': connection_data['relay'], 
            'app_privkey': connection_data['secret'],
            'app_pubkey': Keys.parse(connection_data['secret']).public_key().to_hex()
        }
       
        if not nwc_obj:
            logging.error("[NWC] Failed to process NWC connection string")
            return None
       
        logging.info("[NWC] Creating payment using nwc_utils.tryToPayInvoice()")
       
        # Use tryToPayInvoice directly - this creates the complete signed event
        signed_event = tryToPayInvoice(nwc_obj, lightning_invoice)
       
        # Convert to JSON for transmission
        nwc_command = json.dumps(signed_event)
       
        logging.info("[NWC] Created payment command using tryToPayInvoice()")
        logging.info(f"[NWC] Event ID: {signed_event['id'][:8]}...")
       
        return nwc_command
       
    except Exception as e:
        logging.error(f"[NWC] Error creating payment command: {e}")
        import traceback
        logging.error(f"[NWC] Full traceback: {traceback.format_exc()}")
        return None
    
async def get_reference_author(client, note_id):

    # Get author display name for a referenced note.
    try:
        reference_filter = (Filter()
                        .ids([note_id])
                        .limit(1))
        
        source = EventSource.relays(timedelta(seconds=5))
        reference_events = await client.get_events_of([reference_filter], source)
        
        if reference_events:
            event = reference_events[0]
            event_data = json.loads(event.as_json())
            author_pubkey = PublicKey.from_hex(event_data.get('pubkey'))
            display_name, _ = await get_display_name(client, author_pubkey)
            return display_name or "unknown user"
    except Exception as e:
        logging.error(f"Error getting reference author: {e}")
        return "unknown user"

async def process_mentions_in_note(client, note_data):
    try:
        is_reply = any(tag[0] == 'e' for tag in note_data.get('tags', []))
        content = note_data.get('content', '')

        # Handle note1/nevent1 references first
        note_pattern = r'nostr:note1[a-zA-Z0-9]{59}'
        nevent_pattern = r'nostr:nevent1[a-zA-Z0-9]+'
        
        # Replace note references with short format
        for pattern in [note_pattern, nevent_pattern]:
            matches = re.finditer(pattern, content)
            for match in matches:
                note_ref = match.group(0)
                note_id = note_ref.split('1')[1]
                author = await get_reference_author(client, note_id)
                content = content.replace(note_ref, f"[referenced note by @{author}]")

        # Process mentions from p tags
        p_tags = [tag for tag in note_data.get('tags', []) if tag[0] == 'p']
        for tag in p_tags:
            try:
                pubkey = PublicKey.from_hex(tag[1])
                display_name, _ = await get_display_name(client, pubkey)
                if display_name:
                    # Fixed pattern with word boundary
                    npub_pattern = r'(?:nostr:)?npub[a-zA-Z0-9]{58}\b'
                    content = re.sub(npub_pattern, f"@{display_name}", content, count=1)
                    logging.info(f"Replaced mention with: @{display_name}")
            except Exception as e:
                logging.error(f"Error processing mention from p tag: {e}")

        # Remove nprofile mentions
        nprofile_pattern = r'(?:nostr:)?nprofile[a-zA-Z0-9]+'
        content = re.sub(nprofile_pattern, '', content)
        content = clean_content(content)
        note_data['content'] = content

        if not is_reply:
            note_data['tags'] = [tag for tag in note_data.get('tags', []) if tag[0] != 'p']

    except Exception as e:
        logging.error(f"Error in process_mentions_in_note: {e}")
    return note_data