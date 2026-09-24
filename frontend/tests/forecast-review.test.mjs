import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const require = createRequire(import.meta.url);
const source = readFileSync(new URL('../src/components/ForecastReview.tsx', import.meta.url), 'utf8');
const exports = {};
const state = { selected: 'HELX', select: () => {} };
vm.runInNewContext(ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText, { exports, require: name => name === '../store' ? { useStore: selector => selector(state) }
  : name === '../format' ? { money: (value, digits) => `$${value.toFixed(digits)}` }
  : require(name) });

test('review shows only resolved calls, with per-stock scores and an older-run fallback', () => {
  const symbols = ['NOVA', 'HELX', 'ATLS', 'ORCA', 'VANE', 'CIRR'].map(symbol => ({ symbol, name: `${symbol} Company` }));
  const render = model => renderToStaticMarkup(React.createElement(exports.default, { model, symbols }));
  assert.equal(render({ horizon: 20 }), '');
  const review = { by_symbol: Object.fromEntries(symbols.map(s => [s.symbol, { n: 0, mae: null, baseline_mae: null, coverage: null }])), recent: [] };
  let html = render({ horizon: 20, review });
  assert.equal((html.match(/class="forecast-review-stock"/g) ?? []).length, 6);
  assert.match(html, /No forecasts matured yet/);
  assert.doesNotMatch(html, /forecast-review-chart-scroll/);

  review.by_symbol.HELX = { n: 1, mae: .37, baseline_mae: .4, coverage: 1 };
  review.recent.push({ symbol: 'HELX', issued_tick: 100, target_tick: 120,
    predicted_price: 42.25, actual_price: 42.62, lower: 41, upper: 43, abs_error: .37, covered: true });
  html = render({ horizon: 20, review });
  assert.match(html, /\$0\.37/);
  assert.match(html, /100\.0%/);
  assert.match(html, /T100/);
  assert.match(html, /T120/);
  assert.match(html, /\$42\.25/);
  assert.match(html, /\$42\.62/);
  assert.match(html, /Hit/);
  assert.match(html, /HELX: predicted and actual prices for 1 matured call/);
  assert.equal((html.match(/aria-pressed="true"/g) ?? []).length, 1);
});
