"""PDF rendering for a paper (Slice 1).

Accepts a PaperLayout (pure data) — no model imports. Tests can construct a
PaperLayout directly without a database. The full CBSE-style/branded renderer
arrives in Slice 9; branding slots in at the paper_to_layout() stage without
touching this renderer.
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

from .layout import PaperLayout


def render_paper_pdf(layout: PaperLayout) -> bytes:
    """Return the layout rendered as PDF bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=layout.title,
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
        Paragraph(layout.title, title_style),
        Paragraph("Class 10 — Science", meta_style),
        Paragraph(f"Maximum Marks: {layout.total_marks}", meta_style),
        Spacer(1, 8),
    ]

    for section in layout.sections:
        story.append(Paragraph(section.title, section_style))
        for q in section.questions:
            story.append(
                Paragraph(
                    f"<b>Q{q.number}.</b> {q.text} "
                    f"<i>({q.marks} mark{'s' if q.marks != 1 else ''})</i>",
                    q_style,
                )
            )
            if q.options:
                opts = [
                    ListItem(
                        Paragraph(
                            f"({o.get('label')}) {o.get('text')}", q_style
                        )
                    )
                    for o in q.options
                ]
                story.append(
                    ListFlowable(opts, bulletType="bullet", start="circle", leftIndent=18)
                )
            story.append(Spacer(1, 4))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
