/**
 * Renders an assembled `PaperDocument` (PaperDocumentV1 format).
 *
 * Wraps the shared `PaperDocumentView` in dashboard card chrome. The
 * forwarded ref is used by the dashboard to scroll into view after assembly.
 *
 * @module PaperPreview
 */
import { forwardRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PaperDocumentView } from '@/components/coverage/paper-document-view';
import type { PaperDocument } from '@/types';

export interface PaperPreviewProps {
  paper: PaperDocument;
}

export const PaperPreview = forwardRef<HTMLDivElement, PaperPreviewProps>(
  function PaperPreview({ paper: doc }, ref) {
    return (
      <Card ref={ref}>
        <CardHeader>
          <CardTitle>{doc.paper.title}</CardTitle>
          <p className="text-sm text-muted-foreground">
            Class 10 — Science · Maximum Marks: {doc.paper.totalMarks}
          </p>
        </CardHeader>
        <CardContent>
          <PaperDocumentView paper={doc} includeHeader={false} />
        </CardContent>
      </Card>
    );
  },
);
