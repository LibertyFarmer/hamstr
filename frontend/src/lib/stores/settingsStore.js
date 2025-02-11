import { writable } from 'svelte/store';
import { baseURL } from '$lib/store';
import { get } from 'svelte/store';

function createSettingsStore() {
    const { subscribe, set, update } = writable({
        NOSTR_NPUB: ''
    });

    return {
        subscribe,
        fetchNPUB: async () => {
            try {
                const response = await fetch(`${get(baseURL)}/api/settings`);
                const data = await response.json();
                update(store => ({ ...store, NOSTR_NPUB: data.NOSTR_NPUB }));
            } catch (error) {
                console.error('Error fetching NOSTR_NPUB:', error);
            }
        },
        setNPUB: (value) => {
            update(store => ({ ...store, NOSTR_NPUB: value }));
        }
    };
}

export const settingsStore = createSettingsStore();
