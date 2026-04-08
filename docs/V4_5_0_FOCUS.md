# 4.5.0 Focus

Version 4.5.0 should concentrate on detection stability and safe field
operation, not on expanding the archived pretrain stack.

## 1. Fine-Tuning

Goals:

- Improve detection quality from the completed seed
  `yolo26x_local_pretrained.pt`
- Reduce false positives on buttons, labels, and pin clusters
- Make retraining outcomes more repeatable across engineers and lines

Recommended improvements:

1. Add dataset quality gates before training starts
   - minimum image count per selected class
   - warning for severe class imbalance
   - warning when bbox sizes are abnormally small or large
2. Add validation-centric model selection
   - surface best epoch by `mAP50`, `mAP50-95`, and failure cases
   - keep the last good checkpoint instead of blindly promoting the newest one
3. Add hard negative capture support
   - let engineers save confusing non-target screens
   - use them to suppress false detections in SOP runtime
4. Strengthen reload safety
   - verify the new checkpoint can load before replacing the active model
   - keep one-click rollback to the previous working model
5. Track line-specific evaluation sets
   - keep a small locked validation pack per connector family
   - compare new checkpoints against the previous production model

## 2. SOP Editor

Goals:

- Prevent invalid SOP edits from reaching the line
- Make editor changes easier to review and safer to deploy

Recommended improvements:

1. Add schema-aware field validation for every step type
   - required fields
   - allowed key names
   - numeric range checks for waits, retries, ROI coordinates
2. Add simulation and dry-run preview in the editor
   - show step order
   - show target/button_text resolution
   - flag likely missing labels before save
3. Add change review metadata
   - who changed what
   - why
   - when
4. Add guarded templates for common step patterns
   - login
   - mold setup
   - text input
   - pin verification
5. Add diff-first save UX
   - show exact JSON changes before committing them

## 3. SOP Run

Goals:

- Raise first-pass success rate
- Make failures diagnosable from logs without recreating the run
- Prevent operator-facing instability when the screen environment changes

Recommended improvements:

1. Add preflight checks before each run
   - active window check
   - screen resolution check
   - model presence check
   - OCR backend readiness
2. Capture stronger evidence on failure
   - screenshot
   - active step id
   - OCR candidates
   - top detections with confidence
3. Improve runtime fallback logic
   - OCR-first, then detection, then controlled retry
   - never escalate to unsafe clicks when confidence is low
4. Add per-step confidence thresholds
   - stricter thresholds for destructive actions
   - more tolerant thresholds for navigation-only steps
5. Add recovery boundaries
   - stop after repeated ambiguity
   - prompt for human review instead of compounding bad state

## 4. Release criteria

4.5.0 should be considered healthy only if:

1. App bundle launches the GUI by default.
2. Training defaults prefer `yolo26x_local_pretrained.pt`.
3. Archived pretrain paths are clearly marked and excluded from active app packaging.
4. Documentation points new work toward fine-tuning, SOP Editor, and SOP Run.
