# Large-Context Analysis Rule

Use Gemini CLI only as an optional helper for long-context analysis and review.
Primary code edits, tests, commits, and release work still belong in the main
coding agent session.

## Shared guidance

- Claude, Cursor Codex sidebar, and ChatGPT 5.4 medium should all follow the
  same product rules in this repository.
- If a secondary large-context model is available, use it for exploration,
  diff review, or log triage only.
- Never ask the helper model to edit repository files directly.

## Good delegation targets

- Summarizing a 500+ line file before making a focused edit
- Reviewing a large staged diff for regressions
- Classifying long pytest or build logs
- Mapping dependency or import side effects across multiple files

## Guardrails

- Keep `assets/config.json` and `assets/models/` under the main coding agent's
  control.
- Validate helper-model conclusions against the actual local files before
  editing code.
- Treat helper output as advisory, not as the source of truth.
