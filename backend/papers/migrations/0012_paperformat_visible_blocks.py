from django.db import migrations, models

CBSE_FORMAT_ID = "cbse_science_class_10_board_compact_2026_v1"

CBSE_CHROME_BLOCKS = [
    {"id": "series", "role": "series", "text": "LMNK2", "can": {"editText": True, "delete": True, "reorder": False}},
    {"id": "set", "role": "set", "text": "SET ~ 1", "can": {"editText": True, "delete": True, "reorder": False}},
    {"id": "paper_code", "role": "paper_code", "text": "31/2/1", "can": {"editText": True, "delete": True, "reorder": False}},
    {"id": "subject_label", "role": "subject_label", "text": "विज्ञान", "can": {"editText": True, "delete": True, "reorder": False}},
    {"id": "roll_number", "role": "roll_number", "text": "", "can": {"editText": True, "delete": True, "reorder": False}},
    {"id": "time_allowed", "role": "paper_meta_left", "text": "Time allowed : {duration}", "can": {"editText": True, "delete": True, "reorder": False}},
    {"id": "maximum_marks", "role": "paper_meta_right", "text": "Maximum Marks : {totalMarks}", "can": {"editText": True, "delete": True, "reorder": False}},
    {"id": "footer_left", "role": "footer_left", "text": "31/2/1", "can": {"editText": True, "delete": True, "reorder": False}},
    {"id": "footer_right", "role": "footer_right", "text": "P.T.O.", "can": {"editText": True, "delete": True, "reorder": False}},
]

CBSE_INSTRUCTION_BLOCKS = [
    {"id": "note_heading", "role": "note_heading", "text": "NOTE", "can": {"editText": True, "delete": False, "reorder": False}},
    {"id": "note_printed_pages", "role": "note", "text": "Please check that this question paper contains the correct number of printed pages.", "can": {"editText": True, "delete": False, "reorder": False}},
    {"id": "note_question_count", "role": "note", "text": "Please check that this question paper contains {questionCount} questions.", "can": {"editText": True, "delete": False, "reorder": False}},
    {"id": "note_serial_number", "role": "note", "text": "Please write down the Serial Number of the question in the answer-book at the given place before attempting it.", "can": {"editText": True, "delete": False, "reorder": False}},
    {"id": "note_reading_time", "role": "note", "text": "15 minute time has been allotted to read this question paper. The question paper will be distributed at 10.15 a.m. From 10.15 a.m. to 10.30 a.m., the candidates will read the question paper only and will not write any answer on the answer-book during this period.", "can": {"editText": True, "delete": False, "reorder": False}},
    {"id": "general_instructions_heading", "role": "general_instructions_heading", "text": "General Instructions", "can": {"editText": True, "delete": False, "reorder": False}},
    {"id": "general_instruction_count", "role": "general_instruction", "text": "This question paper contains {questionCount} questions. All questions are compulsory.", "can": {"editText": True, "delete": False, "reorder": False}},
    {"id": "general_instruction_types", "role": "general_instruction", "text": "The question paper has MCQs, very short answer, short answer, long answer and case-based questions. Marks are given against each question.", "can": {"editText": True, "delete": False, "reorder": False}},
    {"id": "general_instruction_choice", "role": "general_instruction", "text": "There is no overall choice in the question paper. However, an internal choice has been provided in some questions. Only one of the choices in such questions must be attempted.", "can": {"editText": True, "delete": False, "reorder": False}},
]


def seed_visible_blocks(apps, schema_editor):
    PaperFormat = apps.get_model("papers", "PaperFormat")
    PaperFormat.objects.filter(format_id=CBSE_FORMAT_ID).update(
        chrome_blocks=CBSE_CHROME_BLOCKS,
        instruction_blocks=CBSE_INSTRUCTION_BLOCKS,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("papers", "0011_paper_answer_document"),
    ]

    operations = [
        migrations.AddField(
            model_name="paperformat",
            name="chrome_blocks",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="paperformat",
            name="instruction_blocks",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(seed_visible_blocks, migrations.RunPython.noop),
    ]
