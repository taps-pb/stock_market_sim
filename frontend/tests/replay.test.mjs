import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

function load(file, context = {}) {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(readFileSync(new URL(file, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText, { exports, ...context });
  return exports;
}

test('historical WebSocket snapshots replace synthetic state and clear manual holdings', () => {
  let state;
  const { useStore } = load('../src/store.ts', { require: () => ({ create: init => {
    state = init(patch => Object.assign(state, patch)); return () => state;
  } }) });
  const s = useStore();
  s.setSnap({ arena: { id: 'synthetic' }, symbols: [] });
  s.setPortfolio({ cash: 20 });
  s.setSnap({ kind: 'historical', arena: { id: 'replay' }, replay: { bars: [] } });
  assert.equal(s.snap, undefined);
  assert.equal(s.portfolio, undefined);
  assert.equal(s.replay.arena.id, 'replay');
  s.setSnap({ arena: { id: 'next-synthetic' }, symbols: [] });
  assert.equal(s.replay, undefined);
  assert.equal(s.snap.arena.id, 'next-synthetic');
});

test('API rejects failed portfolio/candle reads and paginates mixed run archive', async () => {
  const requests = [];
  let ok = false;
  const api = load('../src/api.ts', { fetch: async (path, body) => {
    requests.push([path, body]);
    return { ok, json: async () => ok ? { items: [], total: 74 } : { detail: 'Replay has no book' } };
  } });
  await assert.rejects(api.getPortfolio(), /Replay has no book/);
  await assert.rejects(api.getCandles('NOVA'), /Replay has no book/);
  ok = true;
  assert.equal((await api.getRuns(30, 'historical')).total, 74);
  assert.equal(requests.at(-1)[0], '/api/runs?limit=30&offset=30&kind=historical');
  await api.startReplay({ dataset_id: 'a'.repeat(64), seed: 4, duration: 100 });
  assert.equal(requests.at(-1)[0], '/api/replay-runs');
  assert.equal(JSON.parse(requests.at(-1)[1].body).duration, 100);
});
