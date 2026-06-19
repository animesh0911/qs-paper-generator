# Topic Subtree Context for Generation

Status: accepted

When a teacher generates questions and answers from a selected NCERT topic, the generation prompt uses the selected **ChapterMapNode** plus its descendant **RetrievalChunks** in textbook source order. The canonical JSON remains the reproducible import artifact, but RetrievalChunks are the runtime textbook context because they carry topic ownership, source order, page citations, content types, and bounded text.

This path does not require embeddings: the current `jesc104` topic subtrees are small enough to include fully, and deterministic subtree context is easier to audit than semantic search. Embeddings remain useful for later free-text discovery, such as mapping "carbon chains" to a topic or finding relevant chunks when the user has not selected a canonical ChapterMapNode.

Prompt assembly should treat picture-only chunks without captions as weak context, because they usually contain only the heading text. Captions, activities, formulas, tables, and textbook prose can be included. Existing NCERT question/exercise chunks are excluded by default so the model grounds on textbook facts without copying textbook questions; CBSE style should come from the separate previous-year **Question** bank when needed.

The first generation slice creates question-and-answer candidates together in one model call for the selected topic. This keeps the answer grounded in the same NCERT context as the question and avoids a second paid call; answer generation can be split into a later pass only if quality or validation requires it.
