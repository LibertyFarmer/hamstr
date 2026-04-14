<script>
  import { goto } from '$app/navigation';
  import { Toast, Spinner } from 'flowbite-svelte';
  import { HomeSolid, PenNibSolid, AdjustmentsVerticalOutline, DownloadSolid } from 'flowbite-svelte-icons';
  import { isRequestingNotes } from '$lib/stores/requestNotesStore';
  import { baseURL } from '$lib/stores/baseUrlStore';
  import { onMount } from 'svelte';
  import { NoteRequestType } from '$lib/utils/enums';

  let {
    openWriteNoteModal,
    progressDrawerOpen = $bindable(false),
    isSending = false,
    settingsDrawerHidden = $bindable(true),
    onclearLogs,
    onshowRequestModal
  } = $props();

  let isZapping = $state(false);
  let noteRequestCount = $state(1);
  let showToast = $state(false);
  let toastMessage = $state('');
  let toastType = $state('success');
  let isProcessing = $state(false);

  let apiBaseUrl = $derived($baseURL);

  onMount(async () => {
    isRequestingNotes.set(false);
    progressDrawerOpen = false;
    isProcessing = false;
    console.log('BottomNav mounted, initial drawer state:', progressDrawerOpen);
    await fetchSettings();

    window.addEventListener('requestTypeSelected', handleRequestTypeSelected);
    window.addEventListener('settingsUpdated', fetchSettings);
    window.addEventListener('zapOperationStarted', () => {
      isZapping = true;
      console.log('Zap operation detected - switching to zapping indicator');
    });
    window.addEventListener('zapOperationEnded', () => {
      isZapping = false;
      console.log('Zap operation ended - back to normal indicator');
    });

    window.bottomNavComponent = {
      handleRequestNotes,
      set progressDrawerOpen(value) { progressDrawerOpen = value; },
      get progressDrawerOpen() { return progressDrawerOpen; }
    };

    return () => {
      window.removeEventListener('requestTypeSelected', handleRequestTypeSelected);
      window.removeEventListener('settingsUpdated', fetchSettings);
      window.removeEventListener('zapOperationStarted');
      window.removeEventListener('zapOperationEnded');
      delete window.bottomNavComponent;
    };
  });

  function createToastMessage(requestType, count, searchText = '') {
    if (count === 0) {
      switch (requestType) {
        case NoteRequestType.SEARCH_TEXT: return `No notes found for search "${searchText}"`;
        case NoteRequestType.SEARCH_HASHTAG: return `No notes found for hashtags: ${searchText}`;
        case NoteRequestType.SEARCH_USER: return 'No notes found for NPUB';
        case NoteRequestType.FOLLOWING: return 'No notes found from followed accounts';
        case NoteRequestType.GLOBAL: return 'No global notes found';
        default: return 'No notes found';
      }
    }
    switch (requestType) {
      case NoteRequestType.SEARCH_TEXT: return `Found ${count} note${count !== 1 ? 's' : ''} matching "${searchText}"`;
      case NoteRequestType.SEARCH_HASHTAG: return `Found ${count} note${count !== 1 ? 's' : ''} with hashtag${searchText.includes(',') ? 's' : ''}: ${searchText}`;
      case NoteRequestType.SEARCH_USER: return `Found ${count} note${count !== 1 ? 's' : ''} from NPUB`;
      case NoteRequestType.FOLLOWING: return `Grabbed ${count} note${count !== 1 ? 's' : ''} from followed accounts`;
      case NoteRequestType.GLOBAL: return `Grabbed ${count} note${count !== 1 ? 's' : ''} from the global feed`;
      default: return `Retrieved ${count} note${count !== 1 ? 's' : ''}`;
    }
  }

  function handleRequestTypeSelected(event) {
    const { type } = event.detail;
    onclearLogs?.();
    progressDrawerOpen = true;
    setTimeout(() => handleRequestNotes(type), 200);
  }

  function goHome() { goto('/'); }

  function handleFetchClick() {
    if ($isRequestingNotes) {
      progressDrawerOpen = !progressDrawerOpen;
      return;
    }
    if (!isProcessing && !$isRequestingNotes) {
      onshowRequestModal?.();
      onclearLogs?.();
    }
  }

  function openSettings() { settingsDrawerHidden = false; }

  async function fetchSettings() {
    try {
      console.log('Fetching settings from:', `${apiBaseUrl}/api/settings`);
      const response = await fetch(`${apiBaseUrl}/api/settings`);
      const data = await response.json();
      noteRequestCount = data.NOSTR_DEFAULT_NOTE_REQUEST_COUNT || 1;
      console.log('Settings fetched, note request count:', noteRequestCount);
    } catch (error) {
      console.error('Error fetching settings:', error);
    }
  }

  async function refreshRecentNotes() {
    const response = await fetch(`${apiBaseUrl}/api/notes`);
    if (!response.ok) throw new Error('Failed to fetch recent notes');
    const notes = await response.json();
    window.dispatchEvent(new CustomEvent('notesUpdated', { detail: notes }));
  }

  async function handleRequestNotes(requestType, searchText = '') {
    if ($isRequestingNotes || isProcessing) {
      console.log('Request already in progress, skipping');
      return;
    }
    try {
      isRequestingNotes.set(true);
      isProcessing = true;

      const response = await fetch(`${apiBaseUrl}/request_notes/${noteRequestCount}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requestType, searchText })
      });

      const result = await response.json();
      console.log('Request result:', result);

      if (response.ok) {
        if (!result.success) {
          toastMessage = result.message || 'Unknown error occurred';
          toastType = 'error';
          showToast = true;
          onclearLogs?.();
          progressDrawerOpen = false;
          return;
        }
        await refreshRecentNotes();
        onclearLogs?.();
        await new Promise(resolve => setTimeout(resolve, 300));
        progressDrawerOpen = false;
        await new Promise(resolve => setTimeout(resolve, 300));
        const noteCount = parseInt(result.message.match(/\d+/)[0]) || 0;
        toastMessage = createToastMessage(requestType, noteCount, searchText);
        toastType = 'success';
        showToast = true;
      } else {
        throw new Error(result.message || 'Failed to request notes');
      }
    } catch (err) {
      console.error('Error in handleRequestNotes:', err);
      onclearLogs?.();
      await new Promise(resolve => setTimeout(resolve, 300));
      progressDrawerOpen = false;
      await new Promise(resolve => setTimeout(resolve, 300));
      toastMessage = err.message;
      toastType = 'error';
      showToast = true;
    } finally {
      isRequestingNotes.set(false);
      isProcessing = false;
      setTimeout(() => { showToast = false; }, 3000);
    }
  }

  function handleWriteClick() {
    if (isSending) {
      progressDrawerOpen = !progressDrawerOpen;
    } else {
      openWriteNoteModal();
    }
  }
</script>

<style>
  @keyframes lightning-charge {
    0%   { background: linear-gradient(to top, transparent 0%, transparent 100%); }
    25%  { background: linear-gradient(to top, #6b7280 0%, #6b7280 30%, transparent 30%); }
    50%  { background: linear-gradient(to top, #4b5563 0%, #6b7280 60%, transparent 60%); }
    75%  { background: linear-gradient(to top, #374151 0%, #4b5563 80%, transparent 80%); }
    100% { background: linear-gradient(to top, transparent 0%, transparent 100%); }
  }

  .lightning-charging {
    animation: lightning-charge 2s ease-in-out infinite;
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    mask: url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M7 2v11h3v9l7-12h-4l4-8z'/%3E%3C/svg%3E");
    -webkit-mask: url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M7 2v11h3v9l7-12h-4l4-8z'/%3E%3C/svg%3E");
    mask-size: contain; mask-repeat: no-repeat; mask-position: center;
    -webkit-mask-size: contain; -webkit-mask-repeat: no-repeat; -webkit-mask-position: center;
  }

  @keyframes lightning-glow {
    0%, 100% { filter: drop-shadow(0 0 2px #6b7280); }
    50%       { filter: drop-shadow(0 0 6px #4b5563) drop-shadow(0 0 8px #6b7280); }
  }

  .lightning-glow { animation: lightning-glow 1.8s ease-in-out infinite; }
</style>

{#if showToast}
  <Toast
    class="fixed top-4 left-1/2 -translate-x-1/2 z-[9999]"
    color={toastType === 'success' ? 'green' : toastType === 'error' ? 'red' : 'blue'}
    dismissable
    ondismiss={() => showToast = false}
  >
    <span class="font-semibold">{toastMessage}</span>
  </Toast>
{/if}

<div class="fixed bottom-0 left-0 right-0 z-50 bg-slate-100 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-600">
  <div class="flex justify-center h-16 max-w-lg mx-auto">

    <button onclick={goHome}
      class="inline-flex flex-col items-center justify-center px-5 hover:bg-gray-50 dark:hover:bg-gray-700 group">
      <HomeSolid class="w-6 h-6 mb-1 text-gray-500 dark:text-gray-400 group-hover:text-primary-600" />
      <span class="text-xs text-gray-500 dark:text-gray-400 group-hover:text-primary-600">Home</span>
    </button>

    <button onclick={handleFetchClick} disabled={isSending}
      class="inline-flex flex-col items-center justify-center px-5 hover:bg-gray-50 dark:hover:bg-gray-700 group">
      {#if $isRequestingNotes}
        <div class="w-6 h-6 mb-1 flex items-center justify-center">
          <Spinner size="6" color="gray" />
        </div>
      {:else}
        <DownloadSolid class="w-6 h-6 mb-1 text-gray-500 dark:text-gray-400 group-hover:text-primary-600" />
      {/if}
      <span class="text-xs text-gray-500 dark:text-gray-400 group-hover:text-primary-600">Fetch</span>
    </button>

    <button onclick={handleWriteClick} disabled={$isRequestingNotes}
      class="inline-flex flex-col items-center justify-center px-5 hover:bg-gray-50 dark:hover:bg-gray-700 group">
      {#if isSending && isZapping}
        <div class="w-6 h-6 mb-1 flex items-center justify-center relative lightning-glow">
          <svg class="w-6 h-6 text-gray-600 dark:text-gray-300" viewBox="0 0 24 24" fill="currentColor">
            <path d="M7 2v11h3v9l7-12h-4l4-8z"/>
          </svg>
          <div class="lightning-charging"></div>
        </div>
      {:else if isSending}
        <div class="w-6 h-6 mb-1 flex items-center justify-center">
          <Spinner size="6" color="gray" />
        </div>
      {:else}
        <PenNibSolid class="w-6 h-6 mb-1 text-gray-500 dark:text-gray-400 group-hover:text-primary-600" />
      {/if}
      <span class="text-xs text-gray-500 dark:text-gray-400 group-hover:text-primary-600">
        {isZapping ? 'Zapping' : 'Write'}
      </span>
    </button>

    <button onclick={openSettings}
      class="inline-flex flex-col items-center justify-center px-5 hover:bg-gray-50 dark:hover:bg-gray-700 group">
      <AdjustmentsVerticalOutline class="w-6 h-6 mb-1 text-gray-500 dark:text-gray-400 group-hover:text-primary-600" />
      <span class="text-xs text-gray-500 dark:text-gray-400 group-hover:text-primary-600">Settings</span>
    </button>

  </div>
</div>