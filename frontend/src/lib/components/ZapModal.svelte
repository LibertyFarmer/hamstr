<script>
  import { Modal, Button, Input, Textarea } from 'flowbite-svelte';
  import { onMount } from 'svelte';
  import { ZapType } from '$lib/utils/enums';

  let { show = false, onClose, onSubmit } = $props();

  let isOpen = $state(false);
  let zapAmount = $state(21);
  let zapMessage = $state('HAMSTR');
  let isSending = $state(false);
  let zapContext = $state(null);
  let zapType = $state(ZapType.NOTE_ZAP);

  let modalTitle = $derived(
    zapContext ?
      (zapType === ZapType.NOTE_ZAP ?
        `⚡ Zap Note by ${zapContext.authorName}` :
        `⚡ Zap ${zapContext.authorName}`) :
      '⚡ Send Zap'
  );

  $effect(() => {
    isOpen = show;
  });

  $effect(() => {
    if (!show) {
      zapAmount = 21;
      zapMessage = 'HAMSTR';
      isSending = false;
      zapContext = null;
      zapType = ZapType.NOTE_ZAP;
    }
  });

  onMount(() => {
    const handler = (event) => {
      console.log('Received openZapModal event:', event.detail);
      zapContext = event.detail.context;
      zapType = event.detail.zapType || ZapType.NOTE_ZAP;
      isOpen = true;
    };
    window.addEventListener('openZapModal', handler);
    return () => window.removeEventListener('openZapModal', handler);
  });

  async function handleSubmit(event) {
    event.preventDefault();
    if (isSending) return;

    if (!zapAmount || zapAmount <= 0) {
      window.dispatchEvent(new CustomEvent('showToast', {
        detail: { message: 'Zap amount must be greater than 0', type: 'error' }
      }));
      return;
    }

    if (!zapContext?.lud16) {
      window.dispatchEvent(new CustomEvent('showToast', {
        detail: { message: 'Cannot Zap, no Lightning address', type: 'error' }
      }));
      return;
    }

    isSending = true;

    const zapData = {
      recipient_lud16: zapContext.lud16,
      amount_sats: parseInt(zapAmount),
      message: zapMessage || '',
      zap_type: zapType,
      note_id: zapType === ZapType.NOTE_ZAP ? zapContext.noteId : null,
      recipient_pubkey: zapContext.authorPubkey,
      note_content_preview: zapType === ZapType.NOTE_ZAP ? zapContext.content?.substring(0, 50) + '...' : null
    };

    try {
      await onSubmit(zapData);
      onClose();
    } catch (error) {
      console.error('Error sending zap:', error);
    } finally {
      isSending = false;
    }
  }

  function handleClose() {
    if (!isSending) {
      zapAmount = 21;
      zapMessage = 'HAMSTR';
      zapContext = null;
      zapType = ZapType.NOTE_ZAP;
      onClose();
    }
  }

  function setAmount(amount) { zapAmount = amount; }
</script>

<Modal
  bind:open={isOpen}
  size="md"
  dismissable={true}
  outsideclose={true}
  class="w-full"
  onclose={handleClose}
>
  <form onsubmit={handleSubmit} class="space-y-4">
    <h3 class="text-xl font-medium text-gray-900 dark:text-white">{modalTitle}</h3>

    {#if zapContext}
      <div class="p-4 bg-gray-100 dark:bg-gray-800 rounded-lg">
        <p class="text-sm font-medium mb-2">
          {#if zapType === ZapType.NOTE_ZAP}
            Zapping note by @{zapContext.authorName}
          {:else}
            Zapping user @{zapContext.authorName}
          {/if}
        </p>
        <p class="text-sm text-gray-600 dark:text-gray-400">Lightning Address: {zapContext.lud16}</p>
        {#if zapContext.content && zapType === ZapType.NOTE_ZAP}
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-2 truncate">
            Note: "{zapContext.content}"
          </p>
        {/if}
      </div>
    {/if}

    <div>
      <label for="zap-amount" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        Amount (sats)
      </label>
      <div class="flex gap-2 mb-2">
        {#each [21, 100, 500, 1000] as amount}
          <button
            type="button"
            onclick={() => setAmount(amount)}
            class="px-3 py-1 text-sm rounded border transition-colors"
            class:bg-blue-500={zapAmount === amount}
            class:text-white={zapAmount === amount}
            class:border-blue-500={zapAmount === amount}
            class:border-gray-300={zapAmount !== amount}
            class:hover:bg-gray-100={zapAmount !== amount}
          >
            {amount}
          </button>
        {/each}
      </div>
      <Input id="zap-amount" type="number" bind:value={zapAmount} min="1" placeholder="Custom amount" />
    </div>

    <div>
      <label for="zap-message" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        Message (optional)
      </label>
      <Input id="zap-message" type="text" bind:value={zapMessage} placeholder="Add a message..." />
    </div>

    <div class="flex justify-end space-x-2">
      <Button color="alternative" type="button" onclick={handleClose} disabled={isSending}>
        Cancel
      </Button>
      <Button type="submit" color="yellow" disabled={isSending || !zapAmount}>
        {isSending ? 'Sending...' : `⚡ Zap ${zapAmount} sats`}
      </Button>
    </div>
  </form>
</Modal>