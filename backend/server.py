import json
import threading
import logging
import signal
import time
import requests
import asyncio
from urllib.parse import quote
from core import Core, ModemState, MessageType
from nostr import search_nostr, run_get_recent_notes, publish_note, search_user_notes
from models import NoteRequestType, NoteType, NWCResponseCode, ZapType
from protocol_utils import compress_nostr_data, decompress_nostr_data
import urllib.parse
import config
import os



logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Server:
    def __init__(self):
        self.core = Core(is_server=True)
        self.running = True

    def stop(self, signum=None, frame=None):
        logging.info("Server shutdown requested.")
        self.running = False
        self.core.running = False
        
        def force_exit():
            logging.error("Force exiting due to shutdown timeout")
            os._exit(1)
        
        # Set a timer to force exit after 10 seconds
        timer = threading.Timer(10, force_exit)
        timer.start()

        try:
            self.core.stop()
        except Exception as e:
            logging.error(f"Error during core stop: {e}")
        
        timer.cancel()  # Cancel the force exit timer if we've made it this far

    def run(self):
        logging.info("Server is starting...")
        if not self.core.start():
            logging.error("Failed to start server. Exiting.")
            return

        logging.info("Server is running...")
        
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        def debug_thread():
            while self.running:
                logging.debug(f"Server still running. Active threads: {threading.active_count()}")
                time.sleep(5)

        threading.Thread(target=debug_thread, daemon=True).start()

        try:
            while self.running:
                logging.info("Waiting for incoming connections...")
                try:
                    session = self.core.handle_incoming_connection()
                    if session:
                        try:
                            self.handle_connected_session(session)
                        except Exception as e:
                            logging.error(f"Error handling session: {e}")
                        finally:
                            # Always reset after a session, whether successful or not
                            logging.info("Session ended, resetting for next connection")
                            self.core.reset_for_next_connection()
                    else:
                        # Also reset if no session was returned (failed connection attempt)
                        logging.info("Connection attempt failed or timed out, resetting for next connection")
                        self.core.reset_for_next_connection()
                    
                    self.cleanup_inactive_sessions()
                except Exception as e:
                    logging.error(f"Error in connection handling: {e}")
                    # Also reset on exceptions
                    logging.info("Resetting after connection error")
                    self.core.reset_for_next_connection()
                    
                time.sleep(0.1)  # Small delay to prevent tight loop
                
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Stopping server.")
        finally:
            logging.info("Server main loop exited. Cleaning up...")
            self.cleanup()
            logging.info("Server stopped.")

    def parse_kind9734_zap_note(self, zap_note_json):
    
        try:
            # Validate it's a kind 9734 event
            if zap_note_json.get('kind') != 9734:
                raise ValueError("Not a kind 9734 zap note")
            
            # Extract tags
            tags = zap_note_json.get('tags', [])
            zap_data = {
                'amount_sats': 0,
                'lnaddr': None,
                'recipient_pubkey': None,
                'note_id': None,
                'nwc_relay': None,
                'message': zap_note_json.get('content', '')
            }
            
            # Parse tags
            for tag in tags:
                if len(tag) >= 2:
                    tag_name = tag[0]
                    tag_value = tag[1]
                    
                    if tag_name == "amount":
                        # Amount is in millisats, convert to sats
                        zap_data['amount_sats'] = int(tag_value) // 1000
                    elif tag_name == "lnaddr":
                        zap_data['lnaddr'] = tag_value
                    elif tag_name == "p":
                        zap_data['recipient_pubkey'] = tag_value
                    elif tag_name == "e":
                        zap_data['note_id'] = tag_value
                    elif tag_name == "relay":
                        # Single NWC relay - THIS is what server uses for payment forwarding
                        zap_data['nwc_relay'] = tag_value
                        logging.info(f"[ZAP] Using NWC relay for payment: {tag_value}")
                    elif tag_name == "relays":
                        # Additional publishing relays - server ignores these for NWC
                        logging.info(f"[ZAP] Found additional publishing relays: {tag[1:]}")
            
            # Validate required fields
            if not zap_data['lnaddr'] or not zap_data['recipient_pubkey']:
                raise ValueError("Missing required zap data")
            
            if zap_data['amount_sats'] <= 0:
                raise ValueError("Invalid zap amount")
            
            logging.info(f"[ZAP] Parsed zap data: {zap_data['amount_sats']} sats to {zap_data['lnaddr']}")
            return zap_data
            
        except Exception as e:
            logging.error(f"[ZAP] Error parsing kind 9734 zap note: {e}")
            return None
        
    async def handle_zap_success(self, session):
        """Handle successful payment confirmation from client"""
        logging.info("[ZAP] Payment successful - Lightning payment completed")
        
        # Send success response to client
        await self.send_zap_final_response(session, True)
        
        # Set disconnecting state BEFORE sending disconnect
        session.state = ModemState.DISCONNECTING
        
        # Now send disconnect
        logging.info("[ZAP] Sending disconnect to client")
        self.core.send_disconnect(session)

    async def handle_zap_failure(self, session):
        """Handle payment failure"""
        logging.warning("[ZAP] Payment failed")
        
        # Send failure response to client
        await self.send_zap_final_response(session, False)
        
        # Now send disconnect
        logging.info("[ZAP] Sending disconnect to client")
        self.core.send_disconnect(session)

    async def send_zap_final_response(self, session, zap_published):
        """Send simple control message instead of compressed response"""
        if zap_published:
            # Send simple success control message
            self.core.send_single_packet(session, 0, 0, "ZAP_PUBLISHED".encode(), MessageType.READY)
            logging.info("[ZAP] Sent ZAP_PUBLISHED control message")
        else:
            # Send simple failure control message  
            self.core.send_single_packet(session, 0, 0, "ZAP_FAILED_PUBLISH".encode(), MessageType.READY)
            logging.info("[ZAP] Sent ZAP_FAILED_PUBLISH control message")

    async def request_lightning_invoice_from_zap(self, lightning_address, amount_sats, zap_note_json, zap_message=""):
        """Request Lightning invoice from LNURL callback with NIP-57 zap context."""
        # First resolve the Lightning address
        lnurl_data = await self.resolve_lightning_address(lightning_address)
        
        if lnurl_data is None:
            return None, "RECIPIENT_NOT_FOUND"
        
        # Then request the invoice WITH the zap note
        return await self.request_lightning_invoice(lnurl_data, amount_sats, zap_message, zap_note_json)
        
    async def resolve_lightning_address(self, lightning_address):
     
        #Convert lightning address (user@domain.com) to LNURL endpoint
        try:
            if "@" not in lightning_address:
                raise ValueError("Invalid Lightning address format")
            
            user, domain = lightning_address.split("@", 1)
            
            # LNURL-pay endpoint format: https://domain/.well-known/lnurlp/user
            lnurl_url = f"https://{domain}/.well-known/lnurlp/{user}"
            
            logging.info(f"[LNURL] Resolving {lightning_address} -> {lnurl_url}")
            
            # Make HTTP GET request to LNURL endpoint
            response = requests.get(lnurl_url, timeout=10)
            response.raise_for_status()
            
            lnurl_data = response.json()
            
            # Validate LNURL response
            if "callback" not in lnurl_data:
                raise ValueError("Invalid LNURL response - missing callback")
            
            if "minSendable" not in lnurl_data or "maxSendable" not in lnurl_data:
                raise ValueError("Invalid LNURL response - missing amount limits")
            
            logging.info(f"[LNURL] Successfully resolved {lightning_address}")
            logging.info(f"[LNURL] Callback: {lnurl_data['callback']}")
            logging.info(f"[LNURL] Min: {lnurl_data['minSendable']} msat")
            logging.info(f"[LNURL] Max: {lnurl_data['maxSendable']} msat")
            
            return lnurl_data
            
        except requests.exceptions.RequestException as e:
            logging.error(f"[LNURL] Network error resolving {lightning_address}: {e}")
            return None
        except Exception as e:
            logging.error(f"[LNURL] Error resolving {lightning_address}: {e}")
            return None

    async def request_lightning_invoice(self, lnurl_data, amount_sats, zap_message="", zap_note_json=None):
       
       #Request Lightning invoice from LNURL callback
        try:
            callback_url = lnurl_data["callback"]
            amount_msats = amount_sats * 1000  # Convert sats to millisats
            
            # Check amount limits
            min_sendable = lnurl_data.get("minSendable", 0)
            max_sendable = lnurl_data.get("maxSendable", float('inf'))
            
            if amount_msats < min_sendable:
                logging.error(f"[LNURL] Amount {amount_sats} sats below minimum {min_sendable/1000} sats")
                return None, "AMOUNT_TOO_LOW"
            
            if amount_msats > max_sendable:
                logging.error(f"[LNURL] Amount {amount_sats} sats above maximum {max_sendable/1000} sats")
                return None, "AMOUNT_TOO_HIGH"
            
            # Build callback URL with parameters
            params = {
                "amount": amount_msats
            }
            
            # Add nostr parameter for NIP-57 zap requests
            if zap_note_json:
                params["nostr"] = json.dumps(zap_note_json)
                logging.info(f"[LNURL-ZAP] Added nostr parameter for NIP-57 zap request (note ID: {zap_note_json.get('id', 'unknown')[:8]})")
            else:
                logging.info(f"[LNURL] No zap_note_json provided - regular LNURL payment")

            # Add comment if provided and supported
            if zap_message and lnurl_data.get("commentAllowed", 0) > 0:
                max_comment_length = lnurl_data["commentAllowed"]
                if len(zap_message) <= max_comment_length:
                    params["comment"] = zap_message
                else:
                    # Truncate message to fit
                    params["comment"] = zap_message[:max_comment_length]
            
            logging.info(f"[LNURL] Requesting invoice for {amount_sats} sats")
            logging.info(f"[LNURL] Callback: {callback_url}")
            
            # Make request to callback URL - manually build URL with params
            if params:
                url_params = urllib.parse.urlencode(params)
                full_url = f"{callback_url}?{url_params}"
            else:
                full_url = callback_url

            logging.info(f"[LNURL] Requesting URL: {full_url}")
            response = requests.get(full_url, timeout=10)
            
            invoice_data = response.json()
            
            # Check for errors
            if "status" in invoice_data and invoice_data["status"] == "ERROR":
                error_reason = invoice_data.get("reason", "Unknown error")
                logging.error(f"[LNURL] Invoice request failed: {error_reason}")
                return None, "INVOICE_ERROR"
            
            # Validate invoice response
            if "pr" not in invoice_data:
                logging.error("[LNURL] Invalid invoice response - missing 'pr' field")
                return None, "INVALID_INVOICE"
            
            lightning_invoice = invoice_data["pr"]
            
            logging.info(f"[LNURL] Successfully got invoice: {lightning_invoice[:50]}...")
            
            
            return lightning_invoice, None
            
        except requests.exceptions.RequestException as e:
            logging.error(f"[LNURL] Network error requesting invoice: {e}")
            return None, "NETWORK_ERROR"
        except Exception as e:
            logging.error(f"[LNURL] Error requesting invoice: {e}")
            return None, "UNKNOWN_ERROR"
        
    def parse_nwc_command(self, message):
        try:
            # Server doesn't parse encrypted content - just validates format
            # Accept any non-empty string as valid NWC command
            if message and len(message.strip()) > 0:
                return {
                    'encrypted_payload': message  # Store entire payload for forwarding
                }
            else:
                raise ValueError("Empty NWC command")
                
        except Exception as e:
            logging.error(f"[NWC] Error parsing command: {e}")
            return None

    async def forward_nwc_payment(self, signed_nwc_event_json, relay_url):
    
        try:
            import websockets
            import json
            import asyncio
            import secrets
            
            logging.info(f"[NWC DEBUG] Forwarding to wallet relay: {relay_url}")
            
            # Parse and log the complete event details
            try:
                signed_event = json.loads(signed_nwc_event_json)
                event_id = signed_event['id']
                client_pubkey = signed_event['pubkey']
                wallet_pubkey = signed_event['tags'][0][1] if signed_event.get('tags') else 'MISSING'
                
                logging.info(f"[NWC DEBUG] Event ID: {event_id}")
                logging.info(f"[NWC DEBUG] Client pubkey: {client_pubkey}")
                logging.info(f"[NWC DEBUG] Wallet pubkey: {wallet_pubkey}")
                logging.info(f"[NWC DEBUG] Event kind: {signed_event.get('kind')}")
                logging.info(f"[NWC DEBUG] Event tags: {signed_event.get('tags')}")
                logging.info(f"[NWC DEBUG] Content length: {len(signed_event.get('content', ''))}")
                
            except Exception as e:
                logging.error(f"[NWC DEBUG] Failed to parse signed event: {e}")
                return {'success': False, 'error': 'Invalid signed event format'}
            
            # Connect and debug the full flow
            async with websockets.connect(relay_url) as websocket:
                logging.info(f"[NWC DEBUG] Connected to wallet relay")
                
                # Step 1: Send the payment event FIRST (simpler approach)
                event_message = json.dumps(["EVENT", signed_event])
                await websocket.send(event_message)
                logging.info(f"[NWC DEBUG] Sent payment event to relay")
                logging.info(f"[NWC DEBUG] Event message: {event_message[:200]}...")
                
                # Step 2: Wait for relay OK
                relay_ok_received = False
                ok_timeout = 10
                ok_start = time.time()
                
                while time.time() - ok_start < ok_timeout and not relay_ok_received:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        message = json.loads(response)
                        logging.info(f"[NWC DEBUG] Received: {message}")
                        
                        if message[0] == "OK":
                            ok_event_id = message[1]
                            accepted = message[2]
                            error_msg = message[3] if len(message) > 3 else ""
                            
                            logging.info(f"[NWC DEBUG] Relay OK - Event: {ok_event_id[:8]}, Accepted: {accepted}")
                            if error_msg:
                                logging.info(f"[NWC DEBUG] Error message: {error_msg}")
                            
                            if accepted and ok_event_id == event_id:
                                logging.info(f"[NWC DEBUG] ✅ Relay accepted our payment event")
                                relay_ok_received = True
                            else:
                                logging.error(f"[NWC DEBUG] ❌ Relay rejected: {error_msg}")
                                return {'success': False, 'error': f'Relay error: {error_msg}'}
                        else:
                            logging.info(f"[NWC DEBUG] Other message type: {message[0]}")
                    
                    except asyncio.TimeoutError:
                        logging.info(f"[NWC DEBUG] No immediate response from relay...")
                        continue
                    except Exception as e:
                        logging.error(f"[NWC DEBUG] Error receiving OK: {e}")
                        continue
                
                if not relay_ok_received:
                    logging.error(f"[NWC DEBUG] ❌ No OK received from relay within timeout")
                    return {'success': False, 'error': 'No relay acknowledgment'}
                
                # Step 3: Now subscribe to responses and wait
                subscription_id = secrets.token_hex(8)
                subscribe_msg = [
                    "REQ",
                    subscription_id,
                    {
                        "kinds": [23195],  # NWC response kind
                        "#e": [event_id],  # Events referencing our payment request
                        "#p": [client_pubkey],  # Events to our client pubkey
                        "since": int(time.time()) - 60  # Look back 1 minute
                    }
                ]
                
                await websocket.send(json.dumps(subscribe_msg))
                logging.info(f"[NWC DEBUG] Subscribed with filter: {subscribe_msg}")
                
                # Step 4: Wait for wallet response
                payment_response = None
                response_timeout = 20  # Shorter timeout for debugging
                start_time = time.time()
                
                logging.info(f"[NWC DEBUG] Waiting up to {response_timeout}s for wallet response...")
                
                while time.time() - start_time < response_timeout:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                        message = json.loads(response)
                        
                        logging.info(f"[NWC DEBUG] Received during wait: {message[0]} - {message}")
                        
                        if message[0] == "EVENT":
                            response_event = message[2]
                            logging.info(f"[NWC DEBUG] Response event kind: {response_event.get('kind')}")
                            logging.info(f"[NWC DEBUG] Response event tags: {response_event.get('tags', [])}")
                            
                            if response_event.get('kind') == 23195:
                                logging.info(f"[NWC DEBUG] 🎯 Found kind 23195 response!")
                                # Check if it references our event
                                event_tags = [tag for tag in response_event.get('tags', []) if tag[0] == 'e']
                                if any(event_id in tag for tag in event_tags):
                                    logging.info(f"[NWC DEBUG] ✅ Response references our event!")
                                    payment_response = response_event
                                    break
                                else:
                                    logging.info(f"[NWC DEBUG] ❌ Response doesn't reference our event")
                        
                        elif message[0] == "EOSE":
                            logging.info(f"[NWC DEBUG] End of stored events")
                            continue
                    
                    except asyncio.TimeoutError:
                        logging.info(f"[NWC DEBUG] Still waiting... ({int(time.time() - start_time)}s elapsed)")
                        continue
                    except Exception as e:
                        logging.error(f"[NWC DEBUG] Error during wait: {e}")
                        continue
                
                # Step 5: Close subscription
                await websocket.send(json.dumps(["CLOSE", subscription_id]))
                logging.info(f"[NWC DEBUG] Closed subscription")
                
                # Step 6: Return results
                if payment_response:
                    logging.info(f"[NWC DEBUG] ✅ SUCCESS: Payment response received!")
                    return {
                        'success': True, 
                        'message': 'Payment processed',
                        'encrypted_response': payment_response
                    }
                else:
                    logging.warning(f"[NWC DEBUG] ❌ TIMEOUT: No payment response within {response_timeout}s")
                    return {
                        'success': False, 
                        'error': f'Payment timeout - no response from wallet after {response_timeout}s'
                    }
                
        except Exception as e:
            logging.error(f"[NWC DEBUG] Error forwarding payment: {e}")
            import traceback
            logging.error(f"[NWC DEBUG] Full traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}

    def handle_connected_session(self, session):
        logging.info(f"Handling session for {session.remote_callsign}")
        
        # NEW: DirectProtocol detection and handling
        if (hasattr(self.core, 'protocol_manager') and 
            self.core.protocol_manager and 
            self.core.protocol_manager.get_protocol_type() == 'DirectProtocol'):
            
            logging.info("[SERVER] Using DirectProtocol - waiting for JSON request")
            
            try:
                # Wait for direct JSON request (no packet protocol)
                request_data = self.core.protocol_manager.receive_nostr_response(session, timeout=30)
                
                if request_data:
                    logging.info(f"[SERVER] Received DirectProtocol request: {request_data.get('type')}")
                    
                    # Convert to format your existing process_request expects
                    request_type = request_data.get('type', 'GET_NOTES')
                    count = request_data.get('count', 2)
                    params = request_data.get('params', '')
                    
                    if params:
                        request_string = f"{request_type} {count} {params}"
                    else:
                        request_string = f"{request_type} {count}"
                    
                    # Use your existing process_request method
                    response = self.process_request(request_string)
                    
                    # Send response back via DirectProtocol
                    response_data = {'data': response}
                    success = self.core.protocol_manager.send_nostr_request(session, response_data)
                    
                    if success:
                        logging.info("[SERVER] DirectProtocol response sent")
                        return  # Done - exit the method
                    else:
                        logging.error("[SERVER] Failed to send DirectProtocol response")
                
            except Exception as e:
                logging.error(f"[SERVER] DirectProtocol error: {e}")
        
        # OLD CODE INSERTION POINT: Insert your original code starting here
        logging.info("[SERVER] Using packet protocol")
        
        received_packets = {}
        total_packets = None
        is_note = False
        is_sending_initial_data = False  # Initialize the flag
        
        while session.state in [ModemState.CONNECTED, ModemState.DISCONNECTING] and self.running:
            source_callsign, message, msg_type = self.core.receive_message(session, timeout=1.0)

            if msg_type == MessageType.READY:
                logging.info(f"Received READY from {source_callsign}")
                self.core.send_single_packet(session, 0, 0, "READY".encode(), MessageType.READY)
            elif msg_type == MessageType.NOTE:
                is_note = True
                seq_num, total, content = self.parse_note_packet(message)
                if total_packets is None:
                    total_packets = total
                received_packets[seq_num] = content
                self.core.send_ack(session, seq_num)
                
                logging.info(f"Received packet {seq_num}/{total_packets} for NOTE")
                
                if len(received_packets) == total_packets:
                    logging.info("All note packets received. Waiting for DONE from client.")
            elif msg_type == MessageType.DATA_REQUEST:
                logging.info(f"Received DATA_REQUEST: {message}")
                if self.core.send_ready(session):
                    logging.info("Sent READY, waiting for client READY")
                    if self.core.wait_for_ready(session):
                        try:
                            logging.info("About to process request")
                            response = self.process_request(message)
                            
                            if response is None:
                                logging.error("Process request returned None")
                                continue
                            
                            # Parse response to log meaningful info
                            try:
                                import json
                                response_data = json.loads(response)
                                if isinstance(response_data, dict) and 'events' in response_data:
                                    note_count = len(response_data['events'])
                                    logging.info(f"Successfully prepared {note_count} note(s) for transmission")
                                else:
                                    logging.info(f"Prepared response for transmission")
                            except:
                                logging.info(f"Prepared response for transmission")
                            
                            if self.core.send_response(session, response):
                                logging.info("Response sent successfully")
                                continue
                            else:
                                logging.error("Failed to send response")
                        except Exception as e:
                            logging.error(f"Error in request handling: {str(e)}", exc_info=True)
                    else:
                        logging.error("Did not receive READY message from client")
                else:
                    logging.error("Failed to send READY for DATA_REQUEST")
           
            elif msg_type == MessageType.ZAP_KIND9734_REQUEST:
                logging.info(f"[ZAP] Received ZAP_KIND9734_REQUEST using proper packet system")
                
                # Use the same pattern as NOTE handling - let the packet system reassemble
                seq_num, total_packets, content = self.parse_note_packet(message)
                session.received_packets[seq_num] = content
                self.core.send_ack(session, seq_num)
                
                logging.info(f"Received zap packet {seq_num}/{total_packets}")
                
                # Check if we have all packets
                if len(session.received_packets) == total_packets:
                    logging.info("All zap packets received, waiting for DONE from client")
                    
                    # Wait for DONE message (like DATA_REQUEST pattern)
                    done_received = False
                    start_time = time.time()
                    timeout = config.CONNECTION_TIMEOUT
                    
                    while time.time() - start_time < timeout and not done_received:
                        source_callsign, message, msg_type = self.core.receive_message(session, timeout=1.0)
                        if msg_type == MessageType.DONE:
                            logging.info("[ZAP] Received DONE from client, sending DONE_ACK")
                            # Send DONE_ACK
                            self.core.send_single_packet(session, 0, 0, "DONE_ACK".encode(), MessageType.DONE_ACK)
                            done_received = True
                            break
                    
                    if not done_received:
                        logging.error("[ZAP] Timeout waiting for DONE from client")
                        continue
                    
                    # Now process the zap and follow READY pattern
                    try:
                        # Reassemble and decompress the zap note
                        compressed_note = self.reassemble_note(session.received_packets)
                        decompressed_note = decompress_nostr_data(compressed_note)
                        zap_note_json = json.loads(decompressed_note)
                        
                        logging.info(f"[ZAP] Successfully parsed kind 9734 zap note")
                        
                        # Extract zap data from kind 9734 note
                        zap_data = self.parse_kind9734_zap_note(zap_note_json)

                        logging.info(f"[ZAP DEBUG] Full incoming kind 9734 note: {json.dumps(zap_note_json, indent=2)}")
                        
                        if zap_data:
                            # Store the relay URL in the session for later use
                            session.nwc_relay_url = zap_data.get('nwc_relay', 'wss://relay.getalby.com/v1')
                            
                            # PHASE 4B: STORE ZAP NOTE FOR LATER PUBLISHING
                            session.zap_kind9734_note = zap_note_json  # Add this line
                            logging.info("[ZAP] Cached zap note for publishing after payment")
                            
                            # Generate Lightning invoice FIRST (before sending READY)
                            logging.info(f"[ZAP] Generating Lightning invoice for {zap_data['amount_sats']} sats to {zap_data['lnaddr']}")
                            
                            # Fix: Import asyncio at proper scope
                            import asyncio
                            
                            # Generate Lightning invoice
                            invoice, error = asyncio.run(self.request_lightning_invoice_from_zap(
                                zap_data['lnaddr'], 
                                zap_data['amount_sats'], 
                                zap_note_json,
                                zap_data['message']
                            ))
                            
                            if invoice:
                                # Create successful response
                                response_data = {
                                    "success": True,
                                    "invoice": invoice,
                                    "amount_sats": zap_data['amount_sats'],
                                    "recipient": zap_data['lnaddr']
                                }
                                
                                response_json = json.dumps(response_data)
                                compressed_response = compress_nostr_data(response_json)
                                
                                # Send server READY (server ready to send invoice)
                                if self.core.send_ready(session):
                                    logging.info("[ZAP] Sent READY, waiting for client READY")
                                    
                                    # Wait for client READY (client ready to receive invoice)
                                    if self.core.wait_for_ready(session):
                                        logging.info("[ZAP] Client READY received, sending Lightning invoice")
                                        
                                        # Send Lightning invoice using proper HAMSTR response method
                                        if self.core.send_response(session, compressed_response):
                                            logging.info("[ZAP] Lightning invoice sent successfully")
                                            
                                            # PHASE 2 CONTINUATION: Wait for client READY for NWC payment phase
                                            logging.info("[ZAP] Waiting for client READY for NWC payment phase")
                                            
                                            if self.core.wait_for_ready(session):
                                                logging.info("[ZAP] Client READY received for NWC payment, sending server READY")
                                                
                                                # Send server READY (server ready to receive NWC command)
                                                if self.core.send_ready(session):
                                                    logging.info("[ZAP] Server READY sent for NWC payment phase")
                                                    logging.info("[ZAP] Session continuing to NWC payment handler...")
                                                    # Session continues - NWC_PAYMENT_REQUEST handler will take over
                                                else:
                                                    logging.error("[ZAP] Failed to send server READY for NWC phase")
                                            else:
                                                logging.error("[ZAP] Client not ready for NWC payment phase")
                                        else:
                                            logging.error("[ZAP] Failed to send Lightning invoice")
                                    else:
                                        logging.error("[ZAP] Client not ready to receive invoice")
                                else:
                                    logging.error("[ZAP] Failed to send READY for invoice response")
                                    
                            else:
                                # Invoice generation failed
                                logging.error(f"[ZAP] Invoice generation failed: {error}")
                                
                                if self.core.send_ready(session):
                                    if self.core.wait_for_ready(session):
                                        error_response = json.dumps({
                                            "success": False,
                                            "error": "INVOICE_ERROR",
                                            "message": f"Failed to generate invoice: {error}"
                                        })
                                        compressed_error = compress_nostr_data(error_response)
                                        self.core.send_response(session, compressed_error)
                        else:
                            # Zap note parsing failed
                            logging.error("[ZAP] Failed to parse kind 9734 zap note")
                            
                            if self.core.send_ready(session):
                                if self.core.wait_for_ready(session):
                                    error_response = json.dumps({
                                        "success": False,
                                        "error": "INVALID_ZAP_NOTE",
                                        "message": "Failed to parse kind 9734 zap note"
                                    })
                                    compressed_error = compress_nostr_data(error_response)
                                    self.core.send_response(session, compressed_error)
                        
                        # Clear received packets
                        session.received_packets.clear()
                        
                    except Exception as e:
                        logging.error(f"[ZAP] Error processing zap: {e}")
                        if self.core.send_ready(session):
                            if self.core.wait_for_ready(session):
                                error_response = json.dumps({
                                    "success": False,
                                    "error": "PROCESSING_ERROR",
                                    "message": f"Error processing zap: {str(e)}"
                                })
                                compressed_error = compress_nostr_data(error_response)
                                self.core.send_response(session, compressed_error)
                                
            elif msg_type == MessageType.NWC_PAYMENT_REQUEST:
                logging.info(f"[NWC] Received NWC_PAYMENT_REQUEST using proper packet system")
                
                # Use the same pattern as ZAP handling
                seq_num, total_packets, content = self.parse_note_packet(message)
                session.received_packets[seq_num] = content
                self.core.send_ack(session, seq_num)
                
                logging.info(f"Received NWC payment packet {seq_num}/{total_packets}")
                
                # Check if we have all packets
                if len(session.received_packets) == total_packets:
                    logging.info("All NWC payment packets received, waiting for DONE from client")
                    
                    # Wait for DONE message (like ZAP pattern)
                    done_received = False
                    start_time = time.time()
                    timeout = config.CONNECTION_TIMEOUT
                    
                    while time.time() - start_time < timeout and not done_received:
                        source_callsign, message, msg_type = self.core.receive_message(session, timeout=1.0)
                        if msg_type == MessageType.DONE:
                            logging.info("[NWC] Received DONE from client, sending DONE_ACK")
                            # Send DONE_ACK
                            self.core.send_single_packet(session, 0, 0, "DONE_ACK".encode(), MessageType.DONE_ACK)
                            done_received = True
                            break
                    
                    if not done_received:
                        logging.error("[NWC] Timeout waiting for DONE from client")
                        continue
                    
                    # Now process the NWC payment command
                    try:
                        # Reassemble and decompress the NWC command
                        compressed_command = self.reassemble_note(session.received_packets)
                        nwc_command = decompress_nostr_data(compressed_command)
                        
                        logging.info(f"[NWC] Successfully received NWC command")
                        
                        # Parse the NWC command format
                        nwc_data = self.parse_nwc_command(nwc_command)
                        
                        logging.info(f"[DEBUG] nwc_data result: {nwc_data}")
                        
                        if nwc_data:
                            logging.info("[DEBUG] About to store relay URL")
                            # Store the relay URL in the session for later use
                            session.nwc_relay_url = zap_data.get('nwc_relay', 'wss://relay.getalby.com/v1')
                            logging.info("[DEBUG] Stored relay URL, about to start payment forwarding")
                            
                            # Forward payment to NWC wallet immediately (no premature READY)
                            logging.info("[DEBUG] Starting async payment processing")
                            import asyncio
                            
                            # Run the async payment forwarding
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                logging.info("[NWC] Starting payment forwarding...")
                                # Use relay URL stored from zap note (not from encrypted command)
                                relay_url = getattr(session, 'nwc_relay_url', 'wss://relay.getalby.com/v1')

                                payment_result = loop.run_until_complete(
                                    self.forward_nwc_payment(
                                        nwc_data['encrypted_payload'],  # Use new field name
                                        relay_url  # Use stored relay instead of parsed relay
                                    )
                                )
                                logging.info(f"[NWC] Payment forwarding completed: {payment_result}")
                            finally:
                                loop.close()
                            
                            # Send payment result back to client using proper packet system
                            response_json = json.dumps(payment_result)
                            compressed_response = compress_nostr_data(response_json)

                            # Use proper READY handshake + response like ZAP does
                            if self.core.send_ready(session):
                                logging.info("[NWC] Sent READY for payment response")
                                if self.core.wait_for_ready(session):
                                    logging.info("[NWC] Client READY received, sending payment response")
                                    if self.core.send_response(session, compressed_response):
                                        logging.info("[NWC] Payment response sent successfully")
                                    else:
                                        logging.error("[NWC] Failed to send payment response")
                                else:
                                    logging.error("[NWC] Client not ready for payment response")
                            else:
                                logging.error("[NWC] Failed to send READY for payment response")
                                
                        else:
                            logging.error("[NWC] Failed to parse NWC command")
                            # Send error response using proper packet system
                            error_response = json.dumps({
                                "success": False,
                                "error": "Invalid NWC command format"
                            })
                            compressed_error = compress_nostr_data(error_response)
                            
                            if self.core.send_ready(session):
                                if self.core.wait_for_ready(session):
                                    self.core.send_response(session, compressed_error)
                        
                        # Clear received packets
                        session.received_packets.clear()
                        
                    except Exception as e:
                        logging.error(f"[NWC] Error processing NWC command: {e}")
                        # Send error response using proper packet system
                        error_response = json.dumps({
                            "success": False,
                            "error": f"Processing error: {str(e)}"
                        })
                        compressed_error = compress_nostr_data(error_response)
                        
                        if self.core.send_ready(session):
                            if self.core.wait_for_ready(session):
                                self.core.send_response(session, compressed_error)
                                
            elif msg_type == MessageType.ZAP_SUCCESS_CONFIRM:
                logging.info("[ZAP] Payment successful! Publishing zap note...")
                asyncio.run(self.handle_zap_success(session))

            elif msg_type == MessageType.ZAP_FAILED:
                logging.info("[ZAP] Payment failed! Cleaning up...")
                asyncio.run(self.handle_zap_failure(session))   

            elif msg_type == MessageType.DONE:
                logging.info("Received DONE from client")
                if is_note:
                    if len(received_packets) == total_packets:
                        self.core.send_single_packet(session, 0, 0, "DONE_ACK".encode(), MessageType.DONE_ACK)
                        logging.info("Sent DONE_ACK to client for NOTE")
                        full_note = self.reassemble_note(received_packets)
                        self.process_note(full_note)
                        logging.info("Waiting for client to initiate disconnect")
                        is_note = False  # Reset the flag to prevent reprocessing
                    else:
                        logging.warning("Received DONE but not all packets are present. Requesting missing packets.")
                        missing_packets = self.check_missing_packets(received_packets, total_packets)
                        self.request_missing_packets(session, missing_packets)
                else:
                    # This is for the case when client is sending DONE for other message types
                    self.core.send_single_packet(session, 0, 0, "DONE_ACK".encode(), MessageType.DONE_ACK)
                    logging.info("Sent DONE_ACK to client for non-NOTE message")
            elif msg_type == MessageType.DONE_ACK:
                logging.info(f"Received DONE_ACK from {source_callsign}")
                # This is for the case when server is sending data (e.g., in DATA_REQUEST)
                # Do nothing here, wait for client to initiate disconnect
            elif msg_type == MessageType.DISCONNECT:
                logging.info(f"Received DISCONNECT message from {source_callsign}")
                self.core.connection_manager.handle_disconnect_request(session)
                break
            elif msg_type == MessageType.ACK:
                logging.info(f"Received ACK from {source_callsign}")
                if session.state == ModemState.DISCONNECTING:
                    self.core.connection_manager.cleanup_session(session)
                    break
            elif msg_type == MessageType.PKT_MISSING:
                logging.info(f"Received PKT_MISSING request: {message}")
                if not is_sending_initial_data:  # Add a flag to track if initial data is being sent
                    if self.core.packet_handler.handle_missing_packets_sender(session, message):
                        logging.info("Missing packets sent successfully")
                    else:
                        logging.error("Failed to send missing packets")
                else:
                    logging.info("Received PKT_MISSING while sending initial data. Continuing with initial send.")
            elif msg_type == MessageType.RESPONSE:
                # This is to handle resent packets for notes
                seq_num, total, content = self.parse_note_packet(message)
                received_packets[seq_num] = content
                self.core.send_ack(session, seq_num)
                logging.info(f"Received resent packet {seq_num}/{total_packets} for NOTE")
                
                if len(received_packets) == total_packets:
                    logging.info("All packets received after resend. Waiting for DONE from client.")
            elif msg_type is not None:
                logging.info(f"Received message: Type={msg_type}, Content={message[:50]}...")

            if time.time() - session.last_activity > config.CONNECTION_TIMEOUT:
                logging.info(f"Connection timeout for {session.remote_callsign}")
                self.core.connection_manager.initiate_disconnect(session)
                break

            if not self.running:
                logging.info("Server is shutting down, ending session")
                self.core.connection_manager.initiate_disconnect(session)
                break

            time.sleep(0.1)

        logging.info(f"Session ended for {session.remote_callsign}")

    def parse_note_packet(self, message):
        header, content = message.split(':', 1)
        seq_num, total, _ = header.split('|')
        return int(seq_num), int(total), content

    def reassemble_note(self, received_packets):
        return ''.join(received_packets[i] for i in sorted(received_packets.keys()))

    def process_note(self, note):
        """Process and publish note to NOSTR network."""
        logging.info("Processing received note")
        try:
            decompressed_note = decompress_nostr_data(note)
            note_data = json.loads(decompressed_note)
            note_type = NoteType(note_data.get('note_type', NoteType.STANDARD.value))
            logging.info(f"Processing {note_type.name} note type")
            
            if note_type != NoteType.STANDARD:
                if not note_data.get('reply_to') or not note_data.get('reply_pubkey'):
                    logging.error("Missing required reply metadata")
                    return
            
            success = publish_note(decompressed_note)
            if success:
                logging.info(f"{note_type.name} note published successfully")
            else:
                logging.error(f"Failed to publish {note_type.name} note")
                
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding note JSON: {e}")
        except Exception as e:
            logging.error(f"Error processing note: {e}")

    def reassemble_note(self, received_packets):
        return ''.join(received_packets[i] for i in sorted(received_packets.keys()))
    
    def check_missing_packets(self, received_packets, total_packets):
        return set(range(1, total_packets + 1)) - set(received_packets.keys())

    def request_missing_packets(self, session, missing_packets):
        missing_packets_str = "|".join(map(str, missing_packets))
        self.core.send_single_packet(session, 0, 0, f"PKT_MISSING|{missing_packets_str}".encode(), MessageType.PKT_MISSING)

    def parse_missing_packets(self, message):
        _, missing_packets_str = message.split('|', 1)
        return list(map(int, missing_packets_str.split('|')))

    def process_request(self, request):
        try:
            logging.info("Step 1: Entering process_request")
            command_parts = request.strip().split(' ', 1)
            logging.info(f"Step 2: Command parts: {command_parts}")
            
            # Check if it's a valid command type
            if command_parts[0] not in ["GET_NOTES", "SEND_ZAP"]:
                logging.error("Step 3a: Unknown request type")
                return json.dumps({
                    "success": False,
                    "error_type": "INVALID_REQUEST",
                    "message": "Invalid request type - must be GET_NOTES or SEND_ZAP"
                })

            if len(command_parts) != 2:
                logging.error("Step 3b: Invalid command format")
                return json.dumps({
                    "success": False,
                    "error_type": "INVALID_FORMAT",
                    "message": "Invalid request format"
                })

            params = command_parts[1].split('|')
            logging.info(f"Step 4: Params after split: {params}")
            
            # Handle SEND_ZAP requests
            if command_parts[0] == "SEND_ZAP":
                logging.info("Processing SEND_ZAP request")
                
                if len(params) < 2:
                    logging.error("SEND_ZAP: Missing zap note data")
                    return json.dumps({
                        "success": False,
                        "error_type": "MISSING_PARAMS",
                        "message": "Missing zap note data"
                    })
                
                compressed_note = params[1]
                
                try:
                    # Decompress and parse the kind 9734 zap note  
                    decompressed_note = decompress_nostr_data(compressed_note)
                    zap_note_json = json.loads(decompressed_note)
                    
                    # Extract zap data from kind 9734 note
                    zap_data = self.parse_kind9734_zap_note(zap_note_json)
                    
                    if zap_data:
                        # Generate Lightning invoice using LNURL-pay
                        logging.info(f"[ZAP] Generating Lightning invoice for {zap_data['amount_sats']} sats")
                        
                        invoice, error = asyncio.run(self.request_lightning_invoice_from_zap(
                            zap_data['lnaddr'], 
                            zap_data['amount_sats'], 
                            zap_note_json,
                            zap_data['message']
                        ))
                        
                        if invoice:
                            # Create invoice response
                            invoice_response = json.dumps({
                                "success": True,
                                "invoice": invoice,
                                "amount_sats": zap_data['amount_sats'],
                                "message": "Lightning invoice generated successfully"
                            })
                            
                            logging.info("[ZAP] Lightning invoice generated successfully")
                            return compress_nostr_data(invoice_response)
                        else:
                            error_response = json.dumps({
                                "success": False,
                                "error": "INVOICE_GENERATION_ERROR",
                                "message": f"Failed to generate Lightning invoice: {error}"
                            })
                            return compress_nostr_data(error_response)
                    else:
                        error_response = json.dumps({
                            "success": False,
                            "error": "INVALID_ZAP_NOTE",
                            "message": "Failed to parse kind 9734 zap note"
                        })
                        return compress_nostr_data(error_response)
                        
                except Exception as e:
                    logging.error(f"[ZAP] Error processing zap request: {e}")
                    error_response = json.dumps({
                        "success": False,
                        "error": "PROCESSING_ERROR",
                        "message": f"Error processing zap: {str(e)}"
                    })
                    return compress_nostr_data(error_response)

            # Handle GET_NOTES requests (existing logic)
            elif command_parts[0] == "GET_NOTES":
                if len(params) < 2:
                    logging.error("Step 5: Not enough parameters")
                    return json.dumps({
                        "success": False,
                        "error_type": "MISSING_PARAMS",
                        "message": "Missing required parameters"
                    })

                request_type = NoteRequestType(int(params[0]))
                count = int(params[1])
                search_text = params[2] if len(params) > 2 else None
                
                logging.info(f"Step 6: Parsed values - type: {request_type}, count: {count}, search: {search_text}")
                logging.info(f"Step 7: About to select handler for type {request_type}")
                
                response_data = None
                # Handle each request type
                if request_type == NoteRequestType.SPECIFIC_USER:
                    logging.info("Step 8a: Using SPECIFIC_USER handler")
                    response_data = run_get_recent_notes(search_text, count)
                elif request_type == NoteRequestType.FOLLOWING:
                    logging.info("Step 8b: Using FOLLOWING handler")
                    if not search_text:
                        return json.dumps({
                            "success": False,
                            "error_type": "MISSING_NPUB",
                            "message": "NPUB is required for this request type"
                        })
                    response_data = run_get_recent_notes(search_text, count, request_type)
                elif request_type == NoteRequestType.GLOBAL:
                    logging.info("Step 8c: Using GLOBAL handler")
                    response_data = run_get_recent_notes(search_text, count, request_type)
                elif request_type == NoteRequestType.SEARCH_USER:
                    if not search_text:
                        logging.error("Step 8d: Missing search text for user search")
                        return json.dumps({
                            "success": False,
                            "error_type": "MISSING_SEARCH",
                            "message": "Search text is required for user search"
                        })
                    logging.info(f"Step 8d: Using search_user_notes handler")
                    response_data = run_get_recent_notes(search_text, count, request_type)
                elif request_type == NoteRequestType.SEARCH_TEXT:
                    logging.info("Step 8e: Using SEARCH_TEXT handler")
                    response_data = search_nostr(request_type, count, search_text)
                elif request_type == NoteRequestType.SEARCH_HASHTAG:
                    logging.info("Step 8f: Using SEARCH_HASHTAG handler")
                    response_data = search_nostr(request_type, count, search_text)
                else:
                    logging.error(f"Step 8g: Unknown request type: {request_type}")
                    return json.dumps({
                        "success": False,
                        "error_type": "INVALID_REQUEST_TYPE",
                        "message": f"Invalid request type: {request_type.name}"
                    })

                # Compress the response before returning
                compressed_response = compress_nostr_data(response_data)
                return compressed_response

        except ValueError as e:
            logging.error(f"Error in request processing: {e}")
            return json.dumps({
                "success": False,
                "error_type": "PROCESSING_ERROR",
                "message": f"Error processing request: {str(e)}"
            })
        except Exception as e:
            logging.error(f"Error in process_request: {str(e)}")
            return json.dumps({
                "success": False,
                "error_type": "SYSTEM_ERROR",
                "message": "Internal system error occurred"
            })
    
    def cleanup(self):
        for session in list(self.core.sessions.values()):
            if session.state != ModemState.DISCONNECTING and session.state != ModemState.DISCONNECTED:
                self.core.disconnect(session)
        logging.info("All sessions closed.")

    def cleanup_inactive_sessions(self):
        current_time = time.time()
        for session_id in list(self.core.sessions.keys()):
            session = self.core.sessions[session_id]
            if current_time - session.last_activity > config.CONNECTION_TIMEOUT:
                logging.info(f"Session {session_id} timed out. Disconnecting.")
                self.core.disconnect(session)

if __name__ == "__main__":
    server = Server()
    server.run()