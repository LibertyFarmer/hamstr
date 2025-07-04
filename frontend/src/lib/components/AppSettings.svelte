<script>
  import { onMount, createEventDispatcher } from 'svelte';
  import { baseURL } from '$lib/stores/baseUrlStore';
  import { settingsStore } from '$lib/stores/settingsStore';
  import { Input, Select, Label, Button, Card } from 'flowbite-svelte';

  const dispatch = createEventDispatcher();
 
  let apiBaseUrl;
    
  $: apiBaseUrl = $baseURL;
  
  apiBaseUrl = {baseURL}
  
  let settings = {
    TNC_CLIENT_HOST: '',
    TNC_CLIENT_PORT: '',
    GENERAL_ACK_TIMEOUT: '',
    GENERAL_BAUD_RATE: '',
    GENERAL_SEND_RETRIES: '',
    RADIO_CLIENT_CALLSIGN: ['', 0],
    RADIO_HAMSTR_SERVER: ['', 0],
    NOSTR_DEFAULT_NOTE_REQUEST_COUNT: ''

  };

  let baudRateOptions = ['300', '600', '1200'];
  let headingElement;

  async function fetchSettings() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/settings`);
      const data = await response.json();
      
      console.log('Received settings data:', data);

      const parseCallsign = (callsignData) => {
        if (typeof callsignData === 'string') {
          const match = callsignData.match(/\(([A-Za-z0-9]+),\s*(\d+)\)/);
          return match ? [match[1], parseInt(match[2])] : ['', 0];
        } else if (Array.isArray(callsignData) && callsignData.length === 2) {
          return [callsignData[0].toString(), parseInt(callsignData[1]) || 0];
        } else {
          console.warn('Unexpected callsign format:', callsignData);
          return ['', 0];
        }
      };

      settings = {
        ...data,
        RADIO_CLIENT_CALLSIGN: parseCallsign(data.RADIO_CLIENT_CALLSIGN),
        RADIO_HAMSTR_SERVER: parseCallsign(data.RADIO_HAMSTR_SERVER),
        GENERAL_BAUD_RATE: data.GENERAL_BAUD_RATE.toString()
      };

      console.log('Parsed settings:', settings);
    } catch (error) {
      console.error('Error fetching settings:', error);
      dispatch('settingsSaved', { 
        success: false, 
        message: 'Failed to load settings' 
      });
    }
  }

  async function saveSettings() {
    try {
        const preparedSettings = {
            ...settings,
            RADIO_CLIENT_CALLSIGN: {
                callsign: settings.RADIO_CLIENT_CALLSIGN[0],
                ssid: parseInt(settings.RADIO_CLIENT_CALLSIGN[1])
            },
            RADIO_HAMSTR_SERVER: {
                callsign: settings.RADIO_HAMSTR_SERVER[0],
                ssid: parseInt(settings.RADIO_HAMSTR_SERVER[1])
            },
            // Add this line to ensure the note request count is included
            NOSTR_DEFAULT_NOTE_REQUEST_COUNT: parseInt(settings.NOSTR_DEFAULT_NOTE_REQUEST_COUNT)
        };

        console.log('Saving settings:', preparedSettings);

        const response = await fetch(`${apiBaseUrl}/api/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(preparedSettings)
        });

        if (response.ok) {
            dispatch('settingsSaved', { 
                success: true, 
                message: 'Settings updated successfully' 
            });
            // Add the settingsUpdated event dispatch
            window.dispatchEvent(new CustomEvent('settingsUpdated'));
            setTimeout(() => {
                dispatch('closeDrawer');
            }, 300);
        } else {
            throw new Error('Failed to update settings');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        dispatch('settingsSaved', { 
            success: false, 
            message: 'Failed to update settings' 
        });
    }
}

  onMount(fetchSettings);
</script>

<div class="p-4 space-y-4 sm:space-y-8 text-sm sm:text-base">
  <h2 class="text-2xl font-bold mb-4" bind:this={headingElement} tabindex="-1">App Settings</h2>

  <form on:submit|preventDefault={saveSettings} class="space-y-8">
    <!-- TNC Settings -->
    <Card>
      <h3 class="text-xl font-bold mb-4">TNC Settings</h3>
      <div class="space-y-4">
        <Label class="space-y-2">
          <span>Client Host</span>
          <Input type="text" bind:value={settings.TNC_CLIENT_HOST} />
        </Label>
        <Label class="space-y-2">
          <span>Client Port</span>
          <Input type="number" bind:value={settings.TNC_CLIENT_PORT} />
        </Label>
      </div>
    </Card>

    <!-- General Settings -->
    <Card>
      <h3 class="text-xl font-bold mb-4">General Settings</h3>
      <div class="space-y-4">
        <Label class="space-y-2">
          <span>ACK Timeout</span>
          <Input type="number" bind:value={settings.GENERAL_ACK_TIMEOUT} />
        </Label>
        <Label class="space-y-2">
          <span>Connection Retries</span>
          <Input type="number" bind:value={settings.GENERAL_SEND_RETRIES} />
        </Label>
        <Label class="space-y-2">
          <span>Baud Rate</span>
          <Select bind:value={settings.GENERAL_BAUD_RATE}>
            {#each baudRateOptions as option}
              <option value={option}>{option}</option>
            {/each}
          </Select>
        </Label>
      </div>
    </Card>

    <!-- Radio Settings -->
    <Card>
      <h3 class="text-xl font-bold mb-4">Radio Settings</h3>
      <div class="space-y-4">
        <div class="space-y-2">
          <Label for="client-callsign">Client Callsign</Label>
          <div class="flex items-center space-x-4">
            <Input 
              id="client-callsign"
              class="flex-grow"
              type="text" 
              bind:value={settings.RADIO_CLIENT_CALLSIGN[0]} 
              placeholder="Callsign" 
              maxlength="6"
              on:input={(e) => e.target.value = e.target.value.toUpperCase()}
            />
            <span class="text-2xl font-bold">-</span>
            <Select 
              class="w-24"
              bind:value={settings.RADIO_CLIENT_CALLSIGN[1]}
            >
              {#each Array(16).fill().map((_, i) => i) as ssid}
                <option value={ssid}>{ssid}</option>
              {/each}
            </Select>
          </div>
        </div>
        <div class="space-y-2">
          <Label for="server-callsign">Target Server Callsign</Label>
          <div class="flex items-center space-x-4">
            <Input 
              id="target-callsign"
              class="flex-grow"
              type="text" 
              bind:value={settings.RADIO_HAMSTR_SERVER[0]} 
              placeholder="Callsign" 
              maxlength="6"
              on:input={(e) => e.target.value = e.target.value.toUpperCase()}
            />
            <span class="text-2xl font-bold">-</span>
            <Select 
              class="w-24"
              bind:value={settings.RADIO_HAMSTR_SERVER[1]}
            >
              {#each Array(16).fill().map((_, i) => i) as ssid}
                <option value={ssid}>{ssid}</option>
              {/each}
            </Select>
          </div>
        </div>
      </div>
    </Card>

       <!-- NOSTR Settings -->
      <Card>
        <h3 class="text-xl font-bold mb-4">NOSTR Settings</h3>
        <div class="space-y-4">
            <Label class="space-y-2">
                <span>Default Note Request Count(10 max)</span>
                <Input 
                    type="number" 
                    bind:value={settings.NOSTR_DEFAULT_NOTE_REQUEST_COUNT}
                    min="1"
                    max="10"
                    placeholder="Number of notes to request"
                />
            </Label>
        </div>
      </Card>

      <!-- Storage Management -->
<Card>
  <h3 class="text-xl font-bold mb-4">Storage Management</h3>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <span class="text-lg font-medium">Clear Local Notes</span>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          Delete all stored notes from local database
        </p>
      </div>
      <Button 
        color="red" 
        on:click={async () => {
          if (confirm('Are you sure you want to clear all stored notes? This cannot be undone.')) {
            try {
              const response = await fetch(`${apiBaseUrl}/api/clear_notes`, {
                method: 'POST'
              });
              const result = await response.json();
              
              if (result.success) {
                // Dispatch success event
                dispatch('settingsSaved', {
                  success: true,
                  message: 'Notes cleared successfully'
                });
                // Trigger notes refresh in main view
                window.dispatchEvent(new CustomEvent('notesUpdated', { 
                  detail: { notes: [], pagination: { has_more: false } } 
                }));
              } else {
                throw new Error(result.message);
              }
            } catch (error) {
              dispatch('settingsSaved', {
                success: false,
                message: `Failed to clear notes: ${error.message}`
              });
            }
          }
        }}
      >
        Clear Notes
      </Button>
    </div>
  </div>
</Card>

    <div class="flex justify-end space-x-4">
      <Button type="submit" color="blue">Save</Button>
      <Button type="button" color="light" on:click={() => dispatch('closeDrawer')}>Cancel</Button>
    </div>
  </form>
</div>