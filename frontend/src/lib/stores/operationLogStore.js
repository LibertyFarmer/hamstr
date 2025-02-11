// src/lib/stores/operationLogStore.js
import { writable } from 'svelte/store';

function createOperationLogStore() {
    const { subscribe, set, update } = writable([]);

    return {
        subscribe,
        addLog: (log) => {
            update(logs => {
                // Keep all logs for the current operation
                const newLogs = [...logs, log];
                return newLogs;
            });
        },
        clear: () => {
            set([]);
        }
    };
}

export const operationLogStore = createOperationLogStore();