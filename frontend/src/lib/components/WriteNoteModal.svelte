<script>
  import { Modal, Button, Textarea } from 'flowbite-svelte';
  import { NoteType } from '$lib/utils/enums';
  import { onMount } from 'svelte';

  let { show = false, onClose, onSubmit } = $props();

  let isOpen = $state(false);
  let noteContent = $state('');
  let isSending = $state(false);
  let replyContext = $state(null);
  let replyType = $state(null);
  let mode = $state('write');

  let modalTitle = $derived(
    mode === 'boost' ? 'Boost this note?' :
    mode === 'reply' ? 'Reply to Note' :
    mode === 'quote' ? 'Quote Note' :
    'Write a Note'
  );
  let showTextArea = $derived(mode !== 'boost');

  $effect(() => {
    isOpen = show;
  });

  $effect(() => {
    if (!show) {
      noteContent = '';
      isSending = false;
      replyContext = null;
      replyType = null;
      mode = 'write';
    }
  });

  onMount(() => {
    const handler = (event) => {
      console.log('Received openReplyModal event:', event.detail);
      mode = event.detail.mode || 'reply';
      replyType = event.detail.type;
      replyContext = event.detail.context;
      isOpen = true;
    };
    window.addEventListener('openReplyModal', handler);
    return () => window.removeEventListener('openReplyModal', handler);
  });

  async function handleSubmit(event) {
    event.preventDefault();
    if (isSending) return;
    if (mode !== 'boost' && showTextArea && !noteContent.trim()) return;

    isSending = true;

    const hashtags = [];
    if (showTextArea) {
      noteContent.match(/#[a-zA-Z0-9]+/g)?.forEach(tag => hashtags.push(tag.substring(1)));
    }

    let finalContent = noteContent;
    if (mode === 'quote' && replyContext) {
      finalContent = `${noteContent}\n\n`;
    }

    const noteData = {
      content: finalContent,
      hashtags,
      note_type: mode === 'boost' ? NoteType.REPOST :
                 mode === 'quote' ? NoteType.QUOTE :
                 mode === 'reply' ? NoteType.REPLY :
                 NoteType.STANDARD,
      kind: mode === 'boost' ? 6 : 1
    };

    if (replyContext) {
      if (mode === 'quote') {
        noteData.reply_to = replyContext.noteId;
        noteData.reply_pubkey = replyContext.authorPubkey;
        noteData.tags = [['p', replyContext.authorPubkey], ['e', replyContext.noteId]];
      } else if (mode === 'boost') {
        noteData.repost_id = replyContext.noteId;
        noteData.repost_pubkey = replyContext.authorPubkey;
        noteData.content = replyContext.content;
      } else if (mode === 'reply') {
        noteData.reply_to = replyContext.noteId;
        noteData.reply_pubkey = replyContext.authorPubkey;
      }
    }

    try {
      await onSubmit(noteData);
      onClose();
    } catch (error) {
      console.error('Error sending note:', error);
    } finally {
      isSending = false;
    }
  }

function handleClose() {
  if (!isSending) {
    isOpen = false;
    noteContent = '';
    replyContext = null;
    replyType = null;
    mode = 'write';
    onClose();
  }
}
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

    {#if replyContext}
      <div class="p-4 bg-gray-100 dark:bg-gray-800 rounded-lg">
        <p class="text-sm font-medium mb-2">
          {#if mode === 'boost'}
            Note by @{replyContext.authorName}
          {:else}
            Replying to @{replyContext.authorName}
          {/if}
        </p>
        <p class="text-sm text-gray-600 dark:text-gray-400">{replyContext.content}</p>
      </div>
    {/if}

    {#if showTextArea}
      <Textarea
        required
        disabled={isSending}
        placeholder="Write your note here..."
        rows="4"
        bind:value={noteContent}
        class="w-full resize-none"
      />
      {#if noteContent.match(/#[a-zA-Z0-9]+/g)}
        <div class="text-sm text-gray-600 dark:text-gray-400">
          <span class="font-medium">Hashtags: </span>
          {#each noteContent.match(/#[a-zA-Z0-9]+/g) || [] as tag}
            <span class="inline-block bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded px-2 py-0.5 mr-2 mb-1">
              {tag}
            </span>
          {/each}
        </div>
      {/if}
    {/if}

    <div class="flex justify-end space-x-2">
      <Button color="alternative" type="button" onclick={handleClose} disabled={isSending}>
        Cancel
      </Button>
      <Button
        type="submit"
        color={mode === 'boost' ? 'green' : 'blue'}
        disabled={isSending || (showTextArea && !noteContent.trim())}
      >
        {#if isSending}
          Sending...
        {:else if mode === 'boost'}
          Boost
        {:else if mode === 'quote'}
          Quote
        {:else if mode === 'reply'}
          Reply
        {:else}
          Send Note
        {/if}
      </Button>
    </div>
  </form>
</Modal>