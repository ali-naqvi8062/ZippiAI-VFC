# Phase 3 pilot status — 6 November 2026

The appliance switch and reduced-data pilot are implemented. Five existing public photos replace the original requirement to capture 50 photos, as authorized by the user. These appear to be DeLonghi Dedica-family machines; exact variants are unverified.

## Measured results

Latest run: **0/9 visible targets localized at IoU >= 0.50 (0.0%)**. There were **1/2 false positives** on checked not-visible targets. Median inference time: 14.0 seconds per query; p95: 17.6 seconds, excluding model loading.

The baseline sentence prompts scored 0/9. The second run uses shorter part prompts with unchanged thresholds (box 0.35, text 0.25). Both runs are retained. This is development-set prompt tuning, not an independent held-out evaluation. Reference annotations are approximate assistant visual annotations, not expert ground truth. Unlabelled targets are excluded, not counted as absent.

Best recorded example: photo `train-18`, target `portafilter`, IoU 0.242. This does not meet the overlap criterion; reliable named-part localization remains unresolved.

## Deliverables and limits

- Five photos imported with URLs, hashes, original splits and source annotations recorded in the manifest.
- Eleven scored image/part queries: nine visible and two not visible. Green reference and orange predicted boxes can be compared in the lab and contact sheet.
- Upload, annotation, real inference, evaluation and JSON export are implemented. Fourteen automated checks passed, including image serving and API access guards. JavaScript syntax passed Node checking.
- No water-tank success is claimed. The original water-tank-specific acceptance item has not been demonstrated. This pilot tests the visible parts available in the public photos.
- No live camera tracking, AR overlay anchoring, or DeLonghi-specific repair instructions. Phase 2 Breville content remains separate.
- Small, selected web images cannot establish real-world reliability. Capture conditions, photographer provenance and exact machine variants are unknown. The dataset card has conflicting CC BY 4.0/MIT labels; see README attribution.

See `pilot-results.json` for all results, `baseline-results.json` for the first run, and `pilot-predictions.jpg` for every scored pair. No failures were removed from reported totals.

## Narrow handle demonstration

A third, three-query exploratory check used visual descriptions. “Black handle” produced a visually correct box around the portafilter handle in train-18 (see handle-demo.jpg). “Metal tube” and “metal tray” still failed. All three results are saved in visual-prompt-check.json. The handle box has IoU 0.464 against the broader portafilter-assembly annotation, so it is NOT counted as a full-part success or added to the reported accuracy. The app now exposes a separate portafilter_handle target with the black-handle prompt. This is one qualitative, selected development example, not a validated handle detector. Reference labels and earlier results were not altered to improve scores.
