# HAMSTR - Decentralized NOSTR over Ham Radio

HAMSTR enables fully off-grid NOSTR communication over ham radio. The system allows clients with no internet access to interact with NOSTR relays through a server with internet access, utilizing HF/VHF ham radio bands.

## NOTE

Currently, the client and server share a lot of libraries. For now, clone/download the repo into both client side and server side, then modify the ini. Hopefully, server GUI and non-shared settings/libraries will be in future soon.


## Overview
- Client-server architecture enabling off-grid NOSTR access
- AX.25 protocol and KISS TNC implementation for packet transmission
- Support for 300-1200 baud operation (optimized for 300-600)
- Full NOSTR functionality: reading, writing, replies, boosts, quotes
- Text and hashtag search capabilities
- Following feed support
- Profile display names and lightning address support for future integration

NOTE: Search notes by display name currently not working!

## Requirements
- Python 3.7+
- KISS-compatible TNC (hardware or software like UZ7HO, Direwolf)
- HF/VHF transceiver for both client and server
- NOSTR private key (nsec)
- Valid amateur radio license and callsign

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/LibertyFarmer/hamstr.git
   cd hamstr
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration and Running

1. Start KISS Client and Server TNC software - Both sides must match protocal and baudrate!

### Client Setup

1. Edit `/backend/data/client_settings.ini`:
   - Set client callsign and SSID

2. Run the client application:
   ```bash
   python web_app.py
   ```

3. Access the web interface:
   - Open your browser to `http://localhost:5000`

4. Configure NOSTR in App:
   - Go to Settings > NOSTR Login
   - Enter your nsec key in the encrypted input field
   - Your key will be securely stored for future use

5. Configure Client Settings in app:

   - Go to Settings > App Settings
   - Choose Baud Rate (MUST MATCH TNC ON CLIENT AND SERVER)
   - Configure your TNC port (Default: 8001)
   - Optional: Adjust number of notes to request at a time (Default: 2)

### Server Setup

1. On server, edit `/backend/settings.ini`:

   - Configure TNC port if different from default (Default: 8002)
   - Optional: Modify or add to default NOSTR relay list

2. On server, edit `/backend/data/server_settings.ini`:
   - Set server callsign and SSID

3. To Run the server:
   ```bash
   python server.py
   ```

## Important Notes

### TNC Configuration
- Any KISS-compatible TNC should work
- Software TNCs (UZ7HO, Direwolf) must be configured for KISS mode
- Verify TNC port settings match your configuration
- Default ports: Client 8001, Server 8002

### Callsign Setup
- Client callsign must be set in client_settings.ini
- Server callsign must be configured in server_settings.ini
- Both sides require valid amateur radio callsign AND SSID. use 0 if no SSID.
- SSID can be 0-15

### ⚠️ Warning
- Do not modify timeout settings, retry counts, or ACK parameters unless you understand the implications
- Default settings are optimized for reliable HF packet operation
- Incorrect timing settings can cause communication failures

### Performance Notes
- Optimized for 300-600 baud operation
- Higher baud rates available but may be less reliable
- Maximum packet size is 200 bytes
- Content compression is automatic

## Basic Operation
1. Start client and server applications
2. Configure settings as described above
3. Use the web interface to:
   - Read recent NOSTR posts
   - Write new posts
   - Reply to posts
   - Boost or quote posts
   - Search content
   - Follow other users

## Troubleshooting
- Verify TNC is in KISS mode
- Check port settings match TNC configuration
- Ensure radio PTT is properly configured
- Verify server is running and accessible
- Check callsign settings are correct
- Monitor progress drawer for detailed operation logs

## Security Notes
- Server never has access to NOSTR keys
- All NOSTR operations happen client-side
- Keys are stored securely on client only
- Server acts as a general relay point only

## Future Features
- Dynamic baud rate adjustment based on signal conditions
- Frequency selection using propagation data
- FLDIGI KISS packet support
- Optimize content compression
- Reticulum network integration
- Performance optimization for higher baud rates
- Decentralized authentication system
- Comprehensive documentation

## License
This project is open-source and available under the MIT License.

## Support
For questions or assistance:
- Submit issues on GitHub
- Contact via NOSTR: @LibertyFarmer
   npub: npub1uwh0m2y8y5489nhr27xn8vkumy8flefm30kkx3l0tcn0wss34kaszyfqu7

## Contributing
Contributions and feedback is welcome! Please feel free to submit a Pull Request.

ZAPS ALWAYS APPRECIATED!