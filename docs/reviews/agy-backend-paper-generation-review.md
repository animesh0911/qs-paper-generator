# Code Review Report: AGY Backend Paper Generation Pipelines

This report presents a deep code review of the `backend/papers`, `backend/workflows`, `backend/papers/tests`, and `backend/workflows/tests` modules, and relevant contracts. The focus is on severe logical gaps, data integrity, transactionality, edge cases, test blind spots, and obvious maintainability/performance improvements.

---

## 1. Executive Summary

A comprehensive architectural and code-level audit was conducted on the question-picking, paper-assembly, and resumable LLM extraction/generation workflows. 

The codebase shows strong design patterns—particularly the use of a pure in-memory allocator seam in the picker (`_select_from_pool`) and an elegant per-page checkpointing system via LangGraph. However, several critical gaps were identified:
1. **Broken Transactionality in Assembly**: A partial commit structure in paper assembly leaves orphaned, invalid draft papers in the database if downstream contract validation fails.
2. **Environment/Configuration Sensitivity in Tests**: The resume-from-checkpoint tests crash with a `KeyError: 'created'` depending on local `.env` variables due to pipeline routing mismatches.
3. **Linear Performance Degradation**: The freshness tracker aggregates a teacher's entire historical usage pattern on every run without limits or time boundaries, creating a linear database and memory scaling bottleneck.
4. **Sub-optimal Swap Experience**: Swapping a question to an alternate in the editor causes a validation mismatch 400 error unless the frontend explicitly deletes the answer entry.

All findings are documented below with precise file locations, logical explanations, and concrete code fixes.

---

## 2. Critical & High-Severity Findings

### Finding A: Test Failure and Command Crash on Pipeline Resume Mismatches
* **File:** `bank/management/commands/drain_ingestion_jobs.py` (Line 196–205) and `workflows/tests/test_extraction.py` (Line 93)
* **Status:** High / Critical
* **Reasoning:**
  In local development, developers often set `EXTRACTION_PIPELINE=mistral-ocr-batch` in their `.env` file. However, `test_drain_resumes_running_job_by_thread_id` crashes a `gemini-native-pdf` graph and attempts to resume it via `call_command("drain_ingestion_jobs")`. 
  Because the test's `thread_id` lacks a routing prefix, the command defaults to the configured `mistral-ocr-batch` extractor. When LangGraph loads a checkpoint for a graph structure (`gemini-native-pdf`) using a different graph topology (`mistral-ocr-batch`), it notices that the checkpoint's next execution node does not exist in the new graph. Instead of failing gracefully, the graph engine returns the current state values immediately. Because these values lack the `"created"` and `"skipped"` keys expected by the command's status update logic, a `KeyError: 'created'` is thrown.
  In production, if a pipeline is switched or a thread ID is saved without a prefix, this KeyError will crash the entire cron execution loop of the management command, blocking other ingestion jobs.

* **Concrete Fix:**
  1. Fix the test in `workflows/tests/test_extraction.py` to format the mock thread ID with the pipeline prefix:
     ```diff
     -    thread_id = uuid.uuid4().hex
     +    thread_id = f"gemini-native-pdf:{uuid.uuid4().hex}"
     ```
  2. Add robust fallback logic in `bank/management/commands/drain_ingestion_jobs.py` to handle mismatched graph state structure safely:
     ```python
     # in _process()
     created_count = final.get("created")
     if created_count is None:
         raise ValueError(
             f"Graph execution returned state without 'created' counter. "
             f"This indicates a pipeline mismatch or corrupted checkpoint state for thread {job.thread_id}."
         )
     job.created_count = created_count
     ```

---

### Finding B: Orphaned Draft Papers Due to Post-Commit Validation Failure
* **File:** `backend/papers/builder.py:43–83` (`PaperBuilder.assemble`)
* **Status:** High
* **Reasoning:**
  `PaperBuilder.assemble()` delegates saving the `Paper` and `PaperQuestion` rows to `_persist()`, which is decorated with `@transaction.atomic`. However, downstream calls such as `self._guard_contract(paper, document)` (which checks the V1 contract schema and raises `PaperDocumentContractError` if invalid) and `build_answer_document(paper)` occur **outside** of this transaction block.
  If contract validation fails or `build_answer_document` raises an error, the `_persist()` transaction has already committed. This results in orphaned `Paper` rows with `document=None` and `answer_document=None` polluting the database.

* **Concrete Fix:**
  Move the transaction boundary to cover the entire assembly orchestration within `PaperBuilder.assemble()`:
  ```python
  class PaperBuilder:
      def assemble(self, ...) -> AssemblyResult:
          # Move @transaction.atomic from _persist to the assemble method:
          with transaction.atomic():
              # ... logic to build preset / template ...
              result = QuestionPicker().select(opts)
              paper = self._persist_without_decorator(user, title, result)
              document = PaperDocumentBuilder().build(paper, result, opts, paper_format)
              self._guard_contract(paper, document)
              paper.document = document
              paper.answer_document = build_answer_document(paper)
              paper.save(update_fields=["document", "answer_document"])
          return AssemblyResult(paper=paper, document=document)
  ```

---

## 3. Medium-Severity Findings

### Finding C: Freshness Tracker Query Scales Linearly Over Time
* **File:** `backend/papers/picker.py:145–154` (`QuestionPicker._fetch_usage`)
* **Status:** Medium
* **Reasoning:**
  To support the freshness penalty, the picker queries the database for all question usages by the requesting user:
  ```python
  counts = (
      QuestionUsage.objects.filter(used_by=user)
      .values("question_id")
      .annotate(n=Count("question_id"))
  )
  ```
  This query fetches and aggregates **every** question ever approved by this teacher across their entire account history. If a teacher uses the system for multiple semesters, this dataset grows indefinitely. Loading the complete aggregation into memory and mapping it to a dictionary on every paper generation/review request introduces a slow database-querying and memory-scaling bottleneck.

* **Concrete Fix:**
  Introduce a time-bound window (e.g., lookback to papers approved within the last 180 days) or filter usage counts by recent documents:
  ```python
  from django.utils import timezone
  import datetime

  cutoff = timezone.now() - datetime.timedelta(days=180)
  counts = (
      QuestionUsage.objects.filter(used_by=user, approved_at__gte=cutoff)
      .values("question_id")
      .annotate(n=Count("question_id"))
  )
  ```

---

### Finding D: 400 Bad Request on Question Swap Due to Strict Answer Verification
* **File:** `backend/papers/views.py:125–140` (PATCH `editor-draft` endpoint)
* **Status:** Medium
* **Reasoning:**
  When a teacher swaps a question in a slot to one of its alternates, the frontend updates the slot's `selectedQuestionId`. Since the GET response only includes the answer for the active question (not alternates), the frontend does not have the bank answer for the swapped question. If the frontend submits the PATCH payload with the old answer entry still in the answer document, `validate_answer_document` raises a mismatch error:
  `Slot slot_id answer questionId does not match selected question.`
  The PATCH endpoint checks:
  ```python
  if errors and all("has no answer entry" in error for error in errors):
      # ... automatically rebuild answer document ...
  ```
  Because the error is a mismatch rather than a "has no answer entry" error, the PATCH request is rejected with `400 Bad Request` instead of performing auto-reconciliation. This requires the frontend client to manually find and delete answer entries on swap, creating fragile interface coupling.

* **Concrete Fix:**
  Allow the backend to automatically heal mismatch errors during PATCH validation. In the view handler:
  ```python
  # Rebuild if the errors only consist of missing answers OR mismatch errors
  is_reconcilable = all(
      ("has no answer entry" in err or "does not match selected question" in err)
      for err in errors
  )
  if errors and is_reconcilable:
      # Automatically reconstruct answers from the bank for swapped slots
      answer_document = build_answer_document(
          SimpleNamespace(
              pk=paper.pk,
              document=document,
              answer_document=answer_document,
          )
      )
  ```

---

## 4. Positive Notes

* **In-Memory Selection Seam**: Isolating the pure allocation logic in `QuestionPicker._select_from_pool` decoupled from database reads is an excellent practice that simplifies unit testing.
* **Schema Integrity**: The strict JSON validation step (`validate_paper_document`) at the end of paper assembly prevents malformed documents from contaminating database storage.
* **Resumability Invariants**: The use of single-process checkpointing with same-database tables (ADR-0006) avoids complex external queue dependencies like Redis or Celery.

---

## 5. Suggested Tests

1. **Verify Mismatched Graph Resumption Handling**:
   Write a test that registers a checkpoint under one thread, compiles a new graph with an incompatible node sequence under the same thread, runs the drain command, and verifies that the command fails gracefully with an informative log message rather than a `KeyError`.

2. **Verify Assembly Rollback on Guard Validation Failure**:
   Add a test to `backend/papers/tests/test_builder.py` that mocks `_guard_contract` to raise a `PaperDocumentContractError` and asserts that the `Paper` row is rolled back and not persisted in the database.

3. **Verify Answer Rebuilding on Swapped Question PATCH**:
   Write an API integration test verifying that a PATCH request containing a mismatched `questionId` in the `answer_document` (simulating a frontend question swap) successfully completes and yields the correct bank answer for the new question.
