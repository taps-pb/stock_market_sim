import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const require = createRequire(import.meta.url);
const load = (file, imports = {}) => {
  const source = readFileSync(new URL(file, import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  vm.runInNewContext(code, { exports, require: name => imports[name] ?? require(name) });
  return exports;
};

test('mode defaults Basic, restores Pro, and tolerates disabled storage', () => {
  const { readMode } = load('../src/mode.ts');
  assert.equal(readMode({ getItem: () => null }), 'basic');
  assert.equal(readMode({ getItem: () => 'pro' }), 'pro');
  assert.equal(readMode({ getItem: () => 'invalid' }), 'basic');
  assert.equal(readMode({ getItem: () => { throw new Error('disabled'); } }), 'basic');
});

test('Basic uses actual snapshot values and hides technical charts', () => {
  const format = {
    money: value => `$${value.toFixed(2)}`,
    signedMoney: value => `${value >= 0 ? '+' : ''}$${value.toFixed(2)}`,
    pct: value => `${value.toFixed(2)}%`,
    terminal: status => ['completed', 'failed', 'interrupted'].includes(status),
  };
  const BasicView = load('../src/components/BasicView.tsx', { '../format': format }).default;
  const snap = { tick: 100, symbols: [{ symbol: 'NOVA', name: 'Nova Dynamics', last: 119.24, open: 118 }],
    model: { horizon: 20, signals: { NOVA: { dir: 'up' } } },
    arena: { status: 'running', warmup: 60, agent_halted: false, error: null, agent: { net_pnl: 1286.42, return_pct: 1.29, initial: 100000, total: 101286.42, cash: 63000, positions: [] } } };
  const render = props => renderToStaticMarkup(React.createElement(BasicView, { snap, connected: true, busy: false, onControl: () => {}, onNewExperiment: () => {}, ...props }));
  const html = render();
  assert.match(html, /Nova Dynamics/);
  assert.match(html, /\+\$1286\.42/);
  assert.match(html, /may rise.*next 20 simulation steps/);
  assert.doesNotMatch(html, /<svg|<canvas|chartbox|Decision journal/);
  assert.doesNotMatch(render({ snap: { ...snap, model: null } }), /may rise|may fall/);
  assert.match(render({ connected: false }), /disabled=""/);
});

test('Basic historical replay stays separate from synthetic results', () => {
  const BasicView = load('../src/components/BasicView.tsx', { '../format': {
    money: () => '$0', signedMoney: () => '+$0', pct: () => '0%', terminal: () => false,
  } }).default;
  const replay = { arena: { status: 'running', error: null, elapsed: 12, settings: { duration: 100 } }, replay: { metrics: { n: 0 } } };
  const html = renderToStaticMarkup(React.createElement(BasicView, { replay, connected: true, busy: false, onControl: () => {}, onNewExperiment: () => {} }));
  assert.match(html, /Historical replay/);
  assert.match(html, /Day 12/);
  assert.doesNotMatch(html, /Account value now|Atlas result so far|<canvas|<svg/);
});
