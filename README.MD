# HAMSTR - NOSTR over Ham Radio

HAMSTR enables fully off-grid NOSTR communication over ham radio, allowing clients with no internet access to interact with NOSTR relays through a server with internet connectivity.

NOTE - In this early ALPHA version, the client and server still share a lot of libraries and some settings. The best way to install and use is to follow the directions below on the client machine first by cloning the repo, then setting it up as shown below, after that clone again on the server and follow the server setup and run. The server currently has no GUI, python console only. You will need to have the client online to install and setup, obviously. After that, you can access offline via a web browser. Power users can change the localhost to the machine ip address and access via IP address if they understand flask and the like.

I can try to help, but this is not currently for anyone other than experienced ham radio packet users, those with hf or other data setups, etc... I am not going to troubleshoot or help with every type of radio out there for data modes. For that, see your TNC software docs or forums.



## Quickish Start

### Prerequisites
- Valid amateur radio license
- Python 3.7+
- Node.js 16+
- KISS-compatible TNC (hardware or software like Direwolf)
- HF/VHF transceiver
- NOSTR private key (nsec)

### Installation

1. Clone the repository(will need to on client then again on server):
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

### Server Setup - Once repo cloned on server

1. **Create server settings from template:**

   cd backend/data
   cp server_settings.ini.template server_settings.ini


2. On server, edit `/backend/data/server_settings.ini`:

   - Set server callsign and SSID
   - Configure TNC port if different from default (Default: 8002)
   - Optional: Modify or add to default NOSTR relay list


3. To Run the server:

   python server.py


## Current Features

- NOSTR functionality so far...
  - Read/write posts
  - Reply, boost, quote notes that have been fetched.
  - NPUB, Hashtag and full text search requests
  - Following & Global feed support
  - Profile display names
  - Lightning address support
- AX.25 protocol with KISS TNC
- Optimized for 300-600 baud operation
- Content compression for efficient transmission
- Secure key storage
- Socket.IO real-time logging
- Packet splitting, crc checks, and ax25 format for valid packet checks and automatic packet resend requests.
- Responsive client interface with dark mode support on app
- Server GUI interface
- Frontend and UI implements with settings

## Future Features

- Dynamic baud rate adjustment
- Offline zaps using NOSTR Wallet Connect!
- FLDIGI KISS packet support
- Reticulum network integration and rnode support
- Decentralized authentication for global 24/7 based servers like winlink.
- Performance enhancements for higher baud rates especially those on VHF/UHF



## Technical Notes ## 

### Radio Configuration
- Any KISS-compatiblse TNC supported
- Software TNCs must be in KISS mode
- Default ports: Client 8001, Server 8002
- Optimized for 300-600 baud
- Maximum packet size: 200 bytes

### Security
- NOSTR keys stored only on client
- All NOSTR operations happen client-side
- Server acts only as relay
- Encrypted key storage


## Basic Troubleshooting

- Verify TNC is in KISS mode
- Check port settings in settings.ini
- Check sound card settings
- Ensure radio PTT is configured
- Monitor progress drawer for operation logs
- Check callsign settings format

## Support

- Submit issues on GitHub or DM me on nostr.
- Contact via NOSTR: @LibertyFarmer
  - npub1uwh0m2y8y5489nhr27xn8vkumy8flefm30kkx3l0tcn0wss34kaszyfqu7
- I will try to help, but don't have time for full support.


## License

This project is open-source under the MIT License.

## Contributing

Contributions welcome! Please feel free to submit pull requests, features, bugs, and of course....

---
ZAPS ARE ALWAYS APPRECIATED! ⚡