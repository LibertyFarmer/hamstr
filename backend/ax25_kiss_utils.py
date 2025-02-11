import struct
import zlib

# Constants
FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD

def calculate_checksum(data):
    """Calculate CRC32 checksum."""
    return zlib.crc32(data)

def encode_ax25_address(callsign, ssid, is_last):
    """Encode the AX.25 address field with the correct SSID and control bits."""
    callsign = callsign.ljust(6)  # Pad the call sign to 6 characters
    encoded = [(ord(c) << 1) & 0xFE for c in callsign]
    ssid_byte = ((ssid & 0x0F) << 1)
    if is_last:
        ssid_byte |= 0x01
    encoded.append(ssid_byte)
    return encoded

def decode_ax25_callsign(frame, start_index):
    """Decode a callsign from the AX.25 frame using structured parsing."""
    adjusted_start_index = start_index + 1  # Adjust the start index as needed

    if len(frame) < adjusted_start_index + 7:
        print("Error: Frame is too short to extract callsign and SSID.")
        return ""

    try:
        # Unpack the callsign bytes and the SSID byte
        callsign_bytes, ssid_byte = struct.unpack(">6sB", frame[adjusted_start_index:adjusted_start_index + 7])
        # Decode the callsign by right-shifting each byte by 1 bit
        callsign = ''.join(chr(byte >> 1) for byte in callsign_bytes).strip()
        
        # Extract and decode the SSID
        ssid = (ssid_byte >> 1) & 0x0F
        if 1 <= ssid <= 15:
            callsign = f"{callsign}-{ssid}"

        return callsign

    except struct.error as e:
        print(f"Struct unpacking error: {e}")
        return ""

def clean_message(ax25_frame):
    """Clean the message payload by removing leading unwanted bytes."""
    message_payload = ax25_frame[16:]  # Extract the message starting at index 16

    # Clean any leading null bytes or control characters
    while message_payload and message_payload[0] in (0x00,):
        message_payload = message_payload[1:]

    return message_payload  # Return bytes, not a decoded string

def kiss_wrap(ax25_frame):
    """Wrap the AX.25 frame in a KISS frame for transmission."""
    framed = [FEND, 0x00]
    for byte in ax25_frame:
        if byte == FEND:
            framed.extend([FESC, TFEND])
        elif byte == FESC:
            framed.extend([FESC, TFESC])
        else:
            framed.append(byte)
    framed.append(FEND)
    return bytes(framed)

def kiss_unwrap(kiss_frame):
    """Unwrap a KISS frame and return the AX.25 data."""
    if kiss_frame[0] != FEND or kiss_frame[-1] != FEND:
        return None
    unwrapped = []
    index = 1
    while index < len(kiss_frame) - 1:
        if kiss_frame[index] == FESC:
            if kiss_frame[index + 1] == TFEND:
                unwrapped.append(FEND)
            elif kiss_frame[index + 1] == TFESC:
                unwrapped.append(FESC)
            index += 2
        else:
            unwrapped.append(kiss_frame[index])
            index += 1
    return bytes(unwrapped)

def build_ax25_frame(source, destination, message):
    """Build an AX.25 frame."""
    destination_addr = encode_ax25_address(destination[0], destination[1], is_last=False)
    source_addr = encode_ax25_address(source[0], source[1], is_last=True)
    control_field = [0x03]
    pid_field = [0xF0]
    if isinstance(message, str):
        info_field = list(message.encode('latin-1'))
    else:
        info_field = list(message)
    ax25_frame = destination_addr + source_addr + control_field + pid_field + info_field
    return ax25_frame
