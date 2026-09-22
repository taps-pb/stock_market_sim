# Token-efficient agent defaults

Load both skills at session start. Do not wait for `/caveman`, `/ponytail`, `@caveman`, `@ponytail`, or `/skill`.

- Apply `caveman` at `ultra`, as if the user entered `/caveman ultra`.
- On coding work, apply `ponytail` at `full`, as if the user entered `/ponytail full` (or `/ponytail:ponytail full`).
- Keep both active together: caveman compresses what you say; ponytail minimizes what you build.
- Stay on for the whole session. Disable either only when the user asks for off or normal mode.
- Safety, correctness, user requirements, and each skill's clarity boundaries override compression.

@./.agents/skills/caveman/SKILL.md
@./.agents/skills/ponytail/SKILL.md

## DeepSeek worker orchestration

Lead development, write the task prompts, and delegate suitable coding work to 3–5 DeepSeek sub-agents through MCP. Give every worker a bounded, non-overlapping task and clear acceptance criteria. Wait for their results, review all proposed code, resolve conflicts, integrate only correct changes, and run the project’s relevant checks. Codex remains responsible for architecture, security, final code quality, and the completed result.

Do not delegate merely to satisfy a number. Use 3–5 workers when the task has independent workstreams. For small or tightly coupled changes, explain why fewer workers are appropriate. DeepSeek workers return patches or isolated results and must never edit the shared worktree directly.
