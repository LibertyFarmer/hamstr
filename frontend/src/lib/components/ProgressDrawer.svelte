<script>
import { onMount, createEventDispatcher } from 'svelte';
import { Drawer, Button, Badge, Progressbar } from 'flowbite-svelte';
import { translateLog } from '$lib/logTranslator';
import { writable } from 'svelte/store';

const dispatch = createEventDispatcher();

export let hidden = true;
export let currentOperationLogs = writable([]);
export let clearOperationLogs = () => {};
export const isSending = false;

let logContainer;
let translatedMessages = [];
let progress = 0;
let connectionStatus = 'DISCONNECTED';
let pttStatus = 'RX';  // NEW: PTT status (RX or TX)

$: if (hidden) {
  dispatch('drawerClosed');
}

function formatTime(timestamp) {
  return timestamp.split(' ')[1];
}

function scrollToTop() {
  if (logContainer) {
    logContainer.scrollTop = 0;
  }
}

$: logs = $currentOperationLogs || [];

// Packet-based progress (for packet protocol)
$: packetInfo = logs.reduce((latest, log) => {
    const responseMatch = log.message.match(/Type=RESPONSE, Seq=(\d+)\/(\d+)/);
    const ackMatch = log.message.match(/Type=ACK, Content=ACK\|(\d+)/);
    const noteMatch = log.message.match(/Type=NOTE, Seq=\d+\/(\d+)/);
    const zapMatch = log.message.match(/Type=ZAP_KIND9734_REQUEST, Seq=\d+\/(\d+)/);
    const nwcMatch = log.message.match(/Type=NWC_PAYMENT_REQUEST, Seq=\d+\/(\d+)/);
    const zapAckMatch = log.message.match(/Zap Packet (\d+) confirmed/);
    const nwcAckMatch = log.message.match(/Payment Command Packet (\d+) confirmed/);

    if (noteMatch) return { ...latest, total: parseInt(noteMatch[1]) };
    if (zapMatch) return { ...latest, total: parseInt(zapMatch[1]) };
    if (nwcMatch) return { ...latest, total: parseInt(nwcMatch[1]) };
    
    if (ackMatch) {
        const current = parseInt(ackMatch[1]);
        return {
            current,
            total: latest.total,
            percent: latest.total ? (current / latest.total) * 100 : 0
        };
    }
    if (zapAckMatch) {
        const current = parseInt(zapAckMatch[1]);
        return {
            current,
            total: latest.total,
            percent: latest.total ? (current / latest.total) * 100 : 0
        };
    }
    if (nwcAckMatch) {
        const current = parseInt(nwcAckMatch[1]);
        return {
            current,
            total: latest.total,
            percent: latest.total ? (current / latest.total) * 100 : 0
        };
    }
    if (responseMatch) {
        const [current, total] = [parseInt(responseMatch[1]), parseInt(responseMatch[2])];
        return { current, total, percent: (current / total) * 100 };
    }
    return latest;
}, { current: 0, total: 0, percent: 0 });

// VARA state-based progress (check RAW messages, keep maximum)
$: varaProgress = logs.reduce((currentProgress, log) => {
  const msg = log.message;
  let newProgress = currentProgress;
  
  if (msg.includes('Connecting to') && msg.includes('VARA')) newProgress = Math.max(newProgress, 5);
  if (msg.includes('CONNECTED via VARA')) newProgress = Math.max(newProgress, 10);
  if (msg.includes('[CLIENT] Using protocol layer')) newProgress = Math.max(newProgress, 15);
  if (msg.includes('[CONTROL] Sending via VARA')) newProgress = Math.max(newProgress, 25);
  if (msg.includes('[CONTROL] Transmission complete') || msg.includes('[CONTROL] Data sent successfully')) newProgress = Math.max(newProgress, 35);
  if (msg.includes('[SYSTEM] Waiting for response via VARA')) newProgress = Math.max(newProgress, 45);
  if (msg.includes('[PACKET] Receiving data via VARA')) newProgress = Math.max(newProgress, 60);
  if (msg.includes('[PACKET] Received complete message')) newProgress = Math.max(newProgress, 75);
  if (msg.includes('[CONTROL] Received DONE')) newProgress = Math.max(newProgress, 85);
  if (msg.includes('[CONTROL] Sent DONE_ACK')) newProgress = Math.max(newProgress, 95);
  if (msg.includes('[SESSION] Client disconnect complete')) newProgress = Math.max(newProgress, 100);
  if (msg.includes('[CONTROL] Message received via VARA')) newProgress = Math.max(newProgress, 60);  // Server response received
  if (msg.includes('[CLIENT] Note Published!')) newProgress = Math.max(newProgress, 75);  // Note confirmed published
  if (msg.includes('[CONTROL] Sent DONE')) newProgress = Math.max(newProgress, 95);
  if (msg.includes('[SESSION] Client disconnect complete')) newProgress = Math.max(newProgress, 100);
  
  return newProgress;
}, 0);

// Detect if using VARA or packet protocol
$: isVARA = logs.some(log => log.message.includes('VARA'));

// Use appropriate progress based on protocol
$: progress = isVARA ? varaProgress : (packetInfo.total > 0 ? (packetInfo.current / packetInfo.total) * 100 : 0);

// NEW: PTT Status detection
$: pttStatus = logs.reduce((status, log) => {
  const msg = log.message;
  if (msg.includes('[CONTROL] ⚡ PTT ON')) return 'TX';
  if (msg.includes('[CONTROL] ⚡ PTT OFF')) return 'RX';
  return status;
}, 'RX');

$: connectionStatus = logs.reduce((status, log) => {
  const msg = log.message;
  // VARA connections
  if (msg.includes('[PACKET] CONNECTING to') && msg.includes('VARA')) return 'CONNECTING';
  if (msg.includes('[SESSION] CONNECTED via VARA')) return 'CONNECTED';
  if (msg.includes('[CONTROL] Waiting for DISCONNECT from server')) return 'DISCONNECTING';
  // Packet protocol connections
  if (msg.includes('[SESSION] CONNECTED to')) return 'CONNECTED';
  if (msg.includes('Sending CONNECTION REQUEST')) return 'CONNECTING';
  if (msg.includes('[SESSION] Client initiating disconnect')) return 'DISCONNECTING';
  if (msg.includes('[SESSION] Client disconnect complete')) return 'DISCONNECTED';
  // VARA disconnecting
  if (msg.includes('[SESSION] Disconnecting session:')) return 'DISCONNECTING';
  return status;
}, 'DISCONNECTED');

$: if (logs.length > 0) {
  const newLog = logs[logs.length - 1];
  if (newLog) {
    const translatedMessage = translateLog(newLog.message);
    // Skip messages that return null (PTT messages)
    if (translatedMessage !== null) {
      translatedMessages = [
        {
          translatedMessage: translatedMessage,
          shortTime: formatTime(newLog.timestamp)
        },
        ...translatedMessages
      ];
      setTimeout(scrollToTop, 0);
    }
  }
}

function closeDrawer() {
  console.log('Closing drawer, maintaining current state');
  hidden = true;
  dispatch('drawerClosed');
}

onMount(() => {
  const handleClearLogs = () => {
    console.log('Clearing translated messages');
    translatedMessages = [];
    progress = 0;
    connectionStatus = 'DISCONNECTED';
    pttStatus = 'RX';  // NEW: Reset PTT status
  };

  window.addEventListener('clearLogs', handleClearLogs);
  window.addEventListener('clearProgressLogs', handleClearLogs);

  return () => {
    console.log('ProgressDrawer unmounting');
    window.removeEventListener('clearLogs', handleClearLogs);
    window.removeEventListener('clearProgressLogs', handleClearLogs);
    translatedMessages = [];
    clearOperationLogs();
  };
});
</script>

<Drawer 
  bind:hidden
  placement="bottom"
  width="w-full sm:w-[440px]"
  class="h-[80vh]"
  activateClickOutside={true}
  transitionType="fly"
  transitionParams={{ y: 200 }}
  on:hidden={() => dispatch('drawerClosed')}
>
  <div class="p-4 space-y-4 flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between border-b pb-3">
      <h3 class="text-lg font-semibold">Operation Status</h3>
      <Button size="xs" color="light" class="ml-auto" on:click={closeDrawer}>
        ✕
      </Button>
    </div>

    <!-- Status Section - UPDATED TO 3 COLUMNS -->
    <div class="grid grid-cols-3 gap-4">
      <!-- Progress Section -->
      <div class="col-span-1">
        <div class="mb-2 text-sm font-medium">Progress</div>
        <Progressbar
          progress={progress}
          size="h-4"
          labelInside
          label={`${progress.toFixed(1)}%`}
          color={progress === 100 ? "green" : "blue"}
        />
        <div class="text-xs text-gray-500 mt-1">
          {#if isVARA}
            {progress < 100 ? 'Operation in progress...' : 'Complete'}
          {:else}
            {packetInfo.current} of {packetInfo.total} packets
          {/if}
        </div>
      </div>

      <!-- NEW: PTT Status Section -->
      <div class="col-span-1 flex flex-col items-center justify-center">
        <div class="mb-2 text-sm font-medium">PTT Status</div>
        <div class="flex items-center gap-2">
          <span class="text-2xl" class:animate-pulse={pttStatus === 'TX'}>📡</span>
          <Badge
            color={pttStatus === 'TX' ? 'red' : 'green'}
            large
          >
            {pttStatus}
          </Badge>
        </div>
      </div>

      <!-- Connection Status -->
      <div class="col-span-1 flex flex-col items-center justify-center">
        <div class="mb-2 text-sm font-medium">Connection Status</div>
        <Badge
          color={connectionStatus === 'CONNECTED' ? 'green' : 
                connectionStatus === 'CONNECTING' ? 'yellow' :
                connectionStatus === 'DISCONNECTING' ? 'yellow' : 'red'}
          large
        >
          {connectionStatus}
        </Badge>
      </div>
    </div>

    <!-- Logs Section -->
    <div 
      class="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-900 rounded p-4 min-h-[200px]"
      bind:this={logContainer}
    >
      {#each translatedMessages as log}
        <div class="text-sm mb-1 py-1 px-2 rounded bg-white dark:bg-gray-800">
          <span class="text-gray-500 dark:text-gray-400">{log.shortTime}</span>
          <span class="ml-2">{log.translatedMessage}</span>
        </div>
      {/each}
    </div>
  </div>
</Drawer>