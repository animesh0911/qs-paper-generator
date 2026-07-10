from bank.upload_extraction import pipeline
from bank.upload_extraction.pipeline import OcrMarkdownPage, UploadExtractionPipeline


class FakeChatModel:
    pass


def _pipeline():
    return UploadExtractionPipeline(FakeChatModel())


def test_select_pages_skips_hindi_only_and_keeps_english_questions():
    pages = [
        OcrMarkdownPage(0, "सामान्य निर्देश " * 20),
        OcrMarkdownPage(1, "SECTION A\n1. What is electrolysis?\n(A) one"),
    ]

    selected = _pipeline().select_pages(pages)

    assert [page.index for page in selected] == [1]


def test_batch_pages_supports_fixed_sizes_and_all():
    pages = [OcrMarkdownPage(i, f"{i}. Question") for i in range(5)]
    pipe = _pipeline()

    assert [len(batch) for batch in pipe.batch_pages(pages, 2)] == [2, 2, 1]
    assert pipe.batch_pages(pages, "all") == [pages]


def test_render_batch_uses_human_page_numbers():
    rendered = _pipeline().render_batch([OcrMarkdownPage(2, "3. Why?")])

    assert "OCR PAGE 3" in rendered
    assert "3. Why?" in rendered


def test_structure_pages_is_the_shared_upload_pipeline_seam(monkeypatch):
    seen_markdown = []

    def fake_structure(markdown, chat_model):
        seen_markdown.append(markdown)
        return {
            "questions": [
                {
                    "qtype": "mcq",
                    "marks": 1,
                    "rawText": "What is the mass ratio?",
                    "options": [],
                    "content": {
                        "stem": [
                            {"type": "paragraph", "text": "What is the mass ratio?"}
                        ]
                    },
                    "figures": [],
                }
            ]
        }

    monkeypatch.setattr(pipeline, "structure_ocr_markdown", fake_structure)
    pages = [OcrMarkdownPage(0, "SECTION A\n1. What is the mass ratio?")]

    run = _pipeline().structure_pages(pages=pages, batch_size="all")

    assert len(seen_markdown) == 1
    assert len(run.batches) == 1
    assert run.batches[0].pages == (1,)
    assert len(run.questions) == 1
