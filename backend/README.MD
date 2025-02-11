# HAMSTR - Decentralized NOSTR over Ham Radio

HAMSTR (Ham-radio Assisted Message System for Transmitting NOSTR Reliably) is an open-source project enabling decentralized NOSTR communication over ham radio. This system allows off-grid clients to interact with NOSTR relays through a server with internet access, utilizing HF/VHF ham radio bands.

## Implemented Features

### Core Radio Features
- Client-server architecture for off-grid NOSTR interaction via ham radio
- AX.25 protocol and KISS TNC implementation for packet transmission
- Support for 300, 600, and 1200 baud operation
- Packet system with sequencing, retries, and missing packet requests
- CRC-32 checksum for error detection
- Connection workflow: Connect, Data Request, Ready exchange, Response, Done, Done_ACK, Disconnect
- Error handling with retries and timeouts
- State management using ModemState enum
- Configuration management via settings.ini

### NOSTR Features
- Full note writing and transmission from client to server
- Following feed with recent notes from followed accounts
- Proper note signing and verification
- Reply system with proper NOSTR tagging
- Profile display name support
- Image tag stripping for bandwidth efficiency
- SQLite-based note storage on client side

### UI Features
- Flask-based web UI for the client
- Real-time operation progress tracking
- Connection status monitoring
- Packet progress visualization
- User-friendly error notifications
- Responsive modal system for interactions
- Dark/Light mode support

## Known Bugs
1. Packet transmission stops if initial DONE message is missed by server, leading to timeout and disconnect regardless of packet status
2. Unexplained delay in note requesting process after packet ACK, particularly noticeable at 1200 baud
3. Browser refresh during active operations causes loss of operation tracking until completion

## Upcoming Features
- Dynamic baud rate adjustment based on signal conditions
- Frequency selection using propagation data
- FLDIGI KISS packet support for robust modes
- Content compression for bandwidth optimization
- Local relay implementation for offline operation
- Reticulum network integration
- Performance optimization for higher baud rates
- Decentralized authentication system
- Comprehensive documentation and inline comments

## Requirements
- Python 3.7+
- Software modem or TCP-based KISS compatible setup (e.g., UZ7HO, Direwolf with hamlib)
- HF transceiver for both client and server

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/your-repo/hamstr.git
   cd hamstr
   ```

2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

1. Edit `settings.ini`:
   - Set the callsign for client and server
   - Configure TNC ports if different from default
   - Set your NOSTR public key (npub)

2. Ensure your software modem (e.g., UZ7HO, Direwolf) is properly configured with PTT setup, and port configured for each.

## Usage

### Server
Run the server that is connected to an HF transceiver:
```
python server.py
```

### Client
Run the client app connected to an HF transceiver in the field:
```
python app.py
```

## Project Structure
- `app.py`: Client application
- `server.py`: Server application
- `core.py`: Core functionality
- `ax25_kiss_utils.py`: AX.25 and KISS protocol utilities
- `models.py`: Data models
- `networking.py`: Networking functions
- `config.py`: Configuration handling
- `settings.ini`: User-configurable settings
- `nostr.py`: NOSTR-related functionality

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is open-source and available under the MIT License.

## Contact
For questions or assistance, contact me on NOSTR:
@Liberty Farmer, npub1uwh0m2y8y5489nhr27xn8vkumy8flefm30kkx3l0tcn0wss34kaszyfqu7