"""Resolve asset references in an editor document to backend-issued URLs.

Contract documents carry images as ``{type: image, assetId: "diagrams/..."}``
with no inline URL (contract §9) — ``assetId`` is the canonical storage name.
The editor (BlockNote) needs a loadable URL, and the frontend must not derive
storage paths from ``assetId`` itself (grill decision on #122). So the
editor-draft endpoint enriches its document copy: every content item that
references an ``assetId`` gains a sibling ``url``.

The ``url`` is backend-issued and **non-canonical** — resolved through
``url_for`` (the caller passes ``default_storage.url`` wrapped to an absolute
URI), so it can become a signed S3/CDN URL later without changing the document
model or the canonical ``assetId``. This transform is response-only; the stored
document keeps the lean ``assetId``-only shape.

Where it fits:
- Called by: papers.views.PaperEditorDraftView
- Calls into: a caller-supplied ``url_for(asset_id) -> str``
"""

from __future__ import annotations

from collections.abc import Callable


def with_resolved_asset_urls(node, url_for: Callable[[str], str]):
    """Return a deep copy of ``node`` with a ``url`` added beside every ``assetId``.

    Walks the whole document so an asset reference nested anywhere (a question
    stem, an MCQ option, a case-study subpart, an answer entry) is resolved.
    ``assetId`` is preserved untouched; only a non-empty string ``assetId``
    triggers a ``url``. Non-container input (``None``, scalars) is returned as-is,
    so callers can hand it ``paper.document`` whether or not one exists.
    """
    if isinstance(node, dict):
        resolved = {
            key: with_resolved_asset_urls(value, url_for) for key, value in node.items()
        }
        asset_id = node.get("assetId")
        if isinstance(asset_id, str) and asset_id:
            resolved["url"] = url_for(asset_id)
        return resolved
    if isinstance(node, list):
        return [with_resolved_asset_urls(item, url_for) for item in node]
    return node
