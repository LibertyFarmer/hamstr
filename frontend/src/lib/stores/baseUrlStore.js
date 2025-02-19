import { writable } from 'svelte/store';
import { browser } from '$app/environment';

// Default to development URL
let apiBase = 'http://localhost:5000';

// Only try to use window.location if we're in the browser
if (browser) {
    apiBase = import.meta.env.DEV ? 'http://localhost:5000' : window.location.origin;
}

export const baseURL = writable(apiBase);