/**
 * Company SVG logos and effort icons for the DocuLens model selector,
 * header pill, conversation badges, and Hamburger settings drawer.
 */

const COMPANY_LOGOS = Object.freeze({
  openai: {
    label: 'OpenAI',
    color: '#10a37f',
    bg: 'rgba(16, 163, 127, 0.12)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3c-2.5 0-4.6 1.5-5.4 3.7C4.5 7.3 3 9.3 3 11.6c0 1.8.9 3.4 2.3 4.3-.2 2.3 1.1 4.5 3.3 5.3 1.8.7 3.8.2 5.1-1.1 1.8 1.1 4.2.9 5.8-.6 1.6-1.5 2-3.9 1-5.8 1.2-1.5 1.5-3.6.7-5.4-.8-1.8-2.6-3-4.6-3-.9-1.4-2.6-2.3-4.6-2.3Z"/><circle cx="12" cy="12" r="2.6"/></svg>`,
  },
  google: {
    label: 'Google Gemini',
    color: '#4285f4',
    bg: 'rgba(66, 133, 244, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M12 2c.7 4.9 4.4 8.6 9.3 9.3-4.9.7-8.6 4.4-9.3 9.3-.7-4.9-4.4-8.6-9.3-9.3C7.6 10.6 11.3 6.9 12 2Z"/></svg>`,
  },
  gemini: {
    label: 'Google Gemini',
    color: '#4285f4',
    bg: 'rgba(66, 133, 244, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M12 2c.7 4.9 4.4 8.6 9.3 9.3-4.9.7-8.6 4.4-9.3 9.3-.7-4.9-4.4-8.6-9.3-9.3C7.6 10.6 11.3 6.9 12 2Z"/></svg>`,
  },
  anthropic: {
    label: 'Anthropic Claude',
    color: '#d97757',
    bg: 'rgba(217, 119, 87, 0.14)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14.5 4 20 20h-2.8l-1.2-3.8h-5L9.8 20H7L12.5 4h2Z"/><path d="M4 20 9.2 5.5"/></svg>`,
  },
  meta: {
    label: 'Meta Llama',
    color: '#0668E1',
    bg: 'rgba(6, 104, 225, 0.12)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6.8 8C4.4 8 3 10.2 3 12.8 3 15.4 4.5 17 6.5 17c2.1 0 3.7-2.2 5.5-5 1.8 2.8 3.4 5 5.5 5 2 0 3.5-1.6 3.5-4.2C21 10.2 19.6 8 17.2 8c-2 0-3.6 1.8-5.2 4.2C10.4 9.8 8.8 8 6.8 8Z"/></svg>`,
  },
  deepseek: {
    label: 'DeepSeek',
    color: '#4d6bfe',
    bg: 'rgba(77, 107, 254, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 13c0-4.4 4-8 9-8 4.2 0 7.7 2.5 8.7 6 1.3-.3 2.3.5 2.3 1.7 0 2.5-2.6 4.3-5.2 4.3H15c-1.5 2-3.8 3-6.5 3-3 0-5.5-2-5.5-5v-2Z"/><circle cx="13.5" cy="10.5" r="1" fill="currentColor"/></svg>`,
  },
  groq: {
    label: 'Groq LPU',
    color: '#f55036',
    bg: 'rgba(245, 80, 54, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/></svg>`,
  },
  openrouter: {
    label: 'OpenRouter',
    color: '#6366f1',
    bg: 'rgba(99, 102, 241, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.3 11 15.7 7M8.3 13l7.4 4"/></svg>`,
  },
  mistral: {
    label: 'Mistral AI',
    color: '#fa520f',
    bg: 'rgba(250, 82, 15, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M4 5h4v4H4V5Zm12 0h4v4h-4V5ZM8 9h3v4H8V9Zm5 0h3v4h-3V9Zm-9 4h4v6H4v-6Zm7 0h2v4h-2v-4Zm5 0h4v6h-4v-6Z"/></svg>`,
  },
  qwen: {
    label: 'Qwen',
    color: '#615ced',
    bg: 'rgba(97, 92, 237, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="12 2 20 7 20 17 12 22 4 17 4 7 12 2"/><circle cx="12" cy="12" r="3"/></svg>`,
  },
  xai: {
    label: 'xAI Grok',
    color: '#1f2937',
    bg: 'rgba(31, 41, 55, 0.12)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" aria-hidden="true"><path d="M4 4l16 16M20 4 4 20"/></svg>`,
  },
  together: {
    label: 'Together AI',
    color: '#0ea5e9',
    bg: 'rgba(14, 165, 233, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><circle cx="9" cy="12" r="5"/><circle cx="15" cy="12" r="5"/></svg>`,
  },
  fireworks: {
    label: 'Fireworks AI',
    color: '#ec4899',
    bg: 'rgba(236, 72, 153, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true"><path d="M12 2v6m0 8v6M2 12h6m8 0h6M4.9 4.9l4.2 4.2m5.8 5.8 4.2 4.2M19.1 4.9l-4.2 4.2M9.1 14.9l-4.2 4.2"/></svg>`,
  },
  cerebras: {
    label: 'Cerebras',
    color: '#f97316',
    bg: 'rgba(249, 115, 22, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>`,
  },
  cohere: {
    label: 'Cohere',
    color: '#39594d',
    bg: 'rgba(57, 89, 77, 0.13)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="8" cy="12" r="4"/><path d="M14 8a4 4 0 0 1 0 8"/></svg>`,
  },
  ollama: {
    label: 'Ollama Local',
    color: '#183d36',
    bg: 'rgba(24, 61, 54, 0.12)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 9V6a2 2 0 0 1 4 0v1a2 2 0 0 1 4 0v2a5 5 0 0 1 2 4v4a3 3 0 0 1-3 3H9a3 3 0 0 1-3-3v-4a5 5 0 0 1 2-4Z"/><circle cx="10" cy="13" r="1" fill="currentColor"/><circle cx="14" cy="13" r="1" fill="currentColor"/></svg>`,
  },
  custom: {
    label: 'Custom API',
    color: '#475569',
    bg: 'rgba(71, 85, 105, 0.12)',
    svg: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7.1-7.1l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7.1 7.1l1.7-1.7"/></svg>`,
  },
});

export const EFFORT_LEVELS = Object.freeze([
  {
    id: 'low',
    label: 'Low',
    shortLabel: 'Low · Fast',
    badge: 'Fast 1-Pass',
    description: 'Fastest response (single-pass extraction + strict quote verification)',
    svg: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/></svg>`,
  },
  {
    id: 'medium',
    label: 'Medium',
    shortLabel: 'Medium · Balanced',
    badge: 'Balanced',
    description: 'Balanced speed & multi-stage evidence verification (Recommended)',
    svg: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>`,
  },
  {
    id: 'high',
    label: 'High',
    shortLabel: 'High · Deep',
    badge: 'Deep Review',
    description: 'Expanded context window + thorough multi-chunk cross-checking',
    svg: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2a7 7 0 0 1 7 7c0 2.4-1.2 4.5-3 5.7V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.3C6.2 13.5 5 11.4 5 9a7 7 0 0 1 7-7Z"/><path d="M9 21h6"/></svg>`,
  },
  {
    id: 'max',
    label: 'Max',
    shortLabel: 'Max · Thorough',
    badge: 'Max Reasoning',
    description: 'Maximum reasoning depth & full-document evidence synthesis',
    svg: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="12 2 15.1 8.3 22 9.3 17 14.1 18.2 21 12 17.8 5.8 21 7 14.1 2 9.3 8.9 8.3 12 2"/></svg>`,
  },
]);

/**
 * Resolve company key from model ID or provider ID on the client side as well.
 */
export function resolveCompanyKey(modelId = '', providerId = '', explicitCompany = '') {
  if (explicitCompany && COMPANY_LOGOS[explicitCompany]) {
    return explicitCompany;
  }
  const lower = String(modelId || '').toLowerCase();
  if (lower.includes('deepseek')) return 'deepseek';
  if (lower.includes('gpt-') || lower.includes('codex') || lower.includes('o1') || lower.includes('o3') || lower.includes('o4') || lower.includes('openai')) return 'openai';
  if (lower.includes('gemini') || lower.includes('gemma') || lower.includes('google')) return 'google';
  if (lower.includes('claude') || lower.includes('anthropic')) return 'anthropic';
  if (lower.includes('llama') || lower.includes('meta')) return 'meta';
  if (lower.includes('qwen') || lower.includes('qwq')) return 'qwen';
  if (lower.includes('mistral') || lower.includes('mixtral') || lower.includes('codestral') || lower.includes('ministral')) return 'mistral';
  if (lower.includes('grok') || lower.includes('xai') || lower.includes('x-ai')) return 'xai';
  if (lower.includes('command') || lower.includes('cohere')) return 'cohere';

  const prov = String(providerId || '').toLowerCase();
  if (prov === 'custom_anthropic') return 'anthropic';
  if (COMPANY_LOGOS[prov]) return prov;
  return 'ollama';
}

export function getCompanyBrand(companyOrModel = '', providerId = '') {
  const key = resolveCompanyKey(companyOrModel, providerId, COMPANY_LOGOS[companyOrModel] ? companyOrModel : '');
  const brand = COMPANY_LOGOS[key] || COMPANY_LOGOS.ollama;
  return { key, ...brand };
}

export function getEffortMeta(effortId = 'medium') {
  return EFFORT_LEVELS.find((item) => item.id === effortId) || EFFORT_LEVELS[1];
}
