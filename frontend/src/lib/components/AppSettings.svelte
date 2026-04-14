<script>
  import { onMount } from 'svelte';
  import { baseURL } from '$lib/stores/baseUrlStore';
  import { Input, Select, Label, Button, Card } from 'flowbite-svelte';

  let { onsettingsSaved, oncloseDrawer } = $props();

  let apiBaseUrl = $derived($baseURL);

  let settings = $state({
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
  });

  const baudRateOptions = ['300', '600', '1200'];
  const serialSpeedOptions = ['1200', '9600', '19200', '38400', '57600', '115200'];
  let serialPortOptions = $state([]);
  let headingElement = $state(null);

  let showTcpSettings = $derived(settings.TNC_CONNECTION_TYPE === 'tcp');
  let showSerialSettings = $derived(settings.TNC_CONNECTION_TYPE === 'serial');

  async function fetchSerialPorts() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/serial_ports`);
      const data = await response.json();
      if (data.success) {
        serialPortOptions = data.ports;
      } else {
        serialPortOptions = ['COM3', '/dev/ttyUSB0', '/dev/cu.usbserial'];
      }
    } catch (error) {
      serialPortOptions = ['COM3', '/dev/ttyUSB0', '/dev/cu.usbserial'];
    }
  }

  async function fetchSettings() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/settings`);
      const data = await response.json();

      const parseCallsign = (callsignData) => {
        if (typeof callsignData === 'string') {
          const match = callsignData.match(/\(([A-Za-z0-9]+),\s*(\d+)\)/);
          return match ? [match[1], parseInt(match[2])] : ['', 0];
        } else if (Array.isArray(callsignData) && callsignData.length === 2) {
          return [callsignData[0].toString(), parseInt(callsignData[1]) || 0];
        }
        return ['', 0];
      };

      settings = {
        ...data,
        RADIO_CLIENT_CALLSIGN: parseCallsign(data.RADIO_CLIENT_CALLSIGN),
        RADIO_HAMSTR_SERVER: parseCallsign(data.RADIO_HAMSTR_SERVER),
        GENERAL_BAUD_RATE: data.GENERAL_BAUD_RATE?.toString() || '1200',
        TNC_CONNECTION_TYPE: data.TNC_CONNECTION_TYPE || 'tcp',
        TNC_CLIENT_HOST: data.TNC_CLIENT_HOST || 'localhost',
        TNC_CLIENT_PORT: data.TNC_CLIENT_PORT || '8001',
        TNC_SERIAL_PORT: data.TNC_SERIAL_PORT || 'COM3',
        TNC_SERIAL_SPEED: data.TNC_SERIAL_SPEED?.toString() || '57600'
      };
    } catch (error) {
      onsettingsSaved?.({ success: false, message: 'Failed to load settings' });
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

      const response = await fetch(`${apiBaseUrl}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preparedSettings)
      });

      if (response.ok) {
        onsettingsSaved?.({ success: true, message: 'Settings saved successfully!' });
        window.dispatchEvent(new CustomEvent('settingsUpdated'));
        setTimeout(() => { oncloseDrawer?.(); }, 300);
      } else {
        onsettingsSaved?.({ success: false, message: 'Failed to save settings' });
      }
    } catch (error) {
      onsettingsSaved?.({ success: false, message: 'Network error while saving settings' });
    }
  }

  async function clearNotes() {
    if (!confirm('Are you sure you want to clear all notes? This cannot be undone.')) return;
    try {
      const response = await fetch(`${apiBaseUrl}/api/clear_notes`, { method: 'POST' });
      const result = await response.json();
      onsettingsSaved?.({
        success: result.success,
        message: result.success ? 'Notes cleared successfully!' : 'Failed to clear notes'
      });
    } catch (error) {
      onsettingsSaved?.({ success: false, message: 'Network error while clearing notes' });
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

  onMount(async () => {
    await fetchSerialPorts();
    await fetchSettings();
  });
</script>

<div class="space-y-4 p-2">

  <!-- TNC Settings -->
  <Card class="border-0 shadow-none">
    <h3 class="text-lg font-bold mb-3 text-gray-900 dark:text-white">TNC Settings</h3>
    <div class="space-y-4">
      <Label class="space-y-2">
        <span>TNC Connection Type</span>
        <Select bind:value={settings.TNC_CONNECTION_TYPE}>
          <option value="tcp">TCP</option>
          <option value="serial">Serial</option>
        </Select>
      </Label>

      {#if showTcpSettings}
        <div class="grid grid-cols-2 gap-4">
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

      {#if showSerialSettings}
        <div class="grid grid-cols-2 gap-4">
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

      <div class="grid grid-cols-3 gap-4">
        <Label class="space-y-2">
          <span>ACK Timeout (s)</span>
          <Input type="number" bind:value={settings.GENERAL_ACK_TIMEOUT} />
        </Label>
        <Label class="space-y-2">
          <span>Retries</span>
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
    </div>
  </Card>

  <!-- Radio Settings -->
  <Card class="border-0 shadow-none">
    <h3 class="text-lg font-bold mb-3 text-gray-900 dark:text-white">Radio Settings</h3>
    <div class="space-y-4">
      <div class="space-y-2">
        <Label for="client-callsign">Client Callsign</Label>
        <div class="flex items-center space-x-2">
          <Input
            id="client-callsign"
            class="flex-grow"
            type="text"
            bind:value={settings.RADIO_CLIENT_CALLSIGN[0]}
            placeholder="Your Callsign"
            maxlength="6"
            oninput={(e) => e.target.value = e.target.value.toUpperCase()}
          />
          <span class="text-xl font-bold">-</span>
          <Select class="w-20" bind:value={settings.RADIO_CLIENT_CALLSIGN[1]}>
            {#each Array(16).fill().map((_, i) => i) as ssid}
              <option value={ssid}>{ssid}</option>
            {/each}
          </Select>
        </div>
      </div>
      <div class="space-y-2">
        <Label for="server-callsign">Server Callsign</Label>
        <div class="flex items-center space-x-2">
          <Input
            id="server-callsign"
            class="flex-grow"
            type="text"
            bind:value={settings.RADIO_HAMSTR_SERVER[0]}
            placeholder="Server Callsign"
            maxlength="6"
            oninput={(e) => e.target.value = e.target.value.toUpperCase()}
          />
          <span class="text-xl font-bold">-</span>
          <Select class="w-20" bind:value={settings.RADIO_HAMSTR_SERVER[1]}>
            {#each Array(16).fill().map((_, i) => i) as ssid}
              <option value={ssid}>{ssid}</option>
            {/each}
          </Select>
        </div>
      </div>
    </div>
  </Card>

  <!-- NOSTR Settings -->
  <Card class="border-0 shadow-none">
    <h3 class="text-lg font-bold mb-3 text-gray-900 dark:text-white">NOSTR Settings</h3>
    <Label class="space-y-2">
      <span>Default Note Request Count</span>
      <Input type="number" bind:value={settings.NOSTR_DEFAULT_NOTE_REQUEST_COUNT} placeholder="2" />
    </Label>
  </Card>

  <!-- Database -->
  <Card class="border-0 shadow-none">
    <h3 class="text-lg font-bold mb-3 text-gray-900 dark:text-white">Database</h3>
    <p class="text-sm text-gray-600 dark:text-gray-400 mb-3">
      Clear all locally stored notes. This cannot be undone.
    </p>
    <Button color="red" onclick={clearNotes}>Clear Notes</Button>
  </Card>

  <!-- Action Buttons -->
  <div class="flex justify-center space-x-4 pt-2">
    <Button color="primary" onclick={saveSettings}>Save Settings</Button>
    <Button color="alternative" onclick={resetToDefaults}>Reset to Defaults</Button>
  </div>

</div>