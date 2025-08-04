<script>
  import { formatTimeAgo, timeUpdater } from '$lib/utils/timeUtils';
  import { NoteType, ZapType } from '$lib/utils/enums'; 
  
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

  function handleProfileZap() {
    // Check if note has Lightning address
    if (!note.lud16) {
      // Show toast for no Lightning address
      window.dispatchEvent(new CustomEvent('showToast', {
        detail: {
          message: 'Cannot Zap, no Lightning address',
          type: 'error'
        }
      }));
      return;
    }

    console.log('Setting up profile zap for user:', note);
    const zapContext = {
      // Profile zap context - NO note ID
      authorPubkey: note.pubkey,
      authorName: note.display_name || shortenNpub(note.pubkey),
      lud16: note.lud16
    };
    console.log('Profile zap context:', zapContext);
    
    window.dispatchEvent(new CustomEvent('openZapModal', { 
      detail: { 
        context: zapContext,
        zapType: ZapType.PROFILE_ZAP // Profile zapping
      }
    }));
  }

  function handleNoteZap() {
    // Check if note has Lightning address
    if (!note.lud16) {
      // Show toast for no Lightning address
      window.dispatchEvent(new CustomEvent('showToast', {
        detail: {
          message: 'Cannot Zap, no Lightning address',
          type: 'error'
        }
      }));
      return;
    }

    console.log('Setting up note zap for note:', note);
    const zapContext = {
      // Note-specific context for kind 9734 zap note - INCLUDES note ID
      noteId: note.id,
      authorPubkey: note.pubkey,
      content: note.content,
      authorName: note.display_name || shortenNpub(note.pubkey),
      lud16: note.lud16
    };
    console.log('Note zap context:', zapContext);
    
    window.dispatchEvent(new CustomEvent('openZapModal', { 
      detail: { 
        context: zapContext,
        zapType: ZapType.NOTE_ZAP // Note zapping
      }
    }));
  }
</script>

<!-- Note Card Container -->
<div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mb-4 shadow-sm">
  <!-- Header -->
  <div class="flex items-center justify-between mb-2">
    <!-- Author Info -->
    <div class="flex items-center space-x-3">
      <!-- Profile Picture Placeholder -->
      <div class="w-10 h-10 bg-gray-300 dark:bg-gray-600 rounded-full flex items-center justify-center">
        <svg class="w-6 h-6 text-gray-600 dark:text-gray-400" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
        </svg>
      </div>
      
      <!-- Name and Handle -->
      <div>
        <p class="font-semibold text-gray-900 dark:text-white">
          {note.display_name || shortenNpub(note.pubkey)}
        </p>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {shortenNpub(note.pubkey)}
        </p>
      </div>
    </div>

    <!-- Lightning Badge + Timestamp -->
    <div class="flex items-center space-x-2">
      {#if hasLightning}
        <div class="flex items-center text-yellow-500 dark:text-yellow-400" title="Lightning Address: {note.lud16}">
          <button 
            on:click={handleProfileZap}
            class="flex items-center p-1 hover:text-yellow-600 dark:hover:text-yellow-300 transition-colors cursor-pointer"
            title="Zap User {note.display_name || shortenNpub(note.pubkey)}"
          >
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7 2v11h3v9l7-12h-4l4-8z"/>
            </svg>
          </button>
        </div>
      {/if}
      
      <span class="flex items-center text-sm text-gray-500 dark:text-gray-400">
        <svg class="w-4 h-4 mr-1" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12,6 12,12 16,14"/>
        </svg>
        {timeAgo}
      </span>
    </div>
  </div>

  <!-- Note Content -->
  <div class="mb-4">
    <p class="text-gray-900 dark:text-white text-base leading-relaxed whitespace-pre-wrap break-words">
      {note.content}
    </p>
  </div>

  <!-- Action Buttons -->
  <div class="flex items-center justify-between pt-3 border-t border-gray-200 dark:border-gray-700">
    <!-- Reply Button -->
    <button 
      on:click={handleReply}
      class="flex items-center p-2 space-x-1 sm:space-x-2 hover:text-blue-500 dark:hover:text-blue-400 transition-colors group"
      title="Reply"
    >
      <svg class="w-6 h-6 sm:w-6 sm:h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path 
          d="M3 20l1.3-3.9A9 9 0 1 1 8.1 21L3 20z" 
          stroke-width="2"
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
          d="M17 1l4 4-4 4" 
          stroke-width="2"
        />
        <path 
          d="M3 11V9a4 4 0 0 1 4-4h14" 
          stroke-width="2"
        />
        <path 
          d="M7 23l-4-4 4-4" 
          stroke-width="2"
        />
        <path 
          d="M21 13v2a4 4 0 0 1-4 4H3" 
          stroke-width="2"
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

    <!-- Zap Button (Note Zap) -->
    {#if hasLightning}
      <button 
        on:click={handleNoteZap}
        class="flex items-center p-2 space-x-1 sm:space-x-2 hover:text-yellow-500 dark:hover:text-yellow-400 transition-colors group"
        title="Zap Note"
      >
        <svg class="w-6 h-6 sm:w-6 sm:h-6" viewBox="0 0 24 24" fill="currentColor">
          <path d="M7 2v11h3v9l7-12h-4l4-8z"/>
        </svg>
        <span class="hidden sm:inline text-sm sm:text-base font-bold">⚡ Zap</span>
      </button>
    {/if}

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