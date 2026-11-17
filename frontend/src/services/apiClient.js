/**
 * Typed HTTP client for DocuLens workspace API endpoints.
 */

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'API_ERROR', detail = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export function createApiClient(configOrFetch = {}) {
  const fetchImpl =
    typeof configOrFetch === 'function'
      ? configOrFetch
      : configOrFetch?.fetchImpl || globalThis.fetch;

  async function requestJson(url, options = {}) {
    let response;
    try {
      response = await fetchImpl(url, options);
    } catch (err) {
      throw new ApiError(err?.message || 'Network request failed.', {
        status: 0,
        code: 'NETWORK_ERROR',
      });
    }

    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = body?.detail;
      const message =
        (typeof detail === 'object' && detail?.message) ||
        (typeof detail === 'string' ? detail : null) ||
        body?.message ||
        `Request failed (${response.status})`;
      const code =
        (typeof detail === 'object' && detail?.code) ||
        body?.code ||
        `HTTP_${response.status}`;
      throw new ApiError(message, { status: response.status, code, detail: body });
    }
    return body;
  }

  function getToken(session) {
    return session?.document_token || session?.access_token || '';
  }

  return {
    async getStatus() {
      return requestJson('/api/status');
    },

    async uploadDocument(file) {
      const formData = new FormData();
      formData.append('file', file);
      return requestJson('/api/documents', {
        method: 'POST',
        body: formData,
      });
    },

    async deleteDocument(session) {
      if (!session?.document_id) return;
      try {
        await fetchImpl(`/api/documents/${encodeURIComponent(session.document_id)}`, {
          method: 'DELETE',
          headers: { 'X-Document-Token': getToken(session) },
        });
      } catch {
        // Ignore network errors during cleanup
      }
    },

    async askQuestion(session, question, history = [], options = {}) {
      const payload = { question };
      if (Array.isArray(history) && history.length > 0) {
        payload.history = history;
      }
      if (options && typeof options === 'object') {
        if (options.provider) payload.provider = options.provider;
        if (options.model) payload.model = options.model;
        if (options.effort) payload.effort = options.effort;
        if (typeof options.autoFixPrompt === 'boolean') {
          payload.auto_fix_prompt = options.autoFixPrompt;
        }
      }
      return requestJson(`/api/documents/${encodeURIComponent(session.document_id)}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Document-Token': getToken(session),
        },
        body: JSON.stringify(payload),
      });
    },

    async getPageText(session, pageNumber) {
      return requestJson(
        `/api/documents/${encodeURIComponent(session.document_id)}/pages/${pageNumber}`,
        {
          headers: { 'X-Document-Token': getToken(session) },
        },
      );
    },

    async getProviders() {
      return requestJson('/api/providers');
    },

    async addProviderKey({ provider = 'auto', apiKey = '', baseUrl = '', customModel = '' }) {
      const payload = {
        provider,
        api_key: apiKey,
      };
      if (baseUrl && baseUrl.trim()) {
        payload.base_url = baseUrl.trim();
      }
      if (customModel && customModel.trim()) {
        payload.custom_model = customModel.trim();
      }
      return requestJson('/api/providers/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    },

    async refreshProviderModels(providerId) {
      return requestJson(`/api/providers/${encodeURIComponent(providerId)}/refresh`, {
        method: 'POST',
      });
    },

    async removeProviderKey(providerId) {
      return requestJson(`/api/providers/${encodeURIComponent(providerId)}/key`, {
        method: 'DELETE',
      });
    },

    async selectProviderModel({ provider, model, effort }) {
      return requestJson('/api/providers/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model, effort }),
      });
    },

    async enhancePrompt(question) {
      return requestJson('/api/prompts/enhance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
    },
  };
}
