<script>
  import { onMount } from 'svelte';
  import { Card, Spinner } from 'flowbite-svelte';
  import { baseURL } from '$lib/stores/baseUrlStore';
  import NoteCard from '$lib/components/NoteCard.svelte';

  let notes = [];
  let isLoading = true;
  let error = null;
  let apiBaseUrl;
  let pageNumber = 1;
  let loadingMore = false;
  let hasMore = true;
  const NOTES_PER_PAGE = 10;
    
  $: apiBaseUrl = $baseURL;
  
  async function fetchRecentNotes(page = 1, append = false) {
    if (page === 1) {
      isLoading = true;
    } else {
      loadingMore = true;
    }
    error = null;

    try {
      const response = await fetch(`${apiBaseUrl}/api/notes?page=${page}&limit=${NOTES_PER_PAGE}`);
      if (!response.ok) throw new Error('Failed to fetch notes');
      const data = await response.json();
      
      if (append) {
        notes = [...notes, ...data.notes];
      } else {
        notes = data.notes;
      }
      
      hasMore = data.pagination.has_more;
    } catch (err) {
      console.error("Error fetching notes:", err);
      error = err.message;
    } finally {
      isLoading = false;
      loadingMore = false;
    }
  }

  function handleScroll(event) {
    const bottom = document.documentElement.clientHeight + window.scrollY >= document.documentElement.scrollHeight - 300;
    if (bottom && !loadingMore && hasMore && !isLoading) {
      pageNumber++;
      fetchRecentNotes(pageNumber, true);
    }
  }

  function handleNotesUpdated(event) {
    console.log("Notes updated event received");
    pageNumber = 1;
    if (event.detail && event.detail.notes) {
      notes = event.detail.notes;
      hasMore = event.detail.pagination.has_more;
    } else {
      notes = [];
      hasMore = false;
    }
    isLoading = false;
    error = null;
  }

  onMount(() => {
    fetchRecentNotes();
    window.addEventListener('notesUpdated', handleNotesUpdated);
    window.addEventListener('scroll', handleScroll);
    
    return () => {
      window.removeEventListener('notesUpdated', handleNotesUpdated);
      window.removeEventListener('scroll', handleScroll);
    };
  });
</script>

<svelte:window on:scroll={handleScroll}/>

<div class="w-full min-h-screen bg-gray-50 dark:bg-gray-900">
  <div class="container mx-auto px-4 py-8 pb-20">
    {#if isLoading && !loadingMore}
      <div class="flex justify-center items-center p-8">
        <Spinner size="8" />
      </div>
    {:else if error}
      <Card color="red">
        <p class="text-center">{error}</p>
      </Card>
    {:else}
      <div class="space-y-4 mb-16">
        <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Recent Notes</h2>
        {#if notes.length === 0}
          <Card>
            <p class="text-center text-gray-500">No notes available.</p>
          </Card>
        {:else}
          <div class="space-y-4">
            {#each notes as note (note.id)}
              <NoteCard {note} />
            {/each}
          </div>
        {/if}
        
        {#if loadingMore}
          <div class="flex justify-center p-4">
            <Spinner size="6" />
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>