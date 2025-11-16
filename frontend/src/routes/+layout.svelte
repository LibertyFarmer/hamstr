<script>
  import '../app.postcss';
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

  let currentOperationLogs = writable([]);
  let settingsDrawerHidden = true;
  let showToast = false;
  let toastMessage = '';
  let toastType = 'success';
  let showWriteNoteModal = false;
  let showRequestTypeModal = false;
  let showZapModal = false;  // Fixed: moved to top level
  let isSending = false;
  let progressDrawerOpen = false;
  $: progressDrawerHidden = !progressDrawerOpen;

  let apiBaseUrl;
  $: apiBaseUrl = $baseURL;
  
  function clearOperationLogs() {
    console.log('Clearing all logs');
    currentOperationLogs.set([]);
    // Dispatch a custom event for ProgressDrawer
    window.dispatchEvent(new CustomEvent('clearProgressLogs'));
  }

  function handleSettingsSaved(event) {
    const { success, message } = event.detail;
    toastMessage = message;
    toastType = success ? 'success' : 'error';
    showToast = true;
    setTimeout(() => {
      showToast = false;
    }, 1500);
  }

  function handleToast(event) {
    const { message, type } = event.detail;
    toastMessage = message;
    toastType = type;
    showToast = true;
    setTimeout(() => {
      showToast = false;
    }, 1500);
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
      currentOperationLogs.update(logs => {
        return [...logs, {
          timestamp: data.timestamp,
          level: data.level,
          message: data.message
        }];
      });
    }
  }

  onMount(() => {
    const socket = io($baseURL, {
      withCredentials: true,
      transports: ['websocket']
    });

    socket.on('connect', () => {
      console.log('Connected to server');
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from server');
    });

    socket.on('log', handleLog);

    socket.on('error', (error) => {
      console.error('Socket error:', error);
    });

    window.addEventListener('showToast', handleToast);
    window.addEventListener('clearLogs', clearOperationLogs);
    // Fixed: Added event listener for zap modal
    window.addEventListener('openZapModal', (event) => {
      console.log('Layout received openZapModal event:', event.detail);
      showZapModal = true;
    });

    return () => {
      socket.disconnect();
      window.removeEventListener('showToast', handleToast);
      window.removeEventListener('clearLogs', clearOperationLogs);
      window.removeEventListener('openZapModal');  // Fixed: Added cleanup
    };
  });

  async function handleSubmitNote(noteData) {
  try {
    console.log('Sending note data:', noteData);

    currentOperationLogs.set([]);
    progressDrawerOpen = true;
    showWriteNoteModal = false;
    isSending = true;
    
    // Track the interaction type for database updates
    let interactionType = null;
    let targetNoteId = null;
    
    if (noteData.note_type === 2) { // REPLY
      interactionType = 'replied';
      targetNoteId = noteData.reply_to;
    } else if (noteData.note_type === 4) { // REPOST/BOOST  
      interactionType = 'boosted';
      targetNoteId = noteData.repost_id;
    } else if (noteData.note_type === 3) { // QUOTE
      interactionType = 'quoted'; 
      targetNoteId = noteData.reply_to;
    }
    
    console.log('Interaction tracking:', { interactionType, targetNoteId });
    
    const response = await fetch(`${$baseURL}/api/send_note`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(noteData)
    });

    const result = await response.json();
    
    if (!response.ok) {
      throw new Error(result.message || 'Failed to send note');
    }

    if (result.success) {
      currentOperationLogs.set([]);
      progressDrawerOpen = false;
      
      // NEW: Update interaction status if this was a reply/boost/quote
      if (interactionType && targetNoteId) {
        console.log(`Updating ${interactionType} status for note ${targetNoteId}`);
        try {
          const updateResponse = await fetch(`${$baseURL}/api/notes/${targetNoteId}/interaction`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ type: interactionType })
          });
          
          if (updateResponse.ok) {
            // Dispatch event to update UI immediately
            window.dispatchEvent(new CustomEvent('noteInteractionUpdated', {
              detail: { 
                noteId: targetNoteId, 
                interactionType: interactionType 
              }
            }));
            
            console.log(`Note marked as ${interactionType} in database and UI updated`);
          } else {
            console.error('Failed to update interaction status in database');
          }
        } catch (dbError) {
          console.error(`Error updating ${interactionType} status:`, dbError);
        }
      }
      
      // Refresh notes list
      const notesResponse = await fetch(`${$baseURL}/api/notes`);
      if (notesResponse.ok) {
        const notesData = await notesResponse.json();
        window.dispatchEvent(new CustomEvent('notesUpdated', { 
          detail: notesData 
        }));
      }
      
      await new Promise(resolve => setTimeout(resolve, 300));
      toastMessage = 'Note successfully sent';
      toastType = 'success';
    } else {
      throw new Error(result.message || 'Failed to send note');
    }

  } catch (err) {
    console.error("Error sending note:", err);
    currentOperationLogs.set([]);
    progressDrawerOpen = false;
    toastMessage = `Error: ${err.message}`;
    toastType = 'error';

  } finally {
    isSending = false;
    showToast = true;
    currentOperationLogs.set([]);
    setTimeout(() => {
      showToast = false;
    }, 3000);
  }
}

async function handleSubmitZap(zapData) {
  try {
    console.log('Sending zap data:', zapData);

    // Dispatch zap operation started event
    window.dispatchEvent(new CustomEvent('zapOperationStarted'));

    currentOperationLogs.set([]);  // Clear old logs at start - this is fine
    progressDrawerOpen = true;
    showZapModal = false;
    isSending = true;
    
    // Track which note is being zapped
    const zapNoteId = zapData.note_id;
    
    const response = await fetch(`${$baseURL}/api/send_zap`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(zapData)
    });

    const result = await response.json();
    
    if (!response.ok) {
      throw new Error(result.message || 'Failed to send zap');
    }

    if (result.success) {
      // DON'T clear logs or close drawer here - zap is still running!
      console.log('Zap API call succeeded, operation continuing in background...');
      
      // Wait for the ZAP_PUBLISHED message in the logs
      const waitForZapComplete = new Promise((resolve) => {
        const checkInterval = setInterval(() => {
          const logs = $currentOperationLogs;
          const zapPublished = logs.some(log => 
            log.message.includes('ZAP_PUBLISHED') || 
            log.message.includes('Zap live on NOSTR') ||
            log.message.includes('Zap completed successfully')
          );
          
          if (zapPublished) {
            clearInterval(checkInterval);
            resolve();
          }
        }, 100);
        
        setTimeout(() => {
          clearInterval(checkInterval);
          console.warn('Zap completion timeout - closing drawer anyway');
          resolve();
        }, 15000);
      });
      
      await waitForZapComplete;
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // NOW we can clear and close
      currentOperationLogs.set([]);
      progressDrawerOpen = false;
      
      // Update database to mark note as zapped
      if (zapNoteId) {
        console.log(`Updating zapped status for note ${zapNoteId}`);
        try {
          const updateResponse = await fetch(`${$baseURL}/api/notes/${zapNoteId}/interaction`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
              type: 'zapped',
              amount: zapData.amount_sats
            })
          });
          
          if (updateResponse.ok) {
            window.dispatchEvent(new CustomEvent('noteInteractionUpdated', {
              detail: { 
                noteId: zapNoteId, 
                interactionType: 'zapped',
                zapAmount: zapData.amount_sats
              }
            }));
            
            console.log('Note marked as zapped in database and UI updated');
          } else {
            console.error('Failed to update zap status in database');
          }
        } catch (dbError) {
          console.error('Error updating zap status in database:', dbError);
        }
      }
      
      await new Promise(resolve => setTimeout(resolve, 300));
      toastMessage = '⚡ Zap sent successfully!';
      toastType = 'success';
    } else {
      throw new Error(result.message || 'Failed to send zap');
    }

  } catch (err) {
    console.error("Error sending zap:", err);
    currentOperationLogs.set([]);
    progressDrawerOpen = false;
    toastMessage = `Error: ${err.message}`;
    toastType = 'error';

  } finally {
    window.dispatchEvent(new CustomEvent('zapOperationEnded'));
    
    isSending = false;
    showToast = true;
    // DON'T clear logs here - already cleared in success block
    setTimeout(() => {
      showToast = false;
    }, 3000);
  }
}

</script>

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
  on:settingsSaved={handleSettingsSaved}
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

<svelte:head>
  <title>HAMSTR - NOSTR over HAM</title> 
</svelte:head>

<main class="w-full min-h-screen">
  <TopNav 
  on:searchRequest={(event) => {
      const { searchType, searchText } = event.detail;
      if (window.bottomNavComponent?.handleRequestNotes) {
          window.bottomNavComponent.handleRequestNotes(searchType, searchText);
      }
  }}
  />
  <slot />
</main>

<ProgressDrawer
  bind:hidden={progressDrawerHidden}
  {currentOperationLogs}
  {clearOperationLogs}
  {isSending}
  on:drawerClosed={() => {
    progressDrawerOpen = false;
  }}
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