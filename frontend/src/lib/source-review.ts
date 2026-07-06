export function sourceReviewHref(sourceKey: string): string | null {
  if (sourceKey.startsWith('ai_batch:')) {
    const batchId = sourceKey.slice('ai_batch:'.length);
    return batchId ? `/generation-batches/${batchId}` : null;
  }
  if (sourceKey.startsWith('upload:')) {
    const jobId = sourceKey.slice('upload:'.length);
    return jobId ? `/extractions/${jobId}` : null;
  }
  return null;
}
