# Simple meeting demo

1. Double-click Run-Phase-3.cmd and open http://127.0.0.1:8766. If already running, open the address directly.
2. Say: “Phase 2 extracts information from a manual. Phase 3 is a separate experiment to locate appliance parts in photos.”
3. Say: “I switched to five existing DeLonghi Dedica-family photos for a small pilot.”
4. In section 2 choose the photo labelled train-18, then choose portafilter handle.
5. Click Locate part and wait around 15 seconds. An orange box should appear around the black handle. This is a fresh model prediction, not a stored box. No green reference label is supplied for this narrower target.
6. Say: “This selected example locates the handle using a visual description. It does not yet recognize all appliance parts reliably.”
7. Scroll to the saved results. Say: “The broader test scored zero out of nine full-part targets, with one false detection in two checked not-visible cases. The narrow handle example is separate from that score. Better part detection is still needed.”
8. Open docs/handle-demo.jpg if you need the previously recorded example. Show docs/pilot-predictions.jpg when discussing failures. Do not rerun the full evaluation during the meeting unless you have several minutes.

This demonstrates a working photo-to-prediction workflow and one narrow successful example, not completed robust appliance recognition. Live camera tracking, water-tank localization and DeLonghi repair guidance are not demonstrated.
