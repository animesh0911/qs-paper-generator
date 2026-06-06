"""PDF rendering for a paper.

Consumes `PaperDocumentV1` (the same dict shape the frontend reads) and
emits PDF bytes. No model imports — tests construct a document dict directly.

The primary path prints the React print route through Chromium so the
downloaded PDF follows the same renderer as the editor. The ReportLab path is
kept as a fallback for tests and environments without Playwright installed.

``render_answer_key_pdf`` produces the separate marking-scheme PDF. It is
always ReportLab-rendered (an internal document, not the editor surface) and
joins the canonical document's slot order with the answers passed in.

School branding (``paper.branding``: schoolName/examHeader/logoUrl) is emitted
into the contract by ``papers.document`` and rendered as a header here. The
logo *image* is drawn by the frontend print renderer from ``logoUrl``; the
ReportLab paths render the school name and exam header text only.
"""

import io
import logging

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

from bank.content import flatten_text

logger = logging.getLogger(__name__)


def render_paper_pdf(document: dict, print_url: str | None = None) -> bytes:
    """Render a PaperDocumentV1 dict as PDF bytes."""
    if print_url:
        try:
            return _render_browser_pdf(print_url)
        except Exception:
            logger.warning("Browser PDF renderer failed; falling back.", exc_info=True)
            return _render_reportlab_pdf(document)
    return _render_reportlab_pdf(document)


def _render_browser_pdf(print_url: str) -> bytes:
    """Print the React paper route with Chromium."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(print_url, wait_until="networkidle")
        page.wait_for_selector("[data-print-ready='true']")
        page.emulate_media(media="print")
        pdf = page.pdf(format="A4", print_background=True)
        browser.close()
        return pdf


def _render_reportlab_pdf(document: dict) -> bytes:
    """Fallback PDF renderer for non-browser environments."""
    paper = document["paper"]
    title = paper["title"]
    total_marks = paper["totalMarks"]
    questions_by_id = {_question_id(q): q for q in document.get("questions", [])}

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

    story = _branding_flowables(paper.get("branding"), styles)
    story += [
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
            number = _slot_number(slot)
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
            # Slot overrides are the teacher's post-assembly edits; the contract
            # makes them canonical, so they win over the stored question content
            # region-by-region (v1_contract.md §7/§9).
            overrides = slot.get("overrides") or {}
            regions = overrides.get("regions") or {}
            content = overrides.get("content") or question.get("content", {})
            stem_text = flatten_text(
                regions.get("stem")
                or content.get("stem")
                or [{"text": question["rawText"]}]
            )
            story.append(
                Paragraph(
                    f"<b>Q{number}.</b> {stem_text} "
                    f"<i>({marks} mark{'s' if marks != 1 else ''})</i>",
                    q_style,
                )
            )
            options = (
                regions.get("options")
                or content.get("options")
                or []
            )
            if options:
                opts = [
                    ListItem(
                        Paragraph(
                            f"({opt['label']}) {_option_text(opt, regions)}",
                            q_style,
                        )
                    )
                    for opt in options
                ]
                story.append(
                    ListFlowable(
                        opts,
                        bulletType="bullet",
                        start="circle",
                        leftIndent=18,
                    )
                )
            story.append(Spacer(1, 4))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def render_answer_key_pdf(document: dict, answers_by_id: dict[str, str]) -> bytes:
    """Render the marking-scheme PDF for a paper.

    ``answers_by_id`` maps the contract question id (``"q_{pk}"``) to its answer
    text — supplied by the view from the answer-revealing serializer, never from
    the document (the document deliberately omits answers). Walks the canonical
    slot order so the key numbering matches the question paper exactly.
    """
    paper = document["paper"]
    title = paper["title"]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"Answer Key — {title}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ak_title", parent=styles["Title"], fontSize=15)
    meta_style = ParagraphStyle(
        "ak_meta", parent=styles["Normal"], alignment=TA_CENTER, fontSize=10
    )
    section_style = ParagraphStyle(
        "ak_section", parent=styles["Heading2"], spaceBefore=12, fontSize=12
    )
    a_style = ParagraphStyle(
        "ak_answer", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=6
    )

    story = _branding_flowables(paper.get("branding"), styles)
    story += [
        Paragraph("Answer Key &amp; Marking Scheme", title_style),
        Paragraph(title, meta_style),
        Spacer(1, 8),
    ]

    for section in paper.get("sections", []):
        story.append(Paragraph(section["title"], section_style))
        for slot in section.get("slots", []):
            number = _slot_number(slot)
            marks = slot["marks"]
            mark_label = f"{marks} mark{'s' if marks != 1 else ''}"
            qid = slot.get("selectedQuestionId")
            answer = answers_by_id.get(qid) if qid else None
            if qid is None:
                body = "<i>(unfilled)</i>"
            elif answer:
                body = answer
            else:
                # Filled slot whose source carries no stored answer: surface the
                # gap instead of silently printing a blank marking entry.
                body = "<i>(no answer on file)</i>"
            story.append(Paragraph(f"<b>Q{number}.</b> ({mark_label}) {body}", a_style))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def _branding_flowables(branding: dict | None, styles) -> list:
    """School-identity header flowables (name + exam header) for ReportLab.

    Empty list when no branding — the document omits ``branding`` entirely
    rather than shipping an empty object, so this stays a clean no-op. The logo
    image is the frontend renderer's job; only text is drawn here.
    """
    if not branding:
        return []
    name_style = ParagraphStyle(
        "brand_name", parent=styles["Title"], alignment=TA_CENTER, fontSize=14
    )
    header_style = ParagraphStyle(
        "brand_header", parent=styles["Normal"], alignment=TA_CENTER, fontSize=10
    )
    flowables = []
    if branding.get("schoolName"):
        flowables.append(Paragraph(branding["schoolName"], name_style))
    if branding.get("examHeader"):
        flowables.append(Paragraph(branding["examHeader"], header_style))
    if flowables:
        flowables.append(Spacer(1, 8))
    return flowables


def _question_id(question: dict) -> str:
    """Return the question id across current and legacy document keys."""
    return question.get("id") or question["questionId"]


def _slot_number(slot: dict) -> str:
    """Return the slot display number across current and legacy document keys."""
    return slot.get("number") or slot["displayNumber"]


def _option_text(option: dict, overrides: dict) -> str:
    """Return option text, preferring Slot overrides."""
    return flatten_text(overrides.get(f"option:{option['label']}") or option["content"])
