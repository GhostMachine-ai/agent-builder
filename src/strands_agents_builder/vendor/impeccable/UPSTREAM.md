# Vendored copy of Impeccable (subset)

This directory contains a vendored subset of **Impeccable** by Paul Bakaus,
licensed under Apache-2.0 (see `LICENSE` and `NOTICE.md` in this directory).

- Upstream repository: https://github.com/pbakaus/impeccable
- Upstream commit: `5d10bc842cbccd2ae7d3a88296d87d3be0b125b3`
- Upstream versions: CLI (npm `impeccable`) 3.5.0, skill/plugin 4.0.4
- Vendored on: 2026-08-08

## What is vendored

| Path here | Upstream source | Notes |
|---|---|---|
| `cli/bin/` | `cli/bin/` | detector CLI entry + subcommands |
| `cli/engine/` | `cli/engine/` | detection engine (59 rules), zero third-party deps |
| `cli/lib/impeccable-config.mjs` | `cli/lib/impeccable-config.mjs` | config loader imported by the engine |
| `guidance/SKILL.md` | `.agents/skills/impeccable/SKILL.md` | compiled, harness-neutral tree |
| `guidance/reference/` | `.agents/skills/impeccable/reference/` | **minus** `live.md` and `live-setup.md` |
| `guidance/command-metadata.json` | `.agents/skills/impeccable/scripts/command-metadata.json` | command catalog |
| `agents/` | `skill/agents/` | 4 specialist subagent definitions |
| `LICENSE`, `NOTICE.md` | repo root | verbatim (NOTICE has a Changes section appended) |
| `package.json` | — | stub added here: `{"type": "module"}` so the ESM CLI runs outside the upstream repo |

Not vendored: `skill/scripts/` (live browser-mode machinery), Puppeteer-based URL
scanning, all other harness-specific compiled trees.

## Updating

1. Clone the upstream repo at the desired tag/commit.
2. Re-copy the paths in the table above (delete this tree first, keep `package.json` and this file). `agents/` copies from `skill/agents/`.
3. Remove `guidance/reference/live.md` and `guidance/reference/live-setup.md`.
4. Check for unsubstituted placeholders: `grep -rl '{{' guidance/` must return nothing.
5. Smoke-test from this directory: `node cli/bin/cli.js detect --json --quiet --no-config <fixture.html>` (Node >= 22.18).
6. Update the commit/versions/date above and re-run the test suite.
