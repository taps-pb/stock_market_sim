# Token-efficient agent defaults

Load both skills at session start. Do not wait for `/caveman`, `/ponytail`, `@caveman`, `@ponytail`, or `/skill`.

- Apply `caveman` at `ultra`, as if the user entered `/caveman ultra`.
- On coding work, apply `ponytail` at `full`, as if the user entered `/ponytail full` (or `/ponytail:ponytail full`).
- Keep both active together: caveman compresses what you say; ponytail minimizes what you build.
- Stay on for the whole session. Disable either only when the user asks for off or normal mode.
- Safety, correctness, user requirements, and each skill's clarity boundaries override compression.

@./.agents/skills/caveman/SKILL.md
@./.agents/skills/ponytail/SKILL.md
