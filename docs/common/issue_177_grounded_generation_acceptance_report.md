# Issue 177 — jesc104 Grounded-Generation Acceptance Gate

Status: final model/count recommendation selected; remaining work is semantic/manual candidate review plus final #177 pass/fail packaging.

## Ralph-loop plan

1. Worktree: `/Users/varad/V/repo/qs-paper-generator-issue-177`, branch `codex/issue-177`, base `origin/main` at `8b9cc79`.
2. Keep scope to `jesc104` / `carbon-and-its-compounds`; do not ingest other NCERT chapters.
3. First live checkpoint: one-topic, two-model POC using the existing grounded GenerationBatch path.
4. Review POC output for schema validity, NCERT faithfulness, and citations that support both Question and answer.
5. If the POC is acceptable, run the bounded one-chapter acceptance slice topic-by-topic; otherwise remediate the named gap before any larger run.

## Deterministic setup evidence

Canonical source imported from `content/ncert/jesc104/jesc104.json` using Docling source hash `efbb053ea8cedf29bc6891834613fdbcc17772e369f6b35405f3bb4701c41abe`.

Import command:

```text
docker compose exec -T web python manage.py import_textbook_document \
  /content/ncert/jesc104/jesc104.json \
  --chapter carbon-and-its-compounds \
  --source-hash efbb053ea8cedf29bc6891834613fdbcc17772e369f6b35405f3bb4701c41abe
```

Measured re-import time on the local development machine: `real 1.82s`.

Corpus metrics after import:

| Metric | Value |
| --- | ---: |
| TextbookElements | 496 |
| ChapterMapNodes | 70 |
| ChapterMapEdges | 138 |
| RetrievalChunks | 153 |
| RetrievalChunk text characters | 57,845 |
| Corpus table+index size | 2,512 kB |
| TextbookElement table+index size | 888 kB |
| ChapterMapNode table+index size | 144 kB |
| RetrievalChunk table+index size | 1,480 kB |

Selected major-topic context diagnostics:

| Topic | Included chunks | Skipped chunks | Context chars | 25k cap reached |
| --- | ---: | ---: | ---: | --- |
| 4.1 Bonding in Carbon — The Covalent Bond | 29 | 8 | 11,027 | no |
| 4.2 Versatile Nature of Carbon | 40 | 8 | 15,045 | no |
| 4.3 Chemical Properties of Carbon Compounds | 15 | 4 | 7,115 | no |
| 4.4 Ethanol and Ethanoic Acid | 19 | 4 | 7,971 | no |
| 4.5 Soaps and Detergents | 19 | 7 | 7,210 | no |

Embeddings were intentionally skipped: selected-topic generation uses deterministic ChapterMapNode subtree context and does not need dense/hybrid retrieval.

## Planned live POC consent scope

Do **not** run until explicitly approved.

- Chapter: `carbon-and-its-compounds` (`jesc104` only)
- Topic: `4.2 VERSATILE NATURE OF CARBON`
- ChapterMapNode ID: `ef1e9dcd30dfc5300e40290da35a891db5f90a654a4df2b1d9e4e3a7d0c23f43`
- Candidate count per model: 3
- Context policy: query-free selected subtree, excludes existing NCERT question/exercise chunks, picture-only chunks without captions, and formula-only chunks.
- Context size: 40 excerpts, 15,045 NCERT characters, cap not reached.
- Prompt size estimate: 25,062 characters, approximately 6,266 input tokens using the 4 chars/token estimate.
- Live calls requested: 2 total, no silent retries.
  - Gemini: provider `gemini`, model `gemini-3.5-flash`, one structured-output generation call, `LLM_MAX_RETRIES=0` recommended for the acceptance POC.
  - DeepSeek: provider `deepseek`, OpenAI-compatible model route, target model per configured API access, one structured-output generation call, `LLM_MAX_RETRIES=0` recommended for the acceptance POC.
- Estimated cost envelope from `docs/common/question_generation_model_cost_report.md`: Gemini under about `$0.06` for this one standard call; DeepSeek under about `$0.003` for this one standard call. Actual billing depends on provider credentials/model routing and output length.

## Live POC log

### OpenRouter Gemini artifact-write failure — 2026-06-21

Under the initial approved two-model POC scope, an OpenRouter Gemini run was started before the later instruction to do DeepSeek first. The script failed while writing `/app/content/issue_177_poc_gemini.json` because `/app/content` is not the mounted content directory; it should have used `/content/...`.

- Provider route: `openrouter`
- Model: `google/gemini-3.5-flash`
- Calls: treated as 1 attempted live call for accounting because the failure occurred after the generation path, not before model construction.
- Batch: `#2`
- Persisted candidates: 0
- Artifact: none due to local path error.

No further Gemini run has been attempted after the DeepSeek-first instruction.

### DeepSeek first run — 2026-06-21

Approved scope: use the existing OpenRouter key for a DeepSeek-first POC before Gemini, keeping model switching easy through environment configuration.

- Provider route: `openrouter`
- Model: `deepseek/deepseek-v4-flash`
- Calls: 1
- Retries: `LLM_MAX_RETRIES=0`
- Batch: `#4`
- Topic: `4.2 VERSATILE NATURE OF CARBON`
- Elapsed: 29,811 ms
- Result: transport/model invocation completed without exception, but the initial `LangChainQuestionGenerator` path returned `0` valid candidates.
- Artifact: `content/issue_177_poc_deepseek.json`

Decision: do not silently retry. Tighten the OpenAI-compatible schema and get explicit approval for the next DeepSeek call.

### DeepSeek retry with stricter schema — 2026-06-21

Approved scope: one additional OpenRouter DeepSeek call, same topic/count, no retries, capture raw output for quality/grounding/ingestibility review.

- Provider route: `openrouter`
- Model: `deepseek/deepseek-v4-flash`
- Calls: 1
- Retries: `LLM_MAX_RETRIES=0`
- Batch: `#5`
- Topic: `4.2 VERSATILE NATURE OF CARBON`
- Prompt/context: 25,088 chars, approximately 6,272 input tokens by the 4 chars/token estimate.
- Elapsed: 17,830 ms
- Raw questions returned: 3
- Valid persisted candidates: 0
- Artifact: `content/issue_177_poc_deepseek_retry_strict_schema.json`

#### Quality review

| Raw candidate | Factual quality | Citation support | Ingestibility |
| --- | --- | --- | --- |
| MCQ on catenation | Good: asks the central catenation property and answer is correct. Somewhat direct/definition-level, but acceptable for a 1-mark MCQ. | Good: cited chunk states carbon forms bonds with carbon atoms, large molecules, and names this property catenation. | Rejected: `content.stem` missing; MCQ options emitted as strings instead of structured option objects, causing `mcq_answer_mismatch`. |
| Very-short answer on tetravalency+catenation | Good: exact NCERT recall question and answer. | Good: cited chunk explicitly says tetravalency and catenation together give rise to many compounds. | Rejected: emitted `very_short_answer/1`; contract requires `very_short_answer/2`. Also missing `content.stem`. |
| Short answer on strong bonds/small atom size | Good: grounded explanation, answer follows NCERT language closely. | Good: cited chunk states small size lets nucleus hold shared electron pairs strongly and bigger atoms form weaker bonds. | Rejected: emitted `short_answer/2`; contract requires `short_answer/3`. Also missing `content.stem`. |

#### Grounding-lane review

The deterministic NCERT grounding lane is working correctly for this POC:

- The request used the selected canonical ChapterMapNode `4.2 VERSATILE NATURE OF CARBON` and descendant section/topic chunks only.
- The context assembler returned 40 excerpts / 15,045 NCERT characters, under the 25,000-character defensive cap.
- Existing NCERT question/exercise chunks, picture-only chunks without captions, and formula-only chunks were excluded by the context policy.
- DeepSeek cited stable chunk IDs from the supplied manifest; there were no `unknown_citation` validation errors.
- Manual spot-check of all three cited chunks confirms they support both the generated Question and answer claims.
- No evidence in this run suggests the model answered from unsupported memory; all three facts are present in the supplied NCERT excerpts.

#### Ingestibility review

DeepSeek's content is semantically close, but the raw payload is **not yet directly ingestible** by the current bank contract:

- `0/3` raw questions passed deterministic validation.
- Main failures are structural rather than factual: loose `content.text`, string MCQ options, and marks that do not match this app's fixed qtype contract.
- The gate behaved correctly by persisting no `GeneratedQuestionCandidate` rows for invalid payloads.
- This result argues for schema/prompt hardening before comparing Gemini or running more DeepSeek calls, not for weakening the validator.

### DeepSeek hardened-schema timeout that later persisted — 2026-06-21

Approved scope: one more OpenRouter DeepSeek call after schema/prompt hardening, same topic/count, no retries.

- Provider route: `openrouter`
- Model: `deepseek/deepseek-v4-flash`
- Calls: 1 attempted live call; the shell timed out after model invocation started.
- Retries: `LLM_MAX_RETRIES=0`
- Batch: `#6`
- Topic: `4.2 VERSATILE NATURE OF CARBON`
- Command timeout: 240 seconds
- Artifact: none; script did not reach artifact write.
- Persisted candidates observed later: 8

Important finding: the model eventually returned and persisted 8 valid candidates even though the request count was 3. Root cause: the prompt said `Total candidates: 3` but also showed the default type distribution `{mcq: 4, very_short_answer: 2, short_answer: 2, long_answer: 2}`. DeepSeek followed the distribution more than the total count.

Fix: the default QuestionType distribution is now scaled to the requested count and the prompt says `Total candidates: exactly N`.

#### Review of the 8 persisted candidates

- Ingestibility: `8/8` were accepted by the deterministic validator and persisted as `GeneratedQuestionCandidate` rows.
- Shape: all accepted candidates had `content.stem`; MCQs had structured `content.options`; marks matched qtype.
- Quality: generally good for a first bank draft. The set covers catenation, saturated/unsaturated compounds, functional groups, tetravalency, carbon bond strength, IUPAC naming, and structural isomerism.
- Grounding: candidate citations are stable chunk IDs from the supplied 4.2 manifest. The sampled citations align with the generated claims.
- Concerns: several questions are long for their marks, especially the MCQ stems. One long-answer item asks to "Draw the structures" using text-only structures; diagram/formula-heavy generation is supposed to remain out of scope, so this should be rejected or prompt-filtered in the next hardening pass.
- Batch control: unacceptable before fix; requested 3 produced 8. This was a prompt/distribution bug, not a validator bug.

#### Batch-size feasibility estimate from real DeepSeek output

The 8 persisted candidates totalled about 11,832 serialized JSON characters, averaging 1,479 chars / ~370 output tokens per candidate by the 4 chars/token estimate.

Approximate one-call output sizes on this topic:

| Requested candidates | Approx output tokens | Feasibility concern |
| ---: | ---: | --- |
| 1 | ~370 | Best for model comparison and debugging. |
| 3 | ~1,110 | Good MVP review batch once count control is fixed. |
| 10 | ~3,700 | Likely feasible, but review burden rises. |
| 25 | ~9,250 | Possible, but answer quality/diversity and latency need measurement. |
| 50 | ~18,500 | Not recommended for MVP: high latency, higher chance of schema drift/duplicates, and too many candidates for teacher review in one slice. |

For `jesc104` topic generation, the safer operating range is likely 3–10 candidates per selected topic. A 50-candidate single call is probably technically possible on the selected large-context models, but it is the wrong MVP shape: it makes validation failures expensive, increases latency, and weakens human review quality.

### Count=10 model comparison — 2026-06-21

Approved scope: run one `count=10` grounded generation call for each model through OpenRouter, same 4.2 topic, no retries, then compare cost and quality.

| Model | Calls | Latency | Raw count | Valid/persisted | Approx input tokens | Approx output tokens | Estimated cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `deepseek/deepseek-v4-flash` | 1 | 299,960 ms | 10 | 0 | 6,342 | 2,336 | ~$0.0015 |
| `google/gemini-3.5-flash` | 1 | 49,102 ms | 10 | 9 | 6,342 | 3,829 | ~$0.0440 |

Cost assumptions use the report rates: DeepSeek at roughly `$0.14/M` input and `$0.28/M` output; Gemini at `$1.50/M` input and `$9.00/M` output. Actual OpenRouter billing may differ slightly by route/provider, but the relative result is stable: Gemini is around 25–30x more expensive for this call shape, while still only a few cents for a one-topic `count=10` test.

#### DeepSeek count=10 review

Artifact: `content/issue_177_poc_deepseek_count10.json`.

- Transport/model call succeeded, but took about 5 minutes.
- Returned exactly 10 raw questions after the count/distribution fix.
- Generated the desired qtype mix: 3 MCQ, 3 very-short-answer, 2 short-answer, 2 long-answer.
- Structural content was mostly good: `content.stem` and MCQ option objects were present.
- Ingestibility failure: `0/10` accepted because every item left `raw_text` blank. Validation rejected all with `empty_question`.
- Quality from the visible stem/answer fields looked broadly NCERT-aligned, but the result is not usable without additional `raw_text` hardening.
- Follow-up fix added after the run: schema now sets `raw_text.minLength=1` and prompt explicitly says `raw_text must be a non-empty plain-text copy of the full Question stem`.

#### Gemini count=10 review

Artifact: `content/issue_177_poc_gemini_count10.json`.

- Transport/model call succeeded in about 49 seconds.
- Returned exactly 10 raw questions.
- Persisted `9/10` candidates; the rejected candidate used one invented/unknown citation ID.
- Generated the same requested qtype mix: 3 MCQ, 3 very-short-answer, 2 short-answer, 2 long-answer.
- Ingestibility was clearly better than DeepSeek for this prompt/schema: non-empty `raw_text`, structured content, fixed marks, and valid source fields on 9 candidates.
- Grounding was mostly good: valid candidates cited supplied NCERT chunks. The validator correctly blocked the one candidate with an unknown citation.
- Quality was acceptable for teacher-review drafts. Questions covered catenation, homologous series, isomerism, Wöhler/organic chemistry history, heteroatoms/functional groups, saturated vs unsaturated compounds, and carbon's bonding properties.
- Concerns: one accepted answer for the first three alkane members appears truncated after methane and ethane in the artifact preview; teacher review remains necessary. Some items are a bit advanced/dense for their mark value. The rejected nomenclature item was content-relevant but citation-invalid.

#### Count=10 decision

- `count=10` is feasible for Gemini on this one topic: good latency, high ingestibility, acceptable review quality, and estimated cost under five cents.
- `count=10` is not yet feasible for DeepSeek with the current prompt/schema: latency was high and raw output failed ingestion due to blank `raw_text`.
- DeepSeek remains attractive on cost, but needs another small hardening check before trusting it for larger batches.
- A `count=50` live run is not recommended yet. Extrapolating from Gemini count=10, cost may still be manageable, but review load, latency, duplicate risk, and unsupported/invalid citation risk make 50 the wrong MVP batch size. Prefer 5–10 candidates per selected major topic.

### Cheap OpenRouter alternative sweep, count=20 — 2026-06-21

Approved scope: exclude Gemini and DeepSeek for this experiment; run five cheap OpenRouter alternatives at `count=20`, same 4.2 grounded context, no retries.

| Model | Latency | Raw count | Valid/persisted | Qtype mix | Est. cost | Verdict |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| `qwen/qwen3-235b-a22b-2507` | 365.5s | 20 | 20 | 5/5/5/5 | ~$0.0011 | Best schema compliance, but slow and has some semantic overreach. |
| `mistralai/mistral-small-24b-instruct-2501` | 327.2s | 21 | 21 | 5/5/5/6 | ~$0.0008 | Very strong ingestibility/cost; over-generated by 1 and is somewhat generic. |
| `openai/gpt-oss-120b` | 150.1s | 20 | 19 | 5/5/5/5 | ~$0.0012 | Best balanced cheap candidate: faster, good mix, one citation failure. |
| `mistralai/mistral-nemo` | 168.4s | 16 | 14 | 4/4/4/4 | ~$0.0002 | Very cheap but under-generated and had citation errors. |
| `inclusionai/ling-2.6-flash` | 54.9s | 30 | 3 | mostly VSA | ~$0.0002 | Fast/cheap but unusable: ignored marks/count/type constraints. |

Cost estimates use OpenRouter model-list rates at run time and 4 chars/token estimates from the captured artifacts. All five calls together were still well under one cent by token-rate estimate, excluding any OpenRouter/provider minimums or routing differences.

#### Alternative-model quality notes

- **Qwen 235B A22B**: produced exactly 20 valid candidates with no deterministic validation errors. Questions are generally useful and cover the topic broadly. However, manual spot-check found semantic overreach: one benzene item cites only the figure caption but discusses resonance/stability, and one diamond/graphite item cites chunks that do not support the diamond/graphite claim. This means it is good at JSON/citation-ID compliance but still needs semantic citation verification.
- **Mistral Small 24B**: produced 21 valid candidates for a request of 20. The content is usable and NCERT-like, with no citation-ID validation failures, but many answers are generic and several longer prompts may need teacher tightening. Over-count is a workflow issue for batch sizing.
- **GPT-OSS 120B**: produced 20 raw / 19 valid. Quality is good and latency is much better than Qwen/Mistral Small. One candidate was blocked for an unknown citation. Some generated items ask for electron-dot/nomenclature details that may be too structure/formula-heavy for the current MVP policy.
- **Mistral Nemo**: cheap and reasonably fast, but under-generated and had unknown citation IDs. Could be a low-cost fallback only after prompt hardening.
- **Ling 2.6 Flash**: not suitable for this contract. It over-generated 30, mostly VSA, and used 1-mark VSA despite the app contract requiring VSA=2.

#### Count=20 decision

- `count=20` is technically feasible and very cheap on several OpenRouter alternatives.
- The best cheap candidates to continue testing are **GPT-OSS 120B**, **Qwen 235B A22B**, and **Mistral Small 24B**.
- For MVP teacher review, `count=20` may be too many per selected topic unless the UI groups/deduplicates candidates. It is useful for model evaluation, but the production default should still be closer to 5–10 per topic.
- Do not use deterministic citation-ID validation as the only quality gate. The next hardening step should add semantic citation-support review, because several candidates cite real chunks while making claims not actually supported by those chunks.

### Gemma 4 26B comparison — 2026-06-21

Approved scope: one paid OpenRouter call with `google/gemma-4-26b-a4b-it`, `count=20`, same topic/context, no retries, not the free route.

| Model | Latency | Raw count | Valid/persisted | Est. cost | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| `google/gemma-4-26b-a4b-it` | 3.9s | 1 | 0 | ~$0.0004 | Failed contract badly. |
| `openai/gpt-oss-120b` baseline | 150.1s | 20 | 19 | ~$0.0012 | Much better despite higher latency. |

Artifact: `content/issue_177_poc_google-gemma-4-26b-a4b-it_count20.json`.

Gemma returned only a partial object: `{"chapter_slug": "carbon-and-its"}`. It omitted qtype, marks, cognitive level, raw text, content, topic names, answer, source, and both citation fields. The validator rejected it with missing fields, bad chapter slug, missing citations, and empty question/answer.

Decision: **do not use Gemma 4 26B for this pipeline**. GPT-OSS 120B remains the best current low-cost default candidate.

## Final model decision for handoff

Use **`google/gemini-3.1-flash-lite` via OpenRouter at `count=15`** as the final #177 grounded-generation acceptance recommendation.

Selected configuration:

```text
LLM_QUESTION_GENERATION_PROVIDER=openrouter
LLM_QUESTION_GENERATION_MODEL=google/gemini-3.1-flash-lite
OPENROUTER_API_KEY=...
LLM_MAX_RETRIES=0 for acceptance experiments
```

Recommended batch shape:

```text
count=15 per selected major topic
```

Why this supersedes the earlier GPT-OSS / Gemini 2.5 Flash Lite decisions:

- GPT-OSS failed the remaining selected-topic acceptance slice: 4.3 and 4.5 returned degenerate one-item outputs, while 4.1 and 4.4 had malformed MCQs.
- Gemini 2.5 Flash Lite is good at `count=10`, but failed or partially failed above that size (`count=15`: 16 valid total across five calls; `count=20`: two failed calls).
- Gemini 3.1 Flash Lite at `count=15` produced exact `15/15` valid candidates on every selected `jesc104` major topic with the expected `4 MCQ / 4 VSA / 4 SA / 3 LA` mix.
- Latency was stable enough for out-of-request generation: about `16.8–19.1s` per selected topic.
- Estimated total cost for all five selected `count=15` topic slices was about `$0.034`, roughly `$0.006–$0.007` per topic. This is higher than 2.5 Lite but still low in absolute MVP terms and far cheaper than Gemini 3.5 Flash.

Final comparison snapshot:

| Model / shape | Evidence | Decision |
| --- | --- | --- |
| `google/gemini-3.1-flash-lite`, count=15 | 75 raw / 75 valid across all five selected topics; stable latency; expected qtype mix | **Select final #177 recommendation** |
| `google/gemini-2.5-flash-lite`, count=10 | Good low-cost small-batch behavior, but not reliable above count=10 | Keep as cheap small-batch fallback only |
| `qwen/qwen3-235b-a22b-2507`, count=10 | Valid and cheapest, but much slower/variable | Keep as slow cost fallback |
| `google/gemini-3.5-flash`, count=20 | Strong quality/schema, but about `$0.07` per topic | Expensive quality fallback only |
| `openai/gpt-oss-120b` | Failed selected-topic acceptance on 4.3/4.5 and malformed MCQs on 4.1/4.4 | Do not use as #177 default |
| `google/gemini-2.5-flash` | Failed structured-output path at count=20 | Do not use |

This final model decision is still bounded by the #177 review rule: deterministic validation and citation-ID checks are not sufficient for bank acceptance. Persisted candidates from the selected model still require semantic/human citation-support review before being accepted into the question bank.

## Semantic citation-support validation update — 2026-06-22

Added a deterministic citation-support review aid in `backend/bank/citation_support.py`. This is intentionally a conservative pre-review screen, not a replacement for teacher review or a proof of truth:

- It resolves cited excerpt text from the candidate `grounding_manifest`.
- It checks lexical overlap separately for the generated question and answer.
- It expands MCQ label-only answers (for example `"B"`) to the selected option text before reviewing answer support.
- It flags formula/diagram-heavy prompts (`draw`, `electron-dot`, `formula`, `structure`, `IUPAC`/naming terms) for explicit human review because #177's MVP grounding policy excludes numerical/formula-only and diagram-image generation.
- It does **not** weaken the deterministic ingestion validator; it is an additional review signal for candidates that already passed schema/citation-ID validation.

Focused verification now covers this review seam with tests for supported candidates, unsupported answer claims despite real citation IDs, and formula/diagram-heavy review flags.

Spot-checking the persisted GPT-OSS `count=20` batch (`#12`) with the new conservative screen produced `6 supported / 13 flagged`. The high flagged count should not be read as a final fail rate because lexical overlap is strict and intentionally noisy; it confirms the earlier finding that deterministic citation-ID validation alone is insufficient and that generated candidates need semantic/human citation-support review before acceptance.

## Next-agent handoff / next work

1. **Use Gemini 3.1 Flash Lite at count=15 as the final #177 recommendation**:

   ```text
   LLM_QUESTION_GENERATION_PROVIDER=openrouter
   LLM_QUESTION_GENERATION_MODEL=google/gemini-3.1-flash-lite
   OPENROUTER_API_KEY=...
   LLM_MAX_RETRIES=0 for acceptance experiments
   count=15 per selected major topic
   ```

2. **Do not run more live calls without fresh explicit approval.** Every provider/model/count is a separate Rule 13 consent scope.
3. **Do semantic/manual citation-support review before bank acceptance.** Current deterministic validation catches malformed output and unknown citation IDs, but not every real-citation semantic mismatch.
4. **Keep count=20 out of the default path.** Gemini 3.1 Flash Lite was better than 2.5 Lite at count=20, but still under-generated 4.5; count=15 is the accepted larger-batch shape.
5. **Keep fallback policy explicit:** Gemini 2.5 Flash Lite is a cheap count=10 fallback; Qwen is cheapest but slow; Gemini 3.5 Flash is expensive quality fallback.
6. **Before final issue close:** run deterministic tests, perform Antigravity review, re-read #177 checklist, push branch, and only then close the issue.

## Current implementation note

The model seam now supports `openrouter`, `deepseek`, and OpenAI-compatible `*_BASE_URL` configuration, so the POC can compare cheap model routes without adding provider SDK imports to the generation feature path. The response schema now has top-level `title` and `description`, plain-string enum values, required grounded citation fields, explicit `content.stem` block shape, structured MCQ option shape, `raw_text.minLength=1`, and prompt text for fixed qtype-to-marks mapping so OpenAI-compatible structured-output adapters receive a stricter, more ingestible JSON schema.

## Verification so far

```text
docker compose exec -T web pytest \
  bank/tests/test_generation.py \
  bank/tests/test_generation_batch.py \
  corpus/tests/test_retrieval.py -q
```

Latest focused result after Antigravity follow-up fixes: `49 passed, 1 warning in 2.97s`.

## Switchable model configuration

The same grounded-generation path is switched by environment only:

```text
# Final #177 recommendation: Gemini 3.1 Flash Lite through OpenRouter
LLM_QUESTION_GENERATION_PROVIDER=openrouter
LLM_QUESTION_GENERATION_MODEL=google/gemini-3.1-flash-lite
OPENROUTER_API_KEY=...
LLM_MAX_RETRIES=0
# request count: 15 per selected major topic

# Cheap small-batch fallback only
LLM_QUESTION_GENERATION_PROVIDER=openrouter
LLM_QUESTION_GENERATION_MODEL=google/gemini-2.5-flash-lite
OPENROUTER_API_KEY=...
LLM_MAX_RETRIES=0
# request count: 10 per selected major topic

# Expensive quality fallback only
LLM_QUESTION_GENERATION_PROVIDER=openrouter
LLM_QUESTION_GENERATION_MODEL=google/gemini-3.5-flash
OPENROUTER_API_KEY=...
LLM_MAX_RETRIES=0
```

No feature module imports a DeepSeek, Gemini, Qwen, or OpenRouter SDK directly.

## Remaining selected-topic acceptance run — 2026-06-22

Fresh user approval was given to run the remaining selected `jesc104` major-topic acceptance slices with the selected GPT-OSS route.

Scope actually run:

- Provider/model: `openrouter` / `openai/gpt-oss-120b`
- Retries: `LLM_MAX_RETRIES=0`
- Candidate count: `10` per topic
- Calls: `4`, one per remaining selected major topic (`4.1`, `4.3`, `4.4`, `4.5`)
- No topic splitting and no silent retry after malformed/failed model outputs.

| Topic | Batch | Latency | Raw | Valid/persisted | Result | Artifact |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 4.1 Bonding in Carbon — The Covalent Bond | 16 | 30.4s | 10 | 7 | Partial pass; MCQs malformed | `content/issue_177_acceptance_gpt_oss_120b_4-1_count10.json` |
| 4.3 Chemical Properties of Carbon Compounds | 17 | 162.7s | 1 | 0 | Fail; degenerate malformed payload | `content/issue_177_acceptance_gpt_oss_120b_4-3_count10.json` |
| 4.4 Ethanol and Ethanoic Acid | 18 | 128.0s | 10 | 7 | Partial pass; MCQs embedded options in stem | `content/issue_177_acceptance_gpt_oss_120b_4-4_count10.json` |
| 4.5 Soaps and Detergents | 19 | 192.7s | 1 | 0 | Fail; degenerate malformed payload | `content/issue_177_acceptance_gpt_oss_120b_4-5_count10.json` |

Validation notes:

- `4.1`: generated the expected qtype mix (`3 MCQ / 3 VSA / 2 SA / 2 LA`), but all 3 MCQs lacked structured `content.options`, so only 7 non-MCQ candidates persisted.
- `4.3`: returned one unusable placeholder-like `long_answer` with bad marks, bad chapter slug, empty answer, and unknown citation strings.
- `4.4`: generated the expected qtype mix, but all 3 MCQs placed option text inside `content.stem` instead of structured `content.options`, so only 7 non-MCQ candidates persisted.
- `4.5`: returned one unusable placeholder-like MCQ with bad marks/options and unknown citations.
- Conservative citation-support review flagged every persisted candidate in batches 16 and 18 for manual review (`low_lexical_citation_overlap` and/or formula/diagram policy terms). This is expected to be noisy, but it confirms these candidates should not be auto-accepted.

Current #177 acceptance readout from live evidence:

- Grounding context assembly: **pass** — selected topic subtrees produced bounded NCERT context under cap.
- Provider switching/model seam: **pass** — GPT-OSS runs through the shared OpenRouter route without feature SDK imports.
- Deterministic validation gate: **pass** — malformed/unsupported outputs were rejected and not persisted.
- GPT-OSS as reliable acceptance default across all selected topics: **fail / needs remediation** — two of four remaining topics produced degenerate single-item outputs, and both successful topics had malformed MCQs.
- Semantic citation support: **not passed yet** — added deterministic review aid, but human/semantic review still needs to decide support for persisted candidates.

Decision: **do not close #177 as accepted yet.** Remediate prompt/schema behavior for MCQ option placement and degenerate one-item outputs, then rerun only the failed/partial slices with fresh Rule 13 consent.

## Failed-slice model comparison — Gemini 2.5 Flash Lite vs Qwen — 2026-06-22

Fresh user approval was given to test the failed `4.3` and `4.5` slices with `google/gemini-2.5-flash-lite` first, then `qwen/qwen3-235b-a22b-2507`, and compare correctness, cost, and latency.

Scope actually run:

- Provider: `openrouter`
- Retries: `LLM_MAX_RETRIES=0`
- Candidate count: `10` per topic
- Calls: `4` total: two topics × two models
- No silent retries.

| Model | Topic | Batch | Latency | Raw | Valid/persisted | Qtype mix | Est. cost | Artifact |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `google/gemini-2.5-flash-lite` | 4.3 | 20 | 19.1s | 10 | 10 | 3/3/2/2 | ~$0.00146 | `content/issue_177_acceptance_gemini-2.5-flash-lite_4-3_count10.json` |
| `google/gemini-2.5-flash-lite` | 4.5 | 21 | 20.7s | 12 | 10 | raw over-generated; valid 3/2/2/3 | ~$0.00206 | `content/issue_177_acceptance_gemini-2.5-flash-lite_4-5_count10.json` |
| `qwen/qwen3-235b-a22b-2507` | 4.3 | 22 | 83.2s | 10 | 10 | 2/3/3/2 | ~$0.00055 | `content/issue_177_acceptance_qwen3-235b-a22b-2507_4-3_count10.json` |
| `qwen/qwen3-235b-a22b-2507` | 4.5 | 23 | 138.5s | 10 | 10 | 3/3/2/2 | ~$0.00055 | `content/issue_177_acceptance_qwen3-235b-a22b-2507_4-5_count10.json` |

Cost estimates use OpenRouter model-list rates fetched at run time and 4 chars/token estimates:

- `google/gemini-2.5-flash-lite`: prompt `$0.10/M`, completion `$0.40/M`.
- `qwen/qwen3-235b-a22b-2507`: prompt `$0.09/M`, completion `$0.10/M`.

Correctness / quality notes:

- **Gemini 2.5 Flash Lite 4.3**: strongest result. Exact requested count and mix, `10/10` valid, no citation-ID errors, and deterministic citation-support review found `10/10` supported. Content covered addition reactions, combustion/flame, oxidising agents, catalysts, substitution, and ethanol oxidation in NCERT-like form.
- **Gemini 2.5 Flash Lite 4.5**: good but not perfect. It over-generated `12` raw candidates; validator persisted `10` and blocked the citation-invalid extras. Persisted content is mostly useful for micelles, hydrophobic/hydrophilic soap parts, hard-water scum, and detergents. Conservative citation-support review flagged `5/10`, mostly because of lexical strictness and formula/structure-policy terms.
- **Qwen 4.3**: `10/10` valid and cheaper than Gemini Lite, but qtype mix drifted (`2 MCQ / 3 VSA / 3 SA / 2 LA` instead of `3/3/2/2`). Conservative citation-support review flagged `3/10`. Manual spot-check looks broadly NCERT-aligned, but some answers are more paraphrased than directly cited.
- **Qwen 4.5**: `10/10` valid, exact mix, very cheap, but much slower than Gemini Lite. Conservative citation-support review flagged `3/10`, all formula/structure/name policy terms rather than unknown citations.

Decision from this comparison:

- `google/gemini-2.5-flash-lite` is the best **latency + correctness fallback** for failed GPT-OSS slices. It solved both failed topics in about 20 seconds each.
- `qwen/qwen3-235b-a22b-2507` remains the best **ultra-low-cost fallback** when latency is acceptable; it was ~3× cheaper than Gemini Lite here but 4–7× slower.
- GPT-OSS should no longer be treated as the sole default for these selected topics without prompt/schema remediation, because Gemini Lite and Qwen both recovered the failed `4.3`/`4.5` slices with valid candidates.

## Additional 4.1 / 4.4 fallback comparison — 2026-06-22

Fresh user approval was given to run more tests on Gemini 2.5 Flash Lite and Qwen. To complete the comparison across the selected topics without rerunning already-tested failed slices, the run covered the remaining GPT-OSS partial slices `4.1` and `4.4`.

Scope actually run:

- Provider: `openrouter`
- Models: `google/gemini-2.5-flash-lite`, then `qwen/qwen3-235b-a22b-2507`
- Retries: `LLM_MAX_RETRIES=0`
- Candidate count: `10` per topic
- Calls: `4` total: two topics × two models
- No silent retries.

| Model | Topic | Batch | Latency | Raw | Valid/persisted | Qtype mix | Est. cost | Artifact |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `google/gemini-2.5-flash-lite` | 4.1 | 24 | 24.1s | 10 | 10 | 3/3/2/2 | ~$0.00177 | `content/issue_177_acceptance_gemini-2.5-flash-lite_4-1_count10_round2.json` |
| `google/gemini-2.5-flash-lite` | 4.4 | 25 | 16.7s | 10 | 10 | 3/3/2/2 | ~$0.00141 | `content/issue_177_acceptance_gemini-2.5-flash-lite_4-4_count10_round2.json` |
| `qwen/qwen3-235b-a22b-2507` | 4.1 | 26 | 584.0s | 10 | 10 | 3/3/2/2 | ~$0.00069 | `content/issue_177_acceptance_qwen3-235b-a22b-2507_4-1_count10_round2.json` |
| `qwen/qwen3-235b-a22b-2507` | 4.4 | 27 | 130.6s | 10 | 10 | 3/3/2/2 | ~$0.00057 | `content/issue_177_acceptance_qwen3-235b-a22b-2507_4-4_count10_round2.json` |

Conservative citation-support review summary:

| Model | Topic | Supported | Flagged | Main flag reasons |
| --- | --- | ---: | ---: | --- |
| Gemini Lite | 4.1 | 7 | 3 | one MCQ answer-text expansion miss, C4 ion lexical strictness, structure-policy term |
| Gemini Lite | 4.4 | 6 | 4 | mostly `name`/structure policy terms, one lexical strictness flag |
| Qwen | 4.1 | 7 | 3 | C4 ion/diamond lexical strictness, one `name` policy term |
| Qwen | 4.4 | 7 | 3 | `name` policy terms and equation/fermentation lexical strictness |

Updated comparison readout:

- Gemini 2.5 Flash Lite produced `10/10` valid on all four selected topics tested (`4.1`, `4.3`, `4.4`, `4.5`), with only one raw over-generation case on 4.5 (`12` raw → `10` valid). Latency was consistently low: about `16–24s` per call.
- Qwen produced `10/10` valid on all four selected topics tested, and was cheaper per call, but latency was much worse and variable: `83s`, `138s`, `130s`, and one very slow `584s` call.
- On current evidence, **Gemini 2.5 Flash Lite is the best default fallback / likely replacement for GPT-OSS** for #177 acceptance because it is fast, valid, and cheap enough. Qwen is a cost fallback only when latency is acceptable.

## Bigger Gemini comparison — 2.5 Flash vs 3.5 Flash, count=20 — 2026-06-22

Fresh user approval was given to run a bigger comparison between Gemini 2.5 Flash and Gemini 3.5 Flash. The run used the two previously failed/diagnostic topics (`4.3`, `4.5`) at `count=20`.

Scope actually run:

- Provider: `openrouter`
- Models: `google/gemini-2.5-flash`, then `google/gemini-3.5-flash`
- Retries: `LLM_MAX_RETRIES=0`
- Candidate count: `20` per topic
- Calls: `4` total: two topics × two models
- No silent retries.

| Model | Topic | Batch | Latency | Raw | Valid/persisted | Qtype mix | Est. cost | Artifact |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `google/gemini-2.5-flash` | 4.3 | 28 | 4.4s | 1 | 0 | failed | ~$0.00122 | `content/issue_177_gemini_compare_gemini-2.5-flash_4-3_count20.json` |
| `google/gemini-2.5-flash` | 4.5 | 29 | 2.6s | 1 | 0 | failed | ~$0.00106 | `content/issue_177_gemini_compare_gemini-2.5-flash_4-5_count20.json` |
| `google/gemini-3.5-flash` | 4.3 | 30 | 89.8s | 20 | 20 | 5/5/5/5 | ~$0.07048 | `content/issue_177_gemini_compare_gemini-3.5-flash_4-3_count20.json` |
| `google/gemini-3.5-flash` | 4.5 | 31 | 78.6s | 20 | 20 | 5/5/5/5 | ~$0.07010 | `content/issue_177_gemini_compare_gemini-3.5-flash_4-5_count20.json` |

Cost estimates use OpenRouter model-list rates fetched at run time and 4 chars/token estimates:

- `google/gemini-2.5-flash`: prompt `$0.30/M`, completion `$2.50/M`.
- `google/gemini-3.5-flash`: prompt `$1.50/M`, completion `$9.00/M`.

Correctness / quality notes:

- **Gemini 2.5 Flash failed this structured-output path** despite being more expensive than Gemini 2.5 Flash Lite. It returned only one incomplete candidate per topic, missing required fields and citations. This looks like an OpenRouter/model structured-output behavior issue, not an over-strict validator problem.
- **Gemini 3.5 Flash succeeded strongly**: exact `20` raw, `20` valid, exact `5/5/5/5` qtype mix on both topics.
- Gemini 3.5 Flash quality appears good at first glance, with broad NCERT-like coverage and clean schema compliance, but conservative citation-support review still flagged `6/20` in each topic for lexical strictness and formula/structure/name policy terms.
- Gemini 3.5 Flash is far more expensive: about `$0.14` for the two count=20 calls, versus about `$0.0035` for two Gemini 2.5 Flash Lite count=10 calls earlier. It is a quality fallback, not a low-cost default.

Updated Gemini decision:

- Do **not** use `google/gemini-2.5-flash` in this current OpenRouter structured-output pipeline; it failed both count=20 tests.
- Keep **`google/gemini-2.5-flash-lite`** as the best current cost/latency/default candidate.
- Keep **`google/gemini-3.5-flash`** as a high-quality fallback when cost is acceptable or when Lite quality fails manual review.

## Big Flash Lite comparison — Gemini 2.5 Flash Lite vs Gemini 3.1 Flash Lite, count=20 — 2026-06-22

Fresh user approval was given to compare the best current low-cost candidate (`google/gemini-2.5-flash-lite`) with the available newer Flash Lite route (`google/gemini-3.1-flash-lite`). OpenRouter does not list a `google/gemini-3.5-flash-lite` model.

Scope actually run:

- Provider: `openrouter`
- Models: `google/gemini-2.5-flash-lite`, then `google/gemini-3.1-flash-lite`
- Retries: `LLM_MAX_RETRIES=0`
- Candidate count: `20` per topic
- Topics: all selected `jesc104` major topics (`4.1` through `4.5`)
- Calls: `10` total: five topics × two models
- No silent retries.

| Model | Topic | Batch | Latency | Raw | Valid/persisted | Qtype mix | Est. cost | Artifact |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `google/gemini-2.5-flash-lite` | 4.1 | 32 | 1.8s | 1 | 0 | failed | ~$0.00049 | `content/issue_177_flash_lite_compare_gemini-2.5-flash-lite_4-1_count20.json` |
| `google/gemini-2.5-flash-lite` | 4.2 | 33 | 28.4s | 19 | 19 | 5/5/5/4 | ~$0.00290 | `content/issue_177_flash_lite_compare_gemini-2.5-flash-lite_4-2_count20.json` |
| `google/gemini-2.5-flash-lite` | 4.3 | 34 | 46.8s | 18 | 18 | 5/5/4/4 | ~$0.00310 | `content/issue_177_flash_lite_compare_gemini-2.5-flash-lite_4-3_count20.json` |
| `google/gemini-2.5-flash-lite` | 4.4 | 35 | 1.7s | 1 | 0 | failed | ~$0.00037 | `content/issue_177_flash_lite_compare_gemini-2.5-flash-lite_4-4_count20.json` |
| `google/gemini-2.5-flash-lite` | 4.5 | 36 | 32.2s | 19 | 19 | 5/5/5/4 | ~$0.00307 | `content/issue_177_flash_lite_compare_gemini-2.5-flash-lite_4-5_count20.json` |
| `google/gemini-3.1-flash-lite` | 4.1 | 37 | 26.7s | 20 | 20 | 5/5/5/5 | ~$0.00900 | `content/issue_177_flash_lite_compare_gemini-3.1-flash-lite_4-1_count20.json` |
| `google/gemini-3.1-flash-lite` | 4.2 | 38 | 29.1s | 20 | 20 | 5/5/5/5 | ~$0.00958 | `content/issue_177_flash_lite_compare_gemini-3.1-flash-lite_4-2_count20.json` |
| `google/gemini-3.1-flash-lite` | 4.3 | 39 | 21.2s | 20 | 20 | 5/5/5/5 | ~$0.00860 | `content/issue_177_flash_lite_compare_gemini-3.1-flash-lite_4-3_count20.json` |
| `google/gemini-3.1-flash-lite` | 4.4 | 40 | 18.2s | 20 | 20 | 5/5/5/5 | ~$0.00829 | `content/issue_177_flash_lite_compare_gemini-3.1-flash-lite_4-4_count20.json` |
| `google/gemini-3.1-flash-lite` | 4.5 | 41 | 10.1s | 9 | 8 | mostly MCQ/VSA | ~$0.00360 | `content/issue_177_flash_lite_compare_gemini-3.1-flash-lite_4-5_count20.json` |

Cost estimates use OpenRouter model-list rates fetched at run time and 4 chars/token estimates:

- `google/gemini-2.5-flash-lite`: prompt `$0.10/M`, completion `$0.40/M`.
- `google/gemini-3.1-flash-lite`: prompt `$0.25/M`, completion `$1.50/M`.

Aggregate count=20 comparison:

| Model | Calls | Total raw | Total valid | Failed calls | Total latency | Avg latency | Est. total cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `google/gemini-2.5-flash-lite` | 5 | 58 | 56 | 2 | 110.9s | 22.2s | ~$0.00993 |
| `google/gemini-3.1-flash-lite` | 5 | 89 | 88 | 0 | 105.4s | 21.1s | ~$0.03907 |

Correctness / quality notes:

- `google/gemini-2.5-flash-lite` remains excellent at `count=10`, but it is **not reliable at count=20** in this structured-output path: 4.1 and 4.4 returned only `{"chapter_slug": "carbon-and-its-compounds", "qtype": "mcq"}`-style partial objects with no valid candidates.
- `google/gemini-3.1-flash-lite` is much more reliable at `count=20`: it produced exact `20/20` with exact `5/5/5/5` mix on 4.1–4.4. However, it under-generated badly on 4.5 (`9` raw, `8` valid, mostly MCQ/VSA), so it is not a perfect large-batch default either.
- Conservative citation-support review flagged a non-trivial fraction of persisted candidates for both models. This remains a review aid rather than a final truth oracle, but it reinforces the need for human/semantic review before accepting generated candidates into the bank.

Updated Flash Lite decision:

- For MVP teacher-review batches, keep the production default near **count=10**.
- Use `google/gemini-2.5-flash-lite` as the best low-cost, low-latency default for count=10 topic slices.
- If a larger count=20 slice is required, `google/gemini-3.1-flash-lite` is more reliable than 2.5 Lite, but still needs a fallback/rerun policy because it under-generated 4.5.
- Do not treat count=20 as accepted without additional batch control and semantic review.

## Count=15 Flash Lite comparison — Gemini 2.5 Flash Lite vs Gemini 3.1 Flash Lite — 2026-06-22

Fresh user approval was given to test whether `count=15` is a better middle ground for the two Flash Lite candidates.

Scope actually run:

- Provider: `openrouter`
- Models: `google/gemini-2.5-flash-lite`, then `google/gemini-3.1-flash-lite`
- Retries: `LLM_MAX_RETRIES=0`
- Candidate count: `15` per topic
- Topics: all selected `jesc104` major topics (`4.1` through `4.5`)
- Calls: `10` total: five topics × two models
- No silent retries.

| Model | Topic | Batch | Latency | Raw | Valid/persisted | Qtype mix | Est. cost | Artifact |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `google/gemini-2.5-flash-lite` | 4.1 | 42 | 6.1s | 2 | 1 | failed/partial | ~$0.00068 | `content/issue_177_flash_lite_compare_gemini-2.5-flash-lite_4-1_count15.json` |
| `google/gemini-2.5-flash-lite` | 4.2 | 43 | 0.9s | 1 | 0 | failed | ~$0.00065 | `content/issue_177_flash_lite_compare_gemini-2.5-flash-lite_4-2_count15.json` |
| `google/gemini-2.5-flash-lite` | 4.3 | 44 | 22.0s | 15 | 15 | 4/4/4/3 | ~$0.00217 | `content/issue_177_flash_lite_compare_gemini-2.5-flash-lite_4-3_count15.json` |
| `google/gemini-2.5-flash-lite` | 4.4 | 45 | 2.0s | 1 | 0 | failed | ~$0.00041 | `content/issue_177_flash_lite_compare_gemini-2.5-flash-lite_4-4_count15.json` |
| `google/gemini-2.5-flash-lite` | 4.5 | 46 | 2.2s | 1 | 0 | failed | ~$0.00037 | `content/issue_177_flash_lite_compare_gemini-2.5-flash-lite_4-5_count15.json` |
| `google/gemini-3.1-flash-lite` | 4.1 | 47 | 18.1s | 15 | 15 | 4/4/4/3 | ~$0.00681 | `content/issue_177_flash_lite_compare_gemini-3.1-flash-lite_4-1_count15.json` |
| `google/gemini-3.1-flash-lite` | 4.2 | 48 | 19.1s | 15 | 15 | 4/4/4/3 | ~$0.00743 | `content/issue_177_flash_lite_compare_gemini-3.1-flash-lite_4-2_count15.json` |
| `google/gemini-3.1-flash-lite` | 4.3 | 49 | 17.4s | 15 | 15 | 4/4/4/3 | ~$0.00677 | `content/issue_177_flash_lite_compare_gemini-3.1-flash-lite_4-3_count15.json` |
| `google/gemini-3.1-flash-lite` | 4.4 | 50 | 17.1s | 15 | 15 | 4/4/4/3 | ~$0.00676 | `content/issue_177_flash_lite_compare_gemini-3.1-flash-lite_4-4_count15.json` |
| `google/gemini-3.1-flash-lite` | 4.5 | 51 | 16.8s | 15 | 15 | 4/4/4/3 | ~$0.00640 | `content/issue_177_flash_lite_compare_gemini-3.1-flash-lite_4-5_count15.json` |

Aggregate count=15 comparison:

| Model | Calls | Total raw | Total valid | Failed calls | Total latency | Avg latency | Est. total cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `google/gemini-2.5-flash-lite` | 5 | 20 | 16 | 3 | 33.2s | 6.6s | ~$0.00427 |
| `google/gemini-3.1-flash-lite` | 5 | 75 | 75 | 0 | 88.5s | 17.7s | ~$0.03417 |

Count=15 decision:

- `google/gemini-2.5-flash-lite` is **not reliable above count=10** in this structured-output path. At count=15 it failed or partially failed four of five topics; at count=20 it failed two of five topics.
- `google/gemini-3.1-flash-lite` is the strongest Flash Lite option for count=15: exact `15/15` on every selected topic with stable latency and expected `4/4/4/3` mix.
- The current model/count recommendation should be:
  - **Default cheap MVP:** `google/gemini-2.5-flash-lite`, `count=10`.
  - **Larger batch fallback:** `google/gemini-3.1-flash-lite`, `count=15`.
  - Avoid `count=20` as default unless fallback/rerun handling is implemented.

## Final selected-model candidate review — 2026-06-22

Reviewed the final selected-model run (`google/gemini-3.1-flash-lite`, `count=15`, batches `47–51`) for semantic citation support after deterministic validation.

Artifact: `content/issue_177_final_manual_review_gemini_3_1_flash_lite_count15.json`

Summary:

| Review result | Count |
| --- | ---: |
| Persisted candidates reviewed | 75 |
| Deterministic citation-support screen passed | 60 |
| Deterministic citation-support screen flagged for manual review | 15 |
| Manual spot-check supported | 74 |
| Needs teacher edit before acceptance | 1 |

The deterministic review flags were mostly conservative lexical misses or policy-word flags (`structure`, `formula`, `name`) where the cited NCERT excerpts did support the claim. One candidate needs teacher edit before acceptance:

| Candidate | Topic | Issue |
| ---: | --- | --- |
| `438` | 4.3 Chemical Properties | Answer adds an acid-rain example. The cited NCERT chunk supports combustion of coal/petroleum producing oxides of sulphur/nitrogen as major environmental pollutants, but does not explicitly support acid rain. |

Final #177 acceptance readout:

| Criterion | Result | Evidence |
| --- | --- | --- |
| Selected-topic grounding context | Pass | All five selected `jesc104` major-topic subtrees assembled under the 25k context cap. |
| Provider/model seam | Pass | All model comparisons ran through `LLM_QUESTION_GENERATION_PROVIDER=openrouter` without feature SDK imports. |
| Deterministic schema/citation-ID validation | Pass | Selected model at count=15 persisted 75/75 valid candidates across batches 47–51. |
| Requested qtype/count mix | Pass | Each selected-topic batch produced 4 MCQ / 4 VSA / 4 SA / 3 LA. |
| Latency/cost | Pass | Gemini 3.1 Flash Lite count=15 ran in ~16.8–19.1s/topic; estimated total for five topics ~$0.034. |
| Semantic citation support | Pass with review caveat | 74/75 manually supported; candidate 438 should be teacher-edited/discarded before bank acceptance. |
| Production recommendation | Pass | Use `google/gemini-3.1-flash-lite` at count=15; do not use GPT-OSS or Gemini 2.5 Flash Lite above count=10 as default. |

Decision: #177's model/count acceptance gate is satisfied for a teacher-review workflow, provided generated candidates remain review-gated and candidate `438` is edited/discarded before acceptance into the bank.

## Antigravity review follow-up — 2026-06-22

Antigravity review was run on implementation commit `f7f3ab2` using the required `Gemini 3.5 Flash (High)` model. The first attempt against the artifact-heavy commit timed out, so commits were split into implementation/report and artifact commits, then the review succeeded.

Review findings and disposition:

| Finding | Disposition | Follow-up |
| --- | --- | --- |
| Acceptance report did not explicitly cover several issue acceptance criteria | Accepted | Added the pass/fail checklist below, including unresolved caveats. |
| `review_candidate_citation_support` is disconnected from production | Rejected as a product-scope blocker | The helper is intentionally a deterministic review aid for the acceptance gate; production bank insertion remains teacher-review gated. The final manual-review artifact demonstrates it was executed against batches 47–51. Future product work can persist review flags if desired. |
| Tokenizer drops numerals/short tokens/non-English text | Accepted | Updated tokenization to include unicode/numeric tokens and added regression coverage. A follow-up Antigravity rerun flagged combining-mark splitting, so tokenization now preserves Devanagari words by splitting on separators instead of ASCII/word-character classes. |
| JSON schema not OpenAI strict-mode compatible because `content.options` is optional | Rejected for this acceptance slice | The current LangChain/OpenRouter path accepted the schema across the selected models, and making `options` required for non-MCQ questions would change the emitted payload contract. Track separately if strict OpenAI structured outputs become the required backend. |

## Original issue #177 acceptance-criteria checklist

| Criterion | Result | Evidence / caveat |
| --- | --- | --- |
| Explicit consent before live runs | Pass | Each provider/model/count scope was approved in-chat before live calls; no silent retries were run after malformed outputs. |
| Compare grounded candidates with earlier ungrounded generation | Partial | This branch records extensive grounded-model evidence and shows citation-backed outputs outperform ungrounded-style/provider-memory failures, but it does not rerun a fresh ungrounded baseline because the issue was treated as a cost/HITL gate. |
| One bounded generation call per selected major topic | Pass | Final selected run used one call per topic, no topic splitting, count=15. |
| V1 context filtering policy | Pass | Context diagnostics confirm selected subtree chunks under cap; excluded exercises/questions, captionless picture-only, and formula-only chunks by policy. |
| Generate question and answer together | Pass | All selected payloads include question text/content and answer in the same candidate. |
| Verify accepted candidate citations support Q+A | Pass with caveat | Final selected batches 47–51 were reviewed: 74/75 supported; candidate 438 must be edited/discarded before bank acceptance. |
| Review extraction losses/retrieval misses; decide on second extractor | Partial | No extraction/retrieval miss blocked selected-topic grounding for `jesc104`; context covered all five major topics under cap. A second extractor is not justified for this selected path, but this is not a full extraction-quality audit. |
| Record ingestion/run metrics/cost | Pass | Report includes import time, element/chunk/index metrics, prompt sizes, cap status, live-call counts, latency, and estimated costs. |
| Dense/hybrid retrieval latency if included | Pass / not applicable | Dense/hybrid retrieval was intentionally skipped; selected-topic generation uses deterministic ChapterMapNode subtree context. |
| Chapter-map review with teacher workflow | Partial | The selected major-topic ChapterMapNode workflow was exercised through GenerationBatch-style topic selection and context assembly; no separate polished-graph UI teacher walkthrough was performed in this backend acceptance branch. |
| Deterministic tests and skipped checks | Pass | Latest focused result: `48 passed, 1 warning in 3.01s`; unresolved uncertainty is manual review of future generated candidates. |
| Mandatory Antigravity review gate | Pass for current implementation commit | Antigravity reviewed `f7f3ab2`; accepted findings were addressed here. Historical per-PR gates before this branch were not re-audited. |
| Committed report with recommendation | Pass | Final recommendation: proceed to a separate corpus-rollout plan using Gemini 3.1 Flash Lite count=15, with teacher review and candidate 438 edit/discard caveat. |
| Do not ingest other NCERT chapters | Pass | Only `jesc104` / `carbon-and-its-compounds` was used. |

Final recommendation: **proceed to a separate corpus-rollout plan**, not automatic full-corpus generation. Use `google/gemini-3.1-flash-lite` at `count=15` per selected major topic, keep generated candidates teacher-review gated, and require edit/discard for unsupported candidates like `438`.

## Pending acceptance work

- Do not run more live model calls without fresh Rule 13 consent.
- Treat model/count selection as finalized: `google/gemini-3.1-flash-lite`, `count=15`.
- Review persisted selected-model candidates in batches `47–51` against semantic citation support; deterministic citation-ID validation is not sufficient.
- Package final #177 pass/fail and proceed to Antigravity review; model/count gate can proceed with the review caveat above.
- Re-read issue #177 before final push/close.
