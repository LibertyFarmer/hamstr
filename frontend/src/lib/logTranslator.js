const logTranslations = {
  // Static translations
  '\\[SYSTEM\\] Sending Connection Request': 'Connecting...',
  '\\[CLIENT\\] Failed to request notes': 'Sorry, It failed...',
  '\\[CLIENT\\] Disconnect acknowledged by server': 'Server Disconnected',
  '\\[CLIENT\\] Failed to connect to server.*': 'Connection to server failed',
  '\\[CONTROL\\] CONNECT ACK RECEIVED': 'Connected',
  '\\[CLIENT\\] Received READY from server, sending READY': 'Ready to Send',
  '\\[SESSION\\] DATA_REQUEST sent and READY state achieved': "Ready for Packets",
  '\\[CONTROL\\] Sending TYPE: DATA_REQUEST': 'Sending Note Request',
  '\\[CLIENT\\] READY STATE ACHIEVED': 'Ready to receive data',
  '\\[SESSION] Client initiating disconnect \\[CLIENT_DISCONNECT\\]': 'Sending Disconnect Request...',
  '\\[CONTROL\\] DISCONNECT ACK received': 'Disconnecting',
  '\\[SESSION\\] Sending CONNECTION REQUEST. Waiting for CONNECT_ACK...': 'Sending Connection Request...',
  '\\[CLIENT\\] Attempting to send note to server': 'Starting note transmission...',
  '\\[CLIENT\\] Sending note': 'Preparing to send note...',
  '\\[PACKET\\] DONE packet sent': 'Sending completion signal...',
  '\\[CONTROL\\] Received DONE_ACK, note transmission complete': 'Note transmission complete!',
  '\\[CONTROL\\] Sending packet: Type=READY, Seq=\\d+/\\d+, Estimated transmission time: [\\d.]+ seconds': 'Pulling note(s) from relays...',
  '\\[CONTROL\\] Sending packet: Type=DISCONNECT, Seq=\\d+/\\d+, Estimated transmission time: [\\d.]+ seconds': 'Sending disconnect signal...',
  '\\[CONTROL\\] Sending DISCONNECT for session: [\\w-]+': 'Closing connection...',
  '\\[CONTROL\\] Sending packet: Type=DONE, Seq=\\d+/\\d+, Estimated transmission time: [\\d.]+ seconds': 'Finalizing transmission...',
  '\\[CONTROL\\] Received DONE_ACK, ending transmission': 'Transmission complete',
  '\\[CONTROL\\] Received control: Type=DONE_ACK, Content=DONE_ACK': 'Server acknowledged completion',
  '\\[CONTROL\\] Sending packet: Type=ACK, Seq=\\d+/\\d+, Estimated transmission time: [\\d.]+ seconds': 'Acknowledging packet, waiting for server...',
  '\\[CONTROL\\] Sending control: Type=ACK': 'Confirming receipt...',
  '\\[CONTROL\\] READY sent successfully': 'Ready Sent, waiting for ACK...',
  '\\[CONTROL\\] Received control: Type=READY, Content=READY': 'Ready signal received',
  '\\[CONTROL\\] Sending packet: Type=DATA_REQUEST, Seq=\\d+/\\d+, Estimated transmission time: [\\d.]+ seconds': 'Sending data request...',
  '\\[CONTROL\\] Received control: Type=CONNECT_ACK, Content=Connection Accepted': 'Connection confirmed',
  '\\[CONTROL\\] Sending packet: Type=CONNECT, Seq=\\d+/\\d+, Estimated transmission time: [\\d.]+ seconds': 'Establishing connection...',
  '\\[CONTROL\\] Received control: Type=DONE, Content=DONE': 'Completing transmission...',
  '\\[CONTROL\\] Received DONE message & all packets are accounted for': 'All packets received successfully',
  '\\[CONTROL\\] Sending packet: Type=DONE_ACK, Seq=\\d+/\\d+, Estimated transmission time: [\\d.]+ seconds': 'Confirming completion...',
  '\\[CONTROL\\] Received control: Type=ACK, Content=ACK': 'Received acknowledgement',
  '\\[CONTROL\\] Sending packet: Type=PKT_MISSING, Seq=\\d+/\\d+, Estimated transmission time: [\\d.]+ seconds': 'Requesting missing packets...',
  '\\[SYSTEM\\] All packets successfully reassembled': 'All packets received and verified',
  '\\[PACKET\\] Received missing packet (\\d+)': 'Recovered missing packet...',
  '\\[SYSTEM\\] All missing packets received': 'Successfully recovered all missing packets',
  '\\[CLIENT\\] Signed note created, preparing to send': 'Note Signed, prepping send',
  '\\[CLIENT\\] Creating signed note...': 'Signing Note',
  '\\[CLIENT\\] Note Published!': 'Note live on NOSTR!',
  '\\[CLIENT\\] Note compressed, preparing to send': 'Note signed, ready to send',
 
  // Dynamic translations  

  '\\[CONTROL\\] Received control: Type=PKT_MISSING, Content=PKT_MISSING\\|([\\d,]+)': (match) => {
    const packetNum = match[1];
    return `Packet ${packetNum.padStart(4, '0')} missing, preparing resend...`;
  },
  
  '\\[CONTROL\\] Sending packet: Type=NOTE, Seq=(\\d+)/(\\d+), Estimated transmission time: ([\\d.]+) seconds': (match) => {
    return `Sending Packet ${match[1].padStart(4, '0')} of ${match[2].padStart(4, '0')}`;
  },
 
  '\\[CONTROL\\] Sending packet: Type=NOTE, Seq=(\\d+)/(\\d+)': (match) => {
    return `Sending Packet ${match[1].padStart(4, '0')} of ${match[2].padStart(4, '0')}`;
  },
 
  '\\[CONTROL\\] Received control: Type=ACK, Content=ACK\\|(\\d+)': (match) => {
    return `Packet ${match[1].padStart(4, '0')} confirmed`;
  },
 
  '\\[CLIENT\\] Processed ([0-9]+) notes': (match) => {
    const noteCount = parseInt(match[1], 10);
    return `Processed ${noteCount} ${noteCount === 1 ? 'Note' : 'Notes'}`;
  },
 
  '\\[PACKET\\] Received Message: Type=RESPONSE, Seq=(\\d{4})/(\\d{4})': (match) => {
    const [current, total] = [parseInt(match[1]), parseInt(match[2])];
    return `Received Packet ${current} of ${total}`;
  },
 
  '\\[PACKET\\] Sending message: MessageType\\.DATA_REQUEST to \\(\'([A-Z0-9]+)\',\\s(\\d+)\\)': (match) => {
    return `Requesting Notes from server.`;
  },
  //${match[1]}-${match[2]}
 
  '\\[SESSION\\] CONNECTED to ([A-Z0-9]+-\\d+)': (match) => {
    return `Connected with server`;
  },
  // place back after test ${match[1]}
 
  '\\[SESSION\\] Failed to send request or achieve READY state\\. Attempt (\\d+) of (\\d+)': (match) => {
    return `WARNING: Failed to Achieve READY state. (${match[1]}/${match[2]}). Trying again...`;
  },
 
  '\\[CLIENT\\] JSON NOTE: ([\\s\\S]+)': (match) => {
    return `Full JSON: ${match[1]}`;
  },
 
  '\\[SERVER ERROR\\] Type: ([A-Z_]+), Message: (.+)': (match) => {
    return `Error: ${match[2]}`;
  },
 
  '\\[PACKET\\] Sending message: MessageType\\.NOTE to \\(\'([A-Z0-9]+)\',\\s*(\\d+)\\)': (match) => {
    return `Starting transmission.`;
  },

// place back above : ${match[1]}-${match[2]}

  '\\[WARNING\\] \\[SYSTEM\\] Received DONE but missing packets: {([\\d,]+)}': (match) => {
    const packets = match[1].split(',');
    return `Warning: Missing ${packets.length} packet${packets.length > 1 ? 's' : ''}, requesting resend...`;
  },

  '\\[SYSTEM\\] Attempting to recover packets: ([\\d,]+)': (match) => {
      const packets = match[1].split(',');
      return `Attempting to recover ${packets.length} missing packet${packets.length > 1 ? 's' : ''}...`;
  },

  '\\[PROGRESS\\] ([\\d.]+)% complete': (match) => {
      return `Progress: ${parseFloat(match[1]).toFixed(1)}% complete`;
  },
  '\\[PACKET\\] Attempt (\\d+) failed\\. Retrying in \\d+ seconds\\.\\.\\.': (match) => {
    const attemptNum = parseInt(match[1]);
    const ordinal = attemptNum === 1 ? '1st' : 
                   attemptNum === 2 ? '2nd' : 
                   attemptNum === 3 ? '3rd' : 
                   `${attemptNum}th`;
    return `${ordinal} attempt failed, retrying...`;
  },
  '\\[PACKET\\] Failed to send packet (\\d+)/(\\d+) after (\\d+) attempts\\. Moving to next packet\\.': (match) => {
      const [packet, total, attempts] = match.slice(1).map(num => parseInt(num));
      return `Failed to send packet ${packet.toString().padStart(4, '0')} of ${total.toString().padStart(4, '0')} after ${attempts} attempts`;
  },
  '\\[CONTROL\\] Sending packet: Type=RESPONSE, Seq=(\\d+)/(\\d+), Estimated transmission time: [\\d.]+ seconds': (match) => {
    return `Resending Packet ${match[1].padStart(4, '0')} of ${match[2].padStart(4, '0')}...`;
  }
 };
 
 export function translateLog(message) {
  for (const [pattern, translation] of Object.entries(logTranslations)) {
    const regex = new RegExp(pattern);
    const matches = message.match(regex);
    if (matches) {
      return typeof translation === 'function' ? translation(matches) : translation;
    }
  }
  console.log('No translation found for message:', message);
  return message;
 }