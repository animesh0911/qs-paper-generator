"""Record a deterministic lexical-only TextbookRetriever evaluation baseline.

The command reads a hand-reviewed query set, retrieves Postgres full-text
results, and records explicit pass/fail rows. It never invokes an embedding or
model provider.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bank.models import Chapter
from corpus.retrieval import PostgresTextbookRetriever, TextbookRetrievalRequest


def evaluate_queries(evaluation: list[dict], chapter: Chapter) -> list[dict]:
    """Evaluate supported-topic hits and unsupported empty-context expectations."""
    retriever = PostgresTextbookRetriever()
    rows: list[dict] = []
    for case in evaluation:
        context = retriever.retrieve(
            TextbookRetrievalRequest(
                chapter=chapter,
                query_text=case["query"],
                content_types=tuple(case["expected_content_types"]),
                limit=case.get("result_limit", 5),
            )
        )
        results = [
            {
                "rank": round(result.rank, 8),
                "stable_chunk_id": result.chunk.stable_chunk_id,
                "topic_title": result.chunk.chapter_map_node.title,
                "content_types": result.chunk.content_types,
                "pages": result.chunk.citation["pages"],
                "source_element_ids": result.chunk.source_element_ids,
            }
            for result in context.results
        ]
        expected_topics = set(case["expected_topic_titles"])
        expected_types = set(case["expected_content_types"])
        expected_pages = set(case["expected_source_pages"])
        relevant_positions = [
            index
            for index, result in enumerate(results, start=1)
            if result["topic_title"] in expected_topics
            and expected_types.intersection(result["content_types"])
            and expected_pages.intersection(result["pages"])
        ]
        passed = bool(relevant_positions) if case["supported"] else not bool(results)
        rows.append(
            {
                "id": case["id"],
                "supported": case["supported"],
                "passed": passed,
                "first_relevant_rank": (
                    relevant_positions[0] if relevant_positions else None
                ),
                "result_count": len(results),
                "results": results,
            }
        )
    return rows


def summary(rows: list[dict]) -> dict:
    passed = sum(row["passed"] for row in rows)
    supported = [row for row in rows if row["supported"]]
    unsupported = [row for row in rows if not row["supported"]]
    return {
        "query_count": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "pass_rate": round(passed / len(rows), 4) if rows else 0,
        "supported_passed": sum(row["passed"] for row in supported),
        "supported_count": len(supported),
        "unsupported_passed": sum(row["passed"] for row in unsupported),
        "unsupported_count": len(unsupported),
    }


class Command(BaseCommand):
    help = "Record deterministic lexical TextbookRetriever results (no LLM)."

    def add_arguments(self, parser):
        parser.add_argument("evaluation_path", type=Path)
        parser.add_argument("--chapter", required=True)
        parser.add_argument("--record", type=Path)

    def handle(self, *args, **options):
        path: Path = options["evaluation_path"]
        if not path.is_file():
            raise CommandError(f"Evaluation set not found: {path}")
        try:
            evaluation = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            raise CommandError(f"Cannot read evaluation set: {exc}") from exc
        try:
            chapter = Chapter.objects.get(slug=options["chapter"])
        except Chapter.DoesNotExist as exc:
            raise CommandError(f"Unknown Chapter slug: {options['chapter']}") from exc

        rows = evaluate_queries(evaluation, chapter)
        result = {"summary": summary(rows), "rows": rows}
        self.stdout.write(json.dumps(result["summary"], indent=2))
        if options["record"]:
            record: Path = options["record"]
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(json.dumps(result, indent=2) + "\n")
            self.stdout.write(self.style.SUCCESS(f"Recorded results to {record}."))
