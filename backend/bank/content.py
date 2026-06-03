"""The structured **Content** shape (PaperDocumentV1 §9) and the one tree-walk over it.

Content is a region-keyed dict. ``ITEM_REGIONS`` (stem / assertion / reason /
passage) hold ``ContentItem[]`` directly; ``LABELLED_REGIONS`` (options /
subparts) hold ``{label, content: ContentItem[]}`` entries; ``choices`` holds
choice-groups whose options each carry their own ``content[]``. A ``ContentItem``
is a dict with a ``type`` (``paragraph`` / ``equation`` / ``image`` /
``image_placeholder`` / ``table`` …).

Before this module, every layer that read or rewrote Content re-walked the tree
by hand: the Ingestor's figure-weaving, ``PaperDocumentBuilder``'s
``requiresTable`` scan, and the PDF renderer's text flattener each had their own
recursion. Those collapse into the helpers here so the walk lives in one place.

Where it fits:
- ``bank.diagram_cropper`` calls ``place_item`` to weave a crop into its region.
- ``bank.ingestor`` calls ``has_item`` to flag ``has_diagram``.
- ``papers.document`` calls ``has_item`` for ``metadata.requiresTable``.
- ``papers.pdf`` calls ``flatten_text`` to render a region as plain text.
"""

from __future__ import annotations

from collections.abc import Iterator

# Item-array regions hold ContentItem[] directly. Labelled regions hold
# {label, content:[...]} entries selected by label. (`choices` nests one level
# deeper — group → options → content — but figure placement never targets it.)
ITEM_REGIONS: tuple[str, ...] = ("stem", "assertion", "reason", "passage")
LABELLED_REGIONS: tuple[str, ...] = ("options", "subparts")


def walk(content) -> Iterator[dict]:
    """Yield every ``ContentItem`` (a dict with a ``type``) reachable in ``content``.

    Depth-first across every region and every nested ``content`` list (labelled
    entries, choice-group options), so a caller sees image/table/paragraph items
    at any depth — including inside ``choices``, which the hand-written scanners
    this replaces did not reach.
    """
    if isinstance(content, dict):
        if "type" in content:
            yield content
        for value in content.values():
            yield from walk(value)
    elif isinstance(content, list):
        for item in content:
            yield from walk(item)


def has_item(content, *types: str) -> bool:
    """True if any ContentItem anywhere in ``content`` has one of ``types``."""
    return any(item.get("type") in types for item in walk(content))


def flatten_text(items) -> str:
    """Join a flat ``ContentItem[]`` region's ``text`` fields into one string.

    Shallow by design: callers pass a single region's item list (e.g. a stem or
    an option's content), not the whole tree.
    """
    if not isinstance(items, list):
        return ""
    return " ".join(
        str(it.get("text", "")) for it in items if isinstance(it, dict)
    ).strip()


def place_item(
    content: dict, region: str, item: dict, *, label: str | None = None
) -> None:
    """Insert ``item`` into ``region``, upgrading the first image_placeholder there.

    For an ``ITEM_REGIONS`` region the item goes straight into the region's list.
    For a ``LABELLED_REGIONS`` region the entry whose ``label`` matches ``label``
    (case/space-insensitively — the model's verbatim labels can drift in casing)
    receives the item; if no entry matches it is a no-op, so a mis-localised
    figure soft-misses and its placeholder stays (ADR-0004).
    """
    if region in ITEM_REGIONS:
        items = content.get(region)
        if not isinstance(items, list):
            items = []
            content[region] = items
        _upgrade_or_append(items, item)
        return

    entries = content.get(region)
    if not isinstance(entries, list):
        return
    target = (label or "").strip().casefold()
    for entry in entries:
        if (
            isinstance(entry, dict)
            and (entry.get("label") or "").strip().casefold() == target
        ):
            items = entry.get("content")
            if not isinstance(items, list):
                items = []
                entry["content"] = items
            _upgrade_or_append(items, item)
            return


def _upgrade_or_append(items: list, item: dict) -> None:
    """Swap the first ``image_placeholder`` in ``items`` for ``item``; else append."""
    for i, it in enumerate(items):
        if isinstance(it, dict) and it.get("type") == "image_placeholder":
            items[i] = item
            return
    items.append(item)
