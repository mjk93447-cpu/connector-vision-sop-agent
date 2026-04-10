# Testing Rules

These rules describe the repository test policy for any coding agent.

## Default command

```bash
bash run_tests.sh
```

Use the repository's normal test runner when you need broad validation.

## Active-path preference

- For fast iteration, prioritize tests that exercise the active app surface:
  GUI runtime, model promotion, SOP execution, and training integration.
- Keep archived pretrain tests out of normal app-release validation unless the
  task explicitly targets legacy pretrain maintenance.

## Shared agent interpretation

- Claude, Cursor Codex sidebar, and ChatGPT 5.4 medium should all prefer
  targeted tests first, then broader suites once the active path is stable.
- Do not let a helper model redefine the test scope; the repository rules do.

## New feature expectation

- Changes to SOP execution, GUI behavior, or training/model routing should ship
  with targeted validation.
- Vision and OCR tests should keep using mocks or monkeypatching where the
  existing suite already follows that pattern.
