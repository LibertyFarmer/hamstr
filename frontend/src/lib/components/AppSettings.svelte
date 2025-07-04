<script>
  import { onMount, createEventDispatcher } from 'svelte';
  import { baseURL } from '$lib/stores/baseUrlStore';
  import { settingsStore } from '$lib/stores/settingsStore';
  import { Input, Select, Label, Button, Card } from 'flowbite-svelte';

  const dispatch = createEventDispatcher();
 
  let apiBaseUrl;
    
  $: apiBaseUrl = $baseURL;
  
  let settings = {
    TNC_CLIENT_HOST: '',
    TNC_CLIENT_PORT: '',
    GENERAL_ACK_TIMEOUT: '',
    GENERAL_BAUD_RATE: '',
    GENERAL_SEND_RETRIES: '',
    RADIO_CLIENT_CALLSIGN: ['', 0],
    RADIO_HAMSTR_SERVER: ['', 0],  // Fixed: Use HAMSTR_SERVER consistently
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
        RADIO_HAMSTR_SERVER: parseCallsign(data.RADIO_HAMSTR_SERVER),  // Fixed: Use HAMSTR_SERVER consistently
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
            RADIO_HAMSTR_SERVER: {  // Fixed: Use HAMSTR_SERVER consistently
                callsign: settings.RADIO_HAMSTR_SERVER[0],
                ssid: parseInt(settings.RADIO_HAMSTR_SERVER[1])
            },
            NOSTR_DEFAULT_NOTE_REQUEST_COUNT: parseInt(settings.NOSTR_DEFAULT_NOTE_REQUEST_COUNT)
        };

        console.log('Saving settings:', preparedSettings);

        const response = await fetch(`${apiBaseUrl}/api/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(preparedSettings)
        });

        if (response.ok) {
            const result = await response.json();
            console.log('Settings saved successfully:', result);
            dispatch('settingsSaved', { 
                success: true, 
                message: 'Settings saved successfully!' 
            });
        } else {
            const error = await response.json();
            console.error('Error saving settings:', error);
            dispatch('settingsSaved', { 
                success: false, 
                message: 'Failed to save settings' 
            });
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        dispatch('settingsSaved', { 
            success: false, 
            message: 'Network error while saving settings' 
        });
    }
  }

  onMount(() => {
    fetchSettings();
  });

  function focusHeading() {
    if (headingElement) {
      headingElement.focus();
    }
  }

  function resetToDefaults() {
    settings = {
      TNC_CLIENT_HOST: 'localhost',
      TNC_CLIENT_PORT: '8001',
      GENERAL_ACK_TIMEOUT: '30',
      GENERAL_BAUD_RATE: '1200',
      GENERAL_SEND_RETRIES: '3',
      RADIO_CLIENT_CALLSIGN: ['', 0],
      RADIO_HAMSTR_SERVER: ['', 0],  // Fixed: Use HAMSTR_SERVER consistently
      NOSTR_DEFAULT_NOTE_REQUEST_COUNT: '2'
    };
  }
</script>

<div class="max-w-4xl mx-auto p-6 space-y-6">
  <div class="text-center">
    <h1 bind:this={headingElement} tabindex="-1" class="text-3xl font-bold text-gray-900 dark:text-white mb-2">
      Application Settings
    </h1>
    <p class="text-gray-600 dark:text-gray-400">
      Configure your HAMSTR client settings
    </p>
  </div>

  <div class="flex justify-center space-x-4 mb-6">
    <Button color="primary" on:click={saveSettings}>
      Save Settings
    </Button>
    <Button color="alternative" on:click={resetToDefaults}>
      Reset to Defaults
    </Button>
  </div>

  <div class="grid gap-6">
    <!-- TNC Settings -->
    <Card>
      <h3 class="text-xl font-bold mb-4">TNC Settings</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Label class="space-y-2">
          <span>TNC Host</span>
          <Input type="text" bind:value={settings.TNC_CLIENT_HOST} placeholder="localhost" />
        </Label>
        <Label class="space-y-2">
          <span>TNC Port</span>
          <Input type="number" bind:value={settings.TNC_CLIENT_PORT} placeholder="8001" />
        </Label>
        <Label class="space-y-2">
          <span>ACK Timeout (seconds)</span>
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
              placeholder="Your Callsign" 
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
          <Label for="target-server-callsign">Target Server Callsign</Label>
          <div class="flex items-center space-x-4">
            <Input 
              id="target-server-callsign"
              class="flex-grow"
              type="text" 
              bind:value={settings.RADIO_HAMSTR_SERVER[0]} 
              placeholder="Server Callsign" 
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
          <p class="text-sm text-gray-500 dark:text-gray-400">
            The callsign of the HAMSTR server you want to connect to
          </p>
        </div>
      </div>
    </Card>

    <!-- NOSTR Settings -->
    <Card>
      <h3 class="text-xl font-bold mb-4">NOSTR Settings</h3>
      <div class="space-y-4">
        <Label class="space-y-2">
          <span>Default Note Request Count (10 max)</span>
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
                    dispatch('settingsSaved', { 
                      success: true, 
                      message: 'Notes cleared successfully!' 
                    });
                  } else {
                    dispatch('settingsSaved', { 
                      success: false, 
                      message: 'Failed to clear notes' 
                    });
                  }
                } catch (error) {
                  console.error('Error clearing notes:', error);
                  dispatch('settingsSaved', { 
                    success: false, 
                    message: 'Network error while clearing notes' 
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
  </div>
</div>