"""Paper layout dataclasses.

PaperLayout is the seam between the Paper model and the PDF renderer.
paper_to_layout() reads from the database; render_paper_pdf() renders from
layout — no model imports needed in the renderer, and tests can construct
PaperLayout directly without a database.
"""
from dataclasses import dataclass, field


@dataclass
class QuestionLayout:
    number: int
    text: str
    marks: int
    options: list[dict]
    or_group: int | None = None


@dataclass
class SectionLayout:
    code: str
    title: str
    questions: list[QuestionLayout] = field(default_factory=list)


@dataclass
class PaperLayout:
    title: str
    total_marks: int
    sections: list[SectionLayout] = field(default_factory=list)


def paper_to_layout(paper) -> PaperLayout:
    """Convert a Paper model instance to a flat PaperLayout."""
    from bank.models import Section

    section_labels = dict(Section.choices)
    sections_map: dict[str, SectionLayout] = {}
    for item in paper.items.select_related("question").order_by("order"):
        q = item.question
        if item.section not in sections_map:
            sections_map[item.section] = SectionLayout(
                code=item.section,
                title=section_labels.get(item.section, f"Section {item.section}"),
            )
        sections_map[item.section].questions.append(
            QuestionLayout(
                number=item.order,
                text=q.text,
                marks=q.marks,
                options=q.options or [],
                or_group=item.or_group,
            )
        )
    return PaperLayout(
        title=paper.title,
        total_marks=paper.total_marks,
        sections=list(sections_map.values()),
    )
