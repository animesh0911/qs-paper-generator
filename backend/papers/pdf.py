"""Basic PDF rendering for a paper (Slice 1).

Uses ReportLab (pure-Python, no system deps). The full CBSE-style/branded
renderer arrives in Slice 9.
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

from bank.models import Section

SECTION_LABELS = dict(Section.choices)


def render_paper_pdf(paper):
    """Return the paper rendered as PDF bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
        title=paper.title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=16)
    meta_style = ParagraphStyle("meta", parent=styles["Normal"],
                                alignment=TA_CENTER, fontSize=10)
    section_style = ParagraphStyle("section", parent=styles["Heading2"],
                                   spaceBefore=12, fontSize=12)
    q_style = ParagraphStyle("q", parent=styles["Normal"], fontSize=10,
                             leading=14, spaceAfter=4)

    story = [
        Paragraph(paper.title, title_style),
        Paragraph("Class 10 — Science", meta_style),
        Paragraph(f"Maximum Marks: {paper.total_marks}", meta_style),
        Spacer(1, 8),
    ]

    items = list(paper.items.select_related("question").all())
    current_section = None
    for item in items:
        q = item.question
        if item.section != current_section:
            current_section = item.section
            story.append(Paragraph(SECTION_LABELS.get(current_section,
                                                       f"Section {current_section}"),
                                   section_style))
        story.append(Paragraph(
            f"<b>Q{item.order}.</b> {q.text} <i>({q.marks} mark"
            f"{'s' if q.marks != 1 else ''})</i>",
            q_style,
        ))
        if q.options:
            opts = [
                ListItem(Paragraph(f"({o.get('label')}) {o.get('text')}", q_style))
                for o in q.options
            ]
            story.append(ListFlowable(opts, bulletType="bullet",
                                      start="circle", leftIndent=18))
        story.append(Spacer(1, 4))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
