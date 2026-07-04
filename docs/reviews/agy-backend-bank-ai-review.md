# Code Review: Backend Bank & AI Services

## 1. Executive Summary

This code review provides a deep analysis of the question bank and AI integration modules of the platform. The scope includes:
* **Models & Views**: `backend/bank/models.py`, `backend/bank/views.py`
* **AI Generation & Verification**: `backend/bank/generated_question_gate.py`, `backend/bank/generation.py`, `backend/bank/tests/`
* **AI Services Seam**: `backend/ai_services/llm.py`
* **AI Editor Assistant**: `backend/ai_editor/assistant.py`

The architecture is well-structured, with a provider-agnostic model seam (`ai_services.llm`) and a deterministic validation gate (`generated_question_gate.py`) to isolate untrusted LLM outputs from database persistence. 

However, several severe findings were identified that could compromise system stability, cause runtime database crashes, lead to double billing due to concurrent graph executions, and create data inconsistencies. Key issues include:
1. A **Critical** TypeError crash when converting MCQ candidates that carry a `null` option content.
2. A **High** concurrency race in the cron-run reclaiming logic that allows duplicate worker executions on active LangGraph threads.
3. A **High** stability issue in synchronous HTTP views where LLM parsing errors propagate as 500 errors to teachers.
4. Several **Medium** validation bypasses, transactional gaps, and test environment leakages.

---

## 2. Findings & Evidence

### [Critical] MCQ Option Content Iteration Crash on `null` Value
* **Location**: [generation_batches.py:L407-417](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/generation_batches.py#L407-L417)
* **Evidence**:
  ```python
  def options_from_generated_content(payload):
      if payload["qtype"] != QuestionType.MCQ:
          return []
      options = payload.get("content", {}).get("options", [])
      flattened = []
      for option in options:
          if not isinstance(option, dict):
              continue
          content = option.get("content", [])
          text = " ".join(
              item.get("text", "")
              for item in content
              if isinstance(item, dict) and isinstance(item.get("text"), str)
          ).strip()
          flattened.append({"label": option.get("label", ""), "text": text})
      return flattened
  ```
* **Analysis**:
  If the LLM generates an option with `"content": null` (which is standard JSON null, and common with non-native structured fallback models), `option.get("content", [])` returns `None` instead of `[]` because the key `content` exists.
  When the loop `for item in content:` is executed, it raises `TypeError: 'NoneType' object is not iterable` and rolls back the database transaction. This permanently prevents the teacher from accepting the batch. Moreover, `generated_question_gate.py` does not validate that `option["content"]` is a list, completely bypassing validation.
* **Concrete Fix**:
  1. In [generation_batches.py:L410](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/generation_batches.py#L410), fallback to `[]` when `content` is `None`:
     ```python
     content = option.get("content") or []
     ```
  2. In `generated_question_gate.py` under `_validate_content`, validate option structure:
     ```python
     for option in options:
         if not isinstance(option, dict):
             errors.append(CandidateValidationError(index, "bad_option_format", "Option must be a dictionary"))
             continue
         if not isinstance(option.get("content"), list):
             errors.append(CandidateValidationError(index, "bad_option_content", "Option content must be a list"))
     ```

---

### [High] LangGraph Thread Concurrency Race & Reclaim Overlap
* **Location**: [generation_batches.py:L142-155](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/generation_batches.py#L142-L155)
* **Evidence**:
  ```python
  def claim_generation_batch(batch_id: int) -> tuple[GenerationBatch | None, bool]:
      with transaction.atomic():
          batch = (
              GenerationBatch.objects.select_for_update(skip_locked=True)
              .filter(drainable_filter(timezone.now()), pk=batch_id)
              .first()
          )
          ...
          batch.status = GenerationBatchStatus.GENERATING_QUESTIONS
          batch.save(update_fields=["status", "updated_at"])
          return batch, reclaimed
  ```
* **Analysis**:
  `claim_generation_batch` starts and commits a transaction to mark the batch `status = GENERATING_QUESTIONS`. Once the function exits, the database lock on the row is released. The actual execution `process_generation_batch` runs outside of a transaction to prevent connection pool starvation during slow LLM calls.
  If the LangGraph execution runs longer than 10 minutes (due to rate limits, model latency, or thread resumes), the next cron pass of `drain_generation_batches` will find the batch via `drainable_filter` (since its `updated_at` is stale). Because the row is not locked, the new cron worker will claim the batch and concurrently call `graph.invoke` on the same `thread_id`. This creates race conditions on the checkpointer state, double-billed API calls, and duplicate candidates.
* **Concrete Fix**:
  Use a persistent worker lock or process-level locking around `thread_id` (e.g., via a Redis lock or a dedicated `is_running` flag periodically touched by the active thread) to ensure that two workers never invoke the same thread concurrently.

---

### [High] Uncaught Parsing Exceptions in Synchronous HTTP Views
* **Location**: [assistant.py:L78-80](file:///Users/varad/V/repo/qs-paper-generator/backend/ai_editor/assistant.py#L78-L80) and [assistant.py:L94-96](file:///Users/varad/V/repo/qs-paper-generator/backend/ai_editor/assistant.py#L94-L96)
* **Evidence**:
  ```python
  result: IntentResult = (make_model(ModelPurpose.EDITOR_ASSISTANT) | parser).invoke(
      prompt
  )
  ```
* **Analysis**:
  `classify_intent` runs inside the synchronous HTTP request lifecycle. If the model's output cannot be parsed into `IntentResult` (JSON is malformed or missing fields), the `PydanticOutputParser` raises an exception (`OutputParserException` or `ValidationError`). Since there is no try-except block, the exception propagates, resulting in a 500 Internal Server Error returned to the teacher.
* **Concrete Fix**:
  Wrap the invocation in a try-except block, log the parsing error, and return a clean fallback payload:
  ```python
  try:
      result: IntentResult = (make_model(ModelPurpose.EDITOR_ASSISTANT) | parser).invoke(prompt)
      route = result.route if result.route in INTENT_ROUTES else "off_topic"
      reason = result.reason
  except Exception as exc:
      logger.exception("Assistant intent classification failed: %s", exc)
      route = "off_topic"
      reason = "Fell back due to classification failure."
  return {"route": route, "reason": reason}
  ```

---

### [Medium] Database Updates inside GET Requests
* **Location**: [views.py:L396-402](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/views.py#L396-L402) and [views.py:L407-415](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/views.py#L407-L415)
* **Evidence**:
  ```python
  @api_view(["GET"])
  @permission_classes([IsTeacher])
  def generation_batch_detail(request, batch_id):
      batch = get_owned_generation_batch(request.user, batch_id)
      ...
      batch.expire_if_stale()
      return Response(GenerationBatchSerializer(batch).data)
  ```
* **Analysis**:
  The HTTP GET endpoints `generation_batch_detail` and `generation_batch_candidates` lazily trigger `expire_if_stale()`, which performs database writes (`update()` queries on `GenerationBatch` and `GeneratedQuestionCandidate`). GET requests are expected to be idempotent and read-only. Triggering writes on GET risks performance issues and data corruption if requests are pre-fetched or timed out, especially since they run without an atomic transaction wrapper.
* **Concrete Fix**:
  Do not update state on GET requests. Instead, let the background cron job handle all expirations via `GenerationBatch.expire_ready_batches()`, or change the status check to be dynamic in the serializer without persisting the change to the database during read views.

---

### [Medium] Non-Transactional Multi-Query Batch Expiry
* **Location**: [models.py:L420-428](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/models.py#L420-L428)
* **Evidence**:
  ```python
  cls.objects.filter(pk__in=batch_ids).update(
      status=GenerationBatchStatus.EXPIRED,
      expired_at=now,
      updated_at=now,
  )
  GeneratedQuestionCandidate.objects.filter(
      batch_id__in=batch_ids,
      status=GeneratedQuestionCandidateStatus.READY_FOR_REVIEW,
  ).update(status=GeneratedQuestionCandidateStatus.EXPIRED, updated_at=now)
  ```
* **Analysis**:
  `GenerationBatch.expire_ready_batches()` performs two distinct database updates but is not wrapped in `transaction.atomic()`. In addition, it is called outside the transaction block inside `queue_generation_batch()`. If a crash occurs between the queries, the batches will be updated to `EXPIRED` while their candidates remain in `READY_FOR_REVIEW`, creating an inconsistent state.
* **Concrete Fix**:
  Wrap the updates inside `expire_ready_batches` in `with transaction.atomic():` to guarantee ledger consistency.

---

### [Medium] Missing `source_hash` on Accepted AI-Generated Questions
* **Location**: [generation_batches.py:L369-390](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/generation_batches.py#L369-L390)
* **Evidence**:
  ```python
  def question_from_candidate(candidate, batch):
      payload = candidate.payload
      ...
      return Question.objects.create(
          school=batch.school,
          chapter=chapter,
          ...
          verified=False,
          parse_quality=ParseQuality.CLEAN,
          source_type=SourceType.AI_GENERATED,
          source_name=payload.get("source", {}).get("name", ""),
      )
  ```
* **Analysis**:
  The system uses `source_hash` (the MD5 hash of normalized question text) to deduplicate questions on ingest. When converting an accepted generated question candidate into a `Question`, `question_from_candidate` does not calculate or set this hash (leaving it empty).
  If a teacher later uploads a PDF that contains a question identical to one that was generated by AI and accepted, the deduplication engine will fail to catch it, creating duplicate rows in the bank.
* **Concrete Fix**:
  Import `_fingerprint` from `bank.extraction` and set it on creation:
  ```python
  from bank.extraction import _fingerprint
  ...
  return Question.objects.create(
      ...
      source_hash=_fingerprint(payload["raw_text"]),
      ...
  )
  ```

---

### [Medium] Validation Bypass: Mismatch Between `raw_text` and `content.stem`
* **Location**: [generated_question_gate.py:L196-200](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/generated_question_gate.py#L196-L200)
* **Analysis**:
  The system instructions command the model to match `raw_text` exactly with `content.stem` text. However, `generated_question_gate.py` does not validate this constraint. If a model outputs mismatched text (e.g. changing one field but not the other), the gate accepts it. This creates data inconsistencies between question searching/picking (which queries `text`) and paper rendering (which uses `content`), causing formatting/content mismatches.
* **Concrete Fix**:
  Add validation in the gate:
  ```python
  stem_text = " ".join(item.get("text", "") for item in stem if isinstance(item, dict)).strip()
  if raw_text.strip() != stem_text:
      errors.append(CandidateValidationError(index, "raw_text_stem_mismatch", "raw_text must match content.stem text"))
  ```

---

### [Medium] Ambient Env Leakage in Ingestion Tests
* **Location**: [test_ingestion_job.py:L338](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/tests/test_ingestion_job.py#L338) and [test_ingestion_job.py:L365](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/tests/test_ingestion_job.py#L365)
* **Analysis**:
  Tests like `test_drain_processes_pending_job_into_bank` call `call_command("drain_ingestion_jobs")` without specifying the `--extractor` option. If `EXTRACTION_PIPELINE` is set to `mistral-ocr-batch` in the container/host environment, the command runs the Mistral OCR pipeline and bypasses the mocked `make_chat_model`, calling the real Mistral API and throwing a 400 error when it hits the dummy PDF, making the test suite fragile.
* **Concrete Fix**:
  Explicitly configure `--extractor="gemini-native-pdf"` in the test call:
  ```python
  call_command("drain_ingestion_jobs", extractor="gemini-native-pdf")
  ```

---

### [Medium] Job Error Formatter Misses Standard `DefaultCredentialsError` Messages
* **Location**: [drain_ingestion_jobs.py:L50](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/management/commands/drain_ingestion_jobs.py#L50)
* **Analysis**:
  The function `_format_extraction_error` looks for the substring `"Your default credentials were not found"` to rewrite Google ADC errors. However, standard python `google-auth` exceptions in local setups and tests often raise `"Could not automatically determine credentials"`, bypassing the check and outputting a cryptic failure trace to the user.
* **Concrete Fix**:
  Broaden the match:
  ```python
  if "credentials" in message.lower():
      ...
  ```

---

## 3. Positive Notes

* **Robust LangGraph Checkpointing**: The use of `durability="sync"` in the LangGraph runner is excellent; it prevents duplicate AI token consumption/billing in case of command termination.
* **Telemetry Seam**: Obsverability is extremely clean. Running telemetry inside `LlmCallObserver` (hooked into `init_chat_model`) ensures all services (generation, editor, extraction) are monitored for tokens and latency without contaminating domain code.
* **Type-Aware Selection**: `select_balanced_questions` does a great job maintaining question distribution and balancing question types in review sessions.

---

## 4. Suggested Tests

1. **MCQ Option Content Null-Safe Unit Test**:
   ```python
   def test_options_from_generated_content_handles_null_content():
       payload = {
           "qtype": "mcq",
           "content": {
               "options": [
                   {"label": "A", "content": None},
                   {"label": "B", "content": [{"type": "paragraph", "text": "Option B"}]}
               ]
           }
       }
       # Should not raise TypeError and return correctly parsed options
       options = options_from_generated_content(payload)
       assert len(options) == 2
       assert options[0]["text"] == ""
       assert options[1]["text"] == "Option B"
   ```

2. **Synchronous Intent View Resiliency Test**:
   ```python
   from unittest.mock import patch
   from ai_editor.assistant import classify_intent

   def test_classify_intent_handles_parser_errors():
       # Mock the chain invoke to return invalid JSON output that raises parsing error
       with patch("ai_services.llm.make_chat_model") as mock_model:
           # Trigger classify_intent
           res = classify_intent("invalid payload", paper_title="Test Title")
           assert res["route"] == "off_topic"
   ```

3. **Isolated Extractor Environment Test**:
   Assert that `call_command("drain_ingestion_jobs")` runs against the expected mock extractor regardless of the ambient `EXTRACTION_PIPELINE` environment variable.
