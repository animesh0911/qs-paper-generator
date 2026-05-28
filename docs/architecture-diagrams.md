# Architecture Diagrams

Technical diagrams of the QS Paper Generator system, rendered with Mermaid.

> **How to view**
> - **GitHub**: renders Mermaid in `.md` files natively — open this file on github.com.
> - **VS Code**: install the [Markdown Preview Mermaid Support](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid) extension, then open this file and press `Cmd+Shift+V` (macOS) / `Ctrl+Shift+V` to preview.
> - **CLI / export**: `npx @mermaid-js/mermaid-cli -i docs/architecture-diagrams.md -o out.png` to export.

---

## 1. Process boundaries & runtime topology

```mermaid
flowchart LR
  subgraph Browser["Browser (teacher)"]
    FE["React 19 SPA<br/>Vite • TS • Tailwind • Zod<br/>React Router 7"]
  end

  subgraph DockerHost["docker-compose host"]
    direction TB

    subgraph WebSvc["web — Django 5"]
      DJ["WSGI runserver :8000<br/>DRF views<br/>SessionAuth + CSRF"]
      DJADM["/admin/<br/>Django admin"]
      HZ["/healthz"]
    end

    subgraph WorkerSvc["worker — Celery"]
      CW["celery -A config worker<br/>(ingest jobs, async tagging)"]
    end

    subgraph DB["db — postgres:16"]
      PG[("Postgres<br/>qpg")]
    end

    subgraph Cache["redis:7"]
      RDS[("Redis<br/>broker + result backend")]
    end

    subgraph FEDev["frontend — Vite dev :5173"]
      VITE["vite dev server<br/>proxy → web:8000"]
    end
  end

  subgraph External["External SaaS (lazy SDK import)"]
    AN["Anthropic API"]
    OA["OpenAI API"]
    GM["Gemini API"]
  end

  FE -- "HTTPS JSON<br/>/api/**" --> VITE
  VITE -. "dev proxy" .-> DJ
  FE -- "PDF GET<br/>/api/papers/{id}/pdf/" --> DJ

  DJ <-- "ORM (psycopg)" --> PG
  CW <-- "ORM" --> PG
  DJ -- "enqueue" --> RDS
  CW -- "consume / result" --> RDS

  DJ -- "LLMClient.complete()" --> AN
  CW -- "LLMClient.complete()" --> AN
  DJ -. alt .-> OA
  DJ -. alt .-> GM
```

---

## 2. Django app seams (process-internal modules)

```mermaid
flowchart TB
  subgraph DJ["Django project: config/"]
    direction TB
    URLS["config.urls<br/>/admin/ • /healthz<br/>/api/auth /api/bank /api/papers"]
  end

  subgraph accounts["accounts/"]
    AV["views: Register / Login / Me<br/>SessionAuth"]
    AM["models: User (+School FK)"]
  end

  subgraph bank["bank/ — question ingestion + storage"]
    BV["views<br/>metadata • chapters<br/>ingest • ingest-marking-scheme"]
    ING["Ingestor (coordinator)<br/>parse→strip-hindi→segment→tag→diagrams→persist<br/>apply_answers()"]
    PARS["Parser seam<br/>PdfplumberParser"]
    TAG["Tagger seam<br/>LLMTagger"]
    DIA["DiagramExtractor seam<br/>PdfplumberDiagramExtractor"]
    ANS["AnswerSource seam<br/>MarkingSchemeAnswerSource"]
    LLM["llm.LLMClient seam<br/>Anthropic / OpenAI / Gemini adapters<br/>(lazy SDK import, env-selected)"]
    BMOD["models: Question, Chapter, School"]
  end

  subgraph papers["papers/ — assemble + render"]
    PV["views<br/>AssemblePaperView • PaperDetail<br/>PaperApprove • PaperPdf"]
    TB["TemplateBuilder<br/>Preset → PaperTemplate (Slots, OR-groups)"]
    QP["QuestionPicker<br/>QuestionPool + chapter weights + difficulty mix<br/>→ FilledTemplate + CoverageReport"]
    PB["PaperBuilder.assemble()<br/>persists Paper + PaperQuestion<br/>builds PaperDocumentV1"]
    PDOC["PaperDocumentBuilder<br/>mapping → PaperDocumentV1 JSON"]
    PDF["pdf.render_paper_pdf(document)<br/>reads PaperDocumentV1 only"]
    PMOD["models: Paper, PaperQuestion"]
  end

  URLS --> AV
  URLS --> BV
  URLS --> PV

  BV --> ING
  ING --> PARS
  ING --> TAG
  ING --> DIA
  ING --> ANS
  TAG --> LLM
  ING --> BMOD

  PV --> PB
  PB --> TB
  PB --> QP
  QP --> BMOD
  PB --> PDOC
  PB --> PMOD
  PV --> PDF
  PDOC -. "stored on Paper.document (JSON)" .- PMOD
```

---

## 3. Ingestion data flow (question bank build)

```mermaid
sequenceDiagram
  autonumber
  participant T as Teacher (FE)
  participant V as bank.views.ingest
  participant I as Ingestor
  participant P as Parser (pdfplumber)
  participant Tg as LLMTagger
  participant L as LLMClient adapter
  participant D as DiagramExtractor
  participant PG as Postgres

  T->>V: POST /api/bank/ingest/ (PDF bytes)
  V->>I: ingest(pdf_bytes)
  I->>P: parse(pdf_bytes) → text
  I->>I: strip Hindi • segment → raw_questions
  I->>Tg: tag(raw_questions, chapters)
  Tg->>L: complete(prompt, max_tokens)
  L-->>Tg: JSON tags
  Tg-->>I: + chapter_slug, cognitive_level
  I->>D: extract(pdf_bytes, raw_questions) → image bytes
  I->>PG: bulk insert Question rows (verified=False)
  V-->>T: { created_count }

  Note over T,PG: Marking scheme flow
  T->>V: POST /api/bank/ingest-marking-scheme/
  V->>I: apply_answers(pdf)
  I->>PG: UPDATE Question.answer by ordered id
```

---

## 4. Paper assemble + render flow

```mermaid
sequenceDiagram
  autonumber
  participant FE as React SPA
  participant API as papers.views.AssemblePaperView
  participant PB as PaperBuilder
  participant TB as TemplateBuilder
  participant QP as QuestionPicker
  participant PD as PaperDocumentBuilder
  participant DB as Postgres
  participant PDF as papers.pdf

  FE->>API: POST /api/papers/assemble {preset, chapters, weights, difficulty}
  API->>PB: assemble(options)
  PB->>TB: build(preset) → PaperTemplate (Slots, OR-groups)
  PB->>QP: fill(template, PaperOptions)
  QP->>DB: load QuestionPool by (section,qtype,marks)
  QP-->>PB: FilledTemplate + CoverageReport
  PB->>DB: INSERT Paper + PaperQuestion rows
  PB->>PD: to_document(paper, filled, options)
  PD-->>PB: PaperDocumentV1 (JSON)
  PB->>DB: save Paper.document = doc and Paper.report = coverage
  API-->>FE: 200 PaperDocumentV1 (Zod-validated client side)

  Note over FE,PDF: Render path reads document only
  FE->>API: GET /api/papers/{id}/pdf/
  API->>DB: load Paper.document
  API->>PDF: render_paper_pdf(document)
  PDF-->>API: bytes
  API-->>FE: application/pdf
```

---

## 5. Contract & extensibility seams

```mermaid
flowchart LR
  subgraph Contract["contracts/v1_contract.md — PaperDocumentV1"]
    C1["schemaVersion • request<br/>template • paper • questions[]"]
  end

  subgraph BE["Backend producers"]
    PDOC2["PaperDocumentBuilder"]
    PDF2["pdf.render_paper_pdf"]
  end

  subgraph FEC["Frontend consumer"]
    ZOD["Zod schema (runtime check)<br/>BlockNote editor view"]
  end

  PDOC2 -- "produces" --> C1
  C1 -- "consumed verbatim" --> PDF2
  C1 -- "validated at network boundary" --> ZOD

  subgraph Seams["Adapter seams (depth-first design)"]
    direction TB
    S1["Parser"]
    S2["Tagger → LLMClient (Anthropic/OpenAI/Gemini)"]
    S3["DiagramExtractor"]
    S4["AnswerSource"]
    S5["Preset → TemplateBuilder"]
    S6["QuestionPool (testable without ORM)"]
  end
```

---

## Key invariants

- **Single render contract**: `Paper.document` (PaperDocumentV1) is the only thing the PDF renderer and FE editor read. `PaperQuestion` rows are an assembly snapshot for analytics, not a render input.
- **Process isolation**: `web` (sync DRF) and `worker` (Celery) share Postgres + Redis only; no in-process state.
- **LLM provider swap**: env `LLM_PROVIDER` selects adapter; SDKs imported lazily so unused providers add zero import cost.
- **Four ingestion seams** (`Parser` / `Tagger` / `DiagramExtractor` / `AnswerSource`) let tests inject stubs without PDF I/O or network.
- **Auth**: Django SessionAuth + CSRF; multi-tenant `School` FK present but passive in Slice 1.
