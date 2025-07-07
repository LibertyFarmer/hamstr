<script>
  import { Modal, Button, Input, Textarea } from 'flowbite-svelte';
  import { onMount } from 'svelte';
  import { baseURL } from '$lib/stores/baseUrlStore';
 
  export let show = false;
  export let onClose;
  export let onSubmit;
 
  let zapAmount = 21; // Default to 21 sats
  let zapMessage = 'HAMSTR'; // Default message
  let isSending = false;
  let zapContext = null;
 
  $: modalTitle = zapContext ? `⚡ Zap ${zapContext.authorName}` : '⚡ Send Zap';
 
  $: if (!show) {
    zapAmount = 21;
    zapMessage = 'Thanks!';
    isSending = false;
    zapContext = null;
  }
 
  onMount(() => {
    window.addEventListener('openZapModal', (event) => {
      console.log('Received openZapModal event:', event.detail);
      zapContext = event.detail.context;
      show = true;
    });
    return () => window.removeEventListener('openZapModal');
  });
 
  async function handleSubmit(event) {
    event.preventDefault();
    if (isSending) return;
    
    // Validate amount
    if (!zapAmount || zapAmount <= 0) {
      window.dispatchEvent(new CustomEvent('showToast', {
        detail: {
          message: 'Zap amount must be greater than 0',
          type: 'error'
        }
      }));
      return;
    }

    // Check if recipient has Lightning address
    if (!zapContext?.lud16) {
      window.dispatchEvent(new CustomEvent('showToast', {
        detail: {
          message: 'Cannot Zap, no Lightning address',
          type: 'error'
        }
      }));
      return;
    }

    isSending = true;
    
    const zapData = {
      recipient_lud16: zapContext.lud16,
      amount_sats: parseInt(zapAmount),
      message: zapMessage || ''
    };

    console.log('Submitting zapData:', zapData);
    
    try {
      await onSubmit(zapData);
      show = false;
    } catch (error) {
      console.error('Error sending zap:', error);
    } finally {
      isSending = false;
    }
  }
 
  function handleClose() {
    if (!isSending) {
      show = false;
      zapAmount = 21;
      zapMessage = 'Thanks!';
      zapContext = null;
      onClose();
    }
  }

  // Quick amount buttons
  function setAmount(amount) {
    zapAmount = amount;
  }
</script>
 
<Modal
  bind:open={show}
  size="md"
  dismissable={true}
  outsideclose={true}
  class="w-full"
  on:close={handleClose}
>
  <form on:submit={handleSubmit} class="space-y-4">
    <h3 class="text-xl font-medium text-gray-900 dark:text-white">
      {modalTitle}
    </h3>
    
    {#if zapContext}
      <div class="p-4 bg-gray-100 dark:bg-gray-800 rounded-lg">
        <p class="text-sm font-medium mb-2">
          Sending zap to @{zapContext.authorName}
        </p>
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Lightning Address: {zapContext.lud16}
        </p>
        {#if zapContext.content}
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-2 truncate">
            "{zapContext.content}"
          </p>
        {/if}
      </div>
    {/if}

    <!-- Zap Amount -->
    <div class="space-y-2">
      <label for="zapAmount" class="text-sm font-medium text-gray-900 dark:text-white">
        Amount (sats)
      </label>
      <Input
        id="zapAmount"
        type="number"
        min="1"
        max="999999999"
        bind:value={zapAmount}
        disabled={isSending}
        required
        class="w-full"
      />
      
      <!-- Quick amount buttons -->
      <div class="flex flex-wrap gap-2 mt-2">
        <Button 
          size="xs" 
          color="alternative" 
          type="button"
          on:click={() => setAmount(21)}
          disabled={isSending}
        >
          21
        </Button>
        <Button 
          size="xs" 
          color="alternative" 
          type="button"
          on:click={() => setAmount(100)}
          disabled={isSending}
        >
          100
        </Button>
        <Button 
          size="xs" 
          color="alternative" 
          type="button"
          on:click={() => setAmount(500)}
          disabled={isSending}
        >
          500
        </Button>
        <Button 
          size="xs" 
          color="alternative" 
          type="button"
          on:click={() => setAmount(1000)}
          disabled={isSending}
        >
          1k
        </Button>
        <Button 
          size="xs" 
          color="alternative" 
          type="button"
          on:click={() => setAmount(5000)}
          disabled={isSending}
        >
          5k
        </Button>
      </div>
    </div>

    <!-- Zap Message -->
    <div class="space-y-2">
      <label for="zapMessage" class="text-sm font-medium text-gray-900 dark:text-white">
        Message (optional)
      </label>
      <Input
        id="zapMessage"
        type="text"
        bind:value={zapMessage}
        disabled={isSending}
        placeholder="Thanks! 🔥 Great post! ⚡"
        maxlength="50"
        class="w-full"
      />
      <p class="text-xs text-gray-500 dark:text-gray-400">
        Keep it short for ham radio bandwidth
      </p>
    </div>
 
    <div class="flex justify-end space-x-2">
      <Button color="alternative" type="button" on:click={handleClose} disabled={isSending}>
        Cancel
      </Button>
      <Button 
        type="submit" 
        color="yellow"
        disabled={isSending || !zapAmount || zapAmount <= 0}
      >
        {#if isSending}
          Sending...
        {:else}
          ⚡ Send {zapAmount} sats
        {/if}
      </Button>
    </div>
  </form>
</Modal>