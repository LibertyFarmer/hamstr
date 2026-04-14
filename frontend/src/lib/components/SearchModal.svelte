<script>
  import { Modal, Label, Select, Button, Input } from 'flowbite-svelte';
  import { NoteRequestType } from '$lib/utils/enums';

  let { show = false, onClose = () => {}, onSubmit = () => {} } = $props();

  let isOpen = $state(false);
  let searchText = $state('');
  let searchType = $state(NoteRequestType.SEARCH_TEXT);

  $effect(() => { isOpen = show; });

  const searchTypes = [
    { value: NoteRequestType.SEARCH_TEXT, label: 'Text Search' },
    { value: NoteRequestType.SEARCH_HASHTAG, label: 'Hashtag/Topic Search' },
    { value: NoteRequestType.SEARCH_USER, label: 'Name | NPUB Search' }
  ];

  function handleSubmit() {
    if (searchType === NoteRequestType.SEARCH_USER) {
      onSubmit({ searchType, searchText, isNpubSearch: searchText.toLowerCase().startsWith('npub') });
    } else {
      onSubmit({ searchType, searchText });
    }
    searchText = '';
    onClose();
  }
</script>

<Modal
  bind:open={isOpen}
  size="sm"
  autoclose={false}
  onclose={onClose}
>
  <div class="p-4">
    <h3 class="mb-4 text-xl font-medium text-gray-900 dark:text-white">Search NOSTR</h3>
    <div class="space-y-4">
      <div>
        <Label for="search-type">Search Type</Label>
        <Select id="search-type" class="mt-1" bind:value={searchType}>
          {#each searchTypes as type}
            <option value={type.value}>{type.label}</option>
          {/each}
        </Select>
      </div>
      <div>
        <Label for="search-text">
          Search Term
          {#if searchType === NoteRequestType.SEARCH_USER}
            <span class="ml-1 text-sm text-gray-500">(Enter name or npub1...)</span>
          {/if}
        </Label>
        <Input
          id="search-text"
          type="text"
          placeholder={searchType === NoteRequestType.SEARCH_USER ? 'Enter name or npub1...' : 'Enter search text...'}
          bind:value={searchText}
        />
      </div>
    </div>
    <div class="flex justify-end space-x-2 mt-6">
      <Button color="alternative" onclick={onClose}>Cancel</Button>
      <Button color="primary" onclick={handleSubmit}>Search</Button>
    </div>
  </div>
</Modal>