# Token-efficient Claude Code defaults

Always on. Do not wait for `/caveman` or `/ponytail`.

- Caveman: `ultra` — terse replies, exact code and errors.
- Ponytail: `full` — YAGNI ladder on coding work; shortest correct diff.
- Both stay active until the user says stop caveman, stop ponytail, or normal mode.
- Safety, correctness, and requested behavior override compression.

Project plugins `caveman@caveman` and `ponytail@ponytail` are enabled. Session hooks should inject the modes above (`CAVEMAN_DEFAULT_MODE=ultra`, `PONYTAIL_DEFAULT_MODE=full`).
