# Phase 2 architecture

```text
PDF upload / CLI
   -> byte/type/size checks + SHA256 appliance identity
   -> selected-page text, word boxes and table candidates (pdfplumber)
   -> page rendering (Poppler) + known-manual diagram crops
   -> frozen Codex response OR configurable Gemini JSON generation
   -> Pydantic schema + identity + source/image validation
   -> local MiniLM ONNX embedding
   -> transactional SQLite draft storage
   -> admin edit + source review + explicit human attestations
   -> immutable published version + audit event
   -> appliance/manual-scoped cosine candidate search
```

The LLM drafts offline. It never supplies a new repair action during retrieval. Publication is a separate state change requiring five review attestations and a reviewer identity. All edit requests use the expected version to prevent lost updates. Saving any edit removes publication status, clears approval, increments version, and recomputes the retrieval vector. Historical releases are append-only through the app.

SQLite stores normalized 384-dimensional vectors as JSON. This is sufficient for three procedures; no vector service is needed. The MiniLM repository revision is pinned to `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Tokenizer truncation is 256 tokens; masked mean pooling and L2 normalization follow the model card. Stored model hashes detect changed local files. The ONNX runtime runs on CPU.

The original FastEmbed dependency was evaluated but an optional stemming module was blocked by Windows application control. The implementation instead uses the already functional ONNX Runtime and tokenizer packages directly; no security controls were changed. Only the dependencies actually used are in requirements.txt.

GET routes expose review evidence locally. State-changing requests require a custom header; cross-origin browser requests and unexpected Host values are rejected. All dynamic manual/model strings enter the page through textContent or input values. No dynamic HTML is trusted. Credentials remain server-side. Bind only to loopback. This is not a multiuser production admin service.

The generation prompt treats PDFs as untrusted data. The schema fixes the project safety steps, requires source pages and cause branches, disallows unknown fields and actions, and requires explicit unplugged/cool preconditions. Evidence checks confirm that cited regions contain source text and images belong to the manual. These checks cannot prove that an arbitrary sentence is safe or source-faithful. The human reviewer is a required semantic control. A limited forbidden-instruction check provides additional defense, not a comprehensive natural-language safety classifier.

## APIs

| Method | Route | Purpose |
|---|---|---|
| POST | /api/ingest | Multipart PDF, appliance_id, provider, optional pages |
| GET | /api/manuals | Ingested manual manifests |
| GET | /api/manuals/{sha}/procedures | Current draft/published records |
| GET | /api/manuals/{sha}/evidence | Extracted text, table candidates and word boxes |
| PUT | /api/manuals/{sha}/procedures/{id} | Validated edit with expected_version |
| POST | /api/manuals/{sha}/procedures/{id}/publish | Reviewed publication |
| POST | /api/search | Manual-scoped candidates; drafts only if preview=true |
| GET | /api/manuals/{sha}/export | Current JSON export |
| GET | /assets/{sha}/{name} | Page or diagram PNG |

OpenAPI documentation is available at /docs. POST and PUT requests need `X-AR-Admin: local-review`. This header is a local cross-origin defense, not authentication. Browser uploads can take several seconds; the first model download takes longer. Requests run in FastAPI's worker pool, keeping the async event loop available. Jobs are synchronous and bounded; there is no durable background-job queue.

## Known limits and next handoff

- Live Gemini calls and new-manual generalisation still need an approved credential and an integration test. Provider credentials were not discovered or assumed.
- Scan-only input requires OCR outside this pipeline. Mixed scan/text pages generate warnings; a reviewer must check omitted evidence.
- Automatic diagram semantics and arbitrary part crop generation are not implemented. New-manual drafts use source page images or null references.
- Text-aligned table extraction can split/merge rows. Source-image review is required, especially for conditional cause branches.
- Retrieval only ranks candidates. The known false candidates prevent claiming autonomous 8/10 correct procedure selection; 9/10 is top-1 ranking on a synthetic set.
- Runtime data contains the manual and any submitted model text. No automatic retention cleanup, encrypted storage, authenticated users or production deployment is included.
- Failed/concurrent staging folders are retained for diagnosis; no retention job is installed.
- Real reviewer sign-off, device/appliance access and mentor demo acceptance remain external prerequisites. No booking, messages, publication to a website or Git push was performed.
- Phase 3 should collect the separate real-photo localization set and use stable part IDs. Phase 4 must enforce entry conditions, cause confirmation and tap transitions; the Phase 2 UI is an admin tool, not repair guidance.
