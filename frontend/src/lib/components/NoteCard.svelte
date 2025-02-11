<script>
  import { formatTimeAgo, timeUpdater } from '$lib/utils/timeUtils';
  import { NoteType } from '$lib/utils/enums'; 
  
  export let note;
  
  function shortenNpub(npub) {
    if (!npub) return '';
    return `${npub.slice(0, 6)}...${npub.slice(-6)}`;
  }

  // Reactive time formatting that updates automatically
  $: timeAgo = formatTimeAgo(note.created_at);
  
  function handleThreadView() {
    // TODO: Implement thread view functionality
    console.log('Thread view clicked for note:', note.id);
  }

  // Show Lightning address if available
  $: hasLightning = note.lud16 ? true : false;

  function handleReply() {
    console.log('Setting up reply to note:', note);
    const replyContext = {
      noteId: note.id,
      authorPubkey: note.pubkey,
      content: note.content,
      authorName: note.display_name || shortenNpub(note.pubkey)
    };
    console.log('Reply context:', replyContext);
    
    window.dispatchEvent(new CustomEvent('openReplyModal', { 
      detail: { 
        type: NoteType.REPLY,
        context: replyContext,
        mode: 'reply'
      }
    }));
  }

  function handleRepost() {
    console.log('Setting up repost for note:', note);
    const repostContext = {
      noteId: note.id,
      authorPubkey: note.pubkey,
      content: note.content,
      authorName: note.display_name || shortenNpub(note.pubkey)
    };
    console.log('Repost context:', repostContext);
    
    window.dispatchEvent(new CustomEvent('openReplyModal', { 
      detail: { 
        type: NoteType.REPOST,
        context: repostContext,
        mode: 'boost'
      }
    }));
  }

  function handleQuote() {
    console.log('Setting up quote for note:', note);
    const quoteContext = {
      noteId: note.id,
      authorPubkey: note.pubkey,
      content: note.content,
      authorName: note.display_name || shortenNpub(note.pubkey)
    };
    console.log('Quote context:', quoteContext);
    
    window.dispatchEvent(new CustomEvent('openReplyModal', { 
      detail: { 
        type: NoteType.QUOTE,
        context: quoteContext,
        mode: 'quote'
      }
    }));
  }
</script>

<div class="flex space-x-4 bg-white dark:bg-gray-800 p-4 rounded-lg shadow hover:shadow-md transition-shadow">
  <!-- Avatar Section -->
  <div class="flex-shrink-0">
    <div class="w-14 h-14 rounded-full border-2 border-gray-300 dark:border-gray-600 flex items-center justify-center p-2">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" class="w-full h-full">
        <circle cx="12" cy="12" r="10" stroke-width="2"/>
        <circle cx="12" cy="10" r="3" stroke-width="2"/>
        <path d="M5.5 19.5C7 17 9.5 15.5 12 15.5s5 1.5 6.5 4" stroke-width="2"/>
      </svg>
    </div>
  </div>

  <!-- Content Section -->
  <div class="flex-grow min-w-0">
    <!-- Header Row -->
    <div class="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 mb-2">
      <div class="flex items-center gap-2">
        <span class="font-bold text-lg truncate dark:text-white">
          {note.display_name || shortenNpub(note.pubkey)}
        </span>
        {#if hasLightning}
          <span class="text-yellow-500" title={note.lud16}>⚡</span>
        {/if}
      </div>
      <span class="text-gray-500 dark:text-gray-400 text-sm flex items-center whitespace-nowrap">
        <svg class="w-4 h-4 mr-1" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <circle cx="12" cy="12" r="10" stroke-width="2"/>
          <path d="M12 6v6l4 2" stroke-width="2"/>
        </svg>
        {timeAgo}
      </span>
    </div>

    <!-- Note Content -->
    <div class="text-gray-800 dark:text-gray-200 mb-4 text-base break-words">
      {note.content}
    </div>

    <!-- Action Buttons -->
    <div class="flex items-center justify-around sm:justify-start px-2 sm:px-0 space-x-3 sm:space-x-6 text-gray-500 dark:text-gray-400">
      <!-- Reply Button -->
      <button 
        on:click={handleReply}
        class="flex items-center p-2 space-x-1 sm:space-x-2 hover:text-blue-500 dark:hover:text-blue-400 transition-colors group"
        title="Reply"
      >
        <svg class="w-6 h-6 sm:w-6 sm:h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path 
            d="M9 17L4 12M4 12L9 7M4 12H16C18.7614 12 21 9.76142 21 7" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
        </svg>
        <span class="hidden sm:inline text-sm sm:text-base font-bold">Reply</span>
      </button>

      <!-- Repost Button -->
      <button 
        on:click={handleRepost}
        class="flex items-center p-2 space-x-1 sm:space-x-2 hover:text-green-500 dark:hover:text-green-400 transition-colors group"
        title="Boost"
      >
        <svg class="w-6 h-6 sm:w-6 sm:h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path 
            d="M4 4v7a4 4 0 0 0 4 4h12" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
          <path 
            d="M20 7l-3-3 3-3" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
          <path 
            d="M20 20v-7a4 4 0 0 0-4-4H4" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
          <path 
            d="M4 17l3 3-3 3" 
            stroke-width="2" 
            stroke-linecap="round" 
            stroke-linejoin="round"
          />
        </svg>
        <span class="hidden sm:inline text-sm sm:text-base font-bold">Boost</span>
      </button>

      <!-- Quote Button -->
      <button 
        on:click={handleQuote}
        class="flex items-center p-2 space-x-1 sm:space-x-2 hover:text-purple-500 dark:hover:text-purple-400 transition-colors group"
        title="Quote"
      >
        <svg class="w-6 h-6 sm:w-6 sm:h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path 
            d="M17.5 10H6.5C5.11929 10 4 11.1193 4 12.5V17.5C4 18.8807 5.11929 20 6.5 20H17.5C18.8807 20 20 18.8807 20 17.5V12.5C20 11.1193 18.8807 10 17.5 10Z" 
            stroke-width="2"
          />
          <path 
            d="M14.5 4H7.5C6.11929 4 5 5.11929 5 6.5V11.5" 
            stroke-width="2" 
            stroke-linecap="round"
          />
        </svg>
        <span class="hidden sm:inline text-sm sm:text-base font-bold">Quote</span>
      </button>

      <!-- Thread View Button -->
      <button 
        on:click={handleThreadView}
        class="flex items-center p-2 space-x-1 sm:space-x-2 hover:text-blue-500 dark:hover:text-blue-400 transition-colors group"
        title="View Replies"
      >
        <svg class="w-6 h-6 sm:w-6 sm:h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path 
            d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" 
            stroke-width="2"
          />
        </svg>
        <span class="hidden sm:inline text-sm sm:text-base font-bold">{note.reply_count || 0} Replies</span>
      </button>
    </div>
  </div>
</div>