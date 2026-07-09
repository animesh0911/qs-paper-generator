"""In-place eval framework for the three paid AI workflows.

The evals package benchmarks the *actual production code paths* — never
re-implemented prompts or parallel clients — by riding the injection seams the
codebase already exposes (ADR-0005, Rules 9/11):

- generation:  ``bank.generation.LangChainQuestionGenerator(make_model=...)``
- extraction:  ``bank.extraction.SeamExtractor(make_model=...)`` and
               ``bank.ocr_extractor.MistralOcrMarkdownExtractor(chat_model=...)``
- answers:     ``bank.answer_generation.BankAnswerGenerator(make_model=...)``

Model choice per run is applied through the same env resolution production
uses (``LLM_<PURPOSE>_PROVIDER`` / ``_MODEL`` → ``resolve_chat_model_config``),
so an eval run exercises exactly what a deploy with that env would run.

Three phases, separately resumable so paid work is never repeated to re-score:

1. ``run``    — paid model calls; writes raw artifacts + RunRecords (JSONL).
2. ``score``  — deterministic scorers + LLM-judge accuracy over stored
                artifacts; only judge calls (free on CLI judges) are spent.
3. ``report`` — pure aggregation into comparison tables and the
                per-user/month cost roll-up. No network.

Paid calls are consent-gated (dry-run by default, explicit ``--yes``,
hard USD cap) — see ``evals.budget``.
"""
