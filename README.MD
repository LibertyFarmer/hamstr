# HAMSTR - NOSTR over Ham Radio

**Fully off-grid NOSTR communication and Lightning payments via ham radio**

HAMSTR enables clients with no internet access to interact with NOSTR relays through a radio-connected server. Built on a modular backend architecture supporting multiple radio protocols, from legacy packet radio to modern high-speed digital modes.

[![OpenSats Grant](https://img.shields.io/badge/Funded%20by-OpenSats-orange)](https://opensats.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌟 What Makes HAMSTR Unique

HAMSTR is the world's first implementation of:

- **⚡ Offline Lightning payments over ham radio** with full NOSTR ecosystem integration
- **Complete NIP-57 zap compliance** - zaps appear instantly in Amethyst, Primal, and all NOSTR clients
- **Zero-knowledge server architecture** - server never has access to private keys or user data
- **Modular protocol system** - supports multiple radio transports from legacy packet to modern HF digital modes

**Perfect for:**
- 🚨 Emergency communications when infrastructure is down
- 🌍 Remote areas with no internet connectivity  
- 🔒 Censorship-resistant communications
- 📡 Resilient mesh networking scenarios

---

## 🎯 Current Status

**✅ Working Now:**
- DirectProtocol with VARA HF (fast, reliable, production-ready)
- PacketProtocol for legacy TNC systems (300-1200 baud)
- Complete Lightning zaps via ham radio (NIP-57 compliant)
- Full NOSTR read/write operations (posts, replies, zaps, search)

**🚧 Coming Soon:**
- Reticulum mesh networking integration
- FLDIGI software TNC support
- Multi-server failover and load balancing
- Enhanced VHF/UHF performance optimizations

---

## 📡 Radio Protocol Architecture

HAMSTR uses a modular backend system that abstracts radio protocols from application logic:

### **DirectProtocol** (Recommended)
For reliable digital modes with built-in error correction:

**✅ VARA HF** - *Currently Supported*
- Fast, reliable HF digital mode
- 17-600 bps adaptive speed
- Built-in ARQ and error correction
- Optimized for challenging HF conditions
- **Best choice for most users**

**🚧 Coming Soon:**
- **Reticulum** - Mesh networking with LoRa/packet radio
- **FLDIGI** - Software TNC supporting multiple PSK/RTTY modes

### **PacketProtocol** (Legacy)
For traditional AX.25 packet radio systems:

- Hardware TNCs (KPC-3, KAM, etc.)
- Software TNCs (Direwolf, UZ7HO)
- 300-1200 baud operation
- Custom ARQ implementation
- Full backward compatibility

**Protocol Comparison:**

| Feature | VARA (DirectProtocol) | Packet Radio (PacketProtocol) |
|---------|----------------------|------------------------------|
| Speed | 17-600 bps adaptive | 300-1200 baud fixed |
| Error Correction | Built-in ARQ | Custom HAMSTR ARQ |
| Setup Complexity | Medium | Low |
| HF Performance | Excellent | Good |
| VHF Performance | Good | Excellent |
| Recommended For | Most users | Legacy equipment |

---

## ⚡ Lightning Zap Protocol

Complete offline Lightning payments via ham radio using encrypted NWC:

**How it works:**
1. **Client** sends signed kind 9734 zap note via radio
2. **Server** generates Lightning invoice using LNURL-pay with NIP-57 context
3. **Client** pays via encrypted NWC command transmitted over radio
4. **Server** forwards to wallet, confirms payment, publishes zap receipt to NOSTR
5. **Result** ⚡ Zap appears instantly in all NOSTR clients worldwide

**Timing:** ~2-5 minutes end-to-end depending on radio conditions

**Legal Note:** NWC requires encryption which may be restricted on amateur radio in some jurisdictions. Users are responsible for compliance with local regulations.

---

## 🚀 Quick Start

### Prerequisites

**Required:**
- Valid amateur radio license
- Python 3.7+ (both client and server)
- Node.js 16+ (for frontend build)
- Radio transceiver (HF or VHF/UHF)
- NOSTR private key (nsec)

**For VARA (Recommended):**
- VARA HF modem software (Windows/Wine)
- Sound card interface to radio

**For Packet Radio (Legacy):**
- KISS-compatible TNC (hardware or Direwolf)

**For Lightning Zaps:**
- Lightning wallet with NWC support (Alby, Mutiny, etc.)

### Installation

**1. Clone the repository** (needed on both client and server):
```bash
git clone https://github.com/LibertyFarmer/hamstr.git
cd hamstr
```

**2. Install Python dependencies:**
```bash
# Client machine
pip install -r requirements-client.txt

# Server machine (if separate)
pip install -r requirements-server.txt
```

**3. Build the frontend** (client only):
```bash
cd frontend
npm install
npm run build
cd ..
```

### Client Setup

**1. Create configuration from template:**
```bash
cd backend/data
cp client_settings.ini.template client_settings.ini
```

**2. Edit `backend/data/client_settings.ini`:**
```ini
[RADIO]
# Your station callsign
CLIENT_CALLSIGN = YOURCALL
CLIENT_SSID = 7

# Server you're connecting to
HAMSTR_SERVER = SERVERCALL
SERVER_SSID = 1

[BACKEND]
# Protocol: vara, packet, reticulum (future), fldigi (future)
BACKEND_TYPE = vara

[VARA]
# VARA modem settings (if using VARA)
VARA_HOST = localhost
COMMAND_PORT = 8300
DATA_PORT = 8301

[TNC]
# TNC settings (if using packet radio)
CONNECTION_TYPE = tcp
CLIENT_HOST = localhost
CLIENT_PORT = 8001
```

**3. Run the client:**
```bash
python web_app.py
```

**4. Access web interface:**
- Open browser to `http://localhost:5000`
- Go to Settings → NOSTR Login
- Enter your nsec key (stored encrypted locally)
- Configure radio settings in App Settings

**5. (Optional) Configure Lightning Zaps:**
- Go to Settings → Lightning Setup
- Enter NWC connection URI from your wallet
- Zaps will now work offline via radio!

### Server Setup

**1. Create configuration from template:**
```bash
cd backend/data
cp server_settings.ini.template server_settings.ini
```

**2. Edit `backend/data/server_settings.ini`:**
```ini
[RADIO]
# Server station callsign
S_CALLSIGN = SERVERCALL
SSID = 1

[BACKEND]
# Must match client's protocol
BACKEND_TYPE = vara

[VARA]
# VARA modem settings
VARA_HOST = localhost
COMMAND_PORT = 8300
DATA_PORT = 8301

[NOSTR]
# Add your preferred relays
RELAYS = wss://relay.damus.io,wss://nos.lol,wss://relay.nostr.band
```

**3. Run the server:**
```bash
python server.py
```

**Server runs 24/7 and handles multiple clients automatically!**

---

## ✨ Current Features

### **NOSTR Operations**
- ✅ Read/write posts with content compression
- ✅ Reply, boost, quote notes
- ✅ NPUB, hashtag, and full-text search
- ✅ Following feed & global feed support
- ✅ Profile display names and Lightning addresses
- ✅ Multi-relay publishing for maximum reach

### **⚡ Lightning Zaps**
- ✅ Complete offline zaps via ham radio
- ✅ NIP-57 compliance (appears in all NOSTR clients)
- ✅ Multi-phase protocol: Zap note → Invoice → Payment → Receipt
- ✅ Encrypted NWC commands over radio
- ✅ Automatic receipt publishing to NOSTR

### **Radio Protocol Support**
- ✅ **VARA HF** - DirectProtocol (production-ready)
- ✅ **AX.25 Packet** - PacketProtocol (legacy support)
- ✅ KISS TNC compatibility
- ✅ Content compression for efficiency
- ✅ CRC checks and automatic retransmission
- ✅ Missing packet recovery with retry logic
- ✅ Adaptive timing for varying radio conditions

### **User Experience**
- ✅ Real-time progress tracking with packet status
- ✅ WebSocket logging with friendly translations
- ✅ Responsive design with dark mode
- ✅ Secure encrypted key storage
- ✅ Progress drawer showing transmission details

### **Architecture**
- ✅ Zero-knowledge server (never sees private keys)
- ✅ Client-side signing and encryption
- ✅ Server as pure relay/cache/publisher
- ✅ Modular backend system for easy protocol additions
- ✅ Multi-user server design for public infrastructure

---

## 🔮 Roadmap

### **Near-Term (Q1 2025)**
- 🚧 Reticulum mesh networking integration
- 🚧 FLDIGI software TNC support
- 🚧 GUI TNC configuration (no more .ini editing)
- 🚧 Enhanced zap status display in UI
- 🚧 VHF/UHF performance optimizations

### **Medium-Term (Q2-Q3 2025)**
- 🎯 Multi-server failover and load balancing
- 🎯 Dynamic baud rate adjustment
- 🎯 Decentralized authentication system
- 🎯 Mobile client support (Android/iOS)
- 🎯 APRS integration for position reporting

### **Long-Term Vision**
- 🌟 Global mesh network of HAMSTR servers
- 🌟 Satellite communication support
- 🌟 Emergency broadcast system
- 🌟 Integration with Meshtastic/LoRa networks
- 🌟 Offline-first Lightning routing

---

## 🔧 Technical Details

### **Radio Configuration**

**VARA HF Setup:**
```
1. Install VARA HF modem software
2. Configure sound card interface to radio
3. Set VARA command port: 8300
4. Set VARA data port: 8301
5. Update client/server settings.ini with these ports
```

**Packet Radio Setup:**
```
1. Configure TNC in KISS mode
2. Default ports: Client 8001, Server 8002
3. Baud rate: 300-1200 (must match on both ends)
4. Ensure proper PTT configuration
```

### **Settings Architecture**

- **`settings.ini`** - Shared configuration (timing, packet size, timeouts) - **Read-only**
- **`client_settings.ini`** - Client-specific (callsign, TNC port, server target)
- **`server_settings.ini`** - Server-specific (callsign, TNC port, NOSTR relays)
- Templates provided for both client and server

### **Protocol Flow**

**DirectProtocol (VARA/Reticulum/FLDIGI):**
```
Client → CONNECT → Server
Client → REQUEST → Server
Server → RESPONSE → Client
Client → DONE → Server
Server → DONE_ACK → Client
Client → DISCONNECT → Server
Server → DISCONNECT_ACK → Client
```

**PacketProtocol (Legacy Packet):**
```
Client → CONNECT → Server
Client ↔ READY handshake ↔ Server
Client → DATA_REQUEST (packets) → Server
Server ↔ READY handshake ↔ Client
Server → RESPONSE (packets + ACKs) → Client
Client → DISCONNECT → Server
```

---

## 🐛 Troubleshooting

**VARA Issues:**
- Verify VARA modem is running
- Check sound card settings
- Ensure PTT is configured
- Confirm ports 8300/8301 are correct
- Monitor VARA status window

**Packet Radio Issues:**
- Verify TNC is in KISS mode
- Check port settings in settings.ini
- Ensure baud rates match on both ends
- Test TNC with AGW Packet Engine first
- Monitor progress drawer for errors

**Zap Issues:**
- Ensure NWC wallet is online
- Verify NWC connection string format
- Check Lightning wallet has sufficient balance
- Monitor progress drawer for payment status

**General Tips:**
- Check callsign format: (CALLSIGN, SSID)
- Ensure radio is properly tuned and transmitting
- Monitor progress drawer for real-time diagnostics
- Check both client and server logs for errors

---

## 🤝 Contributing

Contributions are welcome! Areas that need help:

- Additional protocol backends (Reticulum, FLDIGI, ARDOP)
- Performance optimizations for VHF/UHF
- UI/UX improvements
- Documentation and tutorials
- Testing on different radio configurations

**To contribute:**
1. Fork the repository
2. Create a feature branch
3. Submit a pull request with clear description

---

## 📞 Support & Community

- **GitHub Issues:** Bug reports and feature requests
- **NOSTR:** @LibertyFarmer
  - npub: `npub1uwh0m2y8y5489nhr27xn8vkumy8flefm30kkx3l0tcn0wss34kaszyfqu7`
- **Zaps welcome!** ⚡ (now working offline via ham radio!)

**Note:** This is an open-source project with limited support. While I'll help where I can, please understand this is not a commercial product with full-time support.

---

## ⚖️ Legal & Licensing

### **Amateur Radio Regulations**
- Valid amateur radio license required
- Encryption rules vary by jurisdiction (NWC zaps use encryption)
- Users responsible for compliance with local regulations
- Third-party traffic rules may apply

### **Software License**
This project is open-source under the MIT License.

Copyright (c) 2025 Liberty Farmer

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

## 🙏 Acknowledgments

- **OpenSats** for funding this project
- **NOSTR developers** for the open protocol
- **VARA HF team** for excellent digital mode software
- **Ham radio community** for decades of innovation
- **All contributors and testers**

---

**Built with love for freedom, privacy, and resilient communications.**

*73 de Liberty Farmer* 📡⚡🗽