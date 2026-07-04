# Deep Code Review: Paper Setup and Generation Workflow

## Executive Summary
This code review evaluates the frontend implementation of the paper setup and generation workflow. The scope covers:
- **State Management & Hooks**: `frontend/src/hooks/useCoverageForm.hook.ts`
- **Dialogs & Forms**: `frontend/src/components/coverage/coverage-form`
- **Page Orchestration**: `frontend/src/pages/dashboard.page.tsx`
- **Adapters & API Client**: `frontend/src/lib/api.ts`
- **Document Rendering & Printing**: `frontend/src/components/coverage/answer-key-print-view.component.tsx` & `paper-document-view.component.tsx`

While the modular structure separates API, data mapping, and presentation nicely, several logical bugs, state synchronization gaps, accessibility issues, and performance bottlenecks were identified. Most notably:
1. **Stale Data / Crash**: A stale or invalid format ID stored in `sessionStorage` bypasses verification upon API fetch, which will lead to backend paper assembly failures when the user submits.
2. **Unhandled Storage Exceptions**: Calls to `sessionStorage.setItem` are not guarded, which will crash the setup page in private browsing modes or when storage quotas are exceeded.
3. **Inefficient Reconciliation Loop**: The selection modals utilize a custom `reconcileSelection` helper that updates React state inside a loop, triggering up to $2 \times N$ individual state updates.
4. **UX / State Desynchronization**: Changing chapter selections silently filters out selected sources without warning, leading to lost user intent.
5. **Accessibility / Overlay Flaws**: The dialogs lack scroll locking, focus trapping, Escape key handlers, and top-level close controls.

---

## Findings

### Critical & High Findings

#### 1. Stale Format ID Bypass Leading to Backend Failures
*   **File**: `frontend/src/hooks/useCoverageForm.hook.ts:185` and `213-221`
*   **Evidence**:
    ```typescript
    const [selectedFormatId, setSelectedFormatId] = useState(
      saved.selectedFormatId,
    );
    ...
    fetchPaperFormats()
      .then((nextFormats) => {
        setFormats(nextFormats);
        setSelectedFormatId(
          (current) => current || nextFormats[0]?.format_id || '',
        );
      })
    ```
*   **Logical Gap**: If a user previously saved a format ID to `sessionStorage` that is later deleted or becomes unavailable, the hook initializes with that stale `selectedFormatId`. When the format list resolves, the hook only defaults `selectedFormatId` to the first format if `current` is empty. Consequently, `selectedFormatId` remains set to the invalid ID. The dropdown in the UI will display incorrectly (often showing the first item or empty), but clicking **Generate paper** will submit the invalid ID, causing the backend request to throw a 400/500 error.
*   **Fix**: Validate that `selectedFormatId` exists within the resolved formats. If it does not, reset it to the first available format.
    ```typescript
    fetchPaperFormats()
      .then((nextFormats) => {
        setFormats(nextFormats);
        setSelectedFormatId((current) => {
          const exists = nextFormats.some((f) => f.format_id === current);
          return exists ? current : (nextFormats[0]?.format_id || '');
        });
      })
    ```

#### 2. Unhandled `sessionStorage` Exceptions Cause Rendering Crashes
*   **File**: `frontend/src/hooks/useCoverageForm.hook.ts:255-265`
*   **Evidence**:
    ```typescript
    useEffect(() => {
      sessionStorage.setItem(
        COVERAGE_FORM_STORAGE_KEY,
        JSON.stringify({
          selectedFormatId,
          selectedSlugs: Array.from(selectedSlugs),
          selectedSourceKeys: Array.from(selectedSourceKeys),
          difficulty,
          totalMarks,
        }),
      );
    }, [selectedFormatId, selectedSlugs, selectedSourceKeys, difficulty, totalMarks]);
    ```
*   **Logical Gap**: In incognito tabs, private browsing modes, or when storage limits are exceeded, writing to `sessionStorage` throws a `DOMException` (e.g. `QuotaExceededError`). Unlike the read path (`readSavedCoverageForm`), the write operation in this effect is unguarded. An unhandled exception here will crash the component's state update cycle.
*   **Fix**: Wrap the `sessionStorage.setItem` call in a `try-catch` block.
    ```typescript
    useEffect(() => {
      try {
        sessionStorage.setItem(
          COVERAGE_FORM_STORAGE_KEY,
          JSON.stringify({ ... })
        );
      } catch (err) {
        console.warn('Failed to write setup state to sessionStorage:', err);
      }
    }, [selectedFormatId, selectedSlugs, selectedSourceKeys, difficulty, totalMarks]);
    ```

---

## Medium Findings

### 3. Inefficient State Reconciliation Loop in Dialog Approvals
*   **File**: `frontend/src/components/coverage/coverage-form/coverage-form.component.tsx:885-896` (`reconcileSelection`)
*   **Evidence**:
    ```typescript
    function reconcileSelection(
      current: Set<string>,
      next: Set<string>,
      toggle: (value: string) => void,
    ) {
      for (const value of current) {
        if (!next.has(value)) toggle(value);
      }
      for (const value of next) {
        if (!current.has(value)) toggle(value);
      }
    }
    ```
*   **Logical Gap**: The dialog uses `reconcileSelection` to align the parent hook's state with the dialog's local draft. It loops through differences and calls the parent's `toggle` function. If a user toggles $N$ items and clicks **Approve selection**, it schedules $N$ separate state updates. While React 18 batches these state updates during the render cycle, this approach is extremely verbose, creates unnecessary intermediate closures, and requires the hook to expose item-level togglers instead of clean collection setters.
*   **Fix**: Expose bulk setter functions from `useCoverageForm` (e.g., `setSelectedSlugs` and `setSelectedSourceKeys`) and update the collection in a single atomic action:
    ```typescript
    // In coverage-form.component.tsx:
    function approveChapters() {
      form.setSelectedSlugs(draftSlugs);
      setOpen(false);
    }
    ```

### 4. Silent Source Deselection Leads to Lost User Intent
*   **File**: `frontend/src/hooks/useCoverageForm.hook.ts:227-253`
*   **Evidence**:
    ```typescript
    fetchPaperSources(selectedChapterSlugs)
      .then((nextSources) => {
        if (cancelled) return;
        const orderedSources = sortPaperSourcesByUploadTime(nextSources);
        const validKeys = new Set(orderedSources.map((source) => source.key));
        setSources(orderedSources);
        setSelectedSourceKeys(
          (current) =>
            new Set([...current].filter((key) => validKeys.has(key))),
        );
        ...
    ```
*   **Logical Gap**: When the user modifies chapter selections, `fetchPaperSources` is invoked with the updated chapters. Any previously selected sources that are not compatible with the newly selected chapters are silently filtered out of `selectedSourceKeys`. If a user selected a specific source first, and then restricted the chapters, their source priority is quietly discarded without notification.
*   **Fix**: Retain incompatible sources in the state but mark them as inactive/warning states in the UI list, rather than silently deleting them. Alternatively, prompt the user before clearing incompatibilities.

### 5. Modal Dialog Overlay Vulnerable to Scroll Bleed
*   **File**: `frontend/src/components/coverage/coverage-form/coverage-form.component.tsx:318-361` (`SelectionDialog`)
*   **Evidence**:
    ```typescript
    className="fixed inset-0 z-50 flex items-stretch bg-background p-0 sm:items-center sm:bg-foreground/20 sm:p-6"
    ```
*   **Logical Gap**: When the chapter or source selection dialog is open, the background dashboard layout is not locked. Users scrolling a long list of chapters will trigger scrolling on the main page behind the dialog once the dialog boundary is reached.
*   **Fix**: Toggle `overflow: hidden` on `document.body` while the modal dialog is active.
    ```typescript
    useEffect(() => {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }, []);
    ```

### 6. Missing Keyboard Accessibility Features in selection Modals
*   **File**: `frontend/src/components/coverage/coverage-form/coverage-form.component.tsx:318-361`
*   **Evidence**: Lack of keydown event handling or focus trapping.
*   **Logical Gap**: The dialog declares `role="dialog"` and `aria-modal="true"`, but keyboard navigation can escape the boundary of the modal. There is no active focus trap, allowing users to tab into background elements. Additionally, pressing the `Escape` key does not dismiss the modal, and there is no close button in the dialog header.
*   **Fix**:
    - Implement a focus trap within the dialog wrapper.
    - Attach a keydown listener for the `Escape` key to execute `onCancel`.
    - Render an accessible close button in the header.

---

## Low Findings & Maintainability Improvements

### 7. Dead Code: `toggleChapterGroup`
*   **File**: `frontend/src/hooks/useCoverageForm.hook.ts:327-341`
*   **Evidence**: The hook exposes `toggleChapterGroup`, but `ChapterSelectionShell` uses its own local `toggleSetValues` helper inside `ChapterGroups` (line 677).
*   **Fix**: Remove `toggleChapterGroup` from the hook since it is unused.

### 8. Promise Leaks on Unmount
*   **File**: `frontend/src/hooks/useCoverageForm.hook.ts:197-221`
*   **Evidence**:
    ```typescript
    useEffect(() => {
      fetchChapters().then(...);
      fetchPaperFormats().then(...);
    }, []);
    ```
*   **Logical Gap**: If a user navigates away from the page before the initial chapters or formats API requests complete, the state transitions run on an unmounted component.
*   **Fix**: Implement an cleanup active flag inside the mount effect.

### 9. LaTeX Text Rendering in Print Answer Key
*   **File**: `frontend/src/components/coverage/answer-key-print-view.component.tsx:100-109`
*   **Evidence**:
    ```typescript
    if (!item.text && item.latex) {
      return (
        <p>
          <MathExpression latex={item.latex} />
        </p>
      );
    }
    return <p>{contentItemToText(item)}</p>;
    ```
*   **Logical Gap**: If `item.text` is present and contains inline LaTeX, it is returned plain. This bypasses LaTeX typesetting in the answer key print output.
*   **Fix**: Fallback to parsing mixed text-latex or utilize a renderer that splits inline equations similarly to the editor preview.

---

## Positive Notes
- **Clear Separation of Concerns**: The page layout is pure orchestration, delegating logic cleanly to `useCoverageForm` and rendering to isolated views.
- **Robust Schema Validation**: Hook values are mapped to schema contracts at runtime when fetches are initiated, preventing runtime errors in down-funnel page processes.
- **Form State Restorative UX**: The usage of `sessionStorage` provides a great user experience by keeping filters intact across accidental browser reloads.

---

## Suggested Tests

To prevent regression and guarantee robustness, the following test scenarios should be added:

1. **Storage Robustness Test**:
   - Mock `sessionStorage.setItem` to throw a `DOMException`. Verify the hook initializes, updates, and does not crash the page.
2. **Stale Format Validation Test**:
   - Seed `sessionStorage` with an invalid format ID (`"deleted_format_v99"`). Fetch mock formats (`["cbse_science_v1"]`). Verify the hook resolves `selectedFormatId` to `"cbse_science_v1"`.
3. **Source Deselection Warning Test**:
   - Assert that changing chapter selections triggers compatible source re-fetch, and verify that any previously chosen source that is no longer returned is kept in state but flagged rather than silently removed.
4. **Modal Accessibility Test**:
   - Render the `SelectionDialog`, trigger an Escape keypress, and assert that `onCancel` is called.
