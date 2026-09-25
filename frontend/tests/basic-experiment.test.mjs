import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const require = createRequire(import.meta.url);
const code = ts.transpileModule(readFileSync(new URL('../src/components/NewExperiment.tsx', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const store = { snap: undefined, replay: undefined, setSnap: () => {} };
const format = { money: n => `$${n.toLocaleString('en-US')}`, terminal: () => false };
const api = { getDatasets: async () => [], importDataset: async () => ({}), startReplay: async () => ({}) };
const load = imports => {
  const exports = {};
  vm.runInNewContext(code, { exports, require: name => imports[name] ?? require(name) });
  return exports.default;
};
const base = { '../store': { useStore: selector => selector(store) }, '../format': format, '../api': { ...api, startRun: async () => ({}) } };

test('Basic setup offers starting money and four risk stops; Pro setup remains intact', () => {
  const Dialog = load(base);
  const render = basic => renderToStaticMarkup(React.createElement(Dialog, { basic, open: true, close() {}, finish() {} }));
  const basic = render(true);
  assert.match(basic, /Start a new simulation/);
  assert.match(basic, /Starting money/);
  assert.match(basic, /type="number"[^>]*min="1000"[^>]*max="1000000"[^>]*step="1000"/);
  assert.match(basic, /type="range"[^>]*min="0"[^>]*max="3"[^>]*step="1"/);
  assert.equal((basic.match(/aria-pressed="(?:true|false)"/g) ?? []).length, 4);
  for (const level of ['Cautious', 'Balanced', 'Assertive', 'Super risky']) assert.match(basic, new RegExp(level));
  assert.doesNotMatch(basic, /Switch to (?:dark|light) mode|Market seed|Trading duration/);
  const pro = render(false);
  assert.match(pro, /Market seed|Trading duration|Risk profile/);
  assert.match(pro, /value="super_risky"/);
  assert.doesNotMatch(pro, /basic-risk-range/);
});

// Drive component handlers without browser or extra test dependencies.
function setup() {
  const slots = []; let index = 0;
  const calls = [];
  const hooks = {
    useRef: () => { const i = index++; return slots[i] ??= { current: null }; },
    useState: initial => { const i = index++; if (!(i in slots)) slots[i] = initial;
      return [slots[i], next => { slots[i] = typeof next === 'function' ? next(slots[i]) : next; }]; },
    useEffect() {},
  };
  const element = (type, props) => ({ type, props: props ?? {} });
  const Dialog = load({ ...base, react: hooks, 'react/jsx-runtime': { jsx: element, jsxs: element, Fragment: Symbol('fragment') },
    '../api': { ...api, startRun: async body => { calls.push(body); return {}; } } });
  return { render: () => { index = 0; return Dialog({ basic: true, open: true, close() {}, finish() {} }); }, calls };
}
function find(tree, predicate) {
  if (Array.isArray(tree)) { for (const child of tree) { const match = find(child, predicate); if (match) return match; } }
  if (!tree?.props) return null;
  if (predicate(tree)) return tree;
  return find(tree.props.children, predicate);
}
const capital = tree => find(tree, node => node.type === 'input' && node.props.id === 'basic-capital');
const slider = tree => find(tree, node => node.type === 'input' && node.props.id === 'basic-risk');
const submit = tree => find(tree, node => node.type === 'form').props.onSubmit({ preventDefault() {} });

test('Basic submits selected capital and each existing risk policy, never a fixed $100,000', async () => {
  const profiles = [
    ['cautious', .10, .30, .04], ['balanced', .20, .60, .08],
    ['assertive', .30, .90, .12], ['super_risky', .30, .90, .30],
  ];
  for (const [i, [name, position, exposure, drawdown]] of profiles.entries()) {
    const dialog = setup();
    let tree = dialog.render();
    capital(tree).props.onChange({ target: { value: '250000' } });
    slider(tree).props.onChange({ target: { value: String(i) } });
    tree = dialog.render();
    await submit(tree);
    assert.equal(dialog.calls.length, 1);
    assert.equal(dialog.calls[0].capital, 250000);
    assert.equal(dialog.calls[0].risk_profile, name);
    assert.equal(dialog.calls[0].max_position, position);
    assert.equal(dialog.calls[0].max_exposure, exposure);
    assert.equal(dialog.calls[0].max_drawdown, drawdown);
    assert.equal(dialog.calls[0].duration, 1500);
    if (name === 'super_risky') assert.equal(dialog.calls[0].slippage_bps, 100);
  }
});

test('Basic blocks blank and out-of-range amounts', async () => {
  for (const value of ['', '500', '1000500', '1500']) {
    const dialog = setup();
    let tree = dialog.render();
    capital(tree).props.onChange({ target: { value } });
    tree = dialog.render();
    assert.equal(find(tree, node => node.type === 'button' && node.props.type === 'submit').props.disabled, true);
    await submit(tree);
    assert.equal(dialog.calls.length, 0);
  }
});
