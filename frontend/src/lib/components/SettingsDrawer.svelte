<script>
  import { Drawer } from 'flowbite-svelte';
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
  let headingElement = $state(null);

  const nostrURL = 'http://primal.net/p/npub1uwh0m2y8y5489nhr27xn8vkumy8flefm30kkx3l0tcn0wss34kaszyfqu7';

  $effect(() => {
    if (hidden) currentView = 'menu';
  });

  function navigateTo(view) { currentView = view; }
  function goBack() { currentView = 'menu'; }
  function closeDrawer() { hidden = true; currentView = 'menu'; }

  function handleNWCSaved(event) {
    const { success, message } = event.detail;
    onsettingsSaved?.({ success, message });
    if (success) {
      setTimeout(() => { currentView = 'menu'; }, 1000);
    }
  }

  function handleSettingsSaved(event) {
    onsettingsSaved?.(event.detail);
  }
</script>

<Drawer
  open={!hidden}
  placement="right"
  width="w-[85%] sm:w-[440px]"
  class="h-full overflow-hidden"
  outsideclose={true}
  transitionType="fly"
  transitionParams={{ x: 200 }}
  onhide={() => { hidden = true; currentView = 'menu'; }}
>
  <div class="h-full flex flex-col">

    <!-- Header -->
    <div class="flex-shrink-0 p-4 border-b bg-white dark:bg-gray-800">
      <div class="flex items-center gap-2 mb-2">
        {#if currentView !== 'menu'}
          <button
            class="p-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
            onclick={goBack}
          >
            ←
          </button>
        {/if}
        <h2 class="text-lg font-semibold" bind:this={headingElement} tabindex="-1">
          {#if currentView === 'menu'}
            Settings
          {:else if currentView === 'app'}
            App Settings
          {:else if currentView === 'nostr'}
            NOSTR Login
          {:else if currentView === 'nwc'}
            ⚡ NWC Zap Setup
          {:else if currentView === 'about'}
            About HAMSTR
          {/if}
        </h2>
      </div>
    </div>

    <!-- Scrollable Content -->
    <div class="flex-1 overflow-y-auto">
      <div class="p-4 space-y-4 sm:space-y-8 text-sm sm:text-base pb-20">
        <div class="flex justify-center pb-6">
          <img
            src={hamsterSmall}
            alt="HAMSTR Logo"
            class="w-1/2 aspect-square object-contain border-2 border-gray-200 dark:border-gray-600 rounded-lg p-2"
          />
        </div>

        {#if currentView === 'menu'}
          <div class="space-y-4">
            <ul class="space-y-2">
              <li><button class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded" onclick={() => navigateTo('app')}>App Settings</button></li>
              <li><button class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded" onclick={() => navigateTo('nostr')}>NOSTR Login</button></li>
              <li><button class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded" onclick={() => navigateTo('nwc')}>⚡ NWC Zap Setup</button></li>
              <li><button class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded pb-6" onclick={() => navigateTo('about')}>About Hamstr</button></li>
              <li><hr class="my-4"></li>
              <li class="flex justify-center space-x-4">
                <a href="https://github.com/LibertyFarmer/hamstr" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded" target="_blank" rel="noreferrer" aria-label="HAMSTR Github">
                  <Fa icon={faGithub} size="2x"/>
                </a>
                <a href={nostrURL} class="p-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded" target="_blank" rel="noreferrer" aria-label="Nostr Link">
                  <img src={logo} width="32" height="31" alt="Nostr Icon">
                </a>
              </li>
            </ul>
          </div>

        {:else if currentView === 'nostr'}
          <NostrSetup />

        {:else if currentView === 'nwc'}
          <NWCSetup
            onnwcSaved={({ success, message }) => {
              onsettingsSaved?.({ success, message });
              if (success) setTimeout(() => { currentView = 'menu'; }, 1000);
            }}
            oncloseDrawer={() => hidden = true}
          />

        {:else if currentView === 'app'}
          <AppSettings
            onsettingsSaved={handleSettingsSaved}
            oncloseDrawer={() => hidden = true}
          />

        {:else if currentView === 'about'}
          <About />
        {/if}

        {#if currentView === 'menu'}
          <div class="text-center mt-4">
            <a href="/logs" class="text-blue-500 hover:underline text-sm" onclick={closeDrawer}>LOGS</a>
            <p class="text-xs text-gray-500 mt-2">HAMSTR Version 0.00002100</p>
          </div>
        {/if}
      </div>
    </div>

  </div>
</Drawer>