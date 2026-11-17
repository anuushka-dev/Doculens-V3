/**
 * Hamburger Menu (☰) Settings Drawer for managing Official & Third-Party AI API Keys,
 * auto-pulling live provider models, selecting active models, and configuring effort.
 */

import { createEl, getById } from '../utils/dom.js';
import { EFFORT_LEVELS, getCompanyBrand } from '../utils/logos.js';

export function createSettingsDrawer(
  doc,
  {
    store,
    apiClient,
    toast,
    onModelOrEffortChanged,
  } = {},
) {
  const menuToggle = getById(doc, 'menu-toggle');
  const settingsDrawer = getById(doc, 'settings-drawer');
  const drawerBackdrop = getById(doc, 'drawer-backdrop');
  const closeDrawerBtn = getById(doc, 'close-drawer');
  const providerSelect = getById(doc, 'provider-select');
  const apiKeyInput = getById(doc, 'api-key-input');
  const customEndpointDetails = getById(doc, 'custom-endpoint-details');
  const baseUrlGroup = getById(doc, 'base-url-group');
  const baseUrlInput = getById(doc, 'base-url-input');
  const customModelInput = getById(doc, 'custom-model-input');
  const saveKeyBtn = getById(doc, 'save-key-btn');
  const connectedProvidersList = getById(doc, 'connected-providers-list');
  const pulledModelsSearch = getById(doc, 'pulled-models-search');
  const pulledModelsList = getById(doc, 'pulled-models-list');
  const drawerEffortGroup = getById(doc, 'drawer-effort-group');
  const autoFixToggle = getById(doc, 'auto-fix-toggle');

  let searchQuery = '';

  function open() {
    store.setState({ settingsDrawerOpen: true });
    if (settingsDrawer) {
      settingsDrawer.hidden = false;
      settingsDrawer.setAttribute('aria-hidden', 'false');
    }
    if (drawerBackdrop) drawerBackdrop.hidden = false;
    if (menuToggle) menuToggle.setAttribute('aria-expanded', 'true');
    render();
  }

  function close() {
    store.setState({ settingsDrawerOpen: false });
    if (settingsDrawer) {
      settingsDrawer.hidden = true;
      settingsDrawer.setAttribute('aria-hidden', 'true');
    }
    if (drawerBackdrop) drawerBackdrop.hidden = true;
    if (menuToggle) menuToggle.setAttribute('aria-expanded', 'false');
  }

  function toggle() {
    if (store.getState().settingsDrawerOpen) {
      close();
    } else {
      open();
    }
  }

  function updateBaseUrlVisibility() {
    if (!providerSelect) return;
    const selected = providerSelect.value;
    const needsBaseUrl =
      selected === 'custom' ||
      selected === 'custom_anthropic' ||
      selected === 'ollama' ||
      selected === 'openrouter';
    if (baseUrlGroup) {
      baseUrlGroup.hidden = false;
    }
    if (customEndpointDetails && needsBaseUrl) {
      customEndpointDetails.open = true;
    }
    if (baseUrlInput) {
      if (selected === 'custom_anthropic') {
        baseUrlInput.placeholder = 'https://your-gateway.com (or https://vibi.top/v1)';
      } else if (selected === 'custom') {
        baseUrlInput.placeholder = 'https://your-gateway.com/v1 (e.g. https://vibi.top/v1)';
      } else if (selected === 'ollama') {
        baseUrlInput.placeholder = 'http://127.0.0.1:11434';
      } else {
        baseUrlInput.placeholder = 'https://api.deepinfra.com/v1/openai (optional override)';
      }
    }
  }

  function renderConnectedProviders(state) {
    if (!connectedProvidersList) return;
    connectedProvidersList.replaceChildren();

    const configured = (state.providers || []).filter((p) => p.configured);
    if (configured.length === 0) {
      connectedProvidersList.append(
        createEl(doc, 'div', {
          className: 'drawer-empty-note',
          text: 'No cloud API keys added yet. Paste any Official or Third-Party API key above to auto-pull all available models.',
        }),
      );
      return;
    }

    for (const prov of configured) {
      const brand = getCompanyBrand(prov.company || prov.id, prov.id);
      const badge = createEl(doc, 'span', {
        className: 'company-logo-badge',
        attributes: { 'data-company': brand.key },
      });
      badge.innerHTML = brand.svg;

      const info = createEl(doc, 'div', {
        className: 'provider-card-info',
        children: [
          createEl(doc, 'div', {
            className: 'provider-card-title',
            children: [
              createEl(doc, 'strong', { text: prov.name }),
              createEl(doc, 'span', {
                className: 'provider-model-count',
                text: `${(prov.models || []).length} models`,
              }),
            ],
          }),
          createEl(doc, 'span', {
            className: 'provider-masked-key',
            text: prov.masked_key || 'Connected',
          }),
        ],
      });

      const syncBtn = createEl(doc, 'button', {
        type: 'button',
        className: 'ghost-button small-btn',
        text: '↻ Sync',
      });
      syncBtn.addEventListener('click', async () => {
        syncBtn.disabled = true;
        syncBtn.textContent = 'Syncing…';
        try {
          const res = await apiClient.refreshProviderModels(prov.id);
          await hydrateProviders();
          toast?.show(`Synced ${res.model_count || 0} models from ${prov.name}.`);
        } catch (err) {
          toast?.show(err.message || 'Could not sync models.', { error: true });
        } finally {
          syncBtn.disabled = false;
          syncBtn.textContent = '↻ Sync';
        }
      });

      const removeBtn = createEl(doc, 'button', {
        type: 'button',
        className: 'ghost-button small-btn danger-btn',
        text: 'Remove',
      });
      removeBtn.addEventListener('click', async () => {
        removeBtn.disabled = true;
        try {
          const snap = await apiClient.removeProviderKey(prov.id);
          applyProviderSnapshot(snap);
          toast?.show(`Removed ${prov.name} API key.`);
        } catch (err) {
          toast?.show(err.message || 'Could not remove API key.', { error: true });
        } finally {
          removeBtn.disabled = false;
        }
      });

      const card = createEl(doc, 'div', {
        className: 'provider-card',
        children: [
          createEl(doc, 'div', { className: 'provider-card-main', children: [badge, info] }),
          createEl(doc, 'div', {
            className: 'provider-card-actions',
            children: [syncBtn, removeBtn],
          }),
        ],
      });
      connectedProvidersList.append(card);
    }
  }

  function renderPulledModels(state) {
    if (!pulledModelsList) return;
    pulledModelsList.replaceChildren();

    const allModels = state.availableModels || [];
    const q = searchQuery.trim().toLowerCase();
    const filtered = q
      ? allModels.filter(
          (m) =>
            m.id.toLowerCase().includes(q) ||
            (m.name || '').toLowerCase().includes(q) ||
            (m.provider_name || '').toLowerCase().includes(q) ||
            (m.company || '').toLowerCase().includes(q),
        )
      : allModels;

    if (filtered.length === 0) {
      pulledModelsList.append(
        createEl(doc, 'div', {
          className: 'drawer-empty-note',
          text: q ? 'No pulled models match your filter.' : 'No models available yet.',
        }),
      );
      return;
    }

    for (const item of filtered.slice(0, 80)) {
      const isSelected =
        item.id === state.activeModel && item.provider === state.activeProvider;
      const brand = getCompanyBrand(item.company || item.id, item.provider);

      const logoSpan = createEl(doc, 'span', {
        className: 'company-logo-badge',
        attributes: { 'data-company': brand.key },
      });
      logoSpan.innerHTML = brand.svg;

      const textCol = createEl(doc, 'div', {
        className: 'drawer-model-text',
        children: [
          createEl(doc, 'strong', { text: item.name || item.id }),
          createEl(doc, 'small', {
            text: `${brand.label} · via ${item.provider_name || item.provider}`,
          }),
        ],
      });

      const activeTag = createEl(doc, 'span', {
        className: 'drawer-model-check',
        text: isSelected ? '✓ Active' : 'Use',
      });

      const row = createEl(doc, 'button', {
        type: 'button',
        className: `drawer-model-item${isSelected ? ' active' : ''}`,
        children: [logoSpan, textCol, activeTag],
      });
      row.addEventListener('click', async () => {
        await selectModelAndEffort({
          provider: item.provider,
          model: item.id,
          effort: state.activeEffort,
        });
        toast?.show(`Selected ${item.name || item.id} (${brand.label})`);
      });
      pulledModelsList.append(row);
    }
  }

  function renderEffortButtons(state) {
    if (!drawerEffortGroup) return;
    drawerEffortGroup.replaceChildren();

    for (const level of EFFORT_LEVELS) {
      const isSelected = state.activeEffort === level.id;
      const iconWrap = createEl(doc, 'span', { className: 'effort-icon-wrap' });
      iconWrap.innerHTML = level.svg;

      const copy = createEl(doc, 'div', {
        className: 'drawer-effort-copy',
        children: [
          createEl(doc, 'strong', { text: level.shortLabel }),
          createEl(doc, 'small', { text: level.description }),
        ],
      });

      const btn = createEl(doc, 'button', {
        type: 'button',
        className: `drawer-effort-btn${isSelected ? ' active' : ''}`,
        children: [iconWrap, copy],
      });
      btn.addEventListener('click', async () => {
        await selectModelAndEffort({
          provider: state.activeProvider,
          model: state.activeModel,
          effort: level.id,
        });
        toast?.show(`Reasoning effort set to ${level.shortLabel}`);
      });
      drawerEffortGroup.append(btn);
    }
  }

  function render() {
    const state = store.getState();
    renderConnectedProviders(state);
    renderPulledModels(state);
    renderEffortButtons(state);
    if (autoFixToggle) {
      autoFixToggle.checked = Boolean(state.autoFixPrompt);
    }
  }

  function applyProviderSnapshot(snapshot) {
    if (!snapshot) return;
    const active = snapshot.active || {};
    const current = store.getState();
    const nextPatch = {
      providers: snapshot.providers || current.providers,
      availableModels: snapshot.available_models || current.availableModels,
    };
    if (active.provider) nextPatch.activeProvider = active.provider;
    if (active.provider_name) nextPatch.activeProviderName = active.provider_name;
    if (active.model) nextPatch.activeModel = active.model;
    if (active.model_name) nextPatch.activeModelName = active.model_name;
    if (active.company) nextPatch.activeCompany = active.company;
    if (active.effort) nextPatch.activeEffort = active.effort;

    store.setState(nextPatch);
    store.persistPreferences({
      provider: nextPatch.activeProvider || current.activeProvider,
      providerName: nextPatch.activeProviderName || current.activeProviderName,
      model: nextPatch.activeModel || current.activeModel,
      modelName: nextPatch.activeModelName || current.activeModelName,
      company: nextPatch.activeCompany || current.activeCompany,
      effort: nextPatch.activeEffort || current.activeEffort,
      autoFixPrompt: current.autoFixPrompt,
    });
    render();
    onModelOrEffortChanged?.(store.getState());
  }

  async function hydrateProviders() {
    try {
      const snapshot = await apiClient.getProviders();
      applyProviderSnapshot(snapshot);
    } catch {
      // Ignore if offline or in minimal test mocks
    }
  }

  async function selectModelAndEffort({ provider, model, effort }) {
    const state = store.getState();
    const nextProvider = provider || state.activeProvider;
    const nextModel = model || state.activeModel;
    const nextEffort = effort || state.activeEffort;
    const matchedModel = (state.availableModels || []).find(
      (m) => m.id === nextModel && (!provider || m.provider === nextProvider),
    );
    const brand = getCompanyBrand(
      matchedModel?.company || nextModel,
      matchedModel?.provider || nextProvider,
    );

    store.setState({
      activeProvider: matchedModel?.provider || nextProvider,
      activeProviderName: matchedModel?.provider_name || state.activeProviderName,
      activeModel: nextModel,
      activeModelName: matchedModel?.name || nextModel,
      activeCompany: matchedModel?.company || brand.label.toLowerCase(),
      activeEffort: nextEffort,
    });

    const updatedState = store.getState();
    store.persistPreferences({
      provider: updatedState.activeProvider,
      providerName: updatedState.activeProviderName,
      model: updatedState.activeModel,
      modelName: updatedState.activeModelName,
      company: updatedState.activeCompany,
      effort: updatedState.activeEffort,
      autoFixPrompt: updatedState.autoFixPrompt,
    });

    render();
    onModelOrEffortChanged?.(updatedState);

    try {
      const updated = await apiClient.selectProviderModel({
        provider: updatedState.activeProvider,
        model: updatedState.activeModel,
        effort: updatedState.activeEffort,
      });
      if (updated?.active) {
        applyProviderSnapshot({ active: updated.active });
      }
    } catch {
      // Keep local selection if endpoint is mocked
    }
  }

  async function handleSaveKey(event) {
    event?.preventDefault?.();
    if (!apiKeyInput) return;
    const rawKey = apiKeyInput.value.trim().replace(/^Bearer\s+/i, '');
    const selectedProvider = providerSelect ? providerSelect.value : 'auto';
    const rawBaseUrl = baseUrlInput ? baseUrlInput.value.trim() : '';
    const rawCustomModel = customModelInput ? customModelInput.value.trim() : '';
    const isCustomGateway =
      selectedProvider === 'custom' || selectedProvider === 'custom_anthropic';
    const isLocalNoAuth =
      selectedProvider === 'ollama' ||
      /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i.test(rawBaseUrl);

    if (isCustomGateway && !rawBaseUrl) {
      if (customEndpointDetails) customEndpointDetails.open = true;
      toast?.show('Please enter the Base URL of your custom 3rd-party API provider.', {
        error: true,
      });
      baseUrlInput?.focus?.();
      return;
    }

    if (!rawKey && !isLocalNoAuth) {
      toast?.show('Please enter an API key first.', { error: true });
      apiKeyInput.focus?.();
      return;
    }

    if (saveKeyBtn) {
      saveKeyBtn.disabled = true;
      saveKeyBtn.textContent = 'Pulling Models…';
    }
    try {
      const res = await apiClient.addProviderKey({
        provider: selectedProvider,
        apiKey: rawKey,
        baseUrl: rawBaseUrl,
        customModel: rawCustomModel,
      });
      apiKeyInput.value = '';
      if (customModelInput) customModelInput.value = '';
      if (Array.isArray(res.models) && res.models.length > 0) {
        const current = store.getState();
        const merged = [
          ...res.models,
          ...(current.availableModels || []).filter((m) => m.provider !== res.provider),
        ];
        store.setState({ availableModels: merged });
      }
      await hydrateProviders();
      toast?.show(
        `Connected ${res.provider_name || res.provider} · Auto-pulled ${res.model_count || (res.models || []).length} models!`,
      );
    } catch (err) {
      if (customEndpointDetails && (rawBaseUrl || selectedProvider === 'custom')) {
        customEndpointDetails.open = true;
      }
      toast?.show(err.message || 'Could not verify API key or pull models.', { error: true });
    } finally {
      if (saveKeyBtn) {
        saveKeyBtn.disabled = false;
        saveKeyBtn.textContent = 'Add Key & Auto-Pull Models';
      }
    }
  }

  menuToggle?.addEventListener('click', toggle);
  closeDrawerBtn?.addEventListener('click', close);
  drawerBackdrop?.addEventListener('click', close);
  providerSelect?.addEventListener('change', updateBaseUrlVisibility);
  customEndpointDetails?.addEventListener('click', (e) => {
    const presetBtn = e.target?.closest?.('.drawer-preset-btn');
    if (!presetBtn) return;
    const presetUrl = presetBtn.dataset?.presetUrl || '';
    const presetProvider = presetBtn.dataset?.presetProvider || 'custom';
    if (providerSelect) providerSelect.value = presetProvider;
    if (baseUrlInput) baseUrlInput.value = presetUrl;
    if (customEndpointDetails) customEndpointDetails.open = true;
    updateBaseUrlVisibility();
    if (presetUrl) {
      apiKeyInput?.focus?.();
    } else {
      baseUrlInput?.focus?.();
    }
  });
  saveKeyBtn?.addEventListener('click', handleSaveKey);
  apiKeyInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveKey(e);
    }
  });
  pulledModelsSearch?.addEventListener('input', (e) => {
    searchQuery = e.target.value || '';
    renderPulledModels(store.getState());
  });
  autoFixToggle?.addEventListener('change', (e) => {
    const checked = Boolean(e.target.checked);
    store.setState({ autoFixPrompt: checked });
    const st = store.getState();
    store.persistPreferences({
      provider: st.activeProvider,
      providerName: st.activeProviderName,
      model: st.activeModel,
      modelName: st.activeModelName,
      company: st.activeCompany,
      effort: st.activeEffort,
      autoFixPrompt: checked,
    });
    toast?.show(
      checked
        ? 'Smart Prompt Auto-Repair & Doubt Clarification enabled.'
        : 'Smart Prompt Auto-Repair disabled.',
    );
  });

  updateBaseUrlVisibility();
  render();

  return {
    open,
    close,
    toggle,
    render,
    hydrateProviders,
    selectModelAndEffort,
  };
}
