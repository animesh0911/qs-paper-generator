# DeepSeek Models via OpenRouter (Python/LangChain POC Notes)

This document outlines how to call DeepSeek models using OpenRouter's OpenAI-compatible API inside a Python application using LangChain.

---

## 1. API Configuration

### Endpoints and Authentication
*   **Base URL**: `https://openrouter.ai/api/v1`
*   **Authentication Header**: `Authorization: Bearer <OPENROUTER_API_KEY>`
*   **Environment Variable**: `OPENROUTER_API_KEY`

### Optional Attribution Headers
Include these headers to track usage and identify your application in OpenRouter's analytics and rankings:
*   `HTTP-Referer`: Your application's URL (e.g., `https://myapp.com` or `http://localhost:3000` for development).
*   `X-Title` (or `X-OpenRouter-Title`): The name of your application.

---

## 2. Recommended DeepSeek Model Slugs

| Model | OpenRouter Slug | Description / Features |
|---|---|---|
| **DeepSeek-V3 (Flagship Chat)** | `deepseek/deepseek-chat` | Flagship chat/instruct model, great for standard completions and structured tasks. |
| **DeepSeek-R1 (Flagship Reasoning)** | `deepseek/deepseek-r1` | Advanced reasoning model featuring chain-of-thought (reasoning tokens) output. |
| **DeepSeek-R1 Distill Llama 70B** | `deepseek/deepseek-r1-distill-llama-70b` | Distilled reasoning model based on Meta's Llama 3.3 architecture. |
| **DeepSeek-R1 Distill Qwen 32B** | `deepseek/deepseek-r1-distill-qwen-32b` | Distilled reasoning model based on Alibaba's Qwen 2.5 architecture. |
| **Free Tier Router** | `deepseek/deepseek-chat:free` / `deepseek/deepseek-r1:free` | Free endpoints for testing (availability and speed vary). |

*Note: You can programmatically fetch the active models using `GET https://openrouter.ai/api/v1/models`.*

---

## 3. Integration with LangChain Python

### Method A: Using the Dedicated `langchain-openrouter` Package (Recommended)
This is the preferred approach as it natively handles OpenRouter's API responses and handles model features (like reasoning/thinking tokens) correctly.

```bash
pip install -U langchain-openrouter
```

```python
import os
from langchain_openrouter import ChatOpenRouter

# Automatically picks up OPENROUTER_API_KEY environment variable
llm = ChatOpenRouter(
    model="deepseek/deepseek-chat",
    temperature=0.7,
)

response = llm.invoke("Explain Quantum Computing in one sentence.")
print(response.content)
```

### Method B: Using Standard `langchain-openai` (Fallback/Proxy)
If you prefer not to install another library, you can configure the standard `ChatOpenAI` wrapper to point to OpenRouter.

```bash
pip install -U langchain-openai
```

```python
import os
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="deepseek/deepseek-chat",
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "QS Paper Generator POC",
    }
)

response = llm.invoke("Explain Quantum Computing in one sentence.")
print(response.content)
```

---

## 4. Structured Output and JSON Mode

### Native JSON Mode
You can request structured output by setting the `response_format` configuration to `{"type": "json_object"}`.

> [!IMPORTANT]
> When using `json_object`, you **must** explicitly prompt the model to return JSON in the system message or instruction.

```python
from langchain_openrouter import ChatOpenRouter

llm = ChatOpenRouter(model="deepseek/deepseek-chat").bind(
    response_format={"type": "json_object"}
)

response = llm.invoke(
    "Output a JSON object with 'capital' and 'population' for France."
)
print(response.content)
```

### LangChain `with_structured_output`
LangChain's `with_structured_output()` utility will use tool/function calling or JSON schema formatting under the hood.

```python
from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, Field

class CountryInfo(BaseModel):
    capital: str = Field(description="The capital city of the country")
    population: int = Field(description="Approximate population size")

llm = ChatOpenRouter(model="deepseek/deepseek-chat")
structured_llm = llm.with_structured_output(CountryInfo)

result = structured_llm.invoke("Tell me about France.")
print(result.capital, result.population)
```

### DeepSeek-R1 & Reasoning Token Caveats
Using structured output with reasoning models like **DeepSeek-R1** (`deepseek/deepseek-r1`) introduces specific challenges:
1.  **Reasoning vs. JSON**: R1 outputs a chain of thought (reasoning block) before producing the final JSON. While some downstream integrations/providers handle separating this reasoning content, generic JSON parsers may fail if the thinking prefix is included in the raw text output.
2.  **Provider Support**: Structured output schema enforcement (like JSON schema/tool calling) is handled by the underlying provider routing on OpenRouter. Not all providers serving DeepSeek models support strict JSON schema constraints.
3.  **Recommendations**:
    *   For strict structured outputs (e.g. strict Pydantic parsing), prefer **DeepSeek-V3** (`deepseek/deepseek-chat`) or a distilled model (like Llama-70B/Qwen-32B) over the full DeepSeek-R1.
    *   If you must use R1, utilize libraries like [Instructor](https://github.com/instructor-ai/instructor) (with `Mode.MD_JSON` parsing mode) or post-process the response to strip any `<think>...</think>` tags before parsing.

---

## 5. Official References
*   [OpenRouter API Documentation](https://openrouter.ai/docs)
*   [OpenRouter Models Catalog](https://openrouter.ai/models)
*   [LangChain OpenRouter Integration Docs](https://python.langchain.com/docs/integrations/chat/openrouter/)
*   [DeepSeek API Official Documentation](https://api-docs.deepseek.com)
