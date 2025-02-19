# HAMSTR - NOSTR over Ham Radio

HAMSTR enables fully off-grid NOSTR communication over ham radio, allowing clients with no internet access to interact with NOSTR relays through a server with internet connectivity.

## Quick Start

### Prerequisites
- Valid amateur radio license
- Python 3.7+
- Node.js 16+
- KISS-compatible TNC (hardware or software like Direwolf)
- HF/VHF transceiver
- NOSTR private key (nsec)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/LibertyFarmer/hamstr.git
cd hamstr
```

2. Install backend dependencies:
```bash
pip install -r requirements.txt
```

3. Install and build frontend:
```bash
cd frontend
npm install
npm run build
cd ..
```

### Client Setup

1. Edit `backend/settings.ini`:
   - Set `CLIENT_HOST` and `CLIENT_PORT` for your TNC
   - Configure your callsign and SSID
   - Adjust baud rate if needed (default: 600)

2. Start client:
```bash
cd backend
python web_app.py
```

3. Access web interface:
   - Open `http://localhost:5000`
   - Go to Settings > NOSTR Login
   - Enter your nsec key
   - Configure TNC settings if needed

### Server Setup

1. Edit `backend/settings.ini`:
   - Set `SERVER_HOST` and `SERVER_PORT`
   - Configure server callsign
   - Add/modify NOSTR relay list if desired

2. Start server:
```bash
cd backend
python server.py
```

## Features

- Full NOSTR functionality
  - Read/write posts
  - Reply, boost, quote
  - Hashtag and text search
  - Following feed support
  - Profile display names
  - Lightning address support
- AX.25 protocol with KISS TNC
- Optimized for 300-600 baud operation
- Content compression for efficient transmission
- Secure key storage
- Socket.IO real-time logging
- Progress monitoring
- Dark mode support

## Technical Notes

### Radio Configuration
- Any KISS-compatible TNC supported
- Software TNCs must be in KISS mode
- Default ports: Client 8001, Server 8002
- Optimized for 300-600 baud
- Maximum packet size: 200 bytes

### Security
- NOSTR keys stored only on client
- All NOSTR operations happen client-side
- Server acts only as relay
- Encrypted key storage

## Future Features

- Dynamic baud rate adjustment
- Offline zaps using NOSTR Wallet Connect
- FLDIGI KISS packet support
- Reticulum network integration
- Decentralized authentication
- HF propagation optimization
- Performance enhancements for higher baud rates
- Server GUI interface

## Troubleshooting

- Verify TNC is in KISS mode
- Check port settings in settings.ini
- Ensure radio PTT is configured
- Monitor progress drawer for operation logs
- Check callsign settings format

## Support

- Submit issues on GitHub
- Contact via NOSTR: @LibertyFarmer
  - npub1uwh0m2y8y5489nhr27xn8vkumy8flefm30kkx3l0tcn0wss34kaszyfqu7

## License

This project is open-source under the MIT License.

## Contributing

Contributions welcome! Please feel free to submit pull requests.

---
ZAPS APPRECIATED! ⚡