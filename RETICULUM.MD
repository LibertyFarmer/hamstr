# Reticulum with HAMSTR

HAMSTR supports [Reticulum Network Stack](https://reticulum.network/) as a radio transport, enabling off-grid NOSTR and Lightning zaps over LoRa mesh networks without any internet infrastructure.

---

## Hardware

HAMSTR has been tested with **RNode** LoRa devices. Any RNode-compatible hardware should work:

- RAK Wireless WisBlock (RAK4631)
- LilyGO T-Beam, T3S3, LoRa32
- Homebrew builds based on supported chipsets

For a full compatibility list, see the [Reticulum hardware page](https://reticulum.network/hardware.html).

---

## Firmware

RNode devices require two steps — base firmware first, then RNode configuration. Missing the second step is a common gotcha.

**Step 1 — Flash base firmware**

Use the browser-based [RNode Flasher](https://github.com/liamcottle/rnode-flasher) — no local toolchain needed. Connect your device via USB and follow the prompts.

> Official alternative: [RNode Bootstrap Console](https://unsigned.io/rnode/) from the Reticulum author.

**Step 2 — Configure as RNode**

After flashing, run `rnodeconf` to finalize the device:

```bash
pip install rns
rnodeconf --autoinstall
```

Follow the prompts — it detects your device, confirms hardware type, and writes the RNode configuration. Without this step the device won't work with Reticulum.

For full documentation see the [Reticulum Manual](https://markqvist.github.io/Reticulum/manual/).

---

## Installing Reticulum

```bash
pip install rns
```

`rns` includes `rnsd`, `rnodeconf`, and all supporting utilities.

---

## Configuration

Reticulum uses its own config file, separate from HAMSTR's settings. It is created automatically the first time `rnsd` runs.

**Default locations:**
- Linux: `~/.reticulum/config`
- Windows: `C:\Users\<username>\.reticulum\config` — substitute your actual Windows username

You must set `reticulum_config_dir` in your HAMSTR settings file to point to this directory. On Linux you can use `~/.reticulum` as-is. On Windows you must use the full path with your real username — `~` does not expand on Windows.

To use a non-default location, pass `--config <path>` to `rnsd` and use that same path for `reticulum_config_dir`.

> **Tip:** Run `rnsd --exampleconfig` to see every available option with full comments.

The config below is a working baseline for HAMSTR with an RNode. Adjust `port`, `frequency`, `bandwidth`, `spreadingfactor`, and `codingrate` to match your hardware and regional band plan.

```ini
[reticulum]
  enable_transport = False
  share_instance = No
  shared_instance_port = 37428
  instance_control_port = 37429
  panic_on_interface_error = No

[logging]
  loglevel = 4

[interfaces]

  [[AutoInterface]]
    type = AutoInterface
    enabled = no

  [[RNode Interface]]
    type = RNodeInterface
    interface_enabled = yes
    outgoing = true
    port = COM9                # Windows example — Linux: /dev/ttyUSB0 or similar
    frequency = 915000000      # Hz — check your regional band plan
    bandwidth = 250000
    txpower = 17
    spreadingfactor = 11
    codingrate = 5
    flow_control = false
    mtu = 200
```

> **Both client and server must use identical `frequency`, `bandwidth`, `spreadingfactor`, and `codingrate`.** Mismatched parameters are the most common reason two nodes can't hear each other.

---

## Starting the Reticulum Daemon

HAMSTR requires `rnsd` to be running before launch.

**Windows** — run in a separate terminal and leave it open:
```
rnsd
```

**Linux** — run in background:
```bash
rnsd --daemon
```

Or install as a systemd service for always-on operation — see the [Reticulum Manual](https://markqvist.github.io/Reticulum/manual/using.html) for the service file.

---

## Server Setup

When the HAMSTR server starts with `backend_type = reticulum`, it announces itself on the network and displays its **destination hash** and **public key** in the server UI. Share these with your clients — via NOSTR, email, or any out-of-band channel.

In `server_settings.ini`:

```ini
[NETWORK]
backend_type = reticulum

[RETICULUM]
server_grid = CN87         # your Maidenhead grid square
announce_interval = 21600  # seconds between announcements (6 hours default)
```

---

## Client Setup

In `client_settings.ini`:

```ini
[NETWORK]
backend_type = reticulum

[RETICULUM]
hamstr_server_hash = <destination hash from server operator>
hamstr_server_pubkey = <public key from server operator>
connection_timeout = 60
```

Get `hamstr_server_hash` and `hamstr_server_pubkey` from the server operator. Without them the client has no way to address the server.

---

## Troubleshooting

**Device not detected**
- Confirm USB drivers are installed for your board
- Linux: add your user to the `dialout` group — `sudo usermod -aG dialout $USER` then log out/in
- Check the port name — Linux: `ls /dev/ttyUSB*`, Windows: Device Manager → Ports

**Nodes can't hear each other**
- Verify `frequency`, `bandwidth`, `spreadingfactor`, and `codingrate` are identical on both ends
- Check `txpower` — too low at distance, too high may violate regulations in your region
- Confirm `rnsd` is running on both machines before starting HAMSTR

**`rnsd` won't start**
- Only one process can own the RNode serial port at a time — kill any other Reticulum instances first

**Can't connect to server**
- Confirm `hamstr_server_hash` is correct in `client_settings.ini`
- Make sure the server has announced at least once (watch server UI log on the server side)
- Increase `connection_timeout` for long-distance or slow links

**Further help:** [Reticulum Manual](https://markqvist.github.io/Reticulum/manual/) — comprehensive reference for all configuration options and interfaces.