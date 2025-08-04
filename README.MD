# HAMSTR - NOSTR over Ham Radio

HAMSTR enables fully off-grid NOSTR communication over ham radio, allowing clients with no internet access to interact with NOSTR relays through a server with internet connectivity.

**NEW:** ⚡ **Complete offline Lightning zaps via ham radio are now working!** Using NOSTR Wallet Connect (NWC) with full NIP-57 compliance, HAMSTR can send Lightning payments completely offline that appear instantly in all NOSTR clients.

NOTE - In this early ALPHA version, the client and server still share a lot of libraries and some settings. The best way to install and use is to follow the directions below on the client machine first by cloning the repo, then setting it up as shown below, after that clone again on the server and follow the server setup and run. The server currently has no GUI, python console only. You will need to have the client online to install and setup, obviously. After that, you can access offline via a web browser. Power users can change the localhost to the machine ip address and access via IP address if they understand flask and the like.

I can try to help, but this is not currently for anyone other than experienced ham radio packet users, those with hf or other data setups, etc... I am not going to troubleshoot or help with every type of radio out there for data modes. For that, see your TNC software docs or forums.

## What Makes HAMSTR Unique

HAMSTR is the world's first implementation of:
- **Offline Lightning payments over ham radio** with full NOSTR ecosystem integration
- **Complete NIP-57 zap compliance** - zaps appear instantly in Amethyst, Primal, and all NOSTR clients
- **Zero-knowledge server architecture** - server never has access to private keys or user data
- **Multi-phase ham radio protocol** optimized for HF packet radio constraints

Perfect for use in:
- **Censorship regimes** where internet is restricted or monitored
- **Internet outages** and infrastructure failures
- **Remote areas** with no internet connectivity
- **Emergency communications** when traditional payment systems are down

## Quickish Start

### Prerequisites
- Valid amateur radio license
- **Python 3.7+** (required for both client and server)
- **Node.js 16+** (required for frontend build)
- KISS-compatible TNC (hardware or software like Direwolf)
- HF/VHF transceiver
- NOSTR private key (nsec)
- Lightning wallet with NWC support (for zaps)

### Installation

1. **Clone the repository** (will need to clone on both client and server machines):
```bash
git clone https://github.com/LibertyFarmer/hamstr.git
cd hamstr
```

2. **Install client dependencies:**
```bash
pip install -r requirements-client.txt
```

3. **Install and build frontend** (Node.js required):
```bash
cd frontend
npm install
npm run build
cd ..
```

### Client Setup

1. **Create client settings from template:**
```bash
cd backend/data
cp client_settings.ini.template client_settings.ini
```

2. **Edit `/backend/data/client_settings.ini`:**
   - Set client callsign and SSID
   - Configure target server callsign
   - Set TNC port (default: 8001)

3. **Run the client application:**
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

6. **NEW: Configure Lightning Zaps (Optional):**
   - Go to Settings > Lightning Setup
   - Enter NWC connection URI from your Lightning wallet
   - **Note:** Encryption is required for NWC but may be restricted on ham radio in some jurisdictions

### Server Setup - Once repo cloned on server

1. **Create server settings from template:**
   ```bash
   cd backend/data
   cp server_settings.ini.template server_settings.ini
   ```

2. On server, edit `/backend/data/server_settings.ini`:
   - Set server callsign and SSID
   - Configure TNC port if different from default (Default: 8002)
   - Optional: Modify or add to default NOSTR relay list

3. To Run the server:
   ```bash
   python server.py
   ```

## Current Features ✅

### **NOSTR Functionality**
- **Read/write posts** with full content compression
- **Reply, boost, quote notes** that have been fetched
- **NPUB, Hashtag and full text search** requests
- **Following & Global feed** support
- **Profile display names** and Lightning address support
- **Multi-relay publishing** for maximum distribution

### **⚡ Lightning Zap Integration** ✅ **NEW!**
- **Complete offline Lightning zaps** via ham radio using NWC
- **Full NIP-57 compliance** - zaps appear in all NOSTR clients
- **Multi-phase protocol:** Kind 9734 → Invoice → Payment → Receipt
- **~5 minute zap duration** optimized for HF packet radio
- **Encrypted NWC commands** transmitted legally as plaintext over radio
- **Automatic zap receipt publishing** to NOSTR relays

### **Ham Radio Protocol**
- **AX.25 protocol** with KISS TNC compatibility
- **Optimized for 300-600 baud** operation
- **Content compression** for efficient transmission
- **Packet splitting, CRC checks,** and automatic resend requests
- **Missing packet recovery** with retry logic
- **READY handshake system** for reliable multi-phase operations

### **User Interface**
- **Real-time progress tracking** with packet-by-packet status
- **Socket.IO logging** with user-friendly message translation
- **Responsive design** with dark mode support
- **Settings management** with secure key storage
- **Progress drawer** showing transmission status and connection info

### **Security & Architecture**
- **Zero-knowledge server** - never has access to private keys
- **Client-side NOSTR operations** - all signing happens offline
- **Server acts as pure relay** - only caches, forwards, publishes
- **Encrypted key storage** on client only
- **Multi-user server design** for 24/7 public infrastructure

## Future Features

### **Immediate UI Enhancements**
- **Zap status display** on notes that have been zapped
- **Zap-specific progress indicators** in bottom navigation
- **NWC legal disclaimer** for encryption compliance

### **Planned Features**
- **Dynamic baud rate adjustment** based on propagation conditions
- **FLDIGI KISS packet support** for software TNC integration
- **Reticulum network integration** and rnode support
- **Decentralized authentication** for global 24/7 servers like Winlink
- **Performance enhancements** for VHF/UHF higher baud rates
- **Multi-server failover** for redundant connections

## Technical Notes

### **Radio Configuration**
- Any KISS-compatible TNC supported
- Software TNCs must be in KISS mode
- Default ports: Client 8001, Server 8002
- Optimized for 300-600 baud HF operation
- Maximum packet size: 200 bytes for AX.25 compatibility

### **Lightning Zap Protocol**
- **Phase 1:** Client sends signed kind 9734 zap note via radio
- **Phase 2:** Server generates Lightning invoice using LNURL-zap with NIP-57
- **Phase 3:** Client pays via encrypted NWC command transmitted over radio
- **Phase 4:** Server forwards to wallet, confirms payment, publishes receipt
- **Result:** Zap appears instantly in NOSTR ecosystem

### **Settings Architecture**
- **`settings.ini`** - Shared configuration (timing, packet size, timeouts) - **do not modify**
- **`client_settings.ini`** - Client-specific settings (callsign, TNC port, target server)
- **`server_settings.ini`** - Server-specific settings (callsign, TNC port, NOSTR relays)
- **Templates provided** for both client and server settings

## Legal Considerations

**Important:** NWC Lightning zaps require encryption, which may be restricted on amateur radio in some jurisdictions. Users are responsible for compliance with local regulations. HAMSTR is designed for use in areas where traditional internet infrastructure is unavailable, restricted, or compromised.

## Basic Troubleshooting

- Verify TNC is in KISS mode
- Check port settings in settings.ini
- Check sound card settings for software TNCs
- Ensure radio PTT is configured properly
- Monitor progress drawer for operation logs
- Verify callsign settings format: (CALLSIGN, SSID)
- For zaps: Ensure NWC wallet is online and properly configured

## Support

- Submit issues on GitHub or DM me on NOSTR
- Contact via NOSTR: @LibertyFarmer
  - npub1uwh0m2y8y5489nhr27xn8vkumy8flefm30kkx3l0tcn0wss34kaszyfqu7
- I will try to help, but don't have time for full support

## License

This project is open-source under the MIT License.

## Contributing

Contributions welcome! Please feel free to submit pull requests, features, bugs, and of course....

---
**ZAPS ARE ALWAYS APPRECIATED!** ⚡

*Now working offline via ham radio!*