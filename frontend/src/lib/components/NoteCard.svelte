<script>
  import { onMount } from 'svelte';
  import { formatTimeAgo } from '$lib/utils/timeUtils';
  import { NoteType, ZapType } from '$lib/utils/enums';
  import { baseURL } from '$lib/stores/baseUrlStore';

import { untrack } from 'svelte';

let { note } = $props();

// untrack() reads the initial prop value without creating a reactive dependency.
// Real-time updates arrive via the noteInteractionUpdated window event.
let replied = $state(untrack(() => note.replied || false));
let boosted = $state(untrack(() => note.boosted || false));
let quoted = $state(untrack(() => note.quoted || false));
let zapped = $state(untrack(() => note.zapped || false));
let zapAmount = $state(untrack(() => note.zap_amount || 0));
let replyCount = $state(untrack(() => note.reply_count || 0));

  let apiBaseUrl = $derived($baseURL);
  let timeAgo = $derived(formatTimeAgo(note.created_at));
  let hasLightning = $derived(!!note.lud16);

  function shortenNpub(npub) {
    if (!npub) return '';
    return `${npub.slice(0, 6)}...${npub.slice(-6)}`;
  }

  function handleThreadView() {
    console.log('Thread view clicked for note:', note.id);
  }

  function handleReply() {
    window.dispatchEvent(new CustomEvent('openReplyModal', {
      detail: {
        type: NoteType.REPLY,
        context: {
          noteId: note.id,
          authorPubkey: note.pubkey,
          content: note.content,
          authorName: note.display_name || shortenNpub(note.pubkey)
        },
        mode: 'reply'
      }
    }));
  }

  function handleRepost() {
    window.dispatchEvent(new CustomEvent('openReplyModal', {
      detail: {
        type: NoteType.REPOST,
        context: {
          noteId: note.id,
          authorPubkey: note.pubkey,
          content: note.content,
          authorName: note.display_name || shortenNpub(note.pubkey)
        },
        mode: 'boost'
      }
    }));
  }

  function handleQuote() {
    window.dispatchEvent(new CustomEvent('openReplyModal', {
      detail: {
        type: NoteType.QUOTE,
        context: {
          noteId: note.id,
          authorPubkey: note.pubkey,
          content: note.content,
          authorName: note.display_name || shortenNpub(note.pubkey)
        },
        mode: 'quote'
      }
    }));
  }

  function handleProfileZap() {
    if (!note.lud16) {
      window.dispatchEvent(new CustomEvent('showToast', {
        detail: { message: 'Cannot Zap, no Lightning address', type: 'error' }
      }));
      return;
    }
    window.dispatchEvent(new CustomEvent('openZapModal', {
      detail: {
        context: {
          authorPubkey: note.pubkey,
          authorName: note.display_name || shortenNpub(note.pubkey),
          lud16: note.lud16
        },
        zapType: ZapType.PROFILE_ZAP
      }
    }));
  }

  function handleNoteZap() {
    if (!note.lud16) {
      window.dispatchEvent(new CustomEvent('showToast', {
        detail: { message: 'Cannot Zap, no Lightning address', type: 'error' }
      }));
      return;
    }
    window.dispatchEvent(new CustomEvent('openZapModal', {
      detail: {
        context: {
          noteId: note.id,
          authorPubkey: note.pubkey,
          content: note.content,
          authorName: note.display_name || shortenNpub(note.pubkey),
          lud16: note.lud16
        },
        zapType: ZapType.NOTE_ZAP
      }
    }));
  }

  onMount(() => {
    const handleInteractionUpdate = (event) => {
      const { noteId, interactionType, zapAmount: amount } = event.detail;
      if (note.id !== noteId) return;

      if (interactionType === 'replied') { replied = true; replyCount++; }
      else if (interactionType === 'boosted') boosted = true;
      else if (interactionType === 'quoted') quoted = true;
      else if (interactionType === 'zapped') {
        zapped = true;
        if (amount) zapAmount += amount;
      }

      console.log(`Note ${noteId} marked as ${interactionType}`);
    };

    window.addEventListener('noteInteractionUpdated', handleInteractionUpdate);
    return () => window.removeEventListener('noteInteractionUpdated', handleInteractionUpdate);
  });
</script>

<div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mb-4 shadow-sm">

  <!-- Header -->
  <div class="flex items-center justify-between mb-2">
    <div class="flex items-center space-x-3">
      <div class="w-10 h-10 bg-gray-300 dark:bg-gray-600 rounded-full flex items-center justify-center">
        <svg class="w-6 h-6 text-gray-600 dark:text-gray-400" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
        </svg>
      </div>
      <div>
        <p class="font-semibold text-gray-900 dark:text-white">
          {note.display_name || shortenNpub(note.pubkey)}
        </p>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {shortenNpub(note.pubkey)}
        </p>
      </div>
    </div>

    <div class="flex items-center space-x-2">
      {#if hasLightning}
        <button
          onclick={handleProfileZap}
          class="flex items-center p-1 text-yellow-500 dark:text-yellow-400 hover:text-yellow-600 dark:hover:text-yellow-300 transition-colors"
          title="Zap {note.display_name || shortenNpub(note.pubkey)}"
        >
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M7 2v11h3v9l7-12h-4l4-8z"/>
          </svg>
        </button>
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

  <!-- Content -->
  <div class="mb-4">
    <p class="text-gray-900 dark:text-white text-base leading-relaxed whitespace-pre-wrap break-words">
      {note.content}
    </p>
  </div>

  <!-- Actions -->
  <div class="flex items-center justify-between pt-3 border-t border-gray-200 dark:border-gray-700">

    <!-- Reply -->
    <button onclick={handleReply}
      class="flex items-center p-2 space-x-1 sm:space-x-2 transition-colors group relative"
      class:text-blue-500={replied}
      class:hover:text-blue-500={!replied}
      title="Reply">
      <div class="relative">
        <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M3 20l1.3-3.9A9 9 0 1 1 8.1 21L3 20z" stroke-width="2"/>
        </svg>
        {#if replied}
          <div class="absolute -top-1 -right-1 w-3 h-3 bg-blue-500 rounded-full border-2 border-white dark:border-gray-800"></div>
        {/if}
      </div>
      <span class="hidden sm:inline text-sm font-bold">Reply</span>
    </button>

    <!-- Boost -->
    <button onclick={handleRepost}
      class="flex items-center p-2 space-x-1 sm:space-x-2 transition-colors group relative"
      class:text-green-500={boosted}
      class:hover:text-green-500={!boosted}
      title="Boost">
      <div class="relative">
        <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M17 1l4 4-4 4" stroke-width="2"/>
          <path d="M3 11V9a4 4 0 0 1 4-4h14" stroke-width="2"/>
          <path d="M7 23l-4-4 4-4" stroke-width="2"/>
          <path d="M21 13v2a4 4 0 0 1-4 4H3" stroke-width="2"/>
        </svg>
        {#if boosted}
          <div class="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full border-2 border-white dark:border-gray-800"></div>
        {/if}
      </div>
      <span class="hidden sm:inline text-sm font-bold">Boost</span>
    </button>

    <!-- Quote -->
    <button onclick={handleQuote}
      class="flex items-center p-2 space-x-1 sm:space-x-2 transition-colors group relative"
      class:text-purple-500={quoted}
      class:hover:text-purple-500={!quoted}
      title="Quote">
      <div class="relative">
        <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M17.5 10H6.5C5.11929 10 4 11.1193 4 12.5V17.5C4 18.8807 5.11929 20 6.5 20H17.5C18.8807 20 20 18.8807 20 17.5V12.5C20 11.1193 18.8807 10 17.5 10Z" stroke-width="2"/>
          <path d="M14.5 4H7.5C6.11929 4 5 5.11929 5 6.5V11.5" stroke-width="2" stroke-linecap="round"/>
        </svg>
        {#if quoted}
          <div class="absolute -top-1 -right-1 w-3 h-3 bg-purple-500 rounded-full border-2 border-white dark:border-gray-800"></div>
        {/if}
      </div>
      <span class="hidden sm:inline text-sm font-bold">Quote</span>
    </button>

    <!-- Zap -->
    {#if hasLightning}
      <button onclick={handleNoteZap}
        class="flex items-center p-2 space-x-1 sm:space-x-2 transition-colors group relative"
        class:text-yellow-500={zapped}
        class:hover:text-yellow-500={!zapped}
        title="Zap Note">
        <div class="relative">
          <svg class="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
            <path d="M7 2v11h3v9l7-12h-4l4-8z"/>
          </svg>
          {#if zapped}
            <div class="absolute -top-1 -right-1 w-3 h-3 bg-yellow-500 rounded-full border-2 border-white dark:border-gray-800"></div>
          {/if}
        </div>
        <span class="hidden sm:inline text-sm font-bold">
          {#if zapped && zapAmount > 0}
            ⚡ {zapAmount}
          {:else if zapped}
            ⚡ Zapped
          {:else}
            ⚡ Zap
          {/if}
        </span>
      </button>
    {/if}

    <!-- Replies -->
    <button onclick={handleThreadView}
      class="flex items-center p-2 space-x-1 sm:space-x-2 hover:text-blue-500 dark:hover:text-blue-400 transition-colors group"
      title="View Replies">
      <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" stroke-width="2"/>
      </svg>
      <span class="hidden sm:inline text-sm font-bold">{replyCount} Replies</span>
    </button>

  </div>
</div>