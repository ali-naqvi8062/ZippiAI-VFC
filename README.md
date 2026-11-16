# ZippiAI — AR Troubleshooting Companion

A prototype that turns product manuals into reviewable troubleshooting instructions and explores locating appliance parts in photos.

| Phase | What it does | Current status | How to use it |
|---|---|---|---|
| [1 — Planning](phase1/README.md) | Defines the appliance, workflow, architecture and procedure format. | Planning summary and surviving reference page; original supplied PDF is currently unavailable. | Read the documents; there is no application to run. |
| [2 — Manual ingestion](phase2/README.md) | Extracts PDF text and diagrams, loads three source-linked procedure drafts, supports editing/review and semantic search. | Working Breville BES500 demonstration. New-PDF LLM generation requires a Gemini key and has not been live-verified. | Run on port **8765** using the steps below. |
| [3 — Part localization](phase3/README.md) | Loads photos, draws reference boxes, runs a detector and measures its predicted boxes. | Five-photo DeLonghi Dedica-family pilot; one selected handle example works. Broader detection remains unsuccessful. | Run on port **8766** using the steps below. |

Phase 2 and Phase 3 are separate prototypes. Breville repair procedures must not be applied to the DeLonghi photos. Live camera tracking and AR anchoring are not implemented.

## First-time setup

Install **64-bit Python 3.12** and Git. Use **Command Prompt** for the commands below. Python 3.15 caused dependency installation failures in this project; explicitly selecting 3.12 avoids that problem. Each phase has its own environment because its dependencies differ.

```bat
git clone https://github.com/ali-naqvi8062/ZippiAI-VFC.git
cd ZippiAI-VFC
py -3.12 --version
```

There is no need to activate a PowerShell script or change your execution policy. Commands call the environment's Python directly. Internet access is needed for initial package, manual and model downloads. No model weights or Python environments are committed.

## Run Phase 1

Open [phase1/README.md](phase1/README.md). Phase 1 is the project plan, not runnable software. The [original Phase 2 report](phase2/docs/AR_Companion_Phase_2.pdf) also records how the plan was implemented.

## Run Phase 2 — manual review

Fresh PDF extraction requires **Poppler**, with `pdftoppm` available on PATH. The quickest bundled-demo setup below restores the included evidence snapshots and does not need Poppler or a fresh manual download. The official manual server returned HTTP 403 during repository preparation.

From the repository root:

```bat
cd phase2
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
.venv\Scripts\python.exe setup_demo.py --snapshot
Run-Demo.cmd
```

Open **http://127.0.0.1:8765** and leave the command window open. Snapshot setup restores the saved source-page evidence and three drafts, downloads the embedding model and computes embeddings. It is explicitly recorded as snapshot restoration, not fresh PDF extraction.

To exercise fresh extraction instead, install Poppler, check `pdftoppm -v`, then run `.venv\Scripts\python.exe setup_demo.py` in a fresh data workspace. That command downloads and hash-checks the official manual before ingestion. If the server blocks downloading, save the verified BES500 PDF at `phase2/data/input/BES500_USCM_IB_T23_LR.pdf` and rerun. On the original development computer the helper also detects bundled Poppler. Existing manual records are reused; use a separate data workspace for a fresh extraction after snapshot setup.

To demonstrate:

1. Select the loaded Breville manual and inspect its three troubleshooting drafts.
2. Compare a draft with the source-page image and component diagram.
3. Edit and save a draft.
4. Search for `Coffee leaks around the filter holder` with draft preview enabled.
5. Export the JSON. Publish only after an actual human review.

Uploading the **same PDF again** loads its existing record and preserves edits; that is intentional. The bundled mode replays previously generated drafts for this exact manual, rather than making a fresh AI request. For a different manual, see [fresh generation instructions](phase2/README.md#fresh-llm-generation-for-a-new-pdf). Configure Gemini credentials locally; never commit keys.

After initial setup, simply run `phase2\Run-Demo.cmd` again. Use Ctrl+C in its window to stop it.

## Run Phase 3 — photo detection

Open a second Command Prompt. From the repository root:

```bat
cd phase3
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
Run-Phase-3.cmd
```

Open **http://127.0.0.1:8766**. The five pilot photos and reference annotations are included. The Grounding DINO model downloads on the first prediction; allow extra time. Subsequent CPU predictions took about 14–17 seconds on the development computer.

To demonstrate the selected handle example:

1. In section 2 choose photo **train-18**.
2. Choose **portafilter handle**.
3. Click **Locate part**. The orange box is a fresh model prediction around the black handle.
4. Scroll down to the recorded evaluation and discuss its limitations.

Green boxes are reference annotations; orange boxes are model output. The narrower handle target has no green reference annotation. Full evaluation takes several minutes. [Meeting guide](phase3/docs/DEMO_GUIDE.md) · [Recorded handle example](phase3/docs/handle-demo.jpg) · [Detailed status](phase3/docs/PHASE_3_STATUS.md).

**Measured limitation:** both broader runs scored **0/9 visible full-part targets** at IoU ≥ 0.50, with **1 false detection in 2 not-visible cases**. The handle example is a selected qualitative success and is not added to that score. Five public development photos and approximate annotations do not establish general accuracy. Phase 3 is not fully complete; water-tank localization has not been demonstrated.

After initial setup, run `phase3\Run-Phase-3.cmd` again. If the photo folder is missing, run `.venv\Scripts\python.exe import_pilot.py` once to download the pinned five-photo selection. The importer refuses to overwrite existing annotations.

## Tests and reproducible evaluation

Run these from `phase2` after `setup_demo.py` completes:

```bat
.venv\Scripts\python.exe -m pytest tests\test_phase2.py -q
.venv\Scripts\python.exe tests\evaluate_retrieval.py --data-dir data --model-cache data\models --output docs\retrieval-results.json
```

Run these from `phase3`:

```bat
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe evaluate_pilot.py
```

The second command runs actual model inference and rewrites the latest report and contact sheet; earlier baseline evidence remains in separate files. `VISION_MODELS` can point to an existing model cache. Historical checks: Phase 2 had 29 passing tests with the full PDF and 9/10 positive retrieval rankings on a small authored set; snapshot-only setup skips the two tests that need original PDF bytes. Phase 3 had 14 passing software checks. Passing software tests does not imply accurate localization.

## Repository contents

- `phase1/`: planning summary and a surviving page from the supplied plan.
- `phase2/`: app source, tests, sample extraction, drafts, embeddings, report and run helpers.
- `phase3/`: app source, five photos, annotations, source manifest, evaluation records, visual results and meeting guide.
- `docs/`: delivery inventory and surviving brief reference page.

Local runtime databases, virtual environments, model caches, temporary files and duplicate ZIP bundles are excluded. They can be recreated from the source and setup instructions. See [delivery inventory](docs/DELIVERY_INVENTORY.md) and [third-party attribution](THIRD_PARTY_NOTICES.md).
