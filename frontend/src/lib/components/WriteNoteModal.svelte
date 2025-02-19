<script>
  import { Modal, Button, Textarea } from 'flowbite-svelte';
  import { NoteType } from '$lib/utils/enums';
  import { onMount } from 'svelte';
  import { baseURL } from '$lib/stores/baseUrlStore';
 
  export let show = false;
  export let onClose;
  export let onSubmit;
 
  let noteContent = '';
  let isSending = false;
  let replyContext = null;
  let replyType = null;
  let mode = 'write'; // can be 'write', 'reply', 'boost', or 'quote'
 
  $: modalTitle = mode === 'boost' ? 'Boost this note?' : 
                  mode === 'reply' ? 'Reply to Note' : 
                  mode === 'quote' ? 'Quote Note' : 
                  'Write a Note';

  $: showTextArea = mode !== 'boost';
 
  $: if (!show) {
    noteContent = '';
    isSending = false;
    replyContext = null;
    replyType = null;
    mode = 'write';
  }
 
  onMount(() => {
    window.addEventListener('openReplyModal', (event) => {
      console.log('Received openReplyModal event:', event.detail);
      mode = event.detail.mode || 'reply';
      replyType = event.detail.type;
      replyContext = event.detail.context;
      show = true;
    });
    return () => window.removeEventListener('openReplyModal');
  });
 
  async function handleSubmit(event) {
  event.preventDefault();
  if (isSending) return;
  
  // For boost, we don't need content
  if (mode !== 'boost' && showTextArea && !noteContent.trim()) return;

  isSending = true;
  console.log('Current replyType:', replyType);
  console.log('Current replyContext:', replyContext);
  
  const hashtags = [];
  if (showTextArea) {
    noteContent.match(/#[a-zA-Z0-9]+/g)?.forEach(tag => {
      hashtags.push(tag.substring(1));
    });
  }

  // Create final content including note reference for quotes
  let finalContent = noteContent;
  if (mode === 'quote' && replyContext) {
    // We'll let the backend handle the bech32 conversion but structure the content now
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
    console.log('Adding reply/boost/quote context to noteData');
    if (mode === 'quote') {
        noteData.reply_to = replyContext.noteId;     
        noteData.reply_pubkey = replyContext.authorPubkey;
        // Include both pubkeys - author's and the one being quoted
        noteData.tags = [
            ['p', replyContext.authorPubkey],
            ['e', replyContext.noteId]
        ];
    }
    else if (mode === 'boost') {
        noteData.repost_id = replyContext.noteId;
        noteData.repost_pubkey = replyContext.authorPubkey;
        noteData.content = replyContext.content;
    }
    else if (mode === 'reply') {
        noteData.reply_to = replyContext.noteId;
        noteData.reply_pubkey = replyContext.authorPubkey;
    }
  }

  console.log('Submitting noteData:', noteData);
  try {
    await onSubmit(noteData);
    show = false;
  } catch (error) {
    console.error('Error sending note:', error);
  } finally {
    isSending = false;
  }
}
 
  function handleClose() {
    if (!isSending) {
      show = false;
      noteContent = '';
      replyContext = null;
      replyType = null;
      mode = 'write';
      onClose();
    }
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
      <Button color="alternative" type="button" on:click={handleClose} disabled={isSending}>
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