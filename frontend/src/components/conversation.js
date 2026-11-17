/**
 * Conversation stream, starter prompt chips, answer cards, citation buttons,
 * interactive doubt/clarification chips, and markdown transcript export.
 */

import { STARTER_PROMPTS } from '../config/constants.js';
import { createEl, getById } from '../utils/dom.js';
import { getCompanyBrand, getEffortMeta } from '../utils/logos.js';

export function createConversation(
  doc,
  {
    onCitationClick,
    onPromptSelect,
    onCopyAnswer,
    onClearChat,
    onExportChat,
    onAskFollowUp,
  } = {},
) {
  const conversationEl = getById(doc, 'conversation');
  const welcomeEl = getById(doc, 'welcome');
  const starterPromptsEl = getById(doc, 'starter-prompts');
  const clearChatBtn = getById(doc, 'clear-chat');
  const exportChatBtn = getById(doc, 'export-chat');

  function syncToolbarButtons() {
    const hasMessages = Boolean(conversationEl?.querySelector('.message'));
    if (clearChatBtn) clearChatBtn.hidden = !hasMessages;
    if (exportChatBtn) exportChatBtn.hidden = !hasMessages;
  }

  function renderStarterPrompts(visible, disabled = false) {
    if (!starterPromptsEl) return;
    starterPromptsEl.replaceChildren();
    starterPromptsEl.hidden = !visible;
    if (!visible) return;

    for (const promptText of STARTER_PROMPTS) {
      const chip = createEl(doc, 'button', {
        type: 'button',
        className: 'starter-chip',
        text: promptText,
      });
      chip.disabled = disabled;
      chip.addEventListener('click', () => onPromptSelect?.(promptText));
      starterPromptsEl.append(chip);
    }
  }

  function appendUserQuestion(questionText) {
    if (welcomeEl) welcomeEl.hidden = true;
    const card = createEl(doc, 'article', {
      className: 'message question-card',
      children: [
        createEl(doc, 'span', { className: 'role-label', text: 'You' }),
        createEl(doc, 'p', { text: questionText }),
      ],
    });
    conversationEl?.append(card);
    syncToolbarButtons();
    card.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
    return card;
  }

  function appendPendingAnswer(aiContext = {}) {
    const brand = getCompanyBrand(
      aiContext.company || aiContext.model,
      aiContext.provider,
    );
    const effortMeta = getEffortMeta(aiContext.effort || 'medium');

    const card = createEl(doc, 'article', {
      className: 'message answer-card pending thinking',
      children: [
        createEl(doc, 'div', {
          className: 'answer-meta',
          children: [
            createEl(doc, 'span', { className: 'role-label', text: 'DocuLens' }),
            createEl(doc, 'span', {
              className: 'badge',
              text: `Checking PDF evidence · ${brand.label} (${effortMeta.label})…`,
            }),
          ],
        }),
        createEl(doc, 'p', {
          className: 'answer-text',
          text: 'Retrieving relevant passages and verifying supporting quotes…',
        }),
      ],
    });
    conversationEl?.append(card);
    card.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
    return card;
  }

  function buildTelemetryPill(data, aiContext = {}) {
    const modelId = data.model || aiContext.model;
    const providerId = data.provider || aiContext.provider;
    const effortId = data.effort || aiContext.effort;
    if (!modelId && !data.response_time_ms) return null;

    const wrap = createEl(doc, 'span', { className: 'answer-telemetry-pills' });

    if (modelId) {
      const brand = getCompanyBrand(modelId, providerId);
      const modelPill = createEl(doc, 'span', {
        className: 'telemetry-pill model-telemetry',
        attributes: { title: `${brand.label} · ${modelId}` },
      });
      const logoSpan = createEl(doc, 'span', {
        className: 'telemetry-logo',
        attributes: { 'data-company': brand.key },
      });
      logoSpan.innerHTML = brand.svg;
      const shortModel = modelId.includes('/') ? modelId.split('/').pop() : modelId;
      modelPill.append(logoSpan, createEl(doc, 'span', { text: shortModel }));
      wrap.append(modelPill);
    }

    if (effortId) {
      const effortMeta = getEffortMeta(effortId);
      wrap.append(
        createEl(doc, 'span', {
          className: 'telemetry-pill effort-telemetry',
          text: effortMeta.label,
          attributes: { title: effortMeta.description },
        }),
      );
    }

    if (typeof data.response_time_ms === 'number' && data.response_time_ms > 0) {
      const sec = (data.response_time_ms / 1000).toFixed(1);
      const fastLabel =
        data.retrieval_strategy === 'short_pdf_fast' ||
        data.retrieval_strategy === 'short_pdf_direct'
          ? `⚡ ${sec}s · Fast Path`
          : `⚡ ${sec}s`;
      wrap.append(
        createEl(doc, 'span', {
          className: 'telemetry-pill speed-telemetry',
          text: fastLabel,
        }),
      );
    }

    return wrap;
  }

  function resolveAnswer(card, data, { aiContext = {} } = {}) {
    card.className = 'message answer-card';
    card.replaceChildren();

    const answered = data.status === 'answered';
    const isClarification = data.status === 'clarification_needed';

    let badgeClass = 'badge abstained';
    let badgeText = 'Insufficient evidence';
    if (answered) {
      badgeClass = 'badge';
      badgeText = 'Verified citations';
    } else if (isClarification) {
      badgeClass = 'badge clarification';
      badgeText = 'Clarification needed';
    }

    const leftMeta = createEl(doc, 'div', {
      className: 'answer-meta-left',
      children: [
        createEl(doc, 'span', { className: 'role-label', text: 'DocuLens' }),
        createEl(doc, 'span', { className: badgeClass, text: badgeText }),
      ],
    });

    const telemetry = buildTelemetryPill(data, aiContext);
    if (telemetry) {
      leftMeta.append(telemetry);
    }

    const copyBtn = createEl(doc, 'button', {
      type: 'button',
      className: 'ghost-button small-btn',
      text: 'Copy answer',
    });
    copyBtn.addEventListener('click', () => onCopyAnswer?.(data.answer || ''));

    const meta = createEl(doc, 'div', {
      className: 'answer-meta',
      children: [
        leftMeta,
        createEl(doc, 'div', { className: 'answer-actions', children: [copyBtn] }),
      ],
    });
    card.append(meta);

    if (data.resolved_question) {
      card.append(
        createEl(doc, 'p', {
          className: 'resolved-query-note',
          text: `Understood as: ${data.resolved_question}`,
        }),
      );
    }

    card.append(
      createEl(doc, 'p', {
        className: 'answer-text',
        text: data.answer || '',
      }),
    );

    // Interactive Clarification Chips when the model/assistant has a doubt
    const clarificationOptions = Array.isArray(data.clarification_options)
      ? data.clarification_options
      : [];
    if (isClarification && clarificationOptions.length > 0) {
      const chipsWrap = createEl(doc, 'div', { className: 'clarification-chips' });
      for (const optionText of clarificationOptions) {
        const chipBtn = createEl(doc, 'button', {
          type: 'button',
          className: 'clarification-chip',
          text: optionText,
        });
        chipBtn.addEventListener('click', () => {
          if (onAskFollowUp) {
            onAskFollowUp(optionText);
          } else {
            onPromptSelect?.(optionText);
          }
        });
        chipsWrap.append(chipBtn);
      }
      card.append(
        createEl(doc, 'div', {
          className: 'clarification-box',
          children: [
            createEl(doc, 'span', {
              className: 'clarification-label',
              text: 'Select what you meant (or type your reply below):',
            }),
            chipsWrap,
          ],
        }),
      );
    }

    const citations = Array.isArray(data.citations) ? data.citations : [];
    const citedPages =
      Array.isArray(data.cited_pages) && data.cited_pages.length > 0
        ? data.cited_pages
        : Array.from(new Set(citations.map((c) => c.page_number)));

    if (citedPages.length > 0) {
      const bar = createEl(doc, 'div', {
        className: 'cited-pages-bar',
        children: [
          createEl(doc, 'span', {
            className: 'cited-pages-label',
            text: 'Verified PDF pages:',
          }),
        ],
      });
      for (const pageNum of citedPages) {
        const firstCitation = citations.find((c) => c.page_number === pageNum) || {
          page_number: pageNum,
          excerpt: '',
        };
        const pill = createEl(doc, 'button', {
          type: 'button',
          className: 'page-pill',
          text: `PDF page ${pageNum}`,
        });
        pill.addEventListener('click', () => onCitationClick?.(firstCitation));
        bar.append(pill);
      }
      card.append(bar);
    }

    if (citations.length > 0) {
      const list = createEl(doc, 'div', { className: 'citations' });
      citations.forEach((citation, index) => {
        const cardBtn = createEl(doc, 'button', {
          type: 'button',
          className: 'citation-item evidence-card',
          children: [
            createEl(doc, 'div', {
              className: 'citation-top',
              children: [
                createEl(doc, 'span', {
                  className: 'citation-page',
                  text: `Citation ${index + 1} · PDF page ${citation.page_number}`,
                }),
                createEl(doc, 'span', {
                  className: 'citation-hint',
                  text: 'Inspect on page →',
                }),
              ],
            }),
            createEl(doc, 'blockquote', {
              className: 'citation-quote',
              text: citation.excerpt,
            }),
          ],
        });
        cardBtn.addEventListener('click', () => onCitationClick?.(citation));
        list.append(cardBtn);
      });
      card.append(list);
    }

    syncToolbarButtons();
    card.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }

  function resolveError(card, message) {
    card.className = 'message answer-card error-card';
    card.replaceChildren(
      createEl(doc, 'div', {
        className: 'answer-meta',
        children: [
          createEl(doc, 'span', { className: 'role-label', text: 'DocuLens' }),
          createEl(doc, 'span', { className: 'badge abstained', text: 'Request error' }),
        ],
      }),
      createEl(doc, 'p', { className: 'answer-text', text: message }),
    );
    syncToolbarButtons();
  }

  function clear() {
    if (!conversationEl) return;
    for (const node of conversationEl.querySelectorAll('.message')) {
      node.remove();
    }
    if (welcomeEl) welcomeEl.hidden = false;
    syncToolbarButtons();
  }

  if (clearChatBtn) {
    clearChatBtn.addEventListener('click', () => onClearChat?.());
  }
  if (exportChatBtn) {
    exportChatBtn.addEventListener('click', () => onExportChat?.());
  }

  return {
    renderStarterPrompts,
    appendUserQuestion,
    appendPendingAnswer,
    resolveAnswer,
    resolveError,
    clear,
  };
}
