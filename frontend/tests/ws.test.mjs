import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

test('reconnects after a drop; cleanup closes the socket and cancels retries', () => {
  const sockets = [], timers = new Set(), received = [];
  const context = {
    exports: {}, location: { protocol: 'http:', host: 'localhost:5173' },
    WebSocket: class {
      constructor() { sockets.push(this); }
      close() { this.closed = true; this.onclose(); }
    },
    setTimeout: (callback) => { timers.add(callback); return callback; },
    clearTimeout: (callback) => timers.delete(callback),
  };
  const source = readFileSync(new URL('../src/ws.ts', import.meta.url), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText, context);
  const stop = context.exports.connectWs((snapshot) => received.push(snapshot.tick));
  sockets[0].onmessage({ data: '{"tick":1}' });
  assert.deepEqual(received, [1]);
  sockets[0].close();
  assert.equal(timers.size, 1);
  const retry = [...timers][0];
  timers.delete(retry);
  retry();
  assert.equal(sockets.length, 2);
  sockets[1].close();
  stop();
  assert.equal(timers.size, 0);
  assert.equal(sockets[1].closed, true);
  sockets[1].onmessage({ data: '{"tick":2}' });
  assert.deepEqual(received, [1]);
});
