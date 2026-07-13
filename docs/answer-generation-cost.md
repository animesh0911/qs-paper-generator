# Answer generation cost, latency, and quality

Flow: **persisted questions → production answer prompt/parser → answer LLM**

Evaluation date: 2026-07-13

Currency: **1 USD = ₹95.3361**

The evaluation loads persisted `Question` rows and reuses the production prompt and Pydantic parser. Generated answers are saved only as evaluation artifacts; no answers are written to the database.

## High-quality options

Quality was manually reviewed for factual correctness, numerical work, completeness relative to marks, instruction following, and persistence safety. No candidate model or external LLM judge graded the answers.

| Model | Questions | Delivered | **Cost/set** | Cost/question | **Latency** | **Quality** | Recommendation |
|---|---:|---:|---:|---:|---:|---:|---|
| Gemini 3 Flash Preview | 31 | 31/31 | **₹0.8454** | ₹0.0273 | **10.846 s** | **96/100** | Best quality and speed |
| Gemini 2.5 Flash, fixed prompt | 31 | 31/31 | **₹0.7801** | ₹0.0252 | 13.335 s | **95/100** | Best cost/quality balance |
| Gemini 3.5 Flash | 20 | 20/20 | **₹2.7315** | ₹0.1366 | 12.403 s | **91/100** | High quality but poor value |
| Qwen 3.7 Plus | 31 | 31/31 | **₹0.4656** | ₹0.0150 | 33.478 s | **89/100** | Budget option with review |
| Mistral Small 3.2 24B | 20 | 20/20 | **₹0.0834** | ₹0.0042 | 19.953 s | **84/100** | Very cheap; numerical review required |

Rows with different question counts are not direct cost comparisons. The 31-question Gemini and Qwen rows share the same persisted question set; the 20-question Gemini 3.5 and Mistral rows share a different set.

## Supporting 20-question Gemini comparison

| Model | Cost/set | Latency | Quality |
|---|---:|---:|---:|
| Gemini 2.5 Flash | ₹0.5965 | **10.244 s** | **97/100** |
| Gemini 3 Flash Preview | ₹0.8057 | 13.047 s | **96/100** |
| Gemini 3.5 Flash | ₹2.7315 | 12.403 s | **91/100** |

This smaller run confirms that Gemini 2.5 and Gemini 3 Flash are consistently the strongest answer-generation choices.

## Prompt reliability result

The original Gemini 2.5 prompt produced all 31 answer objects but one extra `}` made the complete JSON invalid, so the production parser accepted 0/31 while the provider still charged ₹0.8267.

The prompt was hardened to:

- select exactly one internal `OR` alternative;
- return one unfenced JSON object with balanced braces;
- allow up to 50 words for multi-part two-mark answers;
- verify numerical signs/arithmetic and balance the exact supplied equation;
- repair the unavailable-visual instruction.

On the same 31-question batch after the fix:

| Metric | Before | After |
|---|---:|---:|
| Parsed answers | 0/31 | **31/31** |
| Cost | ₹0.8267 | **₹0.7801** |
| Latency | 15.371 s | **13.335 s** |
| Output tokens | 2,493 | **2,284** |

The corrected run scored approximately 95/100. Its main remaining issues were one assertion/reason answer and overly broad pH ranges.

## Projected answer-generation spend

Using the 31-question measurements:

| Model | 100 sets | 1,000 sets |
|---|---:|---:|
| Gemini 2.5 Flash | **₹78.01** | **₹780.11** |
| Gemini 3 Flash Preview | ₹84.54 | ₹845.43 |
| Qwen 3.7 Plus | ₹46.56 | ₹465.63 |

These are straight-line projections from one run and exclude retries, price changes, exchange-rate changes, and question-length variation.

## Recommendation

- **Default:** Gemini 2.5 Flash with the fixed prompt—approximately 95/100, ₹0.78 for 31 questions, and 13.3 seconds.
- **Premium/faster option:** Gemini 3 Flash Preview—approximately 96/100 and 10.8 seconds for ₹0.85.
- **Budget option:** Qwen 3.7 Plus only when slower latency and mandatory review are acceptable.
- Keep output validation mandatory. A model response must never be persisted unless every expected ID passes Pydantic validation.

Raw evidence:

- `content/eval/answer-generation-model-comparison-20260713/`
- `content/eval/answer-generation-big-batch-model-comparison-20260713/`
- `content/eval/answer-generation-prompt-fixed-job12-gemini25-20260713/`

No database writes occurred.
