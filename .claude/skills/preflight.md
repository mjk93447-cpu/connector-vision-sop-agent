# Preflight Checklist

Use this checklist before large multi-file edits, broad reviews, or release
work. The intent is to keep every coding agent aligned before implementation.

## 1. Define scope

- List the files you expect to touch.
- State the user-facing goal in one or two sentences.

## 2. Check the active path

- Read `docs/ACTIVE_PATHS.md`.
- Confirm whether the task belongs to the shipping app, SOP flow, training, or
  an archived legacy path.

## 3. Choose validation

- Start with the smallest relevant test or smoke check.
- Move to broader validation only after the local change is stable.

## 4. Use helper models carefully

- Long-context helpers such as Gemini can summarize logs or large files.
- Claude, Cursor Codex sidebar, and ChatGPT 5.4 medium should still keep code
  edits, commits, and release actions in the main working session.

## 5. Protect critical assets

- Do not casually modify `assets/config.json`, runtime model slots, or release
  packaging rules without checking downstream effects.
- Avoid archived pretrain paths unless the task explicitly requires them.
