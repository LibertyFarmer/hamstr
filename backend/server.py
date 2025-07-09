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
                        zap_data['nwc_relay'] = tag_value
            
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

    async def request_lightning_invoice_from_zap(self, lightning_address, amount_sats, zap_message=""):
        """Request Lightning invoice from LNURL callback (reuse existing method)."""
        # First resolve the Lightning address
        lnurl_data = await self.resolve_lightning_address(lightning_address)
        
        if lnurl_data is None:
            return None, "RECIPIENT_NOT_FOUND"
        
        # Then request the invoice
        return await self.request_lightning_invoice(lnurl_data, amount_sats, zap_message)
        
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

    async def request_lightning_invoice(self, lnurl_data, amount_sats, zap_message=""):
       
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
            
            # Make request to callback URL
            response = requests.get(callback_url, params=params, timeout=10)
            response.raise_for_status()
            
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
        """Parse NWC command packet."""
        try:
            # Format: "NWC:encrypted_command:wallet_pubkey:relay"
            if not message.startswith("NWC:"):
                raise ValueError("Invalid NWC command format")
            
            parts = message[4:].split(":", 3)  # Remove "NWC:" and split into 3 parts
            if len(parts) != 3:
                raise ValueError("Invalid NWC command parts")
            
            encrypted_command, wallet_pubkey, relay = parts
            
            return {
                'encrypted_command': encrypted_command,
                'wallet_pubkey': wallet_pubkey,
                'relay': relay
            }
            
        except Exception as e:
            logging.error(f"[NWC] Error parsing command: {e}")
            return None

    async def forward_nwc_payment(self, encrypted_command, wallet_pubkey, relay_url):
        """Forward encrypted NWC payment command to wallet relay."""
        try:
            import websockets
            import json
            
            logging.info(f"[NWC] Connecting to relay: {relay_url}")
            
            # Connect to NWC relay
            async with websockets.connect(relay_url) as websocket:
                # Create NIP-47 payment request event (kind 23194)
                # Note: This is a simplified version - the encrypted_command should be 
                # properly formatted as a NOSTR event, but for now we'll send it directly
                
                # For now, return mock success to test the flow
                # TODO: Implement proper NIP-47 event creation and relay communication
                logging.info(f"[NWC] Mock: Payment forwarded to wallet")
                
                return {
                    'success': True,
                    'preimage': 'mock_preimage_12345'
                }
                
        except Exception as e:
            logging.error(f"[NWC] Error forwarding payment: {e}")
            return {
                'success': False,
                'error_code': 'NETWORK_ERROR'
            }

    def handle_connected_session(self, session):
        logging.info(f"Handling session for {session.remote_callsign}")
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
                            logging.info(f"Process request returned: {type(response)}")
                            if response is None:
                                logging.error("Process request returned None")
                                continue
                            logging.info(f"About to send response of type: {type(response)}")
                            
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
                    logging.info("All zap packets received, processing kind 9734 note")
                    
                    # Reassemble and decompress the zap note
                    compressed_note = self.reassemble_note(session.received_packets)
                    
                    try:
                        decompressed_note = decompress_nostr_data(compressed_note)
                        zap_note_json = json.loads(decompressed_note)
                        
                        logging.info(f"[ZAP] Successfully parsed kind 9734 zap note")
                        
                        # For now, just send a simple success response
                        response_message = "ZAP_NOTE_RECEIVED"
                        success = self.core.send_single_packet(
                            session, 0, 0,
                            response_message.encode(),
                            MessageType.RESPONSE
                        )
                        
                        if success:
                            logging.info(f"[ZAP] Sent acknowledgment to client")
                        
                        # Clear received packets for next operation
                        session.received_packets.clear()
                        
                    except Exception as e:
                        logging.error(f"[ZAP] Error processing kind 9734 zap note: {e}")
                        # Send error response
                        error_message = "ZAP_NOTE_ERROR"
                        self.core.send_single_packet(
                            session, 0, 0,
                            error_message.encode(),
                            MessageType.RESPONSE
                        )

            elif msg_type == MessageType.NWC_PAYMENT_REQUEST:
                logging.info(f"[NWC] Received NWC_PAYMENT_REQUEST using proper packet system")
                
                # Use the same pattern as NOTE handling
                seq_num, total_packets, content = self.parse_note_packet(message)
                session.received_packets[seq_num] = content
                self.core.send_ack(session, seq_num)
                
                logging.info(f"Received NWC payment packet {seq_num}/{total_packets}")
                
                # Check if we have all packets
                if len(session.received_packets) == total_packets:
                    logging.info("All NWC payment packets received, processing")
                    
                    # Reassemble the NWC command
                    nwc_command = self.reassemble_note(session.received_packets)
                    
                    try:
                        logging.info(f"[NWC] Processing payment command")
                        
                        # For now, just send a mock success response
                        response_message = "NWC_PAYMENT_SUCCESS"
                        success = self.core.send_single_packet(
                            session, 0, 0,
                            response_message.encode(),
                            MessageType.RESPONSE
                        )
                        
                        if success:
                            logging.info(f"[NWC] Sent payment response to client")
                        
                        # Clear received packets for next operation
                        session.received_packets.clear()
                        
                    except Exception as e:
                        logging.error(f"[NWC] Error processing payment: {e}")
                        # Send error response
                        error_message = "NWC_PAYMENT_ERROR"
                        self.core.send_single_packet(
                            session, 0, 0,
                            error_message.encode(),
                            MessageType.RESPONSE
                        )
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
            
            if command_parts[0] != "GET_NOTES":
                logging.error("Step 3a: Unknown request type")
                return json.dumps({
                    "success": False,
                    "error_type": "INVALID_REQUEST",
                    "message": "Invalid request type - must be GET_NOTES"
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