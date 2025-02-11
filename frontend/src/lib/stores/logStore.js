import { writable } from 'svelte/store';

function createLogStore() {
    const { subscribe, set, update } = writable([]);

    // Load logs from localStorage on initialization
    if (typeof window !== 'undefined') {
        const storedLogs = localStorage.getItem('logs');
        if (storedLogs) {
            set(JSON.parse(storedLogs));
        }
    }

    return {
        subscribe,
        addLog: (log) => {
            update(logs => {
                const newLogs = [log, ...logs].slice(0, 100); // Keep only the latest 100 logs
                if (typeof window !== 'undefined') {
                    localStorage.setItem('logs', JSON.stringify(newLogs));
                }
                return newLogs;
            });
        },
        clear: () => {
            set([]);
            if (typeof window !== 'undefined') {
                localStorage.removeItem('logs');
            }
        },
        loadFromLocalStorage: () => {
            if (typeof window !== 'undefined') {
                const storedLogs = localStorage.getItem('logs');
                if (storedLogs) {
                    set(JSON.parse(storedLogs));
                }
            }
        }
    };
}

export const logStore = createLogStore();