/**
 * Question composer form, character counter, keyboard shortcuts,
 * bottom-bar AI Model Selector (with Company Logo), Effort Selector,
 * and Smart Prompt Enhancer.
 */

import { MAX_QUESTION_LENGTH } from '../config/constants.js';
import { createEl, getById } from '../utils/dom.js';
import { EFFORT_LEVELS, getCompanyBrand, getEffortMeta } from '../utils/logos.js';

export function createComposer(
  doc,
  {
    onSubmit,
    onSelectModelAndEffort,
    onOpenSettingsDrawer,
    onEnhancePrompt,
  } = {},
) {
  const askForm = getById(doc, 'ask-form');
  const questionEl = getById(doc, 'question');
  const charCountEl = getById(doc, 'char-count');
  const sendBtn = getById(doc, 'send');

  const composerModelBtn = getById(doc, 'composer-model-btn');
  const composerModelLogo = getById(doc, 'composer-model-logo');
  const composerModelLabel = getById(doc, 'composer-model-label');
  const modelPopover = getById(doc, 'model-popover');
  const popoverModelSearch = getById(doc, 'popover-model-search');
  const popoverModelList = getById(doc, 'popover-model-list');
  const popoverAddKeyBtn = getById(doc, 'popover-add-key-btn');

  const composerEffortBtn = getById(doc, 'composer-effort-btn');
  const composerEffortIcon = getById(doc, 'composer-effort-icon');
  const composerEffortLabel = getById(doc, 'composer-effort-label');
  const effortPopover = getById(doc, 'effort-popover');
  const popoverEffortList = getById(doc, 'popover-effort-list');

  const enhancePromptBtn = getById(doc, 'enhance-prompt-btn');

  let canAsk = false;
  let modelFilter = '';
  let currentState = {
    activeProvider: 'ollama',
    activeProviderName: 'Ollama Local',
    activeModel: 'qwen3.5:4b',
    activeModelName: 'qwen3.5:4b',
    activeCompany: 'qwen',
    activeEffort: 'medium',
    availableModels: [],
  };

  function updateCounter() {
    if (!questionEl || !charCountEl) return;
    const len = questionEl.value.length;
    charCountEl.textContent = `${len} / ${MAX_QUESTION_LENGTH}`;
    charCountEl.classList.toggle('near-limit', len >= MAX_QUESTION_LENGTH * 0.9);
    const hasText = Boolean(questionEl.value.trim());
    if (sendBtn) sendBtn.disabled = !canAsk || !hasText;
    if (enhancePromptBtn) enhancePromptBtn.disabled = !canAsk || !hasText;
  }

  function setEnabled(enabled, placeholder = '') {
    canAsk = Boolean(enabled);
    if (questionEl) {
      questionEl.disabled = !canAsk;
      if (placeholder) {
        questionEl.placeholder = placeholder;
      } else {
        questionEl.placeholder = canAsk
          ? 'Ask a question about your PDF (English or Hinglish — auto-repaired & cited)…'
          : 'Upload a PDF to start asking questions...';
      }
    }
    updateCounter();
  }

  function setValue(text) {
    if (!questionEl) return;
    questionEl.value = text;
    updateCounter();
  }

  function clear() {
    setValue('');
  }

  function focus() {
    questionEl?.focus?.();
  }

  function closePopovers() {
    if (modelPopover) modelPopover.hidden = true;
    if (effortPopover) effortPopover.hidden = true;
    composerModelBtn?.setAttribute('aria-expanded', 'false');
    composerEffortBtn?.setAttribute('aria-expanded', 'false');
  }

  function renderModelPopoverList() {
    if (!popoverModelList) return;
    popoverModelList.replaceChildren();

    const activeModel = currentState.activeModel || 'qwen3.5:4b';
    const activeProvider = currentState.activeProvider || 'ollama';
    const models =
      Array.isArray(currentState.availableModels) && currentState.availableModels.length > 0
        ? currentState.availableModels
        : [
            {
              id: activeModel,
              name: currentState.activeModelName || activeModel,
              provider: activeProvider,
              provider_name: currentState.activeProviderName || 'Local / Default',
              company: currentState.activeCompany || '',
            },
          ];

    const q = modelFilter.trim().toLowerCase();
    const filtered = q
      ? models.filter(
          (m) =>
            m.id.toLowerCase().includes(q) ||
            (m.name || '').toLowerCase().includes(q) ||
            (m.provider_name || '').toLowerCase().includes(q) ||
            (m.company || '').toLowerCase().includes(q),
        )
      : models;

    if (filtered.length === 0) {
      popoverModelList.append(
        createEl(doc, 'div', {
          className: 'popover-empty',
          text: 'No matching models. Add an API key in ☰ Models & Keys to auto-pull models.',
        }),
      );
      return;
    }

    for (const item of filtered.slice(0, 60)) {
      const isCurrent =
        item.id === activeModel && (!item.provider || item.provider === activeProvider);
      const brand = getCompanyBrand(item.company || item.id, item.provider);

      const iconSpan = createEl(doc, 'span', {
        className: 'company-logo-badge small',
        attributes: { 'data-company': brand.key },
      });
      iconSpan.innerHTML = brand.svg;

      const meta = createEl(doc, 'div', {
        className: 'popover-option-meta',
        children: [
          createEl(doc, 'strong', { text: item.name || item.id }),
          createEl(doc, 'small', {
            text: `${brand.label} · ${item.provider_name || item.provider}`,
          }),
        ],
      });

      const check = createEl(doc, 'span', {
        className: 'popover-option-check',
        text: isCurrent ? '✓' : '',
      });

      const option = createEl(doc, 'button', {
        type: 'button',
        className: `popover-option${isCurrent ? ' active' : ''}`,
        children: [iconSpan, meta, check],
      });

      option.addEventListener('click', () => {
        closePopovers();
        onSelectModelAndEffort?.({
          provider: item.provider,
          model: item.id,
          effort: currentState.activeEffort,
        });
      });
      popoverModelList.append(option);
    }
  }

  function renderEffortPopoverList() {
    if (!popoverEffortList) return;
    popoverEffortList.replaceChildren();

    const activeEffort = currentState.activeEffort || 'medium';
    for (const level of EFFORT_LEVELS) {
      const isCurrent = level.id === activeEffort;
      const iconSpan = createEl(doc, 'span', { className: 'effort-icon-badge' });
      iconSpan.innerHTML = level.svg;

      const meta = createEl(doc, 'div', {
        className: 'popover-option-meta',
        children: [
          createEl(doc, 'strong', { text: level.shortLabel }),
          createEl(doc, 'small', { text: level.description }),
        ],
      });

      const check = createEl(doc, 'span', {
        className: 'popover-option-check',
        text: isCurrent ? '✓' : '',
      });

      const option = createEl(doc, 'button', {
        type: 'button',
        className: `popover-option${isCurrent ? ' active' : ''}`,
        children: [iconSpan, meta, check],
      });

      option.addEventListener('click', () => {
        closePopovers();
        onSelectModelAndEffort?.({
          provider: currentState.activeProvider,
          model: currentState.activeModel,
          effort: level.id,
        });
      });
      popoverEffortList.append(option);
    }
  }

  function renderSelectors(nextState = {}) {
    currentState = { ...currentState, ...nextState };
    const activeModel = currentState.activeModel || 'qwen3.5:4b';
    const activeProvider = currentState.activeProvider || 'ollama';
    const brand = getCompanyBrand(currentState.activeCompany || activeModel, activeProvider);
    const effortMeta = getEffortMeta(currentState.activeEffort || 'medium');

    if (composerModelLogo) {
      composerModelLogo.setAttribute('data-company', brand.key);
      composerModelLogo.innerHTML = brand.svg;
      composerModelLogo.setAttribute('title', brand.label);
    }
    if (composerModelLabel) {
      composerModelLabel.textContent = currentState.activeModelName || activeModel;
    }
    if (composerEffortIcon) {
      composerEffortIcon.innerHTML = effortMeta.svg;
    }
    if (composerEffortLabel) {
      composerEffortLabel.textContent = effortMeta.label;
    }

    renderModelPopoverList();
    renderEffortPopoverList();
  }

  if (questionEl) {
    questionEl.addEventListener('input', updateCounter);
    questionEl.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        if (sendBtn && !sendBtn.disabled) {
          askForm?.dispatchEvent(new doc.defaultView.Event('submit', { cancelable: true }));
        }
      }
    });
  }

  if (askForm) {
    askForm.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!canAsk || !questionEl) return;
      const raw = questionEl.value;
      closePopovers();
      onSubmit?.(raw);
    });
  }

  composerModelBtn?.addEventListener('click', (event) => {
    event.stopPropagation();
    const willOpen = modelPopover ? modelPopover.hidden : false;
    closePopovers();
    if (modelPopover && willOpen) {
      modelPopover.hidden = false;
      composerModelBtn.setAttribute('aria-expanded', 'true');
      renderModelPopoverList();
      popoverModelSearch?.focus?.();
    }
  });

  composerEffortBtn?.addEventListener('click', (event) => {
    event.stopPropagation();
    const willOpen = effortPopover ? effortPopover.hidden : false;
    closePopovers();
    if (effortPopover && willOpen) {
      effortPopover.hidden = false;
      composerEffortBtn.setAttribute('aria-expanded', 'true');
      renderEffortPopoverList();
    }
  });

  popoverModelSearch?.addEventListener('input', (event) => {
    modelFilter = event.target.value || '';
    renderModelPopoverList();
  });

  popoverModelSearch?.addEventListener('click', (event) => {
    event.stopPropagation();
  });

  popoverAddKeyBtn?.addEventListener('click', (event) => {
    event.stopPropagation();
    closePopovers();
    onOpenSettingsDrawer?.();
  });

  enhancePromptBtn?.addEventListener('click', async (event) => {
    event.stopPropagation();
    const raw = questionEl?.value?.trim();
    if (!raw || !onEnhancePrompt) return;
    enhancePromptBtn.disabled = true;
    try {
      await onEnhancePrompt(raw);
    } finally {
      updateCounter();
    }
  });

  doc.addEventListener('click', (event) => {
    if (
      modelPopover &&
      !modelPopover.hidden &&
      !modelPopover.contains(event.target) &&
      !composerModelBtn?.contains(event.target)
    ) {
      closePopovers();
    }
    if (
      effortPopover &&
      !effortPopover.hidden &&
      !effortPopover.contains(event.target) &&
      !composerEffortBtn?.contains(event.target)
    ) {
      closePopovers();
    }
  });

  renderSelectors();

  return {
    setEnabled,
    setValue,
    clear,
    focus,
    renderSelectors,
    closePopovers,
  };
}
