# CBSE Class 10 Science Q&A Generation: Model Selection & API Cost Report

**Date Checked:** June 13, 2026
**Status:** Completed Report
**Target File:** [question_generation_model_cost_report.md](file:///Users/varad/V/repo/qs-paper-generator/docs/common/question_generation_model_cost_report.md)

---

## Executive Summary & Model Selection

Following an audit of the repository's ADRs, scratchboards, and remote issue track, **two models** were selected for question-and-answer generation:
1. **DeepSeek V4 Flash** (Mixture-of-Experts model, released April 2026)
2. **Gemini 3.5 Flash** (Google's default reasoning and extraction model)

### **Key Findings**
* **Is DeepSeek V4 Flash one of them?** **Yes.** DeepSeek V4 Flash is one of the finalized models. It is selected due to its extreme cost-efficiency, large 1M-token context window, and strong reasoning capabilities.
* **What is the other selected model?** **Gemini 3.5 Flash** (via Google AI Studio/Vertex AI). This is the codebase's default model for extraction (ADR-0004) and answer generation (`_DEFAULT_MODEL = "gemini-3.5-flash"`).

### **Provider and Gateway Architecture**
* **Local / Native API:** Access to Gemini is natively handled via `google-genai` and LangChain (`langchain-google-genai`). Access to DeepSeek is officially supported via the DeepSeek API.
* **Intended Production Gateway:** The repository's architectural decisions (specifically [ADR-0005](file:///Users/varad/V/repo/qs-paper-generator/docs/adr/0005-langgraph-llm-orchestration.md) and [issue-142-generation-foundation.md](file:///Users/varad/V/repo/qs-paper-generator/docs/Varad/scratchboards/issue-142-generation-foundation.md)) intend to route multi-provider model calls (such as DeepSeek or Anthropic) through **OpenRouter** or a shared **LiteLLM gateway** (`LLM_PROVIDER` in `docker-compose.yml`), keeping secrets and provider-specific SDK logic server-side.

---

## Model Pricing (as of June 2026)

Pricing is prioritized by official/provider pricing and OpenRouter's aggregator pricing.

| Model | Provider/Gateway | Input Rate (per 1M tokens) | Output Rate (per 1M tokens) | Context Caching Rates |
| :--- | :--- | :--- | :--- | :--- |
| **Gemini 3.5 Flash** | Google AI Studio | $1.50 | $9.00 | Cache Hit: $0.15 / 1M tokens<br>Storage: $0.01 / 1M tokens/hour |
| **Gemini 3.5 Flash** | OpenRouter | $1.50 | $9.00 | Not supported / Passthrough |
| **DeepSeek V4 Flash** | DeepSeek (Official) | $0.14 (Cache Miss) | $0.28 | Cache Hit: $0.0028 / 1M tokens |
| **DeepSeek V4 Flash** | OpenRouter | $0.098 – $0.14 | $0.196 – $0.28 | Varies by routing/provider |

> [!NOTE]
> DeepSeek's official API supports context caching natively with a 98% discount on cache hits ($0.0028 per 1M tokens). Gemini 3.5 Flash supports context caching on Google AI Studio with a 90% discount on cache hits ($0.15 per 1M tokens).

---

## Key Scenarios & Token Assumptions

The RAG generation pipeline operates under the following constraints:
1. **Granularity:** One API call per selected major topic subtree. No topic splitting or multi-call batching.
2. **Defensive Cap:** Bounded maximum of 25,000 NCERT context characters (~10,000 tokens) to prevent context overrun.
3. **Representative Input Size:** ~10,500 input tokens (including prompt, NCERT chunks, and CBSE JSON schema constraints).
4. **Representative Output Size:** Approximately up to 10,000 output tokens (standard expected output is 5,000 tokens for Q&A candidates).

### **Specific Target Sizes**
* **Largest current `jesc104` topic (Topic 4.4: Ethanol & Ethanoic Acid)**:
  * NCERT characters: ~20,536 characters
  * Context + Prompt before schema: ~8.1k tokens
  * Total Input tokens (with schema): **10,500 tokens**
  * Output tokens: up to **10,000 tokens** (Standard: **5,000 tokens**)
* **Common smaller major topics**:
  * NCERT characters: ~8,000 characters
  * Context + Prompt before schema: ~3.1k tokens
  * Total Input tokens (with schema): **5,500 tokens**
  * Output tokens: up to **5,000 tokens** (Standard: **3,000 tokens**)

---

## Cost Estimates

Cost estimations are calculated for cache misses and cache hits across different scenarios and workflows.

### **Cost per Call Scenarios**

#### **1. Cache Miss (Standard/Cold run)**

| Scenario | Input Tokens | Output Tokens | Gemini 3.5 Flash Cost | DeepSeek V4 Flash Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Representative Q&A Call (Standard Output)** | 10,500 | 5,000 | $0.060750 | $0.002870 |
| **Representative Q&A Call (Max Output)** | 10,500 | 10,000 | $0.105750 | $0.004270 |
| **Largest Topic (jesc104 4.4) (Standard Output)** | 10,500 | 5,000 | $0.060750 | $0.002870 |
| **Largest Topic (jesc104 4.4) (Max Output)** | 10,500 | 10,000 | $0.105750 | $0.004270 |
| **Common Smaller Topic (Standard Output)** | 5,500 | 3,000 | $0.035250 | $0.001610 |
| **Common Smaller Topic (Max Output)** | 5,500 | 5,000 | $0.053250 | $0.002170 |

#### **2. Cache Hit (Warm run / Repeat workflow)**

| Scenario | Input Tokens | Output Tokens | Gemini 3.5 Flash Cost | DeepSeek V4 Flash Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Representative Q&A Call (Standard Output)** | 10,500 | 5,000 | $0.046575 | $0.001429 |
| **Representative Q&A Call (Max Output)** | 10,500 | 10,000 | $0.091575 | $0.002829 |
| **Largest Topic (jesc104 4.4) (Standard Output)** | 10,500 | 5,000 | $0.046575 | $0.001429 |
| **Largest Topic (jesc104 4.4) (Max Output)** | 10,500 | 10,000 | $0.091575 | $0.002829 |
| **Common Smaller Topic (Standard Output)** | 5,500 | 3,000 | $0.027825 | $0.000855 |
| **Common Smaller Topic (Max Output)** | 5,500 | 5,000 | $0.045825 | $0.001415 |

---

## User Workflows & API Call Budgets

### **Workflow 1: Generate One Topic**
* **API Calls:** 1 call
* **Scope:** 1 standard representative major topic.
* **Cost Estimations:**
  * **Gemini 3.5 Flash:** $0.060750 (Miss) | $0.046575 (Hit)
  * **DeepSeek V4 Flash:** $0.002870 (Miss) | $0.001429 (Hit)

### **Workflow 2: Generate Five Topics**
* **API Calls:** 5 calls
* **Scope:** 1 largest topic subtree + 4 common smaller topic subtrees.
* **Cost Estimations:**
  * **Gemini 3.5 Flash:** $0.246750 (Miss) | $0.202875 (Hit)
  * **DeepSeek V4 Flash:** $0.010710 (Miss) | $0.006251 (Hit)

### **Workflow 3: Full 13-Chapter Pass**
* **API Calls:** 52 calls
* **Assumptions:** 13 textbook chapters averaging 4 major topics each (52 topics total). We assume 1 largest topic subtree call and 3 smaller topic subtree calls per chapter.
* **Cost Estimations:**
  * **Gemini 3.5 Flash:** $2.749500 (Miss) | $2.275650 (Hit)
  * **DeepSeek V4 Flash:** $0.118300 (Miss) | $0.070143 (Hit)

---

## Key Assumptions & Uncertainties

1. **Token Density:** Standard ratio of 4 characters per token is assumed for NCERT text and JSON schemas.
2. **Schema Overhead:** The structured output schema and system prompts are assumed to consume approximately 2,400 tokens per call.
3. **Cache Invalidation:** OpenRouter does not guarantee cache hits for all routed providers. Actual cache-hit ratios might be lower depending on traffic and OpenRouter-specific configurations.
4. **Validation Drops:** As specified in [issue-142-generation-foundation.md](file:///Users/varad/V/repo/qs-paper-generator/docs/Varad/scratchboards/issue-142-generation-foundation.md), invalid Q&A outputs are discarded before candidate persistence. If a model generates invalid payloads, additional calls may be required to fulfill quotas, raising actual API call counts and final costs.
5. **Gateway Provider:** OpenRouter routing pricing may vary slightly from official platform pricing based on routing markups or selected backend providers.
