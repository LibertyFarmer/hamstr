import { writable } from 'svelte/store';
import { browser } from '$app/environment';

function createPersistentStore(key, startValue) {
    // Get stored value only if in browser
    const storedValue = browser ? localStorage.getItem(key) : null;
    const store = writable(storedValue ? JSON.parse(storedValue) : startValue);
    
    // Only subscribe to changes if in browser
    if (browser) {
        store.subscribe(value => {
            localStorage.setItem(key, JSON.stringify(value));
        });
    }

    return store;
}

export const isRequestingNotes = createPersistentStore('isRequestingNotes', false);