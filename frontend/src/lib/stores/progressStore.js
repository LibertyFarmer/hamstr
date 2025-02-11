import { writable } from 'svelte/store';

function createProgressStore() {
    const { subscribe, set, update } = writable({
        progress: 0,
        isComplete: false,
        message: '',
        operation: '' // 'send' or 'receive'
    });

    return {
        subscribe,
        updateProgress: (data) => update(state => {
            if (data.progress !== undefined) {
                state.progress = data.progress;
            }
            if (data.message !== undefined) {
                state.message = data.message;
            }
            if (data.operation !== undefined) {
                state.operation = data.operation;
            }
            if (data.progress === 100) {
                state.isComplete = true;
                state.message = state.operation === 'send' ? 'Packet send complete' : 'All packets received';
            }
            return state;
        }),
        reset: () => set({
            progress: 0,
            isComplete: false,
            message: '',
            operation: ''
        })
    };
}

export const progressStore = createProgressStore();