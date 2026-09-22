#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { resolve, relative, sep } from "node:path";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

const MODEL = process.env.DEEPSEEK_MODEL || "deepseek-flash";
const KEY_FILE = process.env.DEEPSEEK_KEY_FILE || "/Users/taps-pb/Documents/work/ds_api.txt";
const PROJECT_ROOT = resolve(process.env.DEEPSEEK_PROJECT_ROOT || process.cwd());
const API = "https://api.deepseek.com";
const BLOCKED = new Set([".git", ".venv", "node_modules", "data", "dist", "__pycache__"]);
const MAX_FILE_BYTES = 400_000;
const MAX_CONTEXT_BYTES = 1_500_000;

async function apiKey() {
  const raw = (await readFile(KEY_FILE, "utf8")).trim();
  const assignment = raw.split(/\r?\n/).find(line => /^\s*(?:export\s+)?DEEPSEEK_API_KEY\s*=/.test(line));
  let key = assignment ? assignment.replace(/^\s*(?:export\s+)?DEEPSEEK_API_KEY\s*=\s*/, "").trim() : raw;
  if ((key.startsWith('"') && key.endsWith('"')) || (key.startsWith("'") && key.endsWith("'"))) key = key.slice(1, -1);
  if (!key || /\s/.test(key)) throw new Error("Credential file does not contain a valid raw key or DEEPSEEK_API_KEY assignment");
  return key;
}

async function request(path, init = {}) {
  const key = await apiKey();
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}`, ...init.headers },
    signal: AbortSignal.timeout(180_000),
  });
  const text = await response.text();
  let body;
  try { body = JSON.parse(text); } catch { body = { error: { message: text.slice(0, 500) } }; }
  if (!response.ok) throw new Error(`DeepSeek API ${response.status}: ${body?.error?.message || "request failed"}`);
  return body;
}

async function availableModels() {
  const body = await request("/models", { method: "GET", headers: { "Content-Type": undefined } });
  return (body.data || []).map(item => item.id).filter(Boolean);
}

async function requireModel() {
  const models = await availableModels();
  if (!models.includes(MODEL)) {
    throw new Error(`Required model ${MODEL} is unavailable. Available identifiers: ${models.join(", ") || "none"}`);
  }
  return models;
}

function usageSummary(usage = {}) {
  const input = usage.prompt_tokens || usage.input_tokens || 0;
  const output = usage.completion_tokens || usage.output_tokens || 0;
  const hit = usage.prompt_cache_hit_tokens || usage.input_tokens_details?.cached_tokens || 0;
  const miss = usage.prompt_cache_miss_tokens ?? Math.max(0, input - hit);
  const offPeak = (hit * 0.003 + miss * 0.15 + output * 0.6) / 1_000_000;
  const peak = (hit * 0.006 + miss * 0.3 + output * 1.2) / 1_000_000;
  return {
    input_tokens: input,
    output_tokens: output,
    cache_hit_tokens: hit,
    cache_miss_tokens: miss,
    estimated_usd: { off_peak: Number(offPeak.toFixed(6)), peak: Number(peak.toFixed(6)) },
  };
}

async function loadContext(paths = []) {
  let bytes = 0;
  const files = [];
  for (const requested of paths) {
    if (typeof requested !== "string" || !requested.trim()) throw new Error("context_paths must contain non-empty strings");
    const full = resolve(PROJECT_ROOT, requested);
    const rel = relative(PROJECT_ROOT, full);
    if (!rel || rel.startsWith(`..${sep}`) || rel === ".." || rel.split(sep).some(part => BLOCKED.has(part))) {
      throw new Error(`Context path is outside allowed project sources: ${requested}`);
    }
    const content = await readFile(full, "utf8");
    const size = Buffer.byteLength(content);
    if (size > MAX_FILE_BYTES) throw new Error(`Context file exceeds ${MAX_FILE_BYTES} bytes: ${requested}`);
    bytes += size;
    if (bytes > MAX_CONTEXT_BYTES) throw new Error(`Combined context exceeds ${MAX_CONTEXT_BYTES} bytes`);
    files.push(`\n===== ${rel} =====\n${content}`);
  }
  return files.join("\n");
}

async function runWorker(input) {
  if (!input || typeof input.task !== "string" || !input.task.trim()) throw new Error("task is required");
  await requireModel();
  const context = await loadContext(input.context_paths || []);
  const criteria = Array.isArray(input.acceptance_criteria) ? input.acceptance_criteria : [];
  const prompt = `You are a coding worker. Do not claim to edit files and do not execute commands. Analyze only the supplied context. Return a reviewable proposal in exactly these sections:\n\nEXPLANATION\nShort rationale and risks.\n\nPROPOSED CHANGES\nBulleted file-level changes.\n\nPATCH\nOne unified diff beginning with diff --git. If no change is needed, write NO PATCH.\n\nVALIDATION\nCommands the lead should run.\n\nKeep scope bounded. Preserve unrelated behavior. Never include secrets.\n\nTASK\n${input.task.trim()}\n\nACCEPTANCE CRITERIA\n${criteria.length ? criteria.map(item => `- ${item}`).join("\n") : "- Meet the task with the smallest correct patch."}\n\nPROJECT CONTEXT\n${context || "No files supplied; answer only the focused smoke-test request."}`;
  const body = await request("/chat/completions", {
    method: "POST",
    body: JSON.stringify({
      model: MODEL,
      messages: [
        { role: "system", content: "Produce precise, minimal coding patches for lead review. Never modify a worktree directly." },
        { role: "user", content: prompt },
      ],
      thinking: { type: "disabled" },
      max_tokens: Math.min(Math.max(Number(input.max_output_tokens) || 12_000, 64), 24_000),
    }),
  });
  const content = body.choices?.[0]?.message?.content;
  if (typeof content !== "string" || !content.trim()) throw new Error("DeepSeek returned no worker content");
  return { model: body.model || MODEL, result: content, usage: usageSummary(body.usage) };
}

const tools = [
  {
    name: "check_connection",
    description: "Verify credential readability, exact DeepSeek model availability, and a minimal authenticated API request. Never returns the credential.",
    inputSchema: { type: "object", additionalProperties: false, properties: {} },
  },
  {
    name: "run_worker",
    description: "Send one bounded coding task and selected project files to a DeepSeek worker. Returns explanation, proposed changes, unified patch, validation, and usage. Never edits files.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      required: ["task"],
      properties: {
        task: { type: "string", minLength: 1 },
        context_paths: { type: "array", maxItems: 30, items: { type: "string" }, default: [] },
        acceptance_criteria: { type: "array", maxItems: 20, items: { type: "string" }, default: [] },
        max_output_tokens: { type: "integer", minimum: 64, maximum: 24000, default: 12000 },
      },
    },
  },
  {
    name: "run_workers_parallel",
    description: "Run 3–5 independent DeepSeek coding workers concurrently. Every worker is isolated and returns a patch for lead review; no files are edited.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      required: ["tasks"],
      properties: {
        tasks: {
          type: "array",
          minItems: 3,
          maxItems: 5,
          items: {
            type: "object",
            additionalProperties: false,
            required: ["task"],
            properties: {
              task: { type: "string", minLength: 1 },
              context_paths: { type: "array", maxItems: 30, items: { type: "string" }, default: [] },
              acceptance_criteria: { type: "array", maxItems: 20, items: { type: "string" }, default: [] },
              max_output_tokens: { type: "integer", minimum: 64, maximum: 24000, default: 12000 },
            },
          },
        },
      },
    },
  },
];

const server = new Server(
  { name: "market-lab-deepseek-workers", version: "1.0.0" },
  {
    capabilities: { tools: {} },
    instructions: "Delegate bounded, non-overlapping coding tasks. Workers only return patches. Lead must review, apply accepted changes, resolve conflicts, and validate. Use parallel workers only for independent workstreams.",
  },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools }));
server.setRequestHandler(CallToolRequestSchema, async requestMessage => {
  try {
    const { name, arguments: args = {} } = requestMessage.params;
    let result;
    if (name === "check_connection") {
      const models = await requireModel();
      const body = await request("/chat/completions", {
        method: "POST",
        body: JSON.stringify({ model: MODEL, messages: [{ role: "user", content: "Reply exactly OK." }], max_tokens: 16 }),
      });
      result = {
        credential_file_readable: true,
        requested_model: MODEL,
        available_models: models,
        minimal_response_received: Boolean(body.choices?.[0]?.message),
        response_model: body.model || MODEL,
        usage: usageSummary(body.usage),
      };
    } else if (name === "run_worker") {
      result = await runWorker(args);
    } else if (name === "run_workers_parallel") {
      const tasks = args.tasks;
      if (!Array.isArray(tasks) || tasks.length < 3 || tasks.length > 5) throw new Error("tasks must contain 3–5 workers");
      const settled = await Promise.allSettled(tasks.map(runWorker));
      result = settled.map((item, index) => item.status === "fulfilled"
        ? { index, ok: true, ...item.value }
        : { index, ok: false, error: item.reason instanceof Error ? item.reason.message : String(item.reason) });
    } else {
      throw new Error(`Unknown tool: ${name}`);
    }
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  } catch (error) {
    return {
      isError: true,
      content: [{ type: "text", text: error instanceof Error ? error.message : String(error) }],
    };
  }
});

await server.connect(new StdioServerTransport());
