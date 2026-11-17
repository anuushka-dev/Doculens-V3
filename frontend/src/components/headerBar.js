/**
 * Header status pill and retrieval mode indicator component.
 */

import { getById } from '../utils/dom.js';

export function createHeaderBar(doc, { onCheckStatus } = {}) {
  const connectionEl = getById(doc, 'connection');
  const modePillEl = getById(doc, 'mode-pill');

  function renderStatus(status, activeModelOverride = '') {
    if (!connectionEl) return;
    const modelName = activeModelOverride || status?.active_model || status?.model || status?.ollama_model || 'qwen3.5:4b';
    const ready = Boolean(status?.model_ready ?? status?.ollama_reachable);

    connectionEl.classList.toggle('ready', ready);
    const label = connectionEl.querySelector('span');
    if (label) {
      label.textContent = ready
        ? `${modelName} · ready`
        : `${modelName} · start Ollama`;
    }

    if (modePillEl && status?.retrieval_mode) {
      const isHybrid = status.retrieval_mode === 'hybrid';
      modePillEl.textContent = isHybrid ? 'Hybrid search' : 'Lexical mode';
      modePillEl.title = isHybrid
        ? 'Semantic embeddings + keyword & phrase retrieval active'
        : 'Exact keyword & phrase retrieval active (semantic embeddings offline)';
      modePillEl.classList.toggle('lexical', !isHybrid);
    }
  }

  if (connectionEl) {
    connectionEl.addEventListener('click', () => onCheckStatus?.());
  }

  return { renderStatus };
}
