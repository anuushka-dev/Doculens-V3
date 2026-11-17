/**
 * DocuLens Workspace Application Orchestrator.
 * Connects modular UI components, reactive state store, and backend API service.
 */

import { createComposer } from './components/composer.js';
import { createConversation } from './components/conversation.js';
import { createHeaderBar } from './components/headerBar.js';
import { createSettingsDrawer } from './components/settingsDrawer.js';
import { createSourceModal } from './components/sourceModal.js';
import { createToastManager } from './components/toast.js';
import { createUploadSidebar } from './components/uploadSidebar.js';
import { DEFAULT_LIMITS, MAX_HISTORY_TURNS } from './config/constants.js';
import { ApiError, createApiClient } from './services/apiClient.js';
import { createStore } from './state/store.js';
import { buildMarkdownTranscript, copyToClipboard, getById } from './utils/dom.js';
import { validatePdfFile, validateQuestionText } from './utils/validation.js';

export function createDocuLensApp({
  doc = globalThis.document,
  win = globalThis.window,
  fetchImpl = globalThis.fetch,
} = {}) {
  const store = createStore();
  const apiClient = createApiClient({ fetchImpl });
  const toast = createToastManager(doc);

  // Hydrate persisted AI preferences if available
  const savedPrefs = store.readPersistedPreferences(win?.localStorage);
  if (savedPrefs && typeof savedPrefs === 'object') {
    store.setState({
      activeProvider: savedPrefs.provider || 'ollama',
      activeProviderName: savedPrefs.providerName || 'Ollama Local',
      activeModel: savedPrefs.model || 'qwen3.5:4b',
      activeModelName: savedPrefs.modelName || savedPrefs.model || 'qwen3.5:4b',
      activeCompany: savedPrefs.company || 'qwen',
      activeEffort: savedPrefs.effort || 'medium',
      autoFixPrompt:
        typeof savedPrefs.autoFixPrompt === 'boolean' ? savedPrefs.autoFixPrompt : true,
    });
  }

  const headerBar = createHeaderBar(doc, {
    onCheckStatus: () => refreshStatus(),
  });

  const uploadSidebar = createUploadSidebar(doc, {
    onFileSelected: (file) => handleFileUpload(file),
    onRemove: () => handleRemoveDocument(),
    onExpired: () => handleSessionExpired(),
  });

  const sourceModal = createSourceModal(doc, {
    onFetchPage: async (pageNumber) => {
      const { session } = store.getState();
      if (!session) throw new Error('No active document session.');
      return apiClient.getPageText(session, pageNumber);
    },
    onCopyPage: async (text) => {
      const copied = await copyToClipboard(text, win);
      toast.show(
        copied ? 'Page text copied to clipboard.' : 'Could not copy page text.',
        { error: !copied },
      );
    },
  });

  let composer;

  const settingsDrawer = createSettingsDrawer(doc, {
    store,
    apiClient,
    toast,
    onModelOrEffortChanged: (state) => {
      headerBar.renderStatus(
        {
          ...(state.status || {}),
          model: state.activeModel,
          model_ready:
            state.activeProvider !== 'ollama'
              ? true
              : Boolean(state.status?.model_ready ?? state.status?.ollama_reachable),
        },
        state.activeModel,
      );
      composer?.renderSelectors(state);
    },
  });

  const conversation = createConversation(doc, {
    onCitationClick: (citation) => {
      const { session, originalURL } = store.getState();
      sourceModal.open({ citation, session, originalURL });
    },
    onPromptSelect: (promptText) => {
      composer.setValue(promptText);
      composer.focus();
    },
    onAskFollowUp: (clarifiedQuestion) => {
      handleAskQuestion(clarifiedQuestion);
    },
    onCopyAnswer: async (text) => {
      const copied = await copyToClipboard(text, win);
      toast.show(
        copied ? 'Answer copied to clipboard.' : 'Could not copy answer.',
        { error: !copied },
      );
    },
    onClearChat: () => {
      store.setState({ messages: [] });
      conversation.clear();
      const { session, expired, busy } = store.getState();
      conversation.renderStarterPrompts(Boolean(session && !expired), busy);
      toast.show('Conversation cleared.');
    },
    onExportChat: async () => {
      const { session, messages } = store.getState();
      if (!messages.length) return;
      const md = buildMarkdownTranscript(session, messages);
      const copied = await copyToClipboard(md, win);
      toast.show(
        copied
          ? 'Conversation transcript copied as Markdown.'
          : 'Could not copy transcript.',
        { error: !copied },
      );
    },
  });

  async function handleEnhancePrompt(rawQuestion) {
    try {
      const res = await apiClient.enhancePrompt(rawQuestion);
      const improved = res?.enhanced || res?.enhanced_question;
      if (improved && improved !== rawQuestion) {
        composer.setValue(improved);
        toast.show('✨ Prompt polished for clearer evidence retrieval.');
      } else {
        toast.show('✨ Prompt is already clear and ready!');
      }
    } catch {
      toast.show('Could not enhance prompt right now.', { error: true });
    }
  }

  composer = createComposer(doc, {
    onSubmit: (rawText) => handleAskQuestion(rawText),
    onSelectModelAndEffort: (selection) => {
      settingsDrawer.selectModelAndEffort(selection);
    },
    onOpenSettingsDrawer: () => {
      settingsDrawer.open();
    },
    onEnhancePrompt: handleEnhancePrompt,
  });

  function syncUiState() {
    const state = store.getState();
    const canAsk = Boolean(state.session && !state.expired && !state.busy);
    uploadSidebar.setBusy(state.busy);
    composer.setEnabled(
      canAsk,
      state.expired
        ? 'Session expired. Upload the PDF again to ask questions.'
        : state.session
          ? 'Ask a question about your PDF (English or Hinglish — auto-repaired & cited)…'
          : 'Upload a PDF to start asking questions...',
    );
    composer.renderSelectors(state);
    conversation.renderStarterPrompts(Boolean(state.session && !state.expired), state.busy);
  }

  function revokeOriginalUrl() {
    const { originalURL } = store.getState();
    if (originalURL && win?.URL?.revokeObjectURL) {
      win.URL.revokeObjectURL(originalURL);
    }
  }

  function handleSessionExpired(message = 'Session expired. Please upload the PDF again.') {
    const { session } = store.getState();
    store.setState({ expired: true, expiresAtMs: null });
    uploadSidebar.renderSession(session, { expired: true });
    uploadSidebar.setStatus(message, true);
    syncUiState();
  }

  async function refreshStatus() {
    try {
      const status = await apiClient.getStatus();
      const current = store.getState();
      const limits = {
        max_upload_bytes: status.max_upload_bytes || DEFAULT_LIMITS.max_upload_bytes,
        max_pdf_pages: status.max_pdf_pages || DEFAULT_LIMITS.max_pdf_pages,
        session_ttl_seconds: status.session_ttl_seconds || DEFAULT_LIMITS.session_ttl_seconds,
      };
      const activeModel =
        status.active_model || status.model || status.ollama_model || current.activeModel;
      const nextPatch = {
        status,
        limits,
        activeModel,
        activeModelName:
          status.active_model_name ||
          status.active_model ||
          status.model ||
          status.ollama_model ||
          current.activeModelName,
        activeProvider: status.active_provider || current.activeProvider,
        activeProviderName: status.active_provider_name || current.activeProviderName,
        activeCompany: status.active_company || current.activeCompany,
        activeEffort: status.active_effort || current.activeEffort,
      };
      if (Array.isArray(status.available_models) && status.available_models.length > 0) {
        nextPatch.availableModels = status.available_models;
      }
      store.setState(nextPatch);
      headerBar.renderStatus(status, activeModel);
      uploadSidebar.renderLimits(limits);
      composer.renderSelectors(store.getState());
    } catch {
      headerBar.renderStatus({ model: 'offline', model_ready: false });
    }
  }

  async function handleFileUpload(file) {
    const { limits, session } = store.getState();
    const validation = validatePdfFile(file, limits);
    if (!validation.valid) {
      uploadSidebar.setStatus(validation.message, true);
      uploadSidebar.clearFileInput();
      return;
    }

    store.setState({ busy: true });
    syncUiState();
    uploadSidebar.setStatus('Reading and indexing PDF pages…');

    try {
      if (session?.document_id) {
        await apiClient.deleteDocument(session);
      }
      revokeOriginalUrl();
      const nextOriginalUrl = win?.URL?.createObjectURL ? win.URL.createObjectURL(file) : null;
      const uploaded = await apiClient.uploadDocument(file);
      const ttlSeconds = uploaded.expires_in_seconds || limits.session_ttl_seconds || 3600;
      const expiresAtMs = Date.now() + ttlSeconds * 1000;

      store.setState({
        session: uploaded,
        expired: false,
        expiresAtMs,
        originalURL: nextOriginalUrl,
        messages: [],
      });
      sourceModal.close();
      conversation.clear();
      uploadSidebar.renderSession(uploaded, { expired: false, expiresAtMs });
      const fastNote = uploaded.fast_path_eligible ? ' · ⚡ Short-PDF Fast Path' : '';
      uploadSidebar.setStatus(
        `Indexed ${uploaded.page_count} pages into ${uploaded.chunk_count} searchable passages${fastNote}.`,
      );
      toast.show(`Indexed ${uploaded.filename}`);
    } catch (error) {
      const msg = error instanceof ApiError ? error.message : 'Could not index that PDF.';
      uploadSidebar.setStatus(msg, true);
      toast.show(msg, { error: true });
    } finally {
      uploadSidebar.clearFileInput();
      store.setState({ busy: false });
      syncUiState();
      if (store.getState().session && !store.getState().expired) {
        composer.focus();
      }
    }
  }

  async function handleRemoveDocument() {
    const { session } = store.getState();
    store.setState({ busy: true });
    syncUiState();
    try {
      if (session?.document_id) {
        await apiClient.deleteDocument(session);
      }
    } finally {
      revokeOriginalUrl();
      sourceModal.close();
      conversation.clear();
      composer.clear();
      store.setState({
        busy: false,
        session: null,
        expired: false,
        expiresAtMs: null,
        originalURL: null,
        messages: [],
      });
      uploadSidebar.renderSession(null);
      uploadSidebar.setStatus('');
      syncUiState();
    }
  }

  async function handleAskQuestion(rawQuestion) {
    const state = store.getState();
    if (!state.session || state.expired || state.busy) return;

    const check = validateQuestionText(rawQuestion);
    if (!check.valid) {
      uploadSidebar.setStatus(check.message, true);
      return;
    }

    const questionText = check.question;
    const priorHistory = state.messages
      .slice(-MAX_HISTORY_TURNS)
      .map((m) => ({ role: m.role, content: m.text }));

    store.setState({ busy: true });
    composer.clear();
    syncUiState();

    conversation.appendUserQuestion(questionText);
    const pendingCard = conversation.appendPendingAnswer({
      provider: state.activeProvider,
      model: state.activeModel,
      company: state.activeCompany,
      effort: state.activeEffort,
    });

    try {
      const answerData = await apiClient.askQuestion(
        state.session,
        questionText,
        priorHistory,
        {
          provider: state.activeProvider,
          model: state.activeModel,
          effort: state.activeEffort,
          autoFixPrompt: state.autoFixPrompt,
        },
      );
      conversation.resolveAnswer(pendingCard, answerData, {
        aiContext: {
          provider: state.activeProvider,
          model: state.activeModel,
          company: state.activeCompany,
          effort: state.activeEffort,
        },
      });
      store.setState((prev) => ({
        messages: [
          ...prev.messages,
          { role: 'user', text: questionText },
          {
            role: 'assistant',
            status: answerData.status,
            text: answerData.answer || '',
            citations: answerData.citations || [],
          },
        ],
      }));
    } catch (error) {
      if (error instanceof ApiError && (error.status === 404 || error.status === 403)) {
        conversation.resolveError(pendingCard, error.message);
        handleSessionExpired(error.message);
        return;
      }
      const msg = error instanceof ApiError ? error.message : 'Request failed.';
      conversation.resolveError(pendingCard, msg);
      toast.show(msg, { error: true });
    } finally {
      store.setState({ busy: false });
      syncUiState();
      if (store.getState().session && !store.getState().expired) {
        composer.focus();
      }
    }
  }

  function handleGlobalKeydown(event) {
    const questionEl = getById(doc, 'question');
    const dialogEl = getById(doc, 'source-dialog');
    if (event.key === '/' && doc.activeElement !== questionEl && !dialogEl?.open) {
      const tag = doc.activeElement?.tagName;
      if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
        const { session, expired } = store.getState();
        if (session && !expired) {
          event.preventDefault();
          composer.focus();
        }
      }
    }
    if (event.key === 'Escape' && store.getState().settingsDrawerOpen) {
      settingsDrawer.close();
    }
  }

  doc.addEventListener('keydown', handleGlobalKeydown);

  uploadSidebar.renderLimits(store.getState().limits);
  syncUiState();

  const readyPromise = Promise.all([
    refreshStatus(),
    settingsDrawer.hydrateProviders(),
  ]).then(() => {});

  function destroy() {
    doc.removeEventListener('keydown', handleGlobalKeydown);
    uploadSidebar.destroy();
    toast.destroy();
    revokeOriginalUrl();
  }

  return {
    store,
    apiClient,
    settingsDrawer,
    readyPromise,
    destroy,
  };
}

export const initWorkspaceApp = createDocuLensApp;

if (
  typeof document !== 'undefined' &&
  document.getElementById('ask-form') &&
  !globalThis.__DOCULENS_TEST_ENV__
) {
  createDocuLensApp();
}
