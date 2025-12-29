<script>
    import { Navbar, NavBrand, DarkMode } from 'flowbite-svelte';
    import { SearchOutline } from 'flowbite-svelte-icons';
    import { createEventDispatcher } from 'svelte';
    import SearchModal from '$lib/components/SearchModal.svelte';
    import { isRequestingNotes } from '$lib/stores/requestNotesStore';
    import { baseURL } from '$lib/store';

    const dispatch = createEventDispatcher();
    let showSearchModal = false;
    let apiBaseUrl;
    
    $: apiBaseUrl = $baseURL;

async function handleSearch({ searchType, searchText }) {
    if ($isRequestingNotes) return;

    if (window.bottomNavComponent?.handleRequestNotes) {
        dispatch('clearLogs');
        showSearchModal = false;
        window.bottomNavComponent.progressDrawerOpen = true;  // ✅ Open drawer!
        window.bottomNavComponent.handleRequestNotes(searchType, searchText);
    }
}

</script>
<div class="w-full bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-600">
    <div class="w-full px-6 py-3">
        <div class="grid grid-cols-3 items-center w-full">
            <div>
                <button 
                    on:click={() => showSearchModal = true}
                    class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
                    disabled={$isRequestingNotes}
                >
                    <SearchOutline class="w-6 h-6 text-gray-500 dark:text-gray-400" />
                </button>
            </div>
            <div class="text-center">
                <span class="text-xl font-bold text-gray-800 dark:text-white">HAMSTR</span>
            </div>
            <div class="flex justify-end">
                <DarkMode class="text-gray-500 dark:text-gray-400" />
            </div>
        </div>
    </div>
</div>

<SearchModal 
    show={showSearchModal}
    onClose={() => showSearchModal = false}
    onSubmit={handleSearch}
/>