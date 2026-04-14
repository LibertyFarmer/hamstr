<script>
  import { onMount, untrack } from 'svelte';
  import { Drawer, Button, Badge, Progressbar } from 'flowbite-svelte';
  import { translateLog } from '$lib/logTranslator';
  import { writable } from 'svelte/store';

  let {
    hidden = $bindable(true),
    currentOperationLogs = writable([]),
    clearOperationLogs = () => {},
    isSending = false,
    ondrawerClosed
  } = $props();

  let logContainer = $state(null);
  let translatedMessages = $state([]);

  $effect(() => {
    if (hidden) ondrawerClosed?.();
  });

  function formatTime(timestamp) {
    return timestamp.split(' ')[1];
  }

  function scrollToTop() {
    if (logContainer) logContainer.scrollTop = 0;
  }

  let logs = $derived($currentOperationLogs || []);

  let packetInfo = $derived(logs.reduce((latest, log) => {
    const responseMatch = log.message.match(/Type=RESPONSE, Seq=(\d+)\/(\d+)/);
    const ackMatch = log.message.match(/Type=ACK, Content=ACK\|(\d+)/);
    const noteMatch = log.message.match(/Type=NOTE, Seq=(\d+)\/(\d+)/);
    const zapMatch = log.message.match(/Type=ZAP_KIND9734_REQUEST, Seq=\d+\/(\d+)/);
    const nwcMatch = log.message.match(/Type=NWC_PAYMENT_REQUEST, Seq=\d+\/(\d+)/);
    const zapAckMatch = log.message.match(/Zap Packet (\d+) confirmed/);
    const nwcAckMatch = log.message.match(/Payment Command Packet (\d+) confirmed/);

    if (noteMatch) {
      const current = parseInt(noteMatch[1]);
      const total = parseInt(noteMatch[2]);
      return { current, total, percent: (current / total) * 100 };
    }
    if (zapMatch) return { ...latest, total: parseInt(zapMatch[1]) };
    if (nwcMatch) return { ...latest, total: parseInt(nwcMatch[1]) };
    if (ackMatch) {
      const current = parseInt(ackMatch[1]);
      return { current, total: latest.total, percent: latest.total ? (current / latest.total) * 100 : 0 };
    }
    if (zapAckMatch) {
      const current = parseInt(zapAckMatch[1]);
      return { current, total: latest.total, percent: latest.total ? (current / latest.total) * 100 : 0 };
    }
    if (nwcAckMatch) {
      const current = parseInt(nwcAckMatch[1]);
      return { current, total: latest.total, percent: latest.total ? (current / latest.total) * 100 : 0 };
    }
    if (responseMatch) {
      const [current, total] = [parseInt(responseMatch[1]), parseInt(responseMatch[2])];
      return { current, total, percent: (current / total) * 100 };
    }
    return latest;
  }, { current: 0, total: 0, percent: 0 }));

  let varaProgress = $derived(logs.reduce((currentProgress, log) => {
    const msg = log.message;
    let p = currentProgress;
    if (msg.includes('Connecting to') && msg.includes('VARA')) p = Math.max(p, 5);
    if (msg.includes('CONNECTED via VARA')) p = Math.max(p, 10);
    if (msg.includes('[CLIENT] Using protocol layer')) p = Math.max(p, 15);
    if (msg.includes('[CONTROL] Sending via VARA')) p = Math.max(p, 25);
    if (msg.includes('[CONTROL] Transmission complete') || msg.includes('[CONTROL] Data sent successfully')) p = Math.max(p, 35);
    if (msg.includes('[SYSTEM] Waiting for response via VARA')) p = Math.max(p, 45);
    if (msg.includes('[PACKET] Receiving data via VARA')) p = Math.max(p, 60);
    if (msg.includes('[PACKET] Received complete message')) p = Math.max(p, 75);
    if (msg.includes('[CONTROL] Received DONE')) p = Math.max(p, 85);
    if (msg.includes('[CONTROL] Sent DONE_ACK')) p = Math.max(p, 95);
    if (msg.includes('[SESSION] Client disconnect complete')) p = Math.max(p, 100);
    if (msg.includes('[CONTROL] Message received via VARA')) p = Math.max(p, 60);
    if (msg.includes('[CLIENT] Note Published!')) p = Math.max(p, 75);
    if (msg.includes('[CONTROL] Sent DONE')) p = Math.max(p, 95);
    return p;
  }, 0));

  let reticulumProgress = $derived(logs.reduce((currentProgress, log) => {
    const msg = log.message;
    let p = currentProgress;
    if (msg.includes('[RETICULUM] Connecting to server')) p = Math.max(p, 5);
    if (msg.includes('[RETICULUM] Finding path to server')) p = Math.max(p, 10);
    if (msg.includes('[RETICULUM] Establishing link')) p = Math.max(p, 15);
    if (/\[SESSION\] CONNECTED$/.test(msg)) p = Math.max(p, 20);
    if (msg.includes('[CLIENT] Using protocol layer')) p = Math.max(p, 25);
    if (msg.includes('[CONTROL] Data sent successfully') || msg.includes('[CONTROL] Transmission complete')) p = Math.max(p, 40);
    const transferMatch = msg.match(/\[PROGRESS\] Transfer: (\d+)%/);
    if (transferMatch) p = Math.max(p, 40 + Math.round(parseInt(transferMatch[1]) * 0.45));
    if (msg.includes('[RETICULUM] Response received')) p = Math.max(p, 75);
    if (msg.includes('[CONTROL] Received DONE')) p = Math.max(p, 85);
    if (msg.includes('[CONTROL] Sent DONE_ACK')) p = Math.max(p, 95);
    if (msg.includes('[SESSION] Client disconnect complete') || msg.includes('[SESSION] DISCONNECTED')) p = Math.max(p, 100);
    return p;
  }, 0));

  let isVARA = $derived(logs.some(log => log.message.includes('VARA')));
  let isReticulum = $derived(!isVARA && logs.some(log => /\[SESSION\] CONNECTED$/.test(log.message)));

  let progress = $derived(
    isVARA ? varaProgress
    : isReticulum ? reticulumProgress
    : (packetInfo.total > 0 ? (packetInfo.current / packetInfo.total) * 100 : 0)
  );

  let pttStatus = $derived(logs.reduce((status, log) => {
    const msg = log.message;
    if (msg.includes('[CONTROL] ⚡ PTT ON')) return 'TX';
    if (msg.includes('[CONTROL] ⚡ PTT OFF')) return 'RX';
    return status;
  }, 'RX'));

  let connectionStatus = $derived(logs.reduce((status, log) => {
    const msg = log.message;
    if (msg.includes('[PACKET] CONNECTING to') && msg.includes('VARA')) return 'CONNECTING';
    if (msg.includes('[SESSION] CONNECTED via VARA')) return 'CONNECTED';
    if (msg.includes('[CONTROL] Waiting for DISCONNECT from server')) return 'DISCONNECTING';
    if (msg.includes('[SESSION] CONNECTED to')) return 'CONNECTED';
    if (msg.includes('Sending CONNECTION REQUEST')) return 'CONNECTING';
    if (msg.includes('[SESSION] Client initiating disconnect')) return 'DISCONNECTING';
    if (msg.includes('[SESSION] Client disconnect complete')) return 'DISCONNECTED';
    if (msg.includes('[SESSION] Disconnecting session:')) return 'DISCONNECTING';
    if (msg.includes('[RETICULUM] Connecting to server') || msg.includes('[RETICULUM] Finding path') || msg.includes('[RETICULUM] Establishing link')) return 'CONNECTING';
    if (msg.includes('[SESSION] CONNECTED') && !msg.includes('via VARA') && !msg.includes(' to ')) return 'CONNECTED';
    if (msg.includes('[RETICULUM] Disconnecting')) return 'DISCONNECTING';
    if (msg.includes('[SESSION] DISCONNECTED')) return 'DISCONNECTED';
    return status;
  }, 'DISCONNECTED'));

  // Append new logs to translatedMessages — untrack the read to avoid circular tracking
  $effect(() => {
    if (logs.length > 0) {
      const newLog = logs[logs.length - 1];
      if (newLog) {
        const translatedMessage = translateLog(newLog.message);
        if (translatedMessage !== null) {
          untrack(() => {
            translatedMessages = [
              { translatedMessage, shortTime: formatTime(newLog.timestamp) },
              ...translatedMessages
            ];
          });
          setTimeout(scrollToTop, 0);
        }
      }
    }
  });

  function closeDrawer() {
    console.log('Closing drawer, maintaining current state');
    hidden = true;
    ondrawerClosed?.();
  }

  onMount(() => {
    const handleClearLogs = () => {
      console.log('Clearing translated messages');
      translatedMessages = [];
      // progress, connectionStatus, pttStatus auto-reset via $derived when logs clear
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
  open={!hidden}
  placement="bottom"
  width="w-full sm:w-[440px]"
  class="h-[80vh]"
  outsideclose={true}
  transitionType="fly"
  transitionParams={{ y: 200 }}
  onhide={() => { hidden = true; ondrawerClosed?.(); }}
>
  <div class="p-4 space-y-4 flex flex-col h-full">

    <!-- Header -->
    <div class="flex items-center justify-between border-b pb-3">
      <h3 class="text-lg font-semibold">Operation Status</h3>
      <Button size="xs" color="light" class="ml-auto" onclick={closeDrawer}>✕</Button>
    </div>

    <!-- Status Section -->
    <div class="grid grid-cols-3 gap-4">

      <!-- Progress -->
      <div class="col-span-1">
        <div class="mb-2 text-sm font-medium">Progress</div>
        <Progressbar
          progress={progress}
          size="h-4"
          labelInside
          label={`${progress.toFixed(1)}%`}
          color={progress === 100 ? 'green' : 'blue'}
        />
        <div class="text-xs text-gray-500 mt-1">
          {#if isVARA || isReticulum}
            {progress < 100 ? 'Operation in progress...' : 'Complete'}
          {:else}
            {packetInfo.current} of {packetInfo.total} packets
          {/if}
        </div>
      </div>

      <!-- PTT Status -->
      <div class="col-span-1 flex flex-col items-center justify-center">
        <div class="mb-2 text-sm font-medium">PTT Status</div>
        <div class="flex items-center gap-2">
          <span class="text-2xl" class:animate-pulse={pttStatus === 'TX'}>📡</span>
          <Badge color={pttStatus === 'TX' ? 'red' : 'green'} large>
            {pttStatus}
          </Badge>
        </div>
      </div>

      <!-- Connection Status -->
      <div class="col-span-1 flex flex-col items-center justify-center">
        <div class="mb-2 text-sm font-medium">Connection Status</div>
        <Badge
          color={connectionStatus === 'CONNECTED' ? 'green'
            : connectionStatus === 'CONNECTING' ? 'yellow'
            : connectionStatus === 'DISCONNECTING' ? 'yellow'
            : 'red'}
          large
        >
          {connectionStatus}
        </Badge>
      </div>

    </div>

    <!-- Logs -->
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