<script>
  import { browser } from '$app/environment';
  import { logStore } from '$lib/stores/logStore';

  const categories = ['ALL', 'PROGRESS', 'SYSTEM', 'CLIENT', 'SESSION', 'PACKET', 'CONTROL'];

  let selectedCategory = $state('ALL');
  let storageSize = $state('0 KB');

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
      storageSize = `${(sizeInBytes / 1024).toFixed(2)} KB`;
    }
  }

  function getLogLevelColor(level) {
    switch (level.toUpperCase()) {
      case 'INFO': return 'text-blue-500';
      case 'WARNING': return 'text-yellow-500';
      case 'ERROR': return 'text-red-500';
      case 'DEBUG': return 'text-green-500';
      default: return 'text-gray-500';
    }
  }

  let filteredLogs = $derived(
    selectedCategory === 'ALL'
      ? $logStore
      : $logStore.filter(log => extractLogType(log.message) === selectedCategory)
  );

  // Update storage size whenever logs change
  $effect(() => {
    $logStore;
    updateStorageSize();
  });
</script>

<div class="log-viewer p-4 bg-gray-100 dark:bg-gray-800 rounded-lg pb-24">
  <div class="flex justify-between items-center mb-4">
    <h2 class="text-xl font-bold">HAMSTR LIVE LOGS</h2>
    <div class="flex items-center">
      <span class="mr-4 text-sm text-gray-600 dark:text-gray-400">Storage size: {storageSize}</span>
      <button
        class="bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded"
        onclick={clearLogs}
      >
        Clear Logs
      </button>
    </div>
  </div>

  {#if browser}
    <div class="tabs mb-4 flex overflow-x-auto border-b border-gray-200 dark:border-gray-600">
      {#each categories as category}
        <button
          class="tab px-4 py-2 border-none bg-transparent cursor-pointer whitespace-nowrap"
          class:selected={selectedCategory === category}
          onclick={() => selectedCategory = category}
        >
          {category}
        </button>
      {/each}
    </div>

    <ul class="list-none p-0">
      {#each filteredLogs as log}
        <li class="log-entry my-2 p-2 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded font-mono flex items-center">
          <span class="timestamp text-xs text-gray-500 mr-2">{log.timestamp}</span>
          <span class="font-semibold mr-2 {getLogLevelColor(log.level)}">[{log.level}]</span>
          <span class="ml-2 text-gray-700 dark:text-gray-300">{log.message}</span>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .tab.selected {
    border-bottom: 2px solid #3b82f6;
    font-weight: 700;
  }
</style>