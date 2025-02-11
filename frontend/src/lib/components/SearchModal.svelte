<script>
    import { Modal, Label, Select, Button, Input } from 'flowbite-svelte';
    import { NoteRequestType } from '$lib/utils/enums';
    
    export let show = false;
    export let onClose = () => {};
    export let onSubmit = () => {};

    let searchText = '';
    let searchType = NoteRequestType.SEARCH_TEXT;

    const searchTypes = [
        { value: NoteRequestType.SEARCH_TEXT, label: 'Text Search' },
        { value: NoteRequestType.SEARCH_HASHTAG, label: 'Hashtag/Topic Search' },
        { value: NoteRequestType.SEARCH_USER, label: 'Name | NPUB Search' }
    ];

    function handleSubmit() {
        if (searchType === NoteRequestType.SEARCH_USER) {
            const isNpubSearch = searchText.toLowerCase().startsWith('npub');
            onSubmit({
                searchType,
                searchText,
                isNpubSearch
            });
        } else {
            onSubmit({ searchType, searchText });
        }
        searchText = '';
        onClose();
    }
</script>

<Modal 
    bind:open={show} 
    size="sm" 
    autoclose={false}
    on:close={onClose}
>
    <div class="p-4">
        <h3 class="mb-4 text-xl font-medium text-gray-900 dark:text-white">
            Search NOSTR
        </h3>
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
                        <span class="ml-1 text-sm text-gray-500">
                            (Enter name or npub1...)
                        </span>
                    {/if}
                </Label>
                <Input
                    id="search-text"
                    type="text"
                    placeholder={searchType === NoteRequestType.SEARCH_USER ? 
                        "Enter name or npub1..." : 
                        "Enter search text..."}
                    bind:value={searchText}
                />
            </div>
        </div>
        <div class="flex justify-end space-x-2 mt-6">
            <Button color="alternative" on:click={onClose}>Cancel</Button>
            <Button color="primary" on:click={handleSubmit}>Search</Button>
        </div>
    </div>
</Modal>