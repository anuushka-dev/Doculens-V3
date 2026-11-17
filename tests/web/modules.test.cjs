const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const root = path.join(__dirname, '../..');
const modUrl = (rel) => pathToFileURL(path.join(root, rel)).href;

test('validation module enforces PDF extension, non-empty size, upload byte limit, and question length', async () => {
  const { validatePdfFile, validateQuestionText } = await import(
    modUrl('frontend/src/utils/validation.js')
  );
  const limits = { max_upload_bytes: 1024, max_pdf_pages: 350 };

  assert.equal(validatePdfFile(null, limits).valid, false);
  assert.equal(validatePdfFile({ name: 'notes.txt', size: 10 }, limits).valid, false);
  assert.equal(validatePdfFile({ name: 'empty.pdf', size: 0 }, limits).valid, false);
  assert.equal(validatePdfFile({ name: 'big.pdf', size: 2048 }, limits).valid, false);
  assert.equal(validatePdfFile({ name: 'ok.pdf', size: 512 }, limits).valid, true);

  assert.equal(validateQuestionText('   ').valid, false);
  assert.equal(validateQuestionText('a'.repeat(2001)).valid, false);
  assert.deepEqual(validateQuestionText('  What is the limit?  '), {
    valid: true,
    question: 'What is the limit?',
  });
});

test('dom utils format sizes, countdowns, and markdown transcripts cleanly', async () => {
  const { formatMiB, formatCountdown, buildMarkdownTranscript } = await import(
    modUrl('frontend/src/utils/dom.js')
  );

  assert.equal(formatMiB(20 * 1024 * 1024), '20 MiB');
  assert.equal(formatCountdown(65), '01:05');
  assert.equal(formatCountdown(-3), '00:00');

  const md = buildMarkdownTranscript(
    { filename: 'spec.pdf', document_id: 'doc-1', page_count: 10, chunk_count: 14 },
    [
      { role: 'user', text: 'What is the limit?' },
      {
        role: 'assistant',
        status: 'answered',
        text: '“Max 350 pages.” (PDF page 2)',
        citations: [{ page_number: 2, excerpt: 'Max 350 pages.' }],
      },
    ],
  );
  assert.match(md, /# DocuLens Transcript — spec\.pdf/);
  assert.match(md, /PDF page 2:\*\* Max 350 pages\./);
});

test('store notifies subscribers and clears subscriptions cleanly', async () => {
  const { createStore } = await import(modUrl('frontend/src/state/store.js'));
  const store = createStore();
  assert.equal(store.getState().limits.max_pdf_pages, 350);

  let observed = null;
  const unsub = store.subscribe((s) => {
    observed = s.busy;
  });
  store.setState({ busy: true });
  assert.equal(observed, true);
  unsub();
  store.setState({ busy: false });
  assert.equal(observed, true);
});

test('apiClient maps HTTP errors and timeouts to ApiError', async () => {
  const { createApiClient, ApiError } = await import(
    modUrl('frontend/src/services/apiClient.js')
  );

  const clientErr = createApiClient({
    fetchImpl: async () => ({
      ok: false,
      status: 413,
      json: async () => ({ detail: { code: 'pdf_page_limit_exceeded', message: 'Too many pages.' } }),
    }),
  });
  await assert.rejects(
    () => clientErr.getStatus(),
    (err) => err instanceof ApiError && err.status === 413 && err.code === 'pdf_page_limit_exceeded',
  );

  const clientNetErr = createApiClient({
    fetchImpl: async () => {
      throw new TypeError('connect ECONNREFUSED');
    },
  });
  await assert.rejects(
    () => clientNetErr.getStatus(),
    (err) => err instanceof ApiError && err.code === 'NETWORK_ERROR',
  );

  const recordedBodies = [];
  const clientOk = createApiClient({
    fetchImpl: async (_url, opts) => {
      recordedBodies.push(JSON.parse(opts.body));
      return { ok: true, status: 200, json: async () => ({ status: 'answered', answer: 'ok', citations: [] }) };
    },
  });
  const session = { document_id: 'd1', document_token: 't1' };
  await clientOk.askQuestion(session, 'First question');
  await clientOk.askQuestion(session, 'Follow-up?', [
    { role: 'user', content: 'First question' },
    { role: 'assistant', content: 'Answer 1' },
  ]);
  assert.deepEqual(recordedBodies[0], { question: 'First question' });
  assert.deepEqual(recordedBodies[1], {
    question: 'Follow-up?',
    history: [
      { role: 'user', content: 'First question' },
      { role: 'assistant', content: 'Answer 1' },
    ],
  });
});

test('logos utility resolves company SVG logos and effort metadata for composer & drawer', async () => {
  const { getCompanyBrand, getEffortMeta, resolveCompanyKey } = await import(
    modUrl('frontend/src/utils/logos.js')
  );

  assert.equal(resolveCompanyKey('gpt-4o', 'openai'), 'openai');
  assert.equal(resolveCompanyKey('gemini-2.5-flash', 'gemini'), 'google');
  assert.equal(resolveCompanyKey('claude-3-7-sonnet', 'anthropic'), 'anthropic');
  assert.equal(resolveCompanyKey('llama-3.3-70b-versatile', 'groq'), 'meta');
  assert.equal(resolveCompanyKey('deepseek-r1-distill-llama-70b', 'groq'), 'deepseek');

  const brand = getCompanyBrand('gpt-4o', 'openai');
  assert.equal(brand.label, 'OpenAI');
  assert.match(brand.svg, /<svg/);

  const effort = getEffortMeta('high');
  assert.equal(effort.id, 'high');
  assert.equal(effort.label, 'High');
});

test('apiClient supports provider API key registration, model selection, and prompt enhancement', async () => {
  const { createApiClient } = await import(modUrl('frontend/src/services/apiClient.js'));
  const calls = [];
  const client = createApiClient({
    fetchImpl: async (url, opts = {}) => {
      calls.push({ url, method: opts.method || 'GET', body: opts.body ? JSON.parse(opts.body) : null });
      return {
        ok: true,
        status: 200,
        json: async () => ({ provider: 'groq', model_count: 5, enhanced_question: 'Polished question?' }),
      };
    },
  });

  await client.addProviderKey({ provider: 'groq', apiKey: 'gsk_test123' });
  await client.addProviderKey({
    provider: 'custom',
    apiKey: 'nvapi-123',
    baseUrl: 'https://integrate.api.nvidia.com/v1',
    customModel: 'meta/llama-3.3-70b-instruct',
  });
  await client.selectProviderModel({ provider: 'groq', model: 'llama-3.3-70b-versatile', effort: 'high' });
  await client.enhancePrompt('wht is limit');

  assert.equal(calls[0].url, '/api/providers/key');
  assert.equal(calls[0].body.provider, 'groq');
  assert.equal(calls[0].body.api_key, 'gsk_test123');
  assert.equal(calls[1].url, '/api/providers/key');
  assert.equal(calls[1].body.provider, 'custom');
  assert.equal(calls[1].body.base_url, 'https://integrate.api.nvidia.com/v1');
  assert.equal(calls[1].body.custom_model, 'meta/llama-3.3-70b-instruct');
  assert.equal(calls[2].url, '/api/providers/select');
  assert.equal(calls[2].body.effort, 'high');
  assert.equal(calls[3].url, '/api/prompts/enhance');
});

