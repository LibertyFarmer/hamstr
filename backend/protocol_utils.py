import zlib
import config
import brotli 
import base64

def calculate_crc32(data):
    """Calculate CRC32 checksum."""
    crc = zlib.crc32(data)
    return f"{crc:08x}"  # Return as an 8-character hexadecimal string

def parse_callsign(callsign):
    """Parse a callsign string or tuple into a standardized format."""
    if isinstance(callsign, tuple) and len(callsign) == 2:
        return (callsign[0], int(callsign[1]))
    elif isinstance(callsign, str):
        parts = callsign.split('-')
        call = parts[0]
        ssid = int(parts[1]) if len(parts) > 1 else 0
        return (call, ssid)
    else:
        raise ValueError(f"Invalid callsign format: {callsign}")

def estimate_transmission_time(packet_size):
    """Estimate the transmission time for a packet."""
    # Assuming 10 bits per byte (8 data bits + start bit + stop bit)
    bits_to_send = packet_size * 10
    transmission_time = bits_to_send / config.BAUD_RATE
    return transmission_time + config.PACKET_SEND_DELAY  # Add the configured delay

def compress_nostr_data(data):
    """
    Compress NOSTR data using brotli and encode to base64 string.
    Args:
        data: JSON string to compress
    Returns:
        Base64 encoded string of compressed data
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    compressed = brotli.compress(data)
    return base64.b64encode(compressed).decode('utf-8')

def decompress_nostr_data(encoded_data):
    """
    Decode base64 and decompress NOSTR data.
    Args:
        encoded_data: Base64 encoded string of compressed data
    Returns:
        Original JSON string
    """
    compressed = base64.b64decode(encoded_data)
    decompressed = brotli.decompress(compressed)
    return decompressed.decode('utf-8')