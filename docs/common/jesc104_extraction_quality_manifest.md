# jesc104 Canonical Extraction Quality Manifest

## Canonical Source

- Source chapter: `jesc104.pdf`, "Carbon and its Compounds"
- Source PDF SHA-256:
  `efbb053ea8cedf29bc6891834613fdbcc17772e369f6b35405f3bb4701c41abe`
- Canonical extractor: Docling `2.102.1` without formula enrichment
- Docling document schema: `1.10.0`
- Canonical JSON SHA-256:
  `915fe558fa87a46c796b756e8f6615ee8ef9fc6732cd6ecc6c1d964fc6216f5b`
- Canonical JSON local corpus path:
  `content/ncert/jesc104/jesc104.json`
- Representative committed fixture:
  `backend/corpus/tests/fixtures/jesc104_pages_1_8_16.json`

The full extraction and its 13 MB of referenced/page images remain in the
gitignored developer corpus directory. The representative fixture is committed
for deterministic tests. Importing uses the existing JSON and never runs
Docling.

## Reproduction Command

The canonical artifact was produced by:

```text
/Users/varad/Downloads/jesc104-extraction-comparison/.venv/bin/docling \
  /Users/varad/Downloads/jesc104/jesc104.pdf \
  --output /Users/varad/Downloads/jesc104-extraction-comparison/docling-output \
  --to md --to json
```

Import the existing artifact from the repository root:

```text
docker compose exec web python manage.py import_textbook_document \
  /content/ncert/jesc104/jesc104.json \
  --chapter carbon-and-its-compounds \
  --source-hash efbb053ea8cedf29bc6891834613fdbcc17772e369f6b35405f3bb4701c41abe
```

## Representative Review

### Page 1

- Preserved: chapter opening content, Activity 4.1, source coordinates, first
  table structure, and referenced images.
- Known loss: the Activity 4.1 heading is duplicated in raw Docling text.
  Deterministic normalization collapses the exact duplicate.
- Known risk: page number and print-code text are ordinary raw text elements;
  they remain inspectable until a demonstrated safe cleanup rule exists.

### Page 8

- Preserved: structural-isomer and ring/benzene content, captions, picture
  references, source coordinates, and reading order.
- Known loss: structural diagrams are fragmented across picture/text elements.
  The normalizer preserves those elements and assets rather than inventing a
  textual reconstruction.

### Page 16

- Preserved: "Properties of Ethanoic Acid", activities, reaction text,
  labelled apparatus text, Fig. 4.11 caption, source coordinates, and assets.
- Known loss: the reaction is flattened and chemically unsafe as searchable
  text; the visual source remains available.
- Known loss: sidebar/activity reading order is imperfect in the raw extraction.
  Source order is preserved rather than silently corrected.

## Explicitly Rejected Inputs

- Docling formula enrichment: slow and produced unsafe corrupted chemistry.
- Legacy Docling/formula-enriched JSON:
  `21968f318786de8e3125e0a1cb058d8d7c14f5bd9230d8f21311685757c29f63`
- MarkItDown as canonical source: loses required structure and traceability.
- Marker as an MVP dependency: the current bounded experiment produced no
  usable output.
