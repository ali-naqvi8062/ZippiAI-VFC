# Third-party sources

The Breville manual and diagrams retain their original ownership. Phase 2 includes extracted source evidence for the project demonstration. The full manual is downloaded during setup from https://assets.breville.com/BES500/BES500_USCM_IB_T23_LR.pdf and checked against SHA-256 f0a5e4024b1c57996b4a4771dc7ae9b5f29ff931fa915ec4b40569761dd8012f.

Phase 3 images come from **start2fix / Coffee-Machine-Parts-Detection**: https://huggingface.co/datasets/start2fix/Coffee-Machine-Parts-Detection, pinned revision 86f5bdc0a14e9a5eedc2abea27a24012fa52fae7. Its card lists CC BY 4.0 at the top and MIT in a footer. The conflicting labels and original photographer provenance remain unresolved; inclusion is not a claim of verified commercial reuse rights. The original card, URLs, image hashes, source splits and annotations are preserved in phase3/docs. Changes comprise orientation correction, RGB conversion, resizing and annotation/prediction overlays.

Model weights are not distributed here. Phase 2 downloads the MiniLM model recorded in its embedding manifest. Phase 3 downloads IDEA-Research/grounding-dino-tiny at the revision recorded in vision/core.py. Their upstream model licenses and dependency licenses apply separately. No blanket license is asserted over third-party images, manuals or models.
