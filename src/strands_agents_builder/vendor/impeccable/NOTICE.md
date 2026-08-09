# Third-Party Notices

This project includes content derived from third-party work, used under the terms of its original license.

## Platform Design Skills

The `skill/reference/ios.md` and `skill/reference/android.md` platform reference files are distilled from ehmo's `platform-design-skills` (Apple Human Interface Guidelines and Material Design 3 rules), rewritten in Impeccable's voice.

**Original work:** https://github.com/ehmo/platform-design-skills
**Original license:** MIT
**Author:** ehmo

## Changes made in this vendored copy (Apache License 2.0, Section 4(b))

This directory is a vendored subset of Impeccable (https://github.com/pbakaus/impeccable,
Copyright 2025 Paul Bakaus, Apache-2.0), modified as follows by the strands-agents-builder project:

- Only a subset of the upstream repository is included (detector CLI/engine, the compiled
  skill guidance markdown, and the subagent definitions); live browser mode and other
  harness-specific trees are omitted. See `UPSTREAM.md` for the exact file map.
- `guidance/reference/live.md` and `guidance/reference/live-setup.md` are removed.
- A stub `package.json` (`{"type": "module"}`) was added so the ESM CLI runs outside the
  upstream repository.
- Files were relocated (e.g. `.agents/skills/impeccable/` -> `guidance/`); file contents are
  otherwise unmodified.
