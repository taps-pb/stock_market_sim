import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const require = createRequire(import.meta.url);
const exports = {};
const source = readFileSync(new URL('../src/components/MarketOutlook.tsx', import.meta.url), 'utf8');
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText,
  { exports, require: name => name === '../store' ? { useStore: sel => sel({ selected: 'HELX', select: () => {} }) }
    : name === '../format' ? { money: (n, digits) => `$${n.toFixed(digits)}`, pct: n => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` }
    : require(name) });

test('outlook distinguishes current prices, independent targets, and unseen evaluation', () => {
  const symbols = ['NOVA', 'HELX', 'ATLS', 'ORCA', 'VANE', 'CIRR'].map((symbol, i) => ({ symbol, name: symbol, last: 50 + i }));
  const render = model => renderToStaticMarkup(React.createElement(exports.default, { model, symbols }));
  assert.equal(render({ horizon: 20 }), '');
  assert.match(render({ outlook: { index_now: 103.5, series: [] } }), /Collecting price history/);
  const series = [20, 60, 120].map(horizon => ({ horizon, target_tick: 200 + horizon,
    index_price: 103.5 + horizon / 100, index_lower: 100, index_upper: 109, index_return_pct: .3,
    stocks: Object.fromEntries(symbols.map(s => [s.symbol, { price: s.last + horizon / 20, lower: s.last, upper: s.last + 9, return_pct: 1 }])),
    evaluation: { mae: 1.77, baseline_mae: 1.74, coverage: .78, n: 100 } }));
  const html = render({ outlook: { index_now: 103.5, series } });
  assert.equal((html.match(/class="outlook-card"/g) ?? []).length, 3);
  assert.match(html, /Index now.*?103\.50/s);
  assert.match(html, /20 ticks.*?Target T220/s);
  assert.match(html, /120 ticks.*?Target T320/s);
  assert.match(html, /Current HELX price:.*?\$51\.00/s); // not first forecast's $52
  assert.match(html, /Unseen-market error.*?1\.77 pts/);
  assert.match(html, /Unchanged baseline.*?1\.74 pts/);
  assert.match(html, /Intermediate prices are not predicted/);
});
