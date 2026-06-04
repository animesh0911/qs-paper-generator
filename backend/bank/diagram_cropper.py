"""**DiagramCropper** — the Ingestor's second seam: figure boxes → cropped media assets.

The Extractor localises each diagram as a normalised bounding box on a page; this
seam turns those boxes into stored PNG assets and rewrites the question's
``image_placeholder`` into a real ``image`` item referencing the asset by storage
name (contract §9 — no inline URL). Splitting it out of the Ingestor coordinator
makes figure-weaving testable on its own: the default ``PyMuPdfCropper`` needs
``fitz`` and a real PDF, but tests inject a stub.

``crop(pdf_bytes, rows, fingerprints) -> list[str | None]`` returns each
question's primary (first) cropped asset name for the ``Question.diagram``
FileField, or ``None`` where nothing cropped. It mutates ``rows[i]["content"]``
in place via :func:`bank.content.place_item`. Symmetric to the Extractor seam
(CONTEXT.md ``Ingestor``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from . import content as content_mod


class DiagramCropper(Protocol):
    """Crops each question's figure boxes into assets and rewrites its content."""

    def crop(
        self, pdf_bytes: bytes, rows: list[dict], fingerprints: list[str]
    ) -> list[str | None]: ...


def _open_pdf(pdf_bytes: bytes):
    """Open PDF bytes as a PyMuPDF document, or ``None`` if unparseable.

    Opened once per batch so the stream is parsed a single time rather than once
    per figure. Returns ``None`` on failure so every figure soft-misses and the
    placeholders stay (ADR-0004).
    """
    import fitz

    try:
        return fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:  # noqa: BLE001 — any parse failure is a soft miss
        return None


def _crop_figure(
    doc,
    page_1based: int,
    bbox_norm: list[float],
    *,
    dpi: int = 300,
    pad: float = 0.01,
) -> bytes | None:
    """Crop one figure box from an open PDF ``doc`` to PNG bytes via PyMuPDF.

    ``bbox_norm`` is ``[x0, y0, x1, y1]`` normalized to ``[0, 1]`` with the page
    top-left as origin (the extractor's convention). The box is padded slightly
    to avoid clipping diagram borders, mapped to page points, and rendered at
    ``dpi``. Returns ``None`` on any failure (out-of-range page, empty clip,
    render error) so the caller keeps the question's ``image_placeholder`` — bad
    crops are caught at human review, not by code (ADR-0004).
    """
    import fitz

    try:
        idx = page_1based - 1
        if idx < 0 or idx >= doc.page_count:
            return None
        page = doc[idx]
        rect = page.rect
        x0, y0, x1, y1 = bbox_norm
        x0 = max(0.0, x0 - pad)
        y0 = max(0.0, y0 - pad)
        x1 = min(1.0, x1 + pad)
        y1 = min(1.0, y1 + pad)
        clip = fitz.Rect(
            x0 * rect.width,
            y0 * rect.height,
            x1 * rect.width,
            y1 * rect.height,
        )
        if clip.is_empty or clip.is_infinite:
            return None
        zoom = dpi / 72
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)
        return pix.tobytes("png")
    except Exception:  # noqa: BLE001 — a render failure degrades to placeholder
        return None


class PyMuPdfCropper:
    """Default DiagramCropper — crops with PyMuPDF, saves to ``default_storage``."""

    def crop(
        self, pdf_bytes: bytes, rows: list[dict], fingerprints: list[str]
    ) -> list[str | None]:
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        # Parse the PDF once for the whole batch, not once per figure.
        doc = _open_pdf(pdf_bytes)
        try:
            primary_assets: list[str | None] = []
            for q, fp in zip(rows, fingerprints):
                figures = q.get("figures", []) if doc is not None else []
                content = q.get("content") or {}
                primary: str | None = None
                crop_index = 0
                for figure in figures:
                    png = _crop_figure(doc, figure["page"], figure["bbox"])
                    if png is None:
                        continue
                    asset_id = default_storage.save(
                        f"diagrams/{fp[:8]}-{crop_index}.png", ContentFile(png)
                    )
                    crop_index += 1
                    image_item = {"type": "image", "assetId": asset_id}
                    if figure.get("caption"):
                        image_item["caption"] = figure["caption"]
                    content_mod.place_item(
                        content, figure["region"], image_item, label=figure.get("label")
                    )
                    if primary is None:
                        primary = asset_id
                q["content"] = content
                primary_assets.append(primary)
            return primary_assets
        finally:
            if doc is not None:
                doc.close()


def crop_to_dir(
    pdf_bytes: bytes,
    rows: list[dict],
    fingerprints: list[str],
    assets_dir: Path,
) -> None:
    """Crop figures to PNG files under ``assets_dir`` and rewrite content in place.

    The offline counterpart to ``PyMuPdfCropper`` (which saves to
    ``default_storage``): used by ``extract_paper`` so cropped diagrams are
    committed next to the JSON in ``content/parsed/``. Each crop is written to
    ``assets_dir/<fp8>-<n>.png`` (deterministic, so re-runs reproduce the same
    files) and the question's first ``image_placeholder`` in the figure's region
    is upgraded to ``{type: image, assetId: "diagrams/<fp8>-<n>.png"}``. The
    ``diagrams/`` prefix is the storage name ``load_questions`` re-hydrates into
    ``default_storage`` so the renderer can serve it. A figure that fails to crop
    soft-misses and its placeholder stays (ADR-0004)."""
    doc = _open_pdf(pdf_bytes)
    if doc is None:
        return
    try:
        assets_dir.mkdir(parents=True, exist_ok=True)
        for q, fp in zip(rows, fingerprints):
            content = q.get("content") or {}
            crop_index = 0
            for figure in q.get("figures", []):
                png = _crop_figure(doc, figure["page"], figure["bbox"])
                if png is None:
                    continue
                name = f"{fp[:8]}-{crop_index}.png"
                (assets_dir / name).write_bytes(png)
                crop_index += 1
                image_item = {"type": "image", "assetId": f"diagrams/{name}"}
                if figure.get("caption"):
                    image_item["caption"] = figure["caption"]
                content_mod.place_item(
                    content, figure["region"], image_item, label=figure.get("label")
                )
            q["content"] = content
    finally:
        doc.close()
