<script>
  import { onMount, createEventDispatcher } from 'svelte';
  import { Input, Button, Card, Toggle } from 'flowbite-svelte';
  import { baseURL } from '$lib/stores/baseUrlStore';

  const dispatch = createEventDispatcher();

  let nwcUri = '';
  let showNwcUri = false;
  let hasNwcConnection = false;
  let connectionInfo = null;
  let isConnecting = false;
  let apiBaseUrl;

  $: apiBaseUrl = $baseURL;

  onMount(async () => {
    checkNwcConnection();
  });

  async function checkNwcConnection() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/nwc`);
      const data = await response.json();
      hasNwcConnection = data.has_nwc;
      connectionInfo = data.connection_info;
    } catch (error) {
      console.error('Error checking NWC connection:', error);
    }
  }

  async function handleSubmit() {
    if (isConnecting) return;
    
    try {
      isConnecting = true;

      // Test the connection AND store if successful (new combined flow)
      const testResponse = await fetch(`${apiBaseUrl}/api/test_nwc`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ nwc_uri: nwcUri })
      });
      
      const testResult = await testResponse.json();
      
      if (testResult.success && testResult.stored) {
        // Connection successful and stored
        hasNwcConnection = true;
        nwcUri = '';
        showNwcUri = false;
        await checkNwcConnection(); // Refresh connection info
        
        dispatch('nwcSaved', {
          success: true,
          message: testResult.message || '⚡ Lightning wallet connected successfully!'
        });
      } else if (testResult.success && !testResult.stored) {
        // Connection worked but storage failed
        dispatch('nwcSaved', {
          success: false,
          message: testResult.message || 'Connection successful but failed to store securely'
        });
      } else {
        // Connection failed
        dispatch('nwcSaved', {
          success: false,
          message: testResult.message || testResult.error || 'Failed to connect to wallet'
        });
      }
    } catch (error) {
      console.error('Error connecting NWC wallet:', error);
      dispatch('nwcSaved', {
        success: false,
        message: 'Network error while connecting wallet'
      });
    } finally {
      isConnecting = false;
    }
  }

  async function clearNwcConnection() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/nwc`, {
        method: 'DELETE'
      });
      
      const data = await response.json();
      
      if (data.success) {
        hasNwcConnection = false;
        connectionInfo = null;
        dispatch('nwcSaved', {
          success: true,
          message: 'Lightning wallet disconnected'
        });
      } else {
        dispatch('nwcSaved', {
          success: false,
          message: data.message || 'Failed to disconnect wallet'
        });
      }
    } catch (error) {
      console.error('Error clearing NWC connection:', error);
      dispatch('nwcSaved', {
        success: false,
        message: 'Failed to disconnect wallet'
      });
    }
  }
</script>

<div class="space-y-4">
  <Card>
    <div class="p-4">
      <h3 class="text-lg font-semibold mb-4">⚡ Lightning Wallet Setup</h3>
      
      {#if hasNwcConnection && connectionInfo}
        <div class="space-y-4">
          <div class="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
            <div class="flex items-center mb-2">
              <span class="text-green-600 dark:text-green-400 text-xl mr-2">⚡</span>
              <span class="text-green-800 dark:text-green-200 font-medium">Wallet Connected</span>
            </div>
            <div class="text-sm text-green-700 dark:text-green-300 space-y-1">
              <p><strong>Relay:</strong> {connectionInfo.relay}</p>
              <p><strong>Wallet:</strong> {connectionInfo.wallet_pubkey_preview}</p>
            </div>
          </div>
          
          <div class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <h4 class="font-medium text-blue-800 dark:text-blue-200 mb-2">Ready for Offline Zaps!</h4>
            <p class="text-sm text-blue-700 dark:text-blue-300">
              You can now send Lightning zaps via ham radio. Click ⚡ icons next to posts to zap other users.
            </p>
          </div>
          
          <Button color="red" on:click={clearNwcConnection}>
            Disconnect Wallet
          </Button>
        </div>
      {:else}
        <div class="space-y-4">
          <div class="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
            <h4 class="font-medium text-yellow-800 dark:text-yellow-200 mb-2">Setup Required</h4>
            <p class="text-sm text-yellow-700 dark:text-yellow-300 mb-3">
              Connect your Lightning wallet to send zaps via ham radio. You'll need a NOSTR Wallet Connect (NWC) URI from your wallet.
            </p>
            <details class="text-sm text-yellow-700 dark:text-yellow-300">
              <summary class="cursor-pointer font-medium hover:text-yellow-600">How to get NWC URI</summary>
              <div class="mt-2 pl-4 space-y-2">
                <p><strong>Alby Hub:</strong> Go to Apps → Add new connection → Copy the connection string</p>
                <p><strong>Mutiny:</strong> Settings → Nostr Wallet Connect → Create new connection</p>
                <p><strong>Other wallets:</strong> Look for "NWC", "Nostr Wallet Connect", or "App Connections"</p>
              </div>
            </details>
          </div>

          <form class="space-y-4" on:submit|preventDefault={handleSubmit}>
            <div>
              <div class="flex justify-between items-center mb-2">
                <label for="nwcUri" class="text-sm font-medium text-gray-900 dark:text-gray-300">
                  NWC Connection URI
                </label>
                <Toggle bind:checked={showNwcUri} size="small">Show URI</Toggle>
              </div>
              <Input
                type={showNwcUri ? "text" : "password"}
                id="nwcUri"
                placeholder="nostr+walletconnect://..."
                bind:value={nwcUri}
                required
                disabled={isConnecting}
              />
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Paste your NWC connection string from your Lightning wallet
              </p>
            </div>

            <Button 
              type="submit" 
              color="blue" 
              disabled={isConnecting || !nwcUri.trim()}
              class="w-full"
            >
              {#if isConnecting}
                Connecting...
              {:else}
                ⚡ Connect Lightning Wallet
              {/if}
            </Button>
          </form>

          <div class="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <h4 class="font-medium text-gray-800 dark:text-gray-200 mb-2">Security Note</h4>
            <p class="text-sm text-gray-600 dark:text-gray-400">
              Your wallet connection is stored encrypted locally. The ham radio server never sees your wallet credentials.
            </p>
          </div>
        </div>
      {/if}
    </div>
  </Card>
</div>