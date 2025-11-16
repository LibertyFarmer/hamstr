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
$: packetInfo = logs.reduce((latest, log) => {
    // For requests
    const responseMatch = log.message.match(/Type=RESPONSE, Seq=(\d+)\/(\d+)/);
    // For note ACK confirmations  
    const ackMatch = log.message.match(/Type=ACK, Content=ACK\|(\d+)/);
    // For getting total packet count from sending message
    const noteMatch = log.message.match(/Type=NOTE, Seq=\d+\/(\d+)/);
    
    // NEW: Handle ZAP packet types
    const zapMatch = log.message.match(/Type=ZAP_KIND9734_REQUEST, Seq=\d+\/(\d+)/);
    const nwcMatch = log.message.match(/Type=NWC_PAYMENT_REQUEST, Seq=\d+\/(\d+)/);
    
    // NEW: Handle zap ACK confirmations (from translated messages)
    const zapAckMatch = log.message.match(/Zap Packet (\d+) confirmed/);
    const nwcAckMatch = log.message.match(/Payment Command Packet (\d+) confirmed/);

    if (noteMatch) {
        return { ...latest, total: parseInt(noteMatch[1]) };
    }
    if (zapMatch) {
        return { ...latest, total: parseInt(zapMatch[1]) };
    }
    if (nwcMatch) {
        return { ...latest, total: parseInt(nwcMatch[1]) };
    }
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

$: progress = packetInfo.total > 0 ? (packetInfo.current / packetInfo.total) * 100 : 0;

$: connectionStatus = logs.reduce((status, log) => {
 const msg = log.message;
 if (msg.includes('[SESSION] CONNECTED to')) return 'CONNECTED';
 if (msg.includes('Sending CONNECTION REQUEST')) return 'CONNECTING';
 if (msg.includes('[SESSION] Client initiating disconnect')) return 'DISCONNECTING';
 if (msg.includes('Client disconnect complete')) return 'DISCONNECTED';
 return status;
}, 'DISCONNECTED');

$: if (logs.length > 0) {
 const newLog = logs[logs.length - 1];
 if (newLog) {
   translatedMessages = [
     {
       translatedMessage: translateLog(newLog.message),
       shortTime: formatTime(newLog.timestamp)
     },
     ...translatedMessages
   ];
   setTimeout(scrollToTop, 0);
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

    <!-- Status Section -->
    <div class="grid grid-cols-2 gap-4">
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
          {packetInfo.current} of {packetInfo.total} packets
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