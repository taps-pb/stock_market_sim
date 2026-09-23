import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const require = createRequire(import.meta.url);

test('market board shows six forecasts and an honest missing-signal state', () => {
  const symbols = ['NOVA', 'HELX', 'ATLS', 'ORCA', 'VANE', 'CIRR'].map((symbol, i) => ({ symbol, name: `Company ${i}`, last: 20 + i }));
  const signals = Object.fromEntries(symbols.slice(0, 5).map((s, i) => [s.symbol, {
    price: s.last + 1, return_pct: 5, prob: .68, lower: s.last - 1, upper: s.last + 2, target_tick: 120 + i,
  }]));
  const state = { snap: { symbols, model: { signals, horizon: 20, interval_coverage: .8 } }, selected: 'HELX', select: () => {} };
  const exports = {};
  const source = readFileSync(new URL('../src/components/MarketForecastBoard.tsx', import.meta.url), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports, require: name => name === '../store' ? { useStore: selector => selector(state) }
    : name === '../format' ? { money: (n, digits) => `$${n.toFixed(digits)}`, pct: n => `+${n.toFixed(2)}%` }
    : require(name) });
  const html = renderToStaticMarkup(React.createElement(exports.default));
  assert.equal((html.match(/class="forecast-card"/g) ?? []).length, 6);
  assert.equal((html.match(/aria-pressed="true"/g) ?? []).length, 1);
  assert.match(html, /next 20 ticks · 80% forecast interval/);
  assert.match(html, /Chance of higher close.*?68%/);
  assert.match(html, /Forecast range.*?\$19\.00 – \$22\.00/);
  assert.match(html, /Target tick.*?120/);
  assert.match(html, /CIRR.*?\$25\.00.*?Forecast unavailable|CIRR.*?\$25\.00.*?Collecting price history/s);
});
