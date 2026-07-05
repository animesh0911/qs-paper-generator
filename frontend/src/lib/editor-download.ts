import type { PaperAnswerDocument, PaperDocument } from '@/types';

export async function saveThenDownloadPdfPackage({
  documentSnapshot,
  answerDocument,
  dirty,
  persist,
  download,
  preview,
  reservePreview,
  onSaved,
}: {
  documentSnapshot: PaperDocument;
  answerDocument: PaperAnswerDocument | undefined;
  dirty: boolean;
  persist: (
    paper: PaperDocument,
    answerDocument: PaperAnswerDocument,
  ) => Promise<PaperAnswerDocument>;
  download: (paper: PaperDocument) => Promise<void>;
  preview?: (paper: PaperDocument) => void;
  reservePreview?: () => {
    show: (paper: PaperDocument) => void;
    close: () => void;
  };
  onSaved?: (answerDocument: PaperAnswerDocument) => void;
}): Promise<PaperAnswerDocument> {
  if (!answerDocument) {
    throw new Error('Answer document is still loading.');
  }
  const reconciledAnswerDocument = reconcileAnswerDocumentForPaper(
    documentSnapshot,
    answerDocument,
  );
  const reservedPreview = reservePreview?.();
  let savedAnswerDocument = reconciledAnswerDocument;
  if (dirty) {
    try {
      savedAnswerDocument = await persist(
        documentSnapshot,
        reconciledAnswerDocument,
      );
    } catch (error) {
      reservedPreview?.close();
      throw error;
    }
    onSaved?.(savedAnswerDocument);
  }
  if (reservedPreview) {
    reservedPreview.show(documentSnapshot);
  } else {
    preview?.(documentSnapshot);
  }
  await download(documentSnapshot);
  return savedAnswerDocument;
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
