# Upload flow cost, latency, and quality

Flow: **PDF → GLM-OCR → Markdown → Gemini structuring LLM → visual filter**

Evaluation date: 2026-07-13

Currency: **1 USD = ₹95.3361**

## Manually reviewed model comparison

Paper: `31/6/1` Science — 3.94 MB, 32 pages. Quality was manually reviewed against the paper.

| Structuring model | OCR cost | LLM cost | **Total cost** | OCR latency | LLM latency | **Total latency** | **Quality** | Main finding |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Gemini 3 Flash Preview | ₹0.2621 | ₹3.9511 | **₹4.2132** | 27.178 s | 50.675 s | **77.853 s** | **82/100** | Correct 48 entities; six answerable entries falsely filtered |
| Gemini 2.5 Flash | ₹0.2621 | ₹4.7340 | **₹4.9961** | 27.178 s | 71.825 s | **99.003 s** | **71/100** | Q37–Q39 fragmented into incorrect entities |
| Gemini 3.5 Flash | ₹0.2621 | ₹21.3488 | **₹21.6109** | 27.178 s | 112.965 s | **140.143 s** | **93/100** | Best reviewed quality; Q31 and Q39A/B falsely filtered |

## Cost repeatability

All PDFs below contain 32 pages. GLM cost is calculated from returned token usage at the published $0.03/M input and output rate. Gemini cost is OpenRouter's returned `usage.cost`.

| Paper | Size | GLM-OCR cost | Gemini 3 pipeline | Gemini 2.5 pipeline |
|---|---:|---:|---:|---:|
| `31/6/1` | 3.94 MB | ₹0.2621 | ₹4.2132 | ₹4.9961 |
| `31/6/2` | 3.95 MB | ₹0.2542 | ₹5.8749 | ₹4.8400 |
| `31/5/3` | 4.11 MB | ₹0.2651 | ₹3.9948* | ₹4.5591* |

\* `31/5/3` used the stricter formula-clean prompt. Its full extraction was not manually scored, so these rows are cost measurements rather than quality claims.

Observed planning ranges:

- **GLM-OCR:** ₹0.25–₹0.27 per 32-page PDF.
- **GLM + Gemini 2.5 Flash:** ₹4.56–₹5.00 per PDF.
- **GLM + Gemini 3 Flash Preview:** ₹3.99–₹5.88 per PDF.

Gemini 2.5 was more cost-stable. Gemini 3 output length varied substantially, so its cost needs a wider budget allowance.

## Clean GLM latency verification

A controlled call used the official international `ZaiClient` and `https://api.z.ai/api/paas/v4/layout_parsing`. It accepted all 32 pages in one request despite the current reference documenting 30 pages.

| OCR run | Pages | Cost | Latency |
|---|---:|---:|---:|
| `31/6/1` clean GLM run | 32 | ₹0.2621 | 27.178 s |
| `31/5/3` international GLM run | 32 | ₹0.2651 | 29.396 s |

Multi-minute China-endpoint measurements are excluded from normal latency planning because they included base64 upload failures and regional transport problems.

## Formula fidelity

On `31/5/3`, the source contained `44 × 10⁻⁶ Ω m` and `NH₃`.

- GLM returned poorly spaced `4 4 ×1 0⁻⁶` and `N H₃`.
- A stricter LLM prompt corrected some formulas, but behavior was inconsistent: Gemini 3 altered unrelated prose, while Gemini 2.5 retained `N H₃`.
- Formula cleanup should therefore be deterministic and restricted to LaTeX/formula nodes, with original OCR retained for audit.
- For reference, Mistral OCR returned clean `44 × 10⁻⁶` and `NH₃`, but cost ₹12.2030 for the same 32 pages versus GLM's ₹0.2651.

## Recommendation

- **Best cost/latency/quality balance:** Gemini 3 Flash Preview.
- **Best reviewed quality:** Gemini 3.5 Flash, at a much higher cost.
- **Most predictable cost:** Gemini 2.5 Flash, but its first manually reviewed extraction had structural defects.
- Use international GLM-OCR for production cost and latency; add deterministic formula normalization before persistence.
- Budget approximately **₹6.00 per upload** for the Gemini 3 pipeline until more PDFs establish a reliable upper percentile.

Raw evidence is under `content/eval/upload-runs/`. No database writes occurred.
