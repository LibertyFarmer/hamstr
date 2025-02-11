# HAMSTR - Decentralized NOSTR over Ham Radio

HAMSTR (Ham-radio Assisted Message System for Transmitting NOSTR Reliably) enables fully off-grid NOSTR communication over ham radio. The system allows clients with no internet access to interact with NOSTR relays through a server with internet access, utilizing HF/VHF ham radio bands.

## Overview
- Client-server architecture enabling off-grid NOSTR access
- AX.25 protocol and KISS TNC implementation for packet transmission
- Support for 300-1200 baud operation (optimized for 300-600)
- Full NOSTR functionality: reading, writing, replies, boosts, quotes
- Text and hashtag search capabilities
- Following feed support
- Profile display names and lightning address support

## Requirements
- Python 3.7+
- KISS-compatible TNC (hardware or software like UZ7HO, Direwolf)
- HF/VHF transceiver for both client and server
- NOSTR private key (nsec)
- Valid amateur radio license and callsign

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/your-repo/hamstr.git
   cd hamstr
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### Client Setup
1. Run the client application:
   ```bash
   python web_app.py
   ```

2. Access the web interface:
   - Open your browser to `http://localhost:5173`

3. Configure NOSTR:
   - Go to Settings > NOSTR Login
   - Enter your nsec key in the encrypted input field
   - Your key will be securely stored for future use

4. Configure Client Settings:
   - Go to Settings > App Settings
   - Set your amateur radio callsign and SSID
   - Configure your TNC port (default: 8001)
   - Verify TNC connection
   - Optional: Adjust number of notes to request at a time

### Server Setup
1. Edit `settings.ini`:
   - Set server callsign and SSID
   - Configure TNC port if different from default
   - Optional: Add/modify NOSTR relay list

2. Run the server:
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
- Client callsign must be set in App Settings
- Server callsign must be configured in settings.ini
- Both require valid amateur radio callsigns
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

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.