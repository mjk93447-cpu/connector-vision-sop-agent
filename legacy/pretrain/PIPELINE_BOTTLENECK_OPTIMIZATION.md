# Pipeline Bottleneck Optimization

This document records the current delivery bottlenecks and the mandatory
quality gates that must run before expensive build/download/redeploy steps.

## 1) Current Bottleneck Timeline

Observed cycle for a minor runtime bug:

1. Debug and fix: ~30 minutes
2. Rebuild artifact: ~30 minutes
3. Download 3+ GB artifact: 60+ minutes (network-limited)
4. Redeploy to offline PC: ~10 minutes
5. Test run on offline PC: ~10 minutes

Total loss per small regression: **2+ hours**.

## 2) Optimization Principle

Fail fast before build and before download.  
Any crash that can be detected by static/runtime smoke checks must be blocked
in CI and in local pre-build flow.

## 3) Mandatory Checkpoints

### Checkpoint A: Runtime guard (fast static + import smoke)
- `scripts/preflight_gui_runtime.py`
- `scripts/preflight_pretrain_runtime.py`

Purpose:
- Catch method signature regressions (`@staticmethod` / `self` / `cls`)
- Catch model priority/config regressions in GUI training path
- Catch targeted pretrain runtime regressions (e.g., yaml path binding)

### Checkpoint B: CUDA/runtime smoke
- `scripts/preflight_cuda_pretrain.py`
- `scripts/preflight_cuda_app.py`

Purpose:
- Catch numpy/torch/cv2/ultralytics runtime incompatibility before PyInstaller
- Catch CUDA-wheel mismatch for GPU-intended bundles

### Checkpoint C: Focused regression unit tests
- `tests/unit/test_app_runtime_guardrails.py`
- `tests/unit/test_compact_pretrain_pipeline.py`

Purpose:
- Prevent known crash classes from re-entering (`NameError`, bad method binding)

### Checkpoint D: Launcher dry-run
- `python scripts/run_pretrain_local.py --dry-run --skip-bundle-prep`

Purpose:
- Validate pretrain launcher path without requiring dataset prep

## 3.1) Smart Gate Decision Rules (Built-in)

The gate now supports explicit stage/target selection:

- `scripts/pipeline_quality_gate.ps1 -Stage dev-fast -Target all`
- `scripts/pipeline_quality_gate.ps1 -Stage ci-smart -Target app`
- `scripts/pipeline_quality_gate.ps1 -Stage ci-smart -Target pretrain`
- `scripts/pipeline_quality_gate.ps1 -Stage ci-full -Target all`

Decision table in `ci-smart`:

1. Always run lightweight AST/runtime guards for the selected target.
2. Run heavy smoke + guardrail tests only when target-relevant files changed.
3. Treat dependency/spec/workflow changes as high risk and run target heavy checks.
4. If no runtime-relevant files changed, emit no-op guard and skip heavy checks.

Target path rules:

- App-relevant:
  - `src/main.py`
  - `src/gui/**`
  - `src/training/training_manager.py`
  - `scripts/preflight_gui_runtime.py`
  - `tests/unit/test_app_runtime_guardrails.py`

- Pretrain-relevant:
  - `src/training/compact_pretrain_pipeline.py`
  - `src/pretrain_runtime.py`
  - `scripts/run_pretrain_local.py`
  - `scripts/preflight_pretrain_runtime.py`
  - `tests/unit/test_compact_pretrain_pipeline.py`
  - `tests/unit/test_pretrain_runtime_guardrails.py`

- High-risk dependency/tooling triggers:
  - `requirements*`
  - `build_exe.spec`, `pretrain_exe.spec`
  - `scripts/pyinstaller_support.py`
  - `.github/workflows/**`
  - `src/runtime_compat.py`

## 4) Automated Gate Runner

Use:

```powershell
scripts\pipeline_quality_gate.ps1 -Stage dev-fast
scripts\pipeline_quality_gate.ps1 -Stage ci-prebuild
```

The gate writes machine-readable reports:
- `artifacts/checklists/quality-gate-<stage>-<timestamp>.json`

## 5) CI Integration

The quality gate is called before PyInstaller in:
- `.github/workflows/build.yml` (app bundle)
- `.github/workflows/build-pretrain.yml` (pretrain bundle)

This ensures expensive bundle generation is blocked when early checks fail.

## 6) Offline Deployment Rule

For emergency hotfixes:
1. Rebuild and ship only updated EXE when possible.
2. Avoid full bundle re-download if dataset/model payload is unchanged.
3. Record gate report alongside delivered EXE so the offline test operator can
   confirm checkpoint pass history.
