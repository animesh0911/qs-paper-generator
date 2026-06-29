import type { PaperAnswerDocument, PaperDocument } from '@/types';

export async function saveThenDownloadPdfPackage({
  documentSnapshot,
  answerDocument,
  dirty,
  persist,
  download,
  onSaved,
}: {
  documentSnapshot: PaperDocument;
  answerDocument: PaperAnswerDocument | undefined;
  dirty: boolean;
  persist: (
    paper: PaperDocument,
    answerDocument: PaperAnswerDocument,
  ) => Promise<void>;
  download: (paper: PaperDocument) => Promise<void>;
  onSaved?: (answerDocument: PaperAnswerDocument) => void;
}): Promise<PaperAnswerDocument> {
  if (!answerDocument) {
    throw new Error('Answer document is still loading.');
  }
  const reconciledAnswerDocument = reconcileAnswerDocumentForPaper(
    documentSnapshot,
    answerDocument,
  );
  if (dirty) {
    await persist(documentSnapshot, reconciledAnswerDocument);
    onSaved?.(reconciledAnswerDocument);
  }
  await download(documentSnapshot);
  return reconciledAnswerDocument;
}

export function reconcileAnswerDocumentForPaper(
  paper: PaperDocument,
  answerDocument: PaperAnswerDocument,
): PaperAnswerDocument {
  const answersBySlotId: PaperAnswerDocument['answersBySlotId'] = {};
  for (const section of paper.paper.sections) {
    for (const slot of section.slots) {
      const questionId = slot.selectedQuestionId;
      if (!questionId) continue;
      const existing = answerDocument.answersBySlotId[slot.id];
      if (existing?.questionId === questionId) {
        answersBySlotId[slot.id] = existing;
      }
    }
  }
  return {
    ...answerDocument,
    paperId: paper.paper.id,
    answersBySlotId,
  };
}
