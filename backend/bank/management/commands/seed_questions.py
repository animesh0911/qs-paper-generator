"""Demo seed for local dev — a school, a teacher, and ~11 hand-entered questions.

Run as ``python manage.py seed_questions``. Idempotent: re-runs backfill
chapter and cognitive-level tags on existing rows without duplicating
questions.

Used by:
- ``backend/entrypoint.sh`` (auto-runs on container start).
- Manual ``docker exec ... python manage.py seed_questions`` during dev.

Not used by tests — tests build questions via ``conftest.QuestionFactory``.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import School
from bank.models import Chapter, CognitiveLevel, Question, QuestionType, Section

User = get_user_model()

# A small, hand-entered set of real-style CBSE Class 10 Science questions.
# Slice 1 only needs "a handful" to prove the end-to-end path.
R, U, AP, AN = (
    CognitiveLevel.REMEMBER,
    CognitiveLevel.UNDERSTAND,
    CognitiveLevel.APPLY,
    CognitiveLevel.ANALYSE,
)

# (section, qtype, marks, chapter_slug, cognitive_level, text, options, answer)
QUESTIONS = [
    # Section A — MCQ (1 mark)
    {
        "section": Section.A,
        "qtype": QuestionType.MCQ,
        "marks": 1,
        "chapter_slug": "chemical-reactions-and-equations",
        "level": U,
        "text": "Electrolysis of water is a decomposition reaction. The mass ratio "
        "(M_H : M_O) of hydrogen and oxygen gases liberated at the electrodes is:",
        "options": [
            {"label": "A", "text": "8 : 1"},
            {"label": "B", "text": "2 : 1"},
            {"label": "C", "text": "1 : 2"},
            {"label": "D", "text": "1 : 8"},
        ],
        "answer": "D) 1 : 8",
    },
    {
        "section": Section.A,
        "qtype": QuestionType.MCQ,
        "marks": 1,
        "chapter_slug": "metals-and-non-metals",
        "level": R,
        "text": "The products formed when Aluminium and Magnesium are burnt in the "
        "presence of air respectively are:",
        "options": [
            {"label": "A", "text": "Al3O4 and MgO2"},
            {"label": "B", "text": "Al2O3 and MgO"},
            {"label": "C", "text": "Al3O4 and MgO"},
            {"label": "D", "text": "Al2O3 and MgO2"},
        ],
        "answer": "B) Al2O3 and MgO",
    },
    {
        "section": Section.A,
        "qtype": QuestionType.MCQ,
        "marks": 1,
        "chapter_slug": "control-and-coordination",
        "level": R,
        "text": "Which of the following is a plant hormone that promotes cell "
        "elongation in the part of the shoot away from light?",
        "options": [
            {"label": "A", "text": "Cytokinin"},
            {"label": "B", "text": "Gibberellin"},
            {"label": "C", "text": "Abscisic acid"},
            {"label": "D", "text": "Auxin"},
        ],
        "answer": "D) Auxin",
    },
    {
        "section": Section.A,
        "qtype": QuestionType.MCQ,
        "marks": 1,
        "chapter_slug": "electricity",
        "level": AP,
        "text": "The resistance of a conductor of length l and area of "
        "cross-section A is R. If the length is doubled and area halved, "
        "the new resistance is:",
        "options": [
            {"label": "A", "text": "R"},
            {"label": "B", "text": "2R"},
            {"label": "C", "text": "4R"},
            {"label": "D", "text": "R/4"},
        ],
        "answer": "C) 4R",
    },
    # Section B — Very Short Answer (2 marks)
    {
        "section": Section.B,
        "qtype": QuestionType.VSA,
        "marks": 2,
        "chapter_slug": "life-processes",
        "level": U,
        "text": "Why is respiration considered an exothermic reaction? Explain.",
        "answer": "During respiration glucose is oxidised, releasing energy; "
        "reactions that release energy are exothermic.",
    },
    {
        "section": Section.B,
        "qtype": QuestionType.VSA,
        "marks": 2,
        "chapter_slug": "life-processes",
        "level": R,
        "text": "State two differences between an artery and a vein.",
        "answer": "Arteries carry blood away from the heart, have thick elastic walls, "
        "and no valves; veins carry blood to the heart, have thin walls, and valves.",
    },
    # Section C — Short Answer (3 marks)
    {
        "section": Section.C,
        "qtype": QuestionType.SA,
        "marks": 3,
        "chapter_slug": "metals-and-non-metals",
        "level": U,
        "text": "What is meant by the reactivity series of metals? Arrange the metals "
        "K, Cu, Zn and Mg in decreasing order of reactivity.",
        "answer": "The reactivity series lists metals in order of decreasing "
        "reactivity. Order: K > Mg > Zn > Cu.",
    },
    {
        "section": Section.C,
        "qtype": QuestionType.SA,
        "marks": 3,
        "chapter_slug": "light-reflection-and-refraction",
        "level": U,
        "text": "Draw a labelled ray diagram to show the refraction of light through a "
        "glass slab, and define the term 'lateral displacement'.",
        "answer": "Lateral displacement is the perpendicular distance between "
        "the incident ray produced and the emergent ray. (Diagram expected.)",
    },
    # Section D — Long Answer (5 marks)
    {
        "section": Section.D,
        "qtype": QuestionType.LA,
        "marks": 5,
        "chapter_slug": "light-reflection-and-refraction",
        "level": AP,
        "text": "(a) Define the focal length of a concave mirror. (b) An object is "
        "placed 10 cm from a concave mirror of focal length 15 cm. Find the position, "
        "nature and size characteristics of the image formed.",
        "answer": "Focal length is the distance between the pole and principal focus. "
        "Using 1/v + 1/u = 1/f with u = -10, f = -15 gives v = +30 cm: a virtual, "
        "erect, magnified image behind the mirror.",
    },
    {
        "section": Section.D,
        "qtype": QuestionType.LA,
        "marks": 5,
        "chapter_slug": "life-processes",
        "level": U,
        "text": "Explain the process of digestion of food in the human alimentary "
        "canal, naming the enzymes and the regions where they act.",
        "answer": "Salivary amylase (mouth) -> starch; pepsin (stomach) -> proteins; "
        "pancreatic enzymes and bile (small intestine) -> emulsify and digest "
        "fats, proteins, carbohydrates; absorption in small intestine.",
    },
    # Section E — Case-based (4 marks)
    {
        "section": Section.E,
        "qtype": QuestionType.CASE,
        "marks": 4,
        "chapter_slug": "chemical-reactions-and-equations",
        "level": AN,
        "text": "Read the passage and answer: A student dissolves common salt in water "
        "and passes electricity through it. (i) Name the products at the electrodes. "
        "(ii) Write the chemical name of the process. (iii) State one industrial use "
        "of a product formed.",
        "answer": "(i) Hydrogen and chlorine gas, with sodium hydroxide in solution. "
        "(ii) Chlor-alkali process. (iii) Chlorine is used to make bleaching powder.",
    },
]


class Command(BaseCommand):
    help = "Seed a demo school, a teacher account, and a handful of questions."

    def handle(self, *args, **options):
        school, _ = School.objects.get_or_create(name="Demo School")

        teacher_email = "teacher@example.com"
        if not User.objects.filter(email=teacher_email).exists():
            User.objects.create_user(
                email=teacher_email, password="teacher123", school=school
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created teacher {teacher_email} (password: teacher123)"
                )
            )
        else:
            self.stdout.write(f"Teacher {teacher_email} already exists.")

        chapters_by_slug = {c.slug: c for c in Chapter.objects.all()}
        created = 0
        for q in QUESTIONS:
            chapter = chapters_by_slug.get(q["chapter_slug"])
            obj, was_created = Question.objects.get_or_create(
                text=q["text"],
                defaults={
                    "school": school,
                    "chapter": chapter,
                    "section": q["section"],
                    "qtype": q["qtype"],
                    "marks": q["marks"],
                    "cognitive_level": q["level"],
                    "options": q.get("options", []),
                    "answer": q.get("answer", ""),
                    "parse_quality": "clean",
                },
            )
            if not was_created:
                # Backfill chapter/level on rows seeded before Slice 3.
                updated = False
                if obj.chapter_id is None and chapter is not None:
                    obj.chapter = chapter
                    updated = True
                if obj.cognitive_level != q["level"]:
                    obj.cognitive_level = q["level"]
                    updated = True
                if updated:
                    obj.save(update_fields=["chapter", "cognitive_level"])
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {created} new question(s), "
                f"{Question.objects.count()} total."
            )
        )
