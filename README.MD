# HAMSTR - NOSTR over Ham Radio

**Fully off-grid NOSTR communication and Lightning payments via ham radio**

HAMSTR enables clients with no internet access to interact with NOSTR relays through a radio-connected server. Built on a modular backend architecture supporting multiple radio protocols, from legacy packet radio to modern mesh networking.

[![OpenSats Grant](https://img.shields.io/badge/Funded%20by-OpenSats-orange)](https://opensats.org/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

---

## 🌟 What Makes HAMSTR Unique

HAMSTR is the world's first implementation of:

- **⚡ Offline Lightning payments over ham radio** with full NOSTR ecosystem integration
- **Complete NIP-57 zap compliance** — zaps appear instantly in Amethyst, Primal, and all NOSTR clients
- **Zero-knowledge server architecture** — server never has access to private keys or user data
- **Modular protocol system** — supports multiple radio transports from legacy packet to modern mesh networking

**Perfect for:**
- 🚨 Emergency communications when infrastructure is down
- 🌍 Remote areas with no internet connectivity
- 🔒 Censorship-resistant communications
- 📡 Resilient mesh networking via Reticulum

---

## 🎯 Current Status

**✅ Working Now:**
- AX.25 Packet Radio — PacketProtocol (legacy TNC systems, 300–1200 baud)
- VARA HF — DirectProtocol (fast, reliable, production-ready)
- Reticulum mesh networking — DirectProtocol (LoRa, HF Radio, VHF/UHF Radio — see [RETICULUM.md](RETICULUM.md))
- Complete Lightning zaps via ham radio and LoRa (NIP-57 compliant)
- Full NOSTR read/write operations (posts, replies, zaps, search)

**🚧 Coming Soon:**
- FLDIGI software TNC support
- Cashu ecash wallet integration
- GUI settings — no more manual .ini editing
- Zap-based server authentication

---

## 📡 Radio Protocol Architecture

HAMSTR uses a modular backend that abstracts radio protocols from application logic. Two protocol handlers cover all supported transports:

### DirectProtocol
For reliable transports with built-in error correction. Simple JSON pass-through, no READY/ACK overhead.

| Backend | Status | Speed | Notes |
|---------|--------|-------|-------|
| **VARA HF** | ✅ Working | 17–600 bps adaptive | Best choice for HF |
| **Reticulum** | ✅ Working | Transport-dependent | LoRa, TCP, serial |
| **FLDIGI** | 🚧 Coming Soon | Mode-dependent | PSK, RTTY, etc. |

### PacketProtocol
For traditional AX.25 packet radio. Includes ARQ, CRC, compression, and missing-packet recovery.

| Backend | Status | Speed | Notes |
|---------|--------|-------|-------|
| **AX.25 Packet (TNC)** | ✅ Working | 300–1200 baud | Hardware or software TNC |

---

## ⚡ Lightning Zap Protocol

Complete offline Lightning payments via ham radio using encrypted NWC:

1. **Client** sends signed kind 9734 zap note via radio
2. **Server** generates Lightning invoice using LNURL-pay with NIP-57 context
3. **Client** pays via encrypted NWC command transmitted over radio
4. **Server** forwards to wallet, confirms payment, publishes zap receipt to NOSTR
5. **Result** ⚡ Zap appears instantly in all NOSTR clients worldwide

**Timing:** ~2–5 minutes end-to-end depending on radio conditions

> **Legal Note:** NWC requires encryption which may be restricted on amateur radio in some jurisdictions. Users are responsible for compliance with local regulations.

---

## 🚀 Quick Start

### Prerequisites

**Client:**
- Valid amateur radio license
- Python 3.9+
- Ham radio transceiver + interface to PC
- NOSTR private key (nsec)

**Server (if running your own):**
- Python 3.9+
- PySide6 (Qt GUI)
- Always-on PC or SBC (Raspberry Pi, etc.)

**For VARA HF:**
- VARA HF modem software (Windows or Wine on Linux)
- Sound card interface (Digirig, SignaLink, etc.)

**For Packet Radio:**
- KISS-compatible TNC — hardware (KPC-3, KAM) or software (Direwolf, UZ7HO)

**For Reticulum:**
- See [RETICULUM.md](RETICULUM.md) for full setup guide (RNode hardware, pip install, rnsd config)

**For Lightning Zaps:**
- Lightning wallet with NWC support (Alby, etc.)

---

### Client Setup

The frontend is pre-built and included. No Node.js required.

**1. Clone the repository:**
```bash
git clone https://github.com/LibertyFarmer/hamstr.git
cd hamstr
```

**2. Install Python dependencies:**
```bash
pip install -r requirements-client.txt
```

**3. Run the client:**
```bash
python web_app.py
```

`client_settings.ini` is created automatically from the template on first run.

**4. Open your browser to:** `http://localhost:5000`

- Go to Settings → configure your callsign, backend type, and radio settings
- Go to Settings → NOSTR Login and enter your nsec
- Optionally add your NWC connection string for Lightning zaps

All settings are documented in `backend/data/client_settings.ini.template`.

---

### Server Setup

**1. Install Python dependencies:**
```bash
pip install -r requirements-server.txt
```

**2. Launch the server UI:**
```bash
python server_ui.py
```

`server_settings.ini` is created automatically from the template on first run.

**3.** Configure your callsign, backend type, and radio settings in the Settings dialog, then click **Start Server**.

All settings are documented in `backend/data/server_settings.ini.template`.

---

## ✨ Current Features

### NOSTR Operations
- ✅ Read/write posts with content compression
- ✅ Reply, boost, quote notes
- ✅ NPUB, hashtag, and full-text search
- ✅ Following feed and global feed
- ✅ Profile display names and Lightning addresses
- ✅ Multi-relay publishing

### Lightning Zaps
- ✅ Complete offline zaps via ham radio
- ✅ NIP-57 compliant (appears in all NOSTR clients)
- ✅ Encrypted NWC commands over radio
- ✅ Zap receipt published automatically by server

### Radio Protocol Support
- ✅ AX.25 Packet Radio via KISS TNC (PacketProtocol)
- ✅ VARA HF (DirectProtocol)
- ✅ Reticulum mesh networking (DirectProtocol)
- ✅ Custom Content compression for bandwidth efficiency
- ✅ Custom CRC checks and retransmission (PacketProtocol)
- ✅ Custom Missing packet recovery (PacketProtocol)

### Architecture
- ✅ Zero-knowledge server — never sees private keys
- ✅ All signing and encryption is client-side
- ✅ Server as pure relay/cache/publisher
- ✅ Modular backend — adding protocols is straightforward
- ✅ Multi-client server design

---

## 🔧 Troubleshooting

**VARA Issues:**
- Verify VARA modem is running and sound card is configured
- Check PTT is wired correctly and set in config
- Confirm command port 8300 / data port 8301 match both ends
- Monitor the VARA status window

**Packet Radio Issues:**
- Verify TNC is in KISS mode
- Check host/port in `client_settings.ini` matches TNC
- Test TNC with another application (Direwolf, AGW) first

**Reticulum Issues:**
- See [RETICULUM.md](RETICULUM.md) for full troubleshooting
- Make sure `rnsd` is running before starting HAMSTR
- Confirm you have the correct server destination hash

**Zap Issues:**
- Ensure NWC wallet is online at the server
- Verify NWC connection string format
- Check your Lightning wallet has sufficient balance
- Watch the progress drawer for per-step status

**General:**
- Callsign format must be a tuple: `(CALLSIGN, SSID)`
- Both client and server must use the same backend type
- Check the progress drawer for real-time diagnostics

---

## 🗺️ Roadmap

- 🚧 FLDIGI software TNC backend
- 🚧 Cashu ecash wallet (offline payments, no Lightning required)
- 🚧 Full GUI settings — no manual .ini editing
- 🚧 First-run setup wizard
- 🚧 Zap-based server authentication (pay-per-use)
- 🚧 Enhanced NWC features (balance, history)

**Future:**
- 🎯 Global network of public HAMSTR server nodes
- 🎯 Satellite transport support
- 🎯 Mobile client
- 🎯 APRS position integration

---

## 📞 Support & Community

- **GitHub Issues:** Bug reports and feature requests
- **NOSTR:** `npub1uwh0m2y8y5489nhr27xn8vkumy8flefm30kkx3l0tcn0wss34kaszyfqu7`
- **Zaps welcome!** ⚡

This is a solo open-source project developed in spare time. Support is best-effort.

---

## 📄 License

GPL-3.0 — see [LICENSE](LICENSE) for details.

Source: [github.com/LibertyFarmer/hamstr](https://github.com/LibertyFarmer/hamstr)