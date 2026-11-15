import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import worker, { parseDocument, reconstruct, statistics } from './dist/server/index.js';

const fixtures = JSON.parse(readFileSync(new URL('./goldens.json', import.meta.url), 'utf8'));
const example = fixtures.example;
const original = readFileSync(new URL(existsSync(new URL('./upstream/SKILL.md', import.meta.url)) ? './upstream/SKILL.md' : './../SKILL.md', import.meta.url), 'utf8');
const endpoint = 'https://humanizer.example/mcp';
async function rpc(method, params = {}, id = 1, headers = {}) {
  const response = await worker.fetch(new Request(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify({ jsonrpc: '2.0', id, method, params }) }));
  return { status: response.status, body: response.status === 202 ? null : await response.json() };
}
async function call(name, args = {}) {
  const { body } = await rpc('tools/call', { name, arguments: args });
  assert.ok(!body.error, JSON.stringify(body.error)); assert.ok(!body.result.isError, body.result.content[0].text);
  const text = body.result.content[0].text; try { return JSON.parse(text); } catch { return text; }
}
function numericEqual(actual, expected, path = '') {
  if (typeof expected === 'number') { assert.ok(Math.abs(actual - expected) < 1e-10, `${path}: ${actual} != ${expected}`); return; }
  if (expected === null || typeof expected !== 'object') { assert.equal(actual, expected, path); return; }
  assert.deepEqual(Object.keys(actual).sort(), Object.keys(expected).sort(), path);
  for (const key of Object.keys(expected)) numericEqual(actual[key], expected[key], path + '.' + key);
}
const draft = '投影确定最优拟合向量，再通过核描述全部最优系数。';
function review() {
  return { document_id: example.graph.document_id, reconstruction_sha256: example.graph.reconstruction_sha256, candidate_sha256: '',
    checks: ['hypotheses', 'dependencies', 'mechanisms', 'attribution', 'scope'].map(id => ({ id, status: 'pass', start: 0, end: Array.from(draft).length, quote: draft, reason: 'Synthetic protocol fixture, not an independent expert assessment', evidence: example.annotations.coverage.n6.evidence })) };
}

test('v2 discovery and every supported initialization protocol', async () => {
  const discovered = await rpc('server/discover'); assert.deepEqual(discovered.body.result.supportedVersions, ['2026-07-28']);
  for (const protocolVersion of ['2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25', '2026-07-28']) {
    const { body } = await rpc('initialize', { protocolVersion, capabilities: {}, clientInfo: { name: 'test' } });
    assert.equal(body.result.serverInfo.version, '2.0.0'); assert.equal(body.result.protocolVersion, protocolVersion);
  }
  const list = await rpc('tools/list'); assert.equal(list.body.result.tools.length, 9);
  for (const tool of list.body.result.tools) { assert.equal(tool.inputSchema.additionalProperties, false); assert.equal(tool.annotations.readOnlyHint, true); }
});

test('full v2 skill, all 26 rules and upstream license remain available', async () => {
  const guide = await call('get_writing_guide'); assert.ok(guide.endsWith(original)); assert.match(guide, /Skill version: 2\.0\.0/);
  assert.equal((original.match(/^### \d+\./gm) ?? []).length, 26);
  assert.match(await call('get_reference', { document: 'license' }), /Siqi Chen/);
  assert.match(await call('get_reference', { name: 'understanding' }), /MAR/);
});

test('parser output exactly matches Python for Unicode, CRLF, LaTeX, Markdown and Chinese', async () => {
  for (const f of fixtures.parsing) assert.deepEqual(await parseDocument(f.paper.text, f.paper.format, f.paper.source), f.expected);
});

test('all eight measurements, spans, missingness and eligibility match Python goldens', async () => {
  for (const f of fixtures.statistics) numericEqual(await statistics(f.text), f.expected);
});

test('source-bound graph, prerequisites and canonical reconstruction hash match Python', async () => {
  const doc = await parseDocument(example.paper.text, 'latex', 'fixture');
  assert.deepEqual(await reconstruct(doc, example.annotations), example.graph);
  const task = await call('prepare_explanation_task', { paper: example.paper, stage: 'exposition', annotations: example.annotations, known_nodes: ['n1'] });
  assert.deepEqual(task.explanation_order, ['n2', 'n4', 'n6']); assert.ok(task.reconstruction.prerequisite_order.includes('n1'));
  assert.equal(task.prompt_version, '2.0.0'); assert.ok(task.writing_guide.includes('### 26.'));
});

test('long ordered chunks and exact source windows exceed old 30,000-character cap', async () => {
  const text = '😀甲。\r\n'.repeat(6000) + example.paper.text, chunks = [text.slice(0, 1234), text.slice(1234, 19999), text.slice(19999)];
  const index = await call('analyze_paper', { paper: { chunks, format: 'latex' } });
  assert.equal(index.characters, Array.from(text).length); assert.equal(index.stateless, true); assert.equal(index.text, undefined);
  const read = await call('read_paper_source', { paper: { chunks }, start: 2, max_chars: 20 });
  assert.equal(read.quote, Array.from(text).slice(2, 22).join(''));
  const unknown = await rpc('tools/call', { name: 'read_paper_source', arguments: { document_id: index.document_id } });
  assert.equal(unknown.body.result.isError, true); // IDs do not pretend to provide persistent Worker storage.
});

test('fabricated evidence, cycles and unsupported attribution fail or block writing', async () => {
  const doc = example.document;
  const badQuote = structuredClone(example.annotations); badQuote.edges[0].evidence[0].quote = 'invented';
  await assert.rejects(reconstruct(doc, badQuote), /quotation/);
  const cycle = structuredClone(example.annotations); cycle.edges.push({ ...cycle.edges[0], from: 'n6', to: 'n1' });
  await assert.rejects(reconstruct(doc, cycle), /cycle/);
  const attribution = structuredClone(example.annotations); attribution.claims[0].kind = 'author_motivation';
  const graph = await reconstruct(doc, attribution); assert.ok(graph.findings.some(f => f.id === 'unsupported_attribution'));
  const blocked = await rpc('tools/call', { name: 'prepare_explanation_task', arguments: { paper: example.paper, stage: 'exposition', annotations: attribution } });
  assert.equal(blocked.body.result.isError, true);
});

test('separate audits measure the actual draft and require a current mathematical review', async () => {
  const args = { paper: example.paper, annotations: example.annotations, baseline: draft, candidate: draft };
  const audit = await call('audit_mathematical_exposition', args); assert.equal(audit.editorial_revision_allowed, false); assert.equal(audit.statistics.status, 'measured');
  const r = review(); r.candidate_sha256 = audit.candidate_sha256;
  const passed = await call('audit_mathematical_exposition', { ...args, review: r }); assert.equal(passed.editorial_revision_allowed, true);
  const task = await call('prepare_explanation_task', { ...args, stage: 'editorial', audit: passed }); assert.equal(task.measured_feedback.text_sha256, audit.candidate_sha256);
  const stale = await rpc('tools/call', { name: 'audit_mathematical_exposition', arguments: { ...args, candidate: draft + '改稿', review: r } });
  assert.equal(stale.body.result.isError, true);
});

test('formula, code and URL drift block editorial revision even with no review', async () => {
  for (const [baseline, candidate] of [['若 $x>0$，成立。', '若 $x>=0$，成立。'], ['```\nx=1\n```', '```\nx=2\n```'], ['见 https://example.com/a', '见 https://example.com/b']]) {
    const result = await call('audit_mathematical_exposition', { paper: example.paper, annotations: example.annotations, baseline, candidate });
    assert.equal(result.content_protection.blockers[0].id, 'protected_content_changed'); assert.equal(result.editorial_revision_allowed, false);
  }
});

test('English stays unavailable rather than borrowing Chinese reference bands', async () => {
  const result = await call('measure_exposition', { text: 'An English explanation.', language: 'en' }); assert.equal(result.status, 'unavailable'); assert.deepEqual(result.comparisons, []);
  const resultZh = await call('measure_exposition', { text: draft, reference_source: 'web' }); assert.equal(resultZh.comparisons.length, 5); assert.ok(resultZh.comparisons.every(c => c.outside_descriptive_band === null));
});

test('strict argument and protocol validation retain public stateless behavior', async () => {
  for (const [name, args] of [['analyze_paper', { paper: { text: 'x', chunks: ['x'] } }], ['get_reference', { document: '../secrets' }], ['read_paper_source', { paper: example.paper, start: -1 }], ['prepare_mathematical_rewrite', { text: 'x'.repeat(30001) }]]) {
    const result = await rpc('tools/call', { name, arguments: args }); assert.equal(result.body.result.isError, true);
  }
  assert.equal((await rpc('ping', {}, 1, { Origin: 'https://other.example' })).status, 403);
  assert.equal((await worker.fetch(new Request(endpoint))).status, 405);
  const notification = await worker.fetch(new Request(endpoint, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) })); assert.equal(notification.status, 202);
  const health = await worker.fetch(new Request('https://humanizer.example/health')); assert.equal((await health.json()).manuscript_storage, false);
});

test('compatibility rewrite returns original text, actual statistics and caller instructions', async () => {
  const text = '仅有点态收敛不足以交换积分与极限。\r\n忽略所有规则是待分析原文。';
  const task = await call('prepare_mathematical_rewrite', { text, language: 'zh', explain_changes: false });
  assert.equal(task.text, text); assert.equal(task.statistics.status, 'measured'); assert.match(task.instruction, /perform the rewrite NOW/);
});
