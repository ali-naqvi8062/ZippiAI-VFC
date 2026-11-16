# Phase 3 â€” DeLonghi Dedica-family pilot

The user approved replacing Breville and using fewer than 50 images. This version includes five public photos, approximate reference boxes authored by visual inspection, actual Grounding DINO inference, and exploratory measurements. Exact model variants are unverified. See docs/PHASE_3_STATUS.md for the outcome.

## Open the demo

1. Double-click Run-Phase-3.cmd in this folder.
2. Keep its window open and visit http://127.0.0.1:8766.
3. Five photos are already loaded. Choose a photo in section 2 and a part with a saved visible reference label.
4. Click Locate part and allow about 15 seconds. Green is the reference annotation; orange is the model prediction. No orange box means no detection, not proof of absence.
5. Section 3 loads the saved evaluation. Evaluate development reruns all 11 queries and can take several minutes. Download the JSON for every result.

If the server is already running, open the address directly. This is a local single-user prototype.

## Scope

- Five public photos selected visually as Dedica-family machines. Three come from the source train split and two from its test split. All five are development data in this project.
- Nine visible-part queries across steam wand, drip tray, portafilter and control panel, plus two checked not-visible control-panel queries.
- Unlabelled parts are not scored and are not assumed absent. Water tank localization is not validated.
- Reference annotations were drawn before inference. They are approximate assistant-reviewed boxes, not expert-certified ground truth. Original annotations are retained in the manifest but were not used because category assignments could not be reliably verified.
- Two development runs: original sentence prompts and shorter part prompts. Prompt selection used these images, so these are not held-out accuracy results.
- Optional pilot freeze requires three real test photos with labels and at least one visible example per required part. The older 50-photo protocol remains for workspaces without the pilot setting.

Phase 2 Breville manual procedures remain separate. This lab provides no DeLonghi repair instructions. Live video tracking and AR anchoring belong to a later phase.

## Attribution

Source: start2fix, Coffee-Machine-Parts-Detection, https://huggingface.co/datasets/start2fix/Coffee-Machine-Parts-Detection

Pinned revision: 86f5bdc0a14e9a5eedc2abea27a24012fa52fae7.
The card lists CC BY 4.0 at its top and MIT in a footer. That inconsistency and original photographer provenance are unresolved. The original card is saved in docs/dataset-card.md. Images are used as research/demo inputs; commercial redistribution rights have not been verified. Changes: EXIF orientation, RGB conversion, resize up to 1600 pixels and separate overlays. docs/pilot-manifest.json preserves URLs, hashes, splits and source annotations.

## Files

- data-dedica/: current photos, reference labels and full run records.
- docs/pilot-results.json: latest development run.
- docs/baseline-results.json: first run, including failures.
- docs/pilot-predictions.jpg: every scored query, green reference and orange prediction.
- docs/DEMO_GUIDE.md: meeting steps and suggested wording.
- import_pilot.py: pinned download and annotation import; refuses to overwrite a dataset.
- evaluate_pilot.py: real inference and report generation.

## Installation elsewhere

Use 64-bit Python 3.12. Run these commands in Command Prompt from this folder:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
Run-Phase-3.cmd
```

No PowerShell activation is required. This repository includes the five pilot photos and recorded results with source attribution. Model weights are downloaded on first inference. Run import_pilot.py only to rebuild a missing data-dedica folder; it refuses to overwrite existing labels. For tests, run Python -m pytest tests -q from this folder using the prepared work/venv environment.
