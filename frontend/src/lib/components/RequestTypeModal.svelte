<script>
  import { Modal, Button, Radio } from 'flowbite-svelte';
  import { NoteRequestType } from '$lib/utils/enums';

  export let show = false;
  export let onClose = () => {};
  export let onSubmit = () => {};

  let selectedType = NoteRequestType.FOLLOWING;

  const requestTypes = [

    {
      type: NoteRequestType.FOLLOWING,
      label: 'Following Notes',
      description: 'Get recent post(s) from people you follow'
    },
    {
      type: NoteRequestType.GLOBAL,
      label: 'Global Notes',
      description: 'Get recent post(s) from the global feed(Yikes)'
    },
    {
      type: NoteRequestType.SPECIFIC_USER,
      label: 'My Own Notes',
      description: 'Get your own most recent NOSTR note(s)'
    }
  ];

  function handleSubmit() {
    onSubmit(selectedType);
    onClose();
  }
</script>

<Modal 
  bind:open={show} 
  size="xs" 
  autoclose={false}
  on:close={() => {
      onClose();  // Add this to handle X button clicks
  }}
>
  <div class="p-4">
      <h3 class="mb-4 text-xl font-medium text-gray-900 dark:text-white">
          What would you like to request from NOSTR?
      </h3>
      <div class="space-y-3">
          {#each requestTypes as type}
              <div class="flex items-center">
                  <Radio
                      bind:group={selectedType}
                      value={type.type}
                      class="peer"
                  />
                  <div class="ml-2">
                      <div class="text-sm font-medium text-gray-900 dark:text-white">
                          {type.label}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                          {type.description}
                      </div>
                  </div>
              </div>
          {/each}
      </div>
      <div class="flex justify-end space-x-2 mt-6">
          <Button color="alternative" on:click={onClose}>Cancel</Button>
          <Button color="primary" on:click={handleSubmit}>Get It!</Button>
      </div>
  </div>
</Modal>