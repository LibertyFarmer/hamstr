<script>
    import { onMount } from 'svelte';
    import { Card, Spinner } from 'flowbite-svelte';
    import NoteCard from './NoteCard.svelte';
    import { baseURL } from '$lib/store';
    
    let notes = [];
    let isLoading = true;
    let error = null;
    let pageNumber = 1;
    let loadingMore = false;
    let hasMore = true;
    const NOTES_PER_PAGE = 10;
    
    $: apiBaseUrl = $baseURL;
    
    async function fetchNotes(page = 1, append = false) {
      if (page === 1) {
        isLoading = true;
      } else {
        loadingMore = true;
      }
      error = null;
  
      try {
        const response = await fetch(`${apiBaseUrl}/?page=${page}&limit=${NOTES_PER_PAGE}`);
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
      if (document.documentElement.clientHeight + window.scrollY >= document.documentElement.scrollHeight - 100) {
        if (!loadingMore && hasMore && !isLoading) {
          pageNumber++;
          fetchNotes(pageNumber, true);
        }
      }
    }
  
    onMount(() => {
      fetchNotes();
      window.addEventListener('scroll', handleScroll);
      
      return () => {
        window.removeEventListener('scroll', handleScroll);
      };
    });
  </script>
  
  <div class="w-full bg-gray-50 dark:bg-gray-900">
    <div class="container mx-auto px-4">
      <h2 class="text-2xl font-bold mb-6 text-gray-900 dark:text-white">Recent Notes</h2>
      
      {#if isLoading && !loadingMore}
        <div class="flex justify-center items-center p-8">
          <Spinner size="8" />
        </div>
      {:else if error}
        <Card color="red">
          <p class="text-center">{error}</p>
        </Card>
      {:else}
        <div class="space-y-4">
          {#each notes as note (note.id)}
            <NoteCard {note} />
          {/each}
          
          {#if loadingMore}
            <div class="flex justify-center p-4">
              <Spinner size="6" />
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </div>