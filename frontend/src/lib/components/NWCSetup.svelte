<script>
  import { onMount } from 'svelte';
  import { Input, Button, Card, Toggle } from 'flowbite-svelte';
  import { baseURL } from '$lib/stores/baseUrlStore';

  let { onnwcSaved, oncloseDrawer } = $props();

  let nwcUri = $state('');
  let showNwcUri = $state(false);
  let hasNwcConnection = $state(false);
  let connectionInfo = $state(null);
  let isConnecting = $state(false);

  let apiBaseUrl = $derived($baseURL);

  onMount(async () => {
    await checkNwcConnection();
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
      const testResponse = await fetch(`${apiBaseUrl}/api/test_nwc`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nwc_uri: nwcUri })
      });
      const testResult = await testResponse.json();

      if (testResult.success && testResult.stored) {
        hasNwcConnection = true;
        nwcUri = '';
        showNwcUri = false;
        await checkNwcConnection();
        onnwcSaved?.({ success: true, message: testResult.message || '⚡ Lightning wallet connected successfully!' });
      } else if (testResult.success && !testResult.stored) {
        onnwcSaved?.({ success: false, message: testResult.message || 'Connection successful but failed to store securely' });
      } else {
        onnwcSaved?.({ success: false, message: testResult.message || testResult.error || 'Failed to connect to wallet' });
      }
    } catch (error) {
      console.error('Error connecting NWC wallet:', error);
      onnwcSaved?.({ success: false, message: 'Network error while connecting wallet' });
    } finally {
      isConnecting = false;
    }
  }

  async function clearNwcConnection() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/nwc`, { method: 'DELETE' });
      const data = await response.json();
      if (data.success) {
        hasNwcConnection = false;
        connectionInfo = null;
        onnwcSaved?.({ success: true, message: 'Lightning wallet disconnected' });
      } else {
        onnwcSaved?.({ success: false, message: data.message || 'Failed to disconnect wallet' });
      }
    } catch (error) {
      console.error('Error clearing NWC connection:', error);
      onnwcSaved?.({ success: false, message: 'Failed to disconnect wallet' });
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

          <Button color="red" onclick={clearNwcConnection}>Disconnect Wallet</Button>
        </div>

      {:else}
        <div class="space-y-4">
          <p class="text-sm text-gray-600 dark:text-gray-400">
            Connect your Lightning wallet using a NWC connection string to enable ham radio zaps.
          </p>

          <div>
            <div class="flex justify-between items-center mb-2">
              <label for="nwc-uri" class="text-sm font-medium text-gray-900 dark:text-gray-300">
                NWC Connection String
              </label>
              <Toggle bind:checked={showNwcUri} size="small">Show</Toggle>
            </div>
            <Input
              id="nwc-uri"
              type={showNwcUri ? 'text' : 'password'}
              placeholder="nostr+walletconnect://..."
              bind:value={nwcUri}
            />
          </div>

          <Button
            color="blue"
            onclick={handleSubmit}
            disabled={isConnecting || !nwcUri}
          >
            {isConnecting ? 'Connecting...' : '⚡ Connect Wallet'}
          </Button>

          <div class="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <h4 class="font-medium mb-2 text-sm">How to get a NWC connection string:</h4>
            <ol class="text-sm text-gray-600 dark:text-gray-400 space-y-1 list-decimal list-inside">
              <li>Open Alby or another NWC-compatible wallet</li>
              <li>Go to Developer Settings or Connections</li>
              <li>Create a new app connection</li>
              <li>Copy the nostr+walletconnect:// string</li>
            </ol>
            <p class="text-xs text-gray-500 dark:text-gray-500 mt-3">
              The ham radio server never sees your wallet credentials.
            </p>
          </div>
        </div>
      {/if}
    </div>
  </Card>
</div>