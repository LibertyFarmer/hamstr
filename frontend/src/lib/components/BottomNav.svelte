<script>
  import { goto } from '$app/navigation';
  import { BottomNav, BottomNavItem, Toast, Spinner } from 'flowbite-svelte';
  import { HomeSolid, PenNibSolid, AdjustmentsVerticalOutline, DownloadSolid } from 'flowbite-svelte-icons';
  import { isRequestingNotes } from '$lib/stores/requestNotesStore';
  import { baseURL } from '$lib/store';
  import { onMount } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import { NoteRequestType } from '$lib/utils/enums';

  const dispatch = createEventDispatcher();
  
  export let openWriteNoteModal;
  export let progressDrawerOpen = false;
  export let isSending = false;
  export let settingsDrawerHidden = true;
  
  let noteRequestCount = 1;
  let showToast = false;
  let toastMessage = '';
  let toastType = 'success';
  let apiBaseUrl;
  let isProcessing = false;
  let showRequestTypeModal = false;

  $: apiBaseUrl = $baseURL;

  onMount(async () => {
    isRequestingNotes.set(false);
    progressDrawerOpen = false;
    isProcessing = false;
    console.log('BottomNav mounted, initial drawer state:', progressDrawerOpen);
    await fetchSettings();

    window.addEventListener('requestTypeSelected', handleRequestTypeSelected);
    window.addEventListener('settingsUpdated', fetchSettings);  // Add this
    
    window.bottomNavComponent = {
      handleRequestNotes
    };

    return () => {
      window.removeEventListener('requestTypeSelected', handleRequestTypeSelected);
      window.removeEventListener('settingsUpdated', fetchSettings);  // Add this
      delete window.bottomNavComponent;
    };
});

  function createToastMessage(requestType, count, searchText = '') {
    if (count === 0) {
        switch(requestType) {
            case NoteRequestType.SEARCH_TEXT:
                return `No notes found for search "${searchText}"`;
            case NoteRequestType.SEARCH_HASHTAG:
                return `No notes found for hashtags: ${searchText}`;
            case NoteRequestType.SEARCH_USER:
                return searchText.startsWith('npub') ? 
                    "No notes found for NPUB" : 
                    `No notes found for NPUB`;
            case NoteRequestType.FOLLOWING:
                return "No notes found from followed accounts";
            case NoteRequestType.GLOBAL:
                return "No global notes found";
            default:
                return "No notes found";
        }
    }

    switch(requestType) {
        case NoteRequestType.SEARCH_TEXT:
            return `Found ${count} note${count !== 1 ? 's' : ''} matching "${searchText}"`;
        case NoteRequestType.SEARCH_HASHTAG:
            return `Found ${count} note${count !== 1 ? 's' : ''} with hashtag${searchText.includes(',') ? 's' : ''}: ${searchText}`;
        case NoteRequestType.SEARCH_USER:
            return searchText.startsWith('npub') ? 
                `Found ${count} note${count !== 1 ? 's' : ''} from NPUB` : 
                `Found ${count} note${count !== 1 ? 's' : ''} from NPUB`;
        case NoteRequestType.FOLLOWING:
            return `Grabbed ${count} note${count !== 1 ? 's' : ''} from followed accounts`;
        case NoteRequestType.GLOBAL:
            return `Grabbed ${count} note${count !== 1 ? 's' : ''} from the global feed`;
        default:
            return `Retrieved ${count} note${count !== 1 ? 's' : ''}`;
    }
}

  function handleRequestTypeSelected(event) {
    const { type } = event.detail;
    dispatch('clearLogs');
    progressDrawerOpen = true;
    handleRequestNotes(type);
  }

  function goHome() {
    goto('/');
  }

  function handleFetchClick() {
    console.log('Current states:', { 
      isRequesting: $isRequestingNotes, 
      drawerOpen: progressDrawerOpen, 
      isProcessing 
    });
    
    if ($isRequestingNotes) {
      let newState = !progressDrawerOpen;
      progressDrawerOpen = newState;
      console.log('Setting drawer to:', newState);
      return;
    }
    
    if (!isProcessing && !$isRequestingNotes) {
      dispatch('showRequestModal');
      console.log('Dispatched showRequestModal event');
      dispatch('clearLogs');
    }
  }

  function openSettings() {
    settingsDrawerHidden = false;
  }

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
    try {
      const response = await fetch(`${apiBaseUrl}/`);
      if (!response.ok) throw new Error('Failed to fetch recent notes');
      const notes = await response.json();
      window.dispatchEvent(new CustomEvent('notesUpdated', { detail: notes }));
    } catch (err) {
      console.error("Error fetching notes:", err);
      throw err;
    }
  }

  async function handleRequestNotes(requestType, searchText = '') {
    if ($isRequestingNotes || isProcessing) {
        console.log('Already requesting notes, ignoring');
        return;
    }

    isProcessing = true;
    isRequestingNotes.set(true);
    console.log('Starting note request process');
    progressDrawerOpen = true;

    try {
        console.log(`Making request to ${apiBaseUrl}/request_notes/${noteRequestCount}`);
        const response = await fetch(`${apiBaseUrl}/request_notes/${noteRequestCount}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                requestType: requestType,
                count: noteRequestCount,
                searchText: searchText
            })
        });
        
        console.log('Response received:', response);
        const result = await response.json();
        console.log('Response data:', result);

        if (response.ok) {
            if (!result.success) {
                // Handle error response from server
                toastMessage = result.message || 'Unknown error occurred';
                toastType = 'error';
                showToast = true;
                dispatch('clearLogs');
                progressDrawerOpen = false;
                return;
            }
            
            try {
                // Get fresh notes
                const notesResponse = await fetch(`${apiBaseUrl}/`);
                const notesData = await notesResponse.json();
                
                window.dispatchEvent(new CustomEvent('notesUpdated', { 
                    detail: notesData 
                }));

                dispatch('clearLogs');
                await new Promise(resolve => setTimeout(resolve, 300));
                progressDrawerOpen = false;
                
                await new Promise(resolve => setTimeout(resolve, 300));
                
                // Get the actual number of notes from the original response
                const noteCount = parseInt(result.message.match(/\d+/)[0]) || 0;
                
                // Create toast message using the actual notes count
                toastMessage = createToastMessage(requestType, noteCount, searchText);
                toastType = 'success';
                showToast = true;
            } catch (err) {
                console.error("Error refreshing notes:", err);
                throw err;
            }
        } else {
            throw new Error(result.message || 'Failed to request notes');
        }
    } catch (err) {
        console.error('Error in handleRequestNotes:', err);
        
        dispatch('clearLogs');
        await new Promise(resolve => setTimeout(resolve, 300));
        progressDrawerOpen = false;
        
        await new Promise(resolve => setTimeout(resolve, 300));
        toastMessage = err.message;
        toastType = 'error';
        showToast = true;
    } finally {
        isRequestingNotes.set(false);
        isProcessing = false;
        
        setTimeout(() => {
            showToast = false;
        }, 3000);
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

{#if showToast}
  <Toast
    class="fixed top-4 left-1/2 -translate-x-1/2 z-[9999]"
    color={toastType === 'success' ? 'green' : toastType === 'error' ? 'red' : 'blue'}
    dismissable
    on:dismiss={() => showToast = false}
  >
    <span class="font-semibold">{toastMessage}</span>
  </Toast>
{/if}

<BottomNav position="fixed" navType="border" classOuter="bg-slate-100" classInner="grid-cols-4">
  <BottomNavItem btnName="Home"
    on:click={goHome}>
    <HomeSolid class="w-6 h-6 mb-1 text-gray-500 dark:text-gray-400 group-hover:text-primary-600 dark:group-hover:text-primary-500" />
  </BottomNavItem>

  <BottomNavItem 
  btnName="Fetch"
  on:click={handleFetchClick}
  disabled={isSending} 
  class="relative"
>
  {#if $isRequestingNotes}
    <div class="w-6 h-6 mb-1 flex items-center justify-center cursor-pointer">
      <Spinner size="6" color="gray" />
    </div>
  {:else}
    <DownloadSolid class="w-6 h-6 mb-1 text-gray-500 dark:text-gray-400 group-hover:text-primary-600 dark:group-hover:text-primary-500" />
  {/if}
</BottomNavItem>

<BottomNavItem 
  btnName="Write"
  on:click={handleWriteClick}
  disabled={$isRequestingNotes} 
  class={isSending ? 'cursor-pointer' : ''}>
  {#if isSending}
    <div class="w-6 h-6 mb-1 flex items-center justify-center">
      <Spinner size="6" color="gray" />
    </div>
  {:else}
    <PenNibSolid class="w-6 h-6 mb-1 text-gray-500 dark:text-gray-400 group-hover:text-primary-600 dark:group-hover:text-primary-500" />
  {/if}
</BottomNavItem>

  <BottomNavItem 
    btnName="Settings"
    on:click={openSettings}>
    <AdjustmentsVerticalOutline class="w-6 h-6 mb-1 text-gray-500 dark:text-gray-400 group-hover:text-primary-600 dark:group-hover:text-primary-500" />
  </BottomNavItem>
</BottomNav>