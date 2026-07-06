"""PDF page slicing helpers for the Extractor pipeline."""

from __future__ import annotations


def split_pages(pdf_bytes: bytes) -> list[bytes]:
    """Split a PDF into one single-page PDF per page (in document order).

    Each slice is fed to the model alone so it reads one page deeply rather than
    skimming a long scanned paper. Returns ``[pdf_bytes]`` unchanged if the PDF
    cannot be opened — the caller then does a single whole-document call.
    """
    import fitz

    try:
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:  # noqa: BLE001 — unparseable PDF: fall back to one call
        return [pdf_bytes]
    try:
        pages: list[bytes] = []
        for i in range(src.page_count):
            one = fitz.open()
            try:
                one.insert_pdf(src, from_page=i, to_page=i)
                pages.append(one.tobytes())
            finally:
                one.close()
        return pages or [pdf_bytes]
    finally:
        src.close()


def count_pages(pdf_bytes: bytes) -> int:
    """Page count with ``split_pages``'s fallback semantics: never less than 1.

    An unparseable or empty PDF counts as one page — the whole-document slice
    ``slice_page`` falls back to — so a caller iterating ``range(count_pages())``
    over ``slice_page`` visits exactly the slices ``split_pages`` would return.
    """
    import fitz

    try:
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:  # noqa: BLE001 — unparseable PDF: one whole-document call
        return 1
    try:
        return src.page_count or 1
    finally:
        src.close()


def slice_page(pdf_bytes: bytes, index: int) -> bytes:
    """One single-page PDF slice, copying only that page (O(1) per call).

    The per-step counterpart to ``split_pages`` for the extraction workflow
    (#157), whose ``extract_page`` node re-reads the PDF each super-step:
    slicing just the wanted page keeps a paper's total split work O(pages)
    instead of O(pages²). Same fallback as ``split_pages``: an unparseable or
    empty PDF yields the whole document (its only slice, index 0).
    """
    import fitz

    try:
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:  # noqa: BLE001 — unparseable PDF: the whole-document slice
        return pdf_bytes
    try:
        if src.page_count == 0:
            return pdf_bytes
        one = fitz.open()
        try:
            one.insert_pdf(src, from_page=index, to_page=index)
            return one.tobytes()
        finally:
            one.close()
    finally:
        src.close()


def split_pages_for_runtime(pdf_bytes: bytes) -> list[bytes]:
    """Return page slices, honoring the legacy ``bank.ingestor.split_pages`` hook."""
    import sys

    ingestor_module = sys.modules.get("bank.ingestor")
    splitter = getattr(ingestor_module, "split_pages", split_pages)
    return splitter(pdf_bytes)
