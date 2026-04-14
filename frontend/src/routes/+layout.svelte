<script>
  import '../app.css';
  import '$lib/icons.js';
  import '@fortawesome/fontawesome-svg-core/styles.css';
  import { config } from '@fortawesome/fontawesome-svg-core';
  import { Toast } from 'flowbite-svelte';
  import SettingsDrawer from '$lib/components/SettingsDrawer.svelte';
  import WriteNoteModal from '$lib/components/WriteNoteModal.svelte';
  import BottomNav from '$lib/components/BottomNav.svelte';
  import TopNav from '$lib/components/TopNav.svelte';
  import ProgressDrawer from '$lib/components/ProgressDrawer.svelte';
  import { logStore } from '$lib/stores/logStore';
  import { baseURL } from '$lib/stores/baseUrlStore';
  import { writable } from 'svelte/store';
  import { onMount } from 'svelte';
  import { slide } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';
  import { io } from 'socket.io-client';
  import RequestTypeModal from '$lib/components/RequestTypeModal.svelte';
  import ZapModal from '$lib/components/ZapModal.svelte';

  config.autoAddCss = false;

  let { children } = $props();

  // Stays as a writable store — ProgressDrawer subscribes to it
  const currentOperationLogs = writable([]);

  let settingsDrawerHidden = $state(true);
  let showToast = $state(false);
  let toastMessage = $state('');
  let toastType = $state('success');
  let showWriteNoteModal = $state(false);
  let showRequestTypeModal = $state(false);
  let showZapModal = $state(false);
  let isSending = $state(false);
  let progressDrawerOpen = $state(false);

  let progressDrawerHidden = $derived(!progressDrawerOpen);

  function clearOperationLogs() {
    console.log('Clearing all logs');
    currentOperationLogs.set([]);
    window.dispatchEvent(new CustomEvent('clearProgressLogs'));
  }

  function handleSettingsSaved(event) {
    const { success, message } = event.detail;
    toastMessage = message;
    toastType = success ? 'success' : 'error';
    showToast = true;
    setTimeout(() => { showToast = false; }, 1500);
  }

  function handleToast(event) {
    const { message, type } = event.detail;
    toastMessage = message;
    toastType = type;
    showToast = true;
    setTimeout(() => { showToast = false; }, 1500);
  }

  function handleLog(logData) {
    const data = JSON.parse(logData);
    logStore.addLog({
      timestamp: data.timestamp,
      level: data.level,
      message: data.message
    });

    if (data.message.includes('[CLIENT]') || data.message.includes('[PACKET]') ||
        data.message.includes('[SESSION]') || data.message.includes('[CONTROL]')) {
      currentOperationLogs.update(logs => [...logs, {
        timestamp: data.timestamp,
        level: data.level,
        message: data.message
      }]);
    }
  }

  onMount(() => {
    const socket = io($baseURL, {
      withCredentials: true,
      transports: ['websocket']
    });

    socket.on('connect', () => console.log('Connected to server'));
    socket.on('disconnect', () => console.log('Disconnected from server'));
    socket.on('log', handleLog);
    socket.on('error', (error) => console.error('Socket error:', error));

    window.addEventListener('showToast', handleToast);
    window.addEventListener('clearLogs', clearOperationLogs);
    window.addEventListener('openZapModal', (event) => {
      console.log('Layout received openZapModal event:', event.detail);
      showZapModal = true;
    });

    return () => {
      socket.disconnect();
      window.removeEventListener('showToast', handleToast);
      window.removeEventListener('clearLogs', clearOperationLogs);
    };
  });

  async function handleSubmitNote(noteData) {
    try {
      console.log('Sending note data:', noteData);
      currentOperationLogs.set([]);
      progressDrawerOpen = true;
      showWriteNoteModal = false;
      isSending = true;

      let interactionType = null;
      let targetNoteId = null;
      if (noteData.note_type === 2) { interactionType = 'replied'; targetNoteId = noteData.reply_to; }
      else if (noteData.note_type === 4) { interactionType = 'boosted'; targetNoteId = noteData.repost_id; }
      else if (noteData.note_type === 3) { interactionType = 'quoted'; targetNoteId = noteData.reply_to; }

      const response = await fetch(`${$baseURL}/api/send_note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(noteData)
      });

      const result = await response.json();
      if (!response.ok) throw new Error(result.message || 'Failed to send note');

      if (interactionType && targetNoteId) {
        window.dispatchEvent(new CustomEvent('noteInteractionUpdated', {
          detail: { noteId: targetNoteId, interactionType }
        }));
      }

      toastMessage = result.message || 'Note sent successfully!';
      toastType = 'success';

    } catch (err) {
      console.error('Error sending note:', err);
      currentOperationLogs.set([]);
      progressDrawerOpen = false;
      toastMessage = `Error: ${err.message}`;
      toastType = 'error';
    } finally {
      isSending = false;
      showToast = true;
      setTimeout(() => { showToast = false; }, 3000);
    }
  }

  async function handleSubmitZap(zapData) {
    try {
      currentOperationLogs.set([]);
      progressDrawerOpen = true;
      showZapModal = false;
      isSending = true;
      window.dispatchEvent(new CustomEvent('zapOperationStarted'));

      const response = await fetch(`${$baseURL}/api/send_zap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(zapData)
      });

      const result = await response.json();
      if (!response.ok) throw new Error(result.message || 'Failed to send zap');

      toastMessage = result.message || '⚡ Zap sent successfully!';
      toastType = 'success';

    } catch (err) {
      console.error('Error sending zap:', err);
      currentOperationLogs.set([]);
      progressDrawerOpen = false;
      toastMessage = `Error: ${err.message}`;
      toastType = 'error';
    } finally {
      window.dispatchEvent(new CustomEvent('zapOperationEnded'));
      isSending = false;
      showToast = true;
      setTimeout(() => { showToast = false; }, 3000);
    }
  }
</script>

<svelte:head>
  <title>HAMSTR - NOSTR over HAM</title>
</svelte:head>

{#if showToast}
  <Toast
    class="fixed top-4 left-1/2 -translate-x-1/2 z-[9999]"
    color={toastType === 'success' ? 'green' : toastType === 'error' ? 'red' : 'blue'}
    transition={slide}
    params={{ delay: 200, duration: 300, easing: quintOut }}
    dismissable={true}
    on:dismiss={() => showToast = false}
  >
    <span class="font-semibold">{toastMessage}</span>
  </Toast>
{/if}

<SettingsDrawer
  bind:hidden={settingsDrawerHidden}
  onsettingsSaved={(detail) => handleSettingsSaved({ detail })}
/>

<WriteNoteModal
  show={showWriteNoteModal}
  onClose={() => showWriteNoteModal = false}
  onSubmit={handleSubmitNote}
/>

<ZapModal
  show={showZapModal}
  onClose={() => showZapModal = false}
  onSubmit={handleSubmitZap}
/>

<RequestTypeModal
  show={showRequestTypeModal}
  onClose={() => showRequestTypeModal = false}
  onSubmit={(type) => {
    showRequestTypeModal = false;
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('requestTypeSelected', { detail: { type } }));
    }
  }}
/>

<main class="w-full min-h-screen">
  <TopNav
    on:searchRequest={(event) => {
      const { searchType, searchText } = event.detail;
      if (window.bottomNavComponent?.handleRequestNotes) {
        window.bottomNavComponent.handleRequestNotes(searchType, searchText);
      }
    }}
  />
  {@render children()}
</main>

<ProgressDrawer
  bind:hidden={progressDrawerHidden}
  {currentOperationLogs}
  {clearOperationLogs}
  {isSending}
  ondrawerClosed={() => { progressDrawerOpen = false; }}
/>

<BottomNav
  openWriteNoteModal={() => !isSending && (showWriteNoteModal = true)}
  {isSending}
  bind:settingsDrawerHidden
  bind:progressDrawerOpen
  on:clearLogs={() => {
    console.log('Clear logs event received');
    clearOperationLogs();
  }}
  on:showRequestModal={() => {
    console.log('Show request modal event received');
    showRequestTypeModal = true;
  }}
/>