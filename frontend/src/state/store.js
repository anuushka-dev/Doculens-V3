/**
 * Reactive workspace state store with pub/sub and preference persistence.
 */

import { DEFAULT_AI_PREFS, DEFAULT_LIMITS, PREFS_STORAGE_KEY } from '../config/constants.js';

export function createStore(initialOverrides = {}) {
  let state = {
    limits: { ...DEFAULT_LIMITS },
    busy: false,
    session: null,
    expired: false,
    expiresAtMs: null,
    originalURL: null,
    status: null,
    messages: [],
    activeProvider: DEFAULT_AI_PREFS.provider,
    activeProviderName: DEFAULT_AI_PREFS.providerName,
    activeModel: DEFAULT_AI_PREFS.model,
    activeModelName: DEFAULT_AI_PREFS.modelName,
    activeCompany: DEFAULT_AI_PREFS.company,
    activeEffort: DEFAULT_AI_PREFS.effort,
    autoFixPrompt: DEFAULT_AI_PREFS.autoFixPrompt,
    providers: [],
    availableModels: [],
    settingsDrawerOpen: false,
    ...initialOverrides,
  };

  const listeners = new Set();

  function getState() {
    return state;
  }

  function setState(patch) {
    const nextPatch = typeof patch === 'function' ? patch(state) : patch;
    state = { ...state, ...nextPatch };
    for (const listener of listeners) {
      listener(state);
    }
    return state;
  }

  function subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  function persistPreferences(prefs, storage = globalThis.localStorage) {
    try {
      if (!storage) return;
      storage.setItem(PREFS_STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      // Ignore storage quota errors
    }
  }

  function readPersistedPreferences(storage = globalThis.localStorage) {
    try {
      if (!storage) return null;
      const raw = storage.getItem(PREFS_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  return {
    getState,
    setState,
    subscribe,
    persistPreferences,
    readPersistedPreferences,
  };
}

export const createWorkspaceStore = createStore;
