<script>
  import { onMount, createEventDispatcher } from 'svelte';
  import { Drawer } from 'flowbite-svelte';
  import Fa from 'svelte-fa';
  import { faGithub } from '@fortawesome/free-brands-svg-icons';
  import NostrSetup from '$lib/components/NostrSetup.svelte';
  import AppSettings from '$lib/components/AppSettings.svelte';
  import About from '$lib/components/About.svelte';
  import logo from '$lib/assets/nostr_logo_blk.png';
  import hamsterSmall from '$lib/assets/hamster_small.webp';
  import NWCSetup from '$lib/components/NWCSetup.svelte';

  const dispatch = createEventDispatcher();
  export let hidden = true;
  
  let currentView = 'menu';
  let headingElement;
  let nostrURL = 'http://primal.net/p/npub1uwh0m2y8y5489nhr27xn8vkumy8flefm30kkx3l0tcn0wss34kaszyfqu7';

  // Watch for changes to hidden and reset view when drawer closes
  $: if (hidden) {
    currentView = 'menu';
  }

  function navigateTo(view) {
    currentView = view;
  }

  function goBack() {
    currentView = 'menu';
  }

  function closeDrawer() {
    hidden = true;
    currentView = 'menu'; // Also reset here just to be thorough
  }

  function handleNWCSaved(event) {
  const { success, message } = event.detail;
  dispatch('settingsSaved', { success, message });
  if (success) {
    // Optionally close drawer on successful setup
    setTimeout(() => {
      currentView = 'menu';
    }, 1000);
  }
}

  function handleSettingsSaved(event) {
    dispatch('settingsSaved', event.detail);
  }
</script>

<Drawer 
  bind:hidden
  placement="right"
  width="w-[85%] sm:w-[440px]"
  class="h-full overflow-hidden"
  activateClickOutside={true}
  transitionType="fly"
  transitionParams={{ x: 200 }}
  on:hidden={() => currentView = 'menu'}
>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="flex-shrink-0 p-4 border-b bg-white dark:bg-gray-800">
      <div class="flex items-center gap-2 mb-2">
        {#if currentView !== 'menu'}
          <button 
            class="p-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 rounded" 
            on:click={goBack}
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
              <li><button class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded" on:click={() => navigateTo('app')}>App Settings</button></li>
              <li><button class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded" on:click={() => navigateTo('nostr')}>NOSTR Login</button></li>
              <li><button class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded" on:click={() => navigateTo('nwc')}>⚡ NWC Zap Setup</button></li>
              <li><button class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded pb-6" on:click={() => navigateTo('about')}>About Hamstr</button></li>
              <li><hr class="my-4"></li>
              <li class="flex justify-center space-x-4">
                <a href="https://github.com/Cancerboyuofa/pykiss" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded" target="_blank" alt="Hamstr Github">
                  <Fa icon={faGithub} size="2x"/>
                </a>
                <a href={nostrURL} class="p-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded" target="_blank" alt="Nostr Link">
                  <img src={logo} width="32px" height="31px" alt="Nostr Icon">
                </a>
              </li>
            </ul>
          </div>
        {:else if currentView === 'nostr'}
          <NostrSetup />
        {:else if currentView === 'nwc'}
          <NWCSetup 
            on:nwcSaved={handleNWCSaved}
            on:closeDrawer={() => hidden = true}
          />
        {:else if currentView === 'app'}
          <AppSettings 
            on:settingsSaved={handleSettingsSaved}
            on:closeDrawer={() => hidden = true}
          />
        {:else if currentView === 'about'}
          <About />
        {/if}

        <!-- Footer only shows on main menu -->
        {#if currentView === 'menu'}
          <div class="text-center mt-4">
            <a href="/logs" class="text-blue-500 hover:underline text-sm" on:click={closeDrawer}>LOGS</a>
            <p class="text-xs text-gray-500 mt-2">HAMSTR Version 0.00002100</p>
          </div>
        {/if}
      </div>
    </div>
  </div>
</Drawer>