<script>
  import { fly } from 'svelte/transition';
  import Fa from 'svelte-fa';
  import { faGithub } from '@fortawesome/free-brands-svg-icons';
  import NostrSetup from '$lib/components/NostrSetup.svelte';
  import AppSettings from '$lib/components/AppSettings.svelte';
  import About from '$lib/components/About.svelte';
  import logo from '$lib/assets/nostr_logo_blk.png';
  import hamsterSmall from '$lib/assets/hamster_small.webp';
  import NWCSetup from '$lib/components/NWCSetup.svelte';

  let {
    hidden = $bindable(true),
    onsettingsSaved
  } = $props();

  let currentView = $state('menu');

  const nostrURL = 'http://primal.net/p/npub1uwh0m2y8y5489nhr27xn8vkumy8flefm30kkx3l0tcn0wss34kaszyfqu7';

  function navigateTo(view) { currentView = view; }
  function goBack() { currentView = 'menu'; }
  function closeDrawer() { hidden = true; currentView = 'menu'; }
</script>

{#if !hidden}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 bg-black/50 z-40"
    onclick={closeDrawer}
    role="presentation"
  ></div>

  <!-- Panel -->
  <div
    class="fixed top-0 right-0 h-full z-50 bg-white dark:bg-gray-800 shadow-xl flex flex-col"
    style="width: min(85vw, 440px);"
    transition:fly={{ x: 440, duration: 300, opacity: 1 }}
  >
    <!-- Header -->
    <div class="flex-shrink-0 flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
      <div class="flex items-center gap-2">
        {#if currentView !== 'menu'}
          <button
            class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-lg"
            onclick={goBack}
          >←</button>
        {/if}
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">
          {#if currentView === 'menu'}Settings
          {:else if currentView === 'app'}App Settings
          {:else if currentView === 'nostr'}NOSTR Login
          {:else if currentView === 'nwc'}⚡ NWC Zap Setup
          {:else if currentView === 'about'}About HAMSTR
          {/if}
        </h2>
      </div>
      <button
        class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-gray-500 dark:text-gray-400"
        onclick={closeDrawer}
        aria-label="Close"
      >✕</button>
    </div>

    <!-- Scrollable Content -->
    <div class="flex-1 overflow-y-auto">
      <div class="p-4 pb-20 text-sm sm:text-base">

        {#if currentView === 'menu'}
          <div class="flex justify-center py-6">
            <img
              src={hamsterSmall}
              alt="HAMSTR Logo"
              width="128"
              height="128"
              style="object-fit: contain; border-radius: 8px;"
            />
          </div>

          <ul class="space-y-1">
            <li><button class="w-full text-left px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg text-gray-900 dark:text-white" onclick={() => navigateTo('app')}>App Settings</button></li>
            <li><button class="w-full text-left px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg text-gray-900 dark:text-white" onclick={() => navigateTo('nostr')}>NOSTR Login</button></li>
            <li><button class="w-full text-left px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg text-gray-900 dark:text-white" onclick={() => navigateTo('nwc')}>⚡ NWC Zap Setup</button></li>
            <li><button class="w-full text-left px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg text-gray-900 dark:text-white" onclick={() => navigateTo('about')}>About HAMSTR</button></li>
          </ul>

          <hr class="my-4 dark:border-gray-600">

          <div class="flex justify-center space-x-4 mb-6">
            <a href="https://github.com/LibertyFarmer/hamstr"
              class="p-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded"
              target="_blank" rel="noreferrer" aria-label="HAMSTR Github">
              <Fa icon={faGithub} size="2x"/>
            </a>
            <a href={nostrURL}
              class="p-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded"
              target="_blank" rel="noreferrer" aria-label="Nostr Link">
              <img src={logo} width="32" height="31" alt="Nostr Icon">
            </a>
          </div>

          <div class="text-center">
            <a href="/logs" class="text-blue-500 hover:underline text-sm" onclick={closeDrawer}>LOGS</a>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">HAMSTR Version 0.00002100</p>
          </div>

        {:else if currentView === 'nostr'}
          <NostrSetup />

        {:else if currentView === 'nwc'}
          <NWCSetup
            onnwcSaved={({ success, message }) => {
              onsettingsSaved?.({ success, message });
              if (success) setTimeout(() => { currentView = 'menu'; }, 1000);
            }}
            oncloseDrawer={closeDrawer}
          />

        {:else if currentView === 'app'}
          <AppSettings
            onsettingsSaved={(detail) => onsettingsSaved?.(detail)}
            oncloseDrawer={closeDrawer}
          />

        {:else if currentView === 'about'}
          <About />
        {/if}

      </div>
    </div>

  </div>
{/if}