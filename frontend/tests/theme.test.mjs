import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../src/theme.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const read = getItem => {
  const exports = {};
  vm.runInNewContext(code, { exports, localStorage: { getItem } });
  return exports.readTheme();
};

test('theme defaults light, restores dark, and tolerates disabled storage', () => {
  assert.equal(read(() => null), 'light');
  assert.equal(read(() => 'dark'), 'dark');
  assert.equal(read(() => 'other'), 'light');
  assert.equal(read(() => { throw new Error('storage disabled'); }), 'light');
});
