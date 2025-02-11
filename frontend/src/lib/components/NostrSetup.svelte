<script>
  import { onMount } from 'svelte';
  import { Input, Button, Card, Toggle } from 'flowbite-svelte';
  import { baseURL } from '$lib/store';

  let nsec = '';
  let showNsec = false;
  let hasStoredNsec = false;
  let apiBaseUrl;

  $: apiBaseUrl = $baseURL;

  onMount(async () => {
      checkStoredNsec();
  });

  async function checkStoredNsec() {
      try {
          const response = await fetch(`${apiBaseUrl}/api/nsec`);
          const data = await response.json();
          hasStoredNsec = data.has_nsec;
      } catch (error) {
          console.error('Error checking NSEC:', error);
      }
  }

  async function handleSubmit() {
      try {
          const response = await fetch(`${apiBaseUrl}/api/nsec`, {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json'
              },
              body: JSON.stringify({ nsec })
          });
          
          const data = await response.json();
          
          if (data.success) {
              hasStoredNsec = true;
              nsec = '';
              showNsec = false;
              window.dispatchEvent(new CustomEvent('showToast', {
                  detail: {
                      message: 'NSEC stored successfully',
                      type: 'success'
                  }
              }));
          } else {
              window.dispatchEvent(new CustomEvent('showToast', {
                  detail: {
                      message: data.message,
                      type: 'error'
                  }
              }));
          }
      } catch (error) {
          console.error('Error storing NSEC:', error);
          window.dispatchEvent(new CustomEvent('showToast', {
              detail: {
                  message: 'Failed to store NSEC',
                  type: 'error'
              }
          }));
      }
  }

  async function clearNsec() {
      try {
          const response = await fetch(`${apiBaseUrl}/api/nsec`, {
              method: 'DELETE'
          });
          
          const data = await response.json();
          
          if (data.success) {
              hasStoredNsec = false;
              window.dispatchEvent(new CustomEvent('showToast', {
                  detail: {
                      message: 'NSEC cleared successfully',
                      type: 'success'
                  }
              }));
          } else {
              window.dispatchEvent(new CustomEvent('showToast', {
                  detail: {
                      message: data.message,
                      type: 'error'
                  }
              }));
          }
      } catch (error) {
          console.error('Error clearing NSEC:', error);
          window.dispatchEvent(new CustomEvent('showToast', {
              detail: {
                  message: 'Failed to clear NSEC',
                  type: 'error'
              }
          }));
      }
  }
</script>

<div class="space-y-4">
  <Card>
      <div class="p-4">
          <h3 class="text-lg font-semibold mb-4">NOSTR Login</h3>
          
          {#if hasStoredNsec}
              <div class="space-y-4">
                  <p class="text-green-600 dark:text-green-400">NSEC key is stored and ready for use</p>
                  <Button color="red" on:click={clearNsec}>Clear NSEC</Button>
              </div>
          {:else}
              <form class="space-y-4" on:submit|preventDefault={handleSubmit}>
                  <div>
                      <div class="flex justify-between items-center mb-2">
                          <label for="nsec" class="text-sm font-medium text-gray-900 dark:text-gray-300">NSEC Key</label>
                          <Toggle bind:checked={showNsec} size="small">Show NSEC</Toggle>
                      </div>
                      <Input
                          type={showNsec ? "text" : "password"}
                          id="nsec"
                          placeholder="Enter your nsec1..."
                          bind:value={nsec}
                          required
                      />
                  </div>
                  <Button type="submit" color="blue">Store NSEC</Button>
              </form>
          {/if}
      </div>
  </Card>
</div>