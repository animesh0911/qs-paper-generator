"""PDF rendering for a paper.

Consumes `PaperDocumentV1` (the same dict shape the frontend reads) and
emits PDF bytes. No model imports — tests construct a document dict directly.

The full CBSE-style/branded renderer arrives in Slice 9.
"""

import io
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


def render_paper_pdf(document: dict) -> bytes:
    """Render a PaperDocumentV1 dict as PDF bytes."""
    paper = document["paper"]
    title = paper["title"]
    total_marks = paper["totalMarks"]
    questions_by_id = {q["questionId"]: q for q in document.get("questions", [])}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=16)
    meta_style = ParagraphStyle(
        "meta", parent=styles["Normal"], alignment=TA_CENTER, fontSize=10
    )
    section_style = ParagraphStyle(
        "section", parent=styles["Heading2"], spaceBefore=12, fontSize=12
    )
    q_style = ParagraphStyle(
        "q", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=4
    )

    story = [
        Paragraph(escape(title), title_style),
        Paragraph(escape(_paper_subtitle(document)), meta_style),
        Paragraph(f"Maximum Marks: {total_marks}", meta_style),
        Spacer(1, 8),
    ]
    story.extend(_paper_chrome_flowables(paper, q_style))

    for section in paper.get("sections", []):
        story.append(Paragraph(escape(section["title"]), section_style))
        if section.get("subtitle"):
            story.append(Paragraph(escape(section["subtitle"]), meta_style))
        if section.get("instructions"):
            story.append(Paragraph(escape(section["instructions"]), q_style))
        for slot in section.get("slots", []):
            qid = slot.get("selectedQuestionId")
            question = questions_by_id.get(qid) if qid else None
            marks = slot["marks"]
            number = slot["displayNumber"]
            if question is None:
                mark_label = f"{marks} mark{'s' if marks != 1 else ''}"
                story.append(
                    Paragraph(
                        f"<b>Q{number}.</b> <i>(unfilled, {mark_label})</i>",
                        q_style,
                    )
                )
                story.append(Spacer(1, 4))
                continue
            question_paragraphs = _slot_question_paragraphs(slot, question)
            first_paragraph = question_paragraphs[0] if question_paragraphs else ""
            story.append(
                Paragraph(
                    f"<b>Q{number}.</b> {escape(first_paragraph)} "
                    f"<i>({marks} mark{'s' if marks != 1 else ''})</i>",
                    q_style,
                )
            )
            for paragraph in question_paragraphs[1:]:
                story.append(Paragraph(escape(paragraph), q_style))
            options = _slot_region(slot, question, "options")
            if options:
                opts = [
                    ListItem(
                        Paragraph(
                            f"({escape(str(opt['label']))}) "
                            f"{escape(_content_items_text(opt.get('content', [])))}",
                            q_style,
                        )
                    )
                    for opt in options
                ]
                story.append(
                    ListFlowable(
                        opts, bulletType="bullet", start="circle", leftIndent=18
                    )
                )
            story.append(Spacer(1, 4))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def _paper_subtitle(document: dict) -> str:
    template = document.get("template", {})
    paper = document.get("paper", {})
    class_level = template.get("classLevel", "10")
    subject = template.get("subject", "Science")
    return paper.get("subtitle") or f"Class {class_level} - {subject}"


def _paper_chrome_flowables(paper: dict, style: ParagraphStyle) -> list:
    flowables = []
    for block in paper.get("headerBlocks", []):
        flowables.append(Paragraph(escape(block.get("text", "")), style))
    for block in paper.get("instructionBlocks", []):
        flowables.append(Paragraph(escape(block.get("text", "")), style))
    if flowables:
        flowables.append(Spacer(1, 8))
    return flowables


def _slot_question_paragraphs(slot: dict, question: dict) -> list[str]:
    content = question.get("content", {})
    paragraphs: list[str] = []
    for region_key in ["stem", "assertion", "reason", "passage"]:
        text = _content_items_text(_slot_region(slot, question, region_key))
        if text:
            paragraphs.append(text)
    for subpart in content.get("subparts", []) or []:
        text = _content_items_text(subpart.get("content", []))
        if text:
            paragraphs.append(f"({subpart.get('label')}) {text}")
    for choice_group in content.get("choices", []) or []:
        choice_texts = [
            _content_items_text(option.get("content", []))
            for option in choice_group.get("options", [])
        ]
        choice_texts = [text for text in choice_texts if text]
        if choice_texts:
            paragraphs.append(" OR ".join(choice_texts))
    if not paragraphs and question.get("rawText"):
        paragraphs.append(question["rawText"])
    return paragraphs


def _slot_region(slot: dict, question: dict, region_key: str):
    overrides = slot.get("overrides") or {}
    regions = overrides.get("regions") or {}
    if region_key in regions:
        return regions[region_key]
    return question.get("content", {}).get(region_key) or []


def _content_items_text(items: list[dict]) -> str:
    parts: list[str] = []
    for item in items:
        if item.get("text"):
            parts.append(str(item["text"]))
        elif item.get("latex"):
            parts.append(str(item["latex"]))
        elif item.get("rows"):
            parts.extend(" | ".join(row) for row in item["rows"])
        elif item.get("caption"):
            parts.append(str(item["caption"]))
    return " ".join(parts).strip()
