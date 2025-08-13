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
    TNC_CONNECTION_TYPE: 'tcp',
    TNC_SERIAL_PORT: 'COM3',
    TNC_SERIAL_SPEED: '57600',
    GENERAL_ACK_TIMEOUT: '',
    GENERAL_BAUD_RATE: '',
    GENERAL_SEND_RETRIES: '',
    RADIO_CLIENT_CALLSIGN: ['', 0],
    RADIO_HAMSTR_SERVER: ['', 0],
    NOSTR_DEFAULT_NOTE_REQUEST_COUNT: ''
  };

  let baudRateOptions = ['300', '600', '1200'];
  let serialSpeedOptions = ['1200', '9600', '19200', '38400', '57600', '115200'];
  let serialPortOptions = [];
  let headingElement;

  // Fetch dynamic serial ports from backend
  async function fetchSerialPorts() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/serial_ports`);
      const data = await response.json();
      
      if (data.success) {
        serialPortOptions = data.ports;
        console.log(`Loaded ${data.ports.length} serial ports for ${data.platform}:`, data.ports);
      } else {
        console.error('Failed to fetch serial ports:', data.error);
        // Fallback to basic ports
        serialPortOptions = ['COM3', '/dev/ttyUSB0', '/dev/cu.usbserial'];
      }
    } catch (error) {
      console.error('Error fetching serial ports:', error);
      // Fallback to basic ports
      serialPortOptions = ['COM3', '/dev/ttyUSB0', '/dev/cu.usbserial'];
    }
  }

  // Reactive statement to handle TNC type changes
  $: showTcpSettings = settings.TNC_CONNECTION_TYPE === 'tcp';
  $: showSerialSettings = settings.TNC_CONNECTION_TYPE === 'serial';

  async function fetchSettings() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/settings`);
      const data = await response.json();
      
      console.log('Received settings data:', data);
      console.log('TNC-related keys in response:', Object.keys(data).filter(key => key.includes('TNC')));

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
        GENERAL_BAUD_RATE: data.GENERAL_BAUD_RATE?.toString() || '1200',
        // Handle TNC settings with proper defaults and ensure they load correctly
        TNC_CONNECTION_TYPE: data.TNC_CONNECTION_TYPE || 'tcp',
        TNC_CLIENT_HOST: data.TNC_CLIENT_HOST || 'localhost',
        TNC_CLIENT_PORT: data.TNC_CLIENT_PORT || '8001',
        TNC_SERIAL_PORT: data.TNC_SERIAL_PORT || 'COM3',
        TNC_SERIAL_SPEED: data.TNC_SERIAL_SPEED?.toString() || '57600'
      };

      console.log('Final parsed settings:', settings);
      console.log('TNC_CONNECTION_TYPE set to:', settings.TNC_CONNECTION_TYPE);
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
            // Add the settingsUpdated event dispatch
            window.dispatchEvent(new CustomEvent('settingsUpdated'));
            // Close the drawer after successful save
            setTimeout(() => {
                dispatch('closeDrawer');
            }, 300);
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

  onMount(async () => {
    await fetchSerialPorts(); // Fetch dynamic serial ports first
    await fetchSettings();    // Then load settings
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
      TNC_CONNECTION_TYPE: 'tcp',
      TNC_SERIAL_PORT: 'COM3',
      TNC_SERIAL_SPEED: '57600',
      GENERAL_ACK_TIMEOUT: '30',
      GENERAL_BAUD_RATE: '1200',
      GENERAL_SEND_RETRIES: '3',
      RADIO_CLIENT_CALLSIGN: ['', 0],
      RADIO_HAMSTR_SERVER: ['', 0],
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

  <div class="grid gap-6">
    <!-- TNC Settings -->
    <Card>
      <h3 class="text-xl font-bold mb-4">TNC Settings</h3>
      
      <!-- TNC Connection Type Selector -->
      <div class="mb-6">
        <Label class="space-y-2">
          <span>TNC Connection Type</span>
          <Select bind:value={settings.TNC_CONNECTION_TYPE}>
            <option value="tcp">TCP</option>
            <option value="serial">Serial</option>
          </Select>
        </Label>
      </div>

      <!-- TCP Settings (conditional) -->
      {#if showTcpSettings}
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <Label class="space-y-2">
            <span>TNC Host</span>
            <Input type="text" bind:value={settings.TNC_CLIENT_HOST} placeholder="localhost" />
          </Label>
          <Label class="space-y-2">
            <span>TNC Port</span>
            <Input type="number" bind:value={settings.TNC_CLIENT_PORT} placeholder="8001" />
          </Label>
        </div>
      {/if}

      <!-- Serial Settings (conditional) -->
      {#if showSerialSettings}
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <Label class="space-y-2">
            <span>Serial Port</span>
            <Select bind:value={settings.TNC_SERIAL_PORT}>
              {#each serialPortOptions as port}
                <option value={port}>{port}</option>
              {/each}
            </Select>
          </Label>
          <Label class="space-y-2">
            <span>Serial Speed</span>
            <Select bind:value={settings.TNC_SERIAL_SPEED}>
              {#each serialSpeedOptions as speed}
                <option value={speed}>{speed}</option>
              {/each}
            </Select>
          </Label>
        </div>
      {/if}

      <!-- Common TNC Settings -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
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
        </div>
      </div>
    </Card>

    <!-- NOSTR Settings -->
    <Card>
      <h3 class="text-xl font-bold mb-4">NOSTR Settings</h3>
      <div class="space-y-4">
        <Label class="space-y-2">
          <span>Default Note Request Count</span>
          <Input type="number" bind:value={settings.NOSTR_DEFAULT_NOTE_REQUEST_COUNT} placeholder="2" />
        </Label>
      </div>
    </Card>

    <!-- Database Settings -->
    <Card>
      <h3 class="text-xl font-bold mb-4">Database</h3>
      <div class="space-y-4">
        <p class="text-gray-600 dark:text-gray-400">
          Clear all locally stored notes from the database. This cannot be undone.
        </p>
        <div>
          <Button 
            color="red" 
            on:click={async () => {
              if (confirm('Are you sure you want to clear all notes? This cannot be undone.')) {
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

  <!-- ONLY ONE SET OF BUTTONS - AT THE BOTTOM -->
  <div class="flex justify-center space-x-4 mt-8">
    <Button color="primary" on:click={saveSettings}>
      Save Settings
    </Button>
    <Button color="alternative" on:click={resetToDefaults}>
      Reset to Defaults
    </Button>
  </div>
</div>