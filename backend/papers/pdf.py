"""PDF rendering for a paper.

Consumes `PaperDocumentV1` (the same dict shape the frontend reads) and
emits PDF bytes. No model imports — tests construct a document dict directly.

The full CBSE-style/branded renderer arrives in Slice 9.
"""

import io

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
        Paragraph(title, title_style),
        Paragraph("Class 10 — Science", meta_style),
        Paragraph(f"Maximum Marks: {total_marks}", meta_style),
        Spacer(1, 8),
    ]

    for section in paper.get("sections", []):
        story.append(Paragraph(section["title"], section_style))
        for slot in section.get("slots", []):
            qid = slot.get("selectedQuestionId")
            question = questions_by_id.get(qid) if qid else None
            marks = slot["marks"]
            number = slot["displayNumber"]
            if question is None:
                story.append(
                    Paragraph(
                        f"<b>Q{number}.</b> "
                        f"<i>(unfilled, {marks} mark{'s' if marks != 1 else ''})</i>",
                        q_style,
                    )
                )
                story.append(Spacer(1, 4))
                continue
            story.append(
                Paragraph(
                    f"<b>Q{number}.</b> {question['rawText']} "
                    f"<i>({marks} mark{'s' if marks != 1 else ''})</i>",
                    q_style,
                )
            )
            options = question.get("content", {}).get("options") or []
            if options:
                opts = [
                    ListItem(
                        Paragraph(
                            f"({opt['label']}) {opt['content'][0]['text']}", q_style
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
