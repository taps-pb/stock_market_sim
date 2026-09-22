#!/usr/bin/env node
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const transport = new StdioClientTransport({
  command: process.execPath,
  args: [new URL("./server.mjs", import.meta.url).pathname],
  cwd: new URL("../..", import.meta.url).pathname,
  env: {
    ...process.env,
    DEEPSEEK_KEY_FILE: process.env.DEEPSEEK_KEY_FILE || "/Users/taps-pb/Documents/work/ds_api.txt",
    DEEPSEEK_MODEL: process.env.DEEPSEEK_MODEL || "deepseek-flash",
  },
});
const client = new Client({ name: "deepseek-mcp-smoke", version: "1.0.0" });

function parsed(result) {
  const text = result.content?.find(item => item.type === "text")?.text;
  if (result.isError) throw new Error(text || "MCP tool failed");
  return JSON.parse(text);
}

try {
  await client.connect(transport);
  const listed = await client.listTools();
  console.log(`tools: ${listed.tools.map(tool => tool.name).join(", ")}`);

  const check = parsed(await client.callTool({ name: "check_connection", arguments: {} }));
  console.log(JSON.stringify({ check }, null, 2));

  const one = parsed(await client.callTool({
    name: "run_worker",
    arguments: {
      task: "Smoke test only: propose adding a file named nothing. Conclude no change is needed and return NO PATCH.",
      max_output_tokens: 256,
    },
  }));
  console.log(JSON.stringify({ single_worker: { model: one.model, usage: one.usage, result_received: Boolean(one.result) } }, null, 2));

  const parallel = parsed(await client.callTool({
    name: "run_workers_parallel",
    arguments: {
      tasks: ["alpha", "beta", "gamma"].map(label => ({
        task: `Parallel smoke test ${label}: report NO PATCH because no project change is requested.`,
        max_output_tokens: 256,
      })),
    },
  }));
  console.log(JSON.stringify({ parallel_workers: parallel.map(item => ({ index: item.index, ok: item.ok, usage: item.usage })) }, null, 2));
} finally {
  await client.close();
}
