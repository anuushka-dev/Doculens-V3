/**
 * Frontend workspace constants and defaults.
 * These mirror backend defaults until /api/status hydrates runtime limits.
 */

export const STORAGE_KEY = 'doculens.activeSession.v2';
export const PREFS_STORAGE_KEY = 'doculens.aiPreferences.v2';

export const MAX_QUESTION_LENGTH = 2000;
export const MAX_QUESTION_CHARS = 2000;
export const MAX_HISTORY_TURNS = 12;
export const EXPIRY_WARNING_SECONDS = 300;

export const DEFAULT_LIMITS = Object.freeze({
  max_upload_bytes: 20 * 1024 * 1024,
  max_pdf_pages: 350,
  session_ttl_seconds: 3600,
});

export const STARTER_PROMPTS = Object.freeze([
  'What is the main purpose and scope of this document?',
  'What limits, thresholds, or deadlines are stated?',
  'What requirements or conditions apply?',
  'Summarize the key findings with page citations.',
]);

export const DEFAULT_AI_PREFS = Object.freeze({
  provider: 'ollama',
  providerName: 'Ollama Local',
  model: 'qwen3.5:4b',
  modelName: 'qwen3.5:4b',
  company: 'qwen',
  effort: 'medium',
  autoFixPrompt: true,
});
