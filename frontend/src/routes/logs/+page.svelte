<script>
    import { onMount } from 'svelte';
    import { afterNavigate } from '$app/navigation';
    import { browser } from '$app/environment';
    import { writable } from 'svelte/store';
    import { logStore } from '$lib/stores/logStore';

    let categories = ['ALL', 'PROGRESS', 'SYSTEM', 'CLIENT', 'SESSION', 'PACKET', 'CONTROL'];
    let selectedCategoryStore = writable('ALL');
    let storageSize = writable('0 KB');

    onMount(() => {
    logStore.loadFromLocalStorage();
    updateStorageSize();
    });

    function extractLogType(message) {
        const match = message.match(/^\[(.*?)\]/);
        return match ? match[1].toUpperCase() : 'OTHER';
    }

    function clearLogs() {
        logStore.clear();
        updateStorageSize();
    }

    function updateStorageSize() {
        if (browser) {
            const logs = localStorage.getItem('logs');
            const sizeInBytes = logs ? new Blob([logs]).size : 0;
            const sizeInKB = (sizeInBytes / 1024).toFixed(2);
            storageSize.set(`${sizeInKB} KB`);
        }
    }

    function getLogLevelColor(level) {
        switch(level.toUpperCase()) {
            case 'INFO': return 'text-blue-500';
            case 'WARNING': return 'text-yellow-500';
            case 'ERROR': return 'text-red-500';
            case 'DEBUG': return 'text-green-500';
            default: return 'text-gray-500';
        }
    }

    $: filteredLogs = $selectedCategoryStore === 'ALL' 
        ? $logStore 
        : $logStore.filter(log => extractLogType(log.message) === $selectedCategoryStore);

    // Update storage size when logs change
    $: {
        $logStore;
        updateStorageSize();
    }
</script>

<div class="log-viewer p-4 bg-gray-100 rounded-lg">
    <div class="flex justify-between items-center mb-4">
        <h2 class="text-xl font-bold">HAMSTR LIVE LOGS</h2>
        <div class="flex items-center">
            <span class="mr-4 text-sm text-gray-600">Storage size: {$storageSize}</span>
            <button 
                class="bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded"
                on:click={clearLogs}
            >
                Clear Logs
            </button>
        </div>
    </div>
    
    {#if browser}
        <div class="tabs mb-4">
            {#each categories as category}
                <button 
                    class="tab {$selectedCategoryStore === category ? 'selected' : ''}"
                    on:click={() => selectedCategoryStore.set(category)}
                >
                    {category}
                </button>
            {/each}
        </div>

        <div class="max-h-[400px] overflow-y-auto">
            <ul class="space-y-2">
                {#each filteredLogs as log}
                    <li class="log-entry bg-white p-2 rounded shadow flex items-center">
                        <span class="timestamp text-xs text-gray-500 mr-2">{log.timestamp}</span>
                        <span class="font-mono font-semibold {getLogLevelColor(log.level)}">[{log.level}]</span>
                        <span class="ml-2 text-gray-700">{log.message}</span>
                    </li>
                {/each}
            </ul>
        </div>
    {:else}
        <p>Loading...</p>
    {/if}
</div>

<style>
    .log-viewer {
        background-color: #f5f5f5;
        border-radius: 8px;
    }
    .tabs {
        display: flex;
        overflow-x: auto;
        white-space: nowrap;
        border-bottom: 1px solid #e2e8f0;
    }
    .tab {
        padding: 0.5rem 1rem;
        border: none;
        background: none;
        cursor: pointer;
    }
    .tab.selected {
        border-bottom: 2px solid #3b82f6;
        font-weight: bold;
    }
    ul {
        list-style: none;
        padding-left: 0;
    }
    .log-entry {
        margin: 0.5rem 0;
        padding: 0.5rem;
        background-color: #ffffff;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-family: monospace;
    }
    .timestamp {
        color: #666;
        margin-right: 0.5rem;
    }
    .level {
        font-weight: bold;
        margin-right: 0.5rem;
    }
    .message {
        color: #333;
    }
</style>