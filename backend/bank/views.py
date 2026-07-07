"""Bank endpoints.

* ``GET  /api/bank/metadata/`` — canonical labels for Section / QuestionType /
  CognitiveLevel.
* ``GET  /api/bank/chapters/`` — full 13-chapter taxonomy.
* ``POST /api/bank/ingest/`` — teacher PDF upload. Persists the PDF + queues an
  ``IngestionJob`` (status ``pending``) and returns **202** with the job id. The
  Gemini extraction runs out-of-request via the ``drain_ingestion_jobs`` cron
  command — no LLM call inside the request.
* ``GET  /api/bank/ingest/{job_id}/`` — poll a job's status / result counts.
* ``POST /api/bank/generation-batches/`` — queue bulk AI Question generation.
* ``GET  /api/bank/generation-batches/{batch_id}/`` — poll generation status.
* ``GET  /api/bank/generation-batches/{batch_id}/candidates/`` — list valid
  generated candidates for teacher review.
* ``POST /api/bank/generation-batches/{batch_id}/accept/`` — import selected
  generated candidates and reject the rest.

The HTTP path is the *live* ingestion front door (teachers uploading their own
PDFs at runtime); the committed-JSON CLI path (``extract_paper`` →
``load_questions``) is the *developer* one. Both are intentional — see the
two-front-door note in CONTEXT.md ``Ingestor``.
"""

import base64

from django.db.models import Count, Max, Q
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from .answer_generation import (
    AnswerGenerationConflict,
    answer_generation_state,
    queue_ingestion_answer_generation,
)
from .generation_batches import (
    GenerationBatchBadSelection,
    GenerationBatchConflict,
    accept_generation_batch_selection,
    discard_generation_batch,
    get_owned_generation_batch,
    list_generation_batches,
    queue_generation_batch,
    requeue_generation_batch,
)
from .models import (
    Chapter,
    CognitiveLevel,
    GeneratedQuestionCandidate,
    GeneratedQuestionCandidateStatus,
    GenerationBatch,
    IngestionJob,
    IngestionJobStatus,
    Question,
    QuestionType,
    Section,
)
from .permissions import IsTeacher
from .serializers import (
    AnswerGenerationJobSerializer,
    BankQuestionSerializer,
    ChapterTaxonomySerializer,
    GeneratedAnswerSerializer,
    GeneratedQuestionCandidateSerializer,
    GenerationBatchAcceptSerializer,
    GenerationBatchCreateSerializer,
    GenerationBatchSerializer,
    IngestionJobSerializer,
    IngestionUploadSerializer,
)


@api_view(["GET"])
def metadata(request):
    """Serve canonical section and question-type vocabulary."""
    return Response(
        {
            "sections": [{"code": k, "label": v} for k, v in Section.choices],
            "question_types": [
                {"code": k, "label": v} for k, v in QuestionType.choices
            ],
            "cognitive_levels": [
                {"code": k, "label": v} for k, v in CognitiveLevel.choices
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsTeacher])
def question_sources(request):
    """Distinct source papers in the visible bank, for the bank's source filter.

    Same tenancy + usable-quality scope as ``questions``: the global/seeded bank
    plus the teacher's school, clean+partial only. Returns one entry per
    ``source_name`` (the human-readable paper label, populated for every row)
    with its question ``count``, most-populated first, so the filter lists the
    papers a teacher is most likely to browse at the top.
    """
    rows = (
        Question.objects.filter(
            Q(school__isnull=True) | Q(school=request.user.school),
            parse_quality__in=["clean", "partial"],
        )
        .exclude(source_name="")
        .values("source_name")
        .annotate(count=Count("id"))
        .order_by("-count", "source_name")
    )
    return Response(
        [
            {"value": r["source_name"], "label": r["source_name"], "count": r["count"]}
            for r in rows
        ]
    )


@api_view(["GET"])
def chapters(request):
    return Response(ChapterTaxonomySerializer(Chapter.objects.all(), many=True).data)


@api_view(["GET"])
@permission_classes([IsTeacher])
def sources(request):
    """Source groups for generate-page prioritisation.

    Returns tagged bank sources (including committed 2026 CBSE papers), uploaded
    PDFs, and accepted AI-generation sessions in recency order. The opaque
    ``key`` is the only value the assemble endpoint needs; selecting a source
    prioritises its questions for the first draft while editor alternatives
    continue to show every compatible question. Optional ``chapter`` query
    params narrow the list after chapter selection.
    """
    chapter_slugs = request.query_params.getlist("chapter")
    visible_questions = Question.objects.filter(
        Q(school__isnull=True) | Q(school=request.user.school),
        parse_quality__in=["clean", "partial"],
    )
    source_fields = ("source_type", "source_name", "source_file_name")
    bank_source_questions = visible_questions.filter(ingestion_job__isnull=True)
    bank_sources = (
        bank_source_questions.exclude(source_file_name="")
        .values(*source_fields)
        .annotate(question_count=Count("id"), created_at=Max("created_at"))
    )
    matching_counts: dict[tuple[str, str, str], int] = {}
    if chapter_slugs:
        matching_counts = {
            (row["source_type"], row["source_name"], row["source_file_name"]): row[
                "matching_question_count"
            ]
            for row in bank_source_questions.filter(chapter__slug__in=chapter_slugs)
            .exclude(source_file_name="")
            .values(*source_fields)
            .annotate(matching_question_count=Count("id"))
        }

    bank_items = []
    for row in bank_sources:
        source_key = (row["source_type"], row["source_name"], row["source_file_name"])
        matching_question_count = (
            matching_counts.get(source_key, 0)
            if chapter_slugs
            else row["question_count"]
        )
        if chapter_slugs and matching_question_count == 0:
            continue
        bank_items.append(
            {
                "key": f"source_file:{_source_file_key(row['source_file_name'])}",
                "kind": "bank_source",
                "title": row["source_name"] or row["source_file_name"],
                "detail": dict(Question._meta.get_field("source_type").choices).get(
                    row["source_type"], row["source_type"] or "Tagged bank source"
                ),
                "question_count": row["question_count"],
                "matching_question_count": matching_question_count,
                "created_at": row["created_at"],
                "status": "available",
            }
        )
    bank_items.sort(
        key=lambda item: (item["matching_question_count"], item["question_count"]),
        reverse=True,
    )
    bank_items = bank_items[:40]

    uploads = (
        IngestionJob.objects.filter(school=request.user.school)
        .annotate(question_count=Count("questions"))
        .order_by("-created_at")[:20]
    )
    upload_items = [
        {
            "key": f"upload:{job.pk}",
            "kind": "upload",
            "title": job.source_file_name or f"Upload #{job.pk}",
            "detail": job.get_source_type_display(),
            "question_count": job.question_count,
            "matching_question_count": job.question_count,
            "created_at": job.created_at,
            "status": job.status,
        }
        for job in uploads
    ]

    batches = (
        GenerationBatch.objects.filter(
            created_by=request.user,
            school=request.user.school,
            accepted_at__isnull=False,
        )
        .prefetch_related("chapters")
        .order_by("-accepted_at", "-created_at")[:20]
    )
    batch_ids = [batch.pk for batch in batches]
    counts = dict(
        GeneratedQuestionCandidate.objects.filter(
            batch_id__in=batch_ids,
            status=GeneratedQuestionCandidateStatus.ACCEPTED,
            question_id__isnull=False,
        )
        .values("batch_id")
        .annotate(n=Count("question_id"))
        .values_list("batch_id", "n")
    )
    batch_items = []
    for batch in batches:
        imported_count = counts.get(batch.pk, 0)
        chapter_detail = ", ".join(
            batch.chapters.order_by("order").values_list("name", flat=True)[:3]
        )
        detail_prefix = chapter_detail or batch.difficulty_preset
        imported_label = f"{imported_count} imported"
        batch_items.append(
            {
                "key": f"ai_batch:{batch.pk}",
                "kind": "ai_session",
                "title": f"AI Q&A session #{batch.pk}",
                "detail": f"{detail_prefix} · {imported_label}"
                if detail_prefix
                else imported_label,
                "question_count": imported_count,
                "matching_question_count": imported_count,
                "created_at": batch.accepted_at or batch.created_at,
                "status": batch.status,
            }
        )

    kind_rank = {"bank_source": 2, "upload": 1, "ai_session": 0}
    items = sorted(
        [*bank_items, *upload_items, *batch_items],
        key=lambda item: (
            kind_rank.get(item["kind"], 0),
            item.get("matching_question_count") or 0,
            item.get("question_count") or 0,
            item["created_at"],
        ),
        reverse=True,
    )
    return Response(items)


def _source_file_key(source_file_name: str) -> str:
    """URL-safe opaque key for a bank source filename."""
    encoded = base64.urlsafe_b64encode(source_file_name.encode()).decode()
    return encoded.rstrip("=")


@api_view(["GET", "POST"])
@parser_classes([MultiPartParser])
@permission_classes([IsTeacher])
def ingest(request):
    """List recent ingestion jobs or queue a teacher PDF for extraction.

    ``GET`` returns the school's recent jobs so the frontend can keep showing
    background extraction progress after the teacher leaves the upload screen.

    ``POST`` accepts multipart/form-data with field ``pdf`` (file) plus optional
    ``source_type`` (one of ``SourceType``; defaults to ``previous_year_paper``).
    It persists the PDF and creates a pending ``IngestionJob`` scoped to the
    teacher's school — **no Gemini call here**. The ``drain_ingestion_jobs`` cron
    command does the extraction later.
    Response: **202** with the serialised job (``id``, ``status`` …) to poll.
    """
    if request.method == "GET":
        jobs = IngestionJob.objects.filter(school=request.user.school).order_by(
            "-created_at"
        )[:20]
        return Response(IngestionJobSerializer(jobs, many=True).data)

    serializer = IngestionUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    pdf_file = serializer.validated_data["pdf"]

    job = IngestionJob.objects.create(
        school=request.user.school,
        created_by=request.user,
        pdf=pdf_file,
        source_file_name=pdf_file.name or "",
        source_type=serializer.validated_data["source_type"],
    )
    return Response(IngestionJobSerializer(job).data, status=202)


@api_view(["GET", "DELETE"])
@permission_classes([IsTeacher])
def ingest_status(request, job_id):
    """Poll or dismiss one ingestion job, scoped to the teacher's school.

    A teacher may only touch jobs from their own school — a cross-school id is a
    404 (not 403), so the endpoint never confirms another school's job exists.

    ``DELETE`` dismisses a **failed** job (removes it from the queue). Only
    ``failed`` jobs are dismissable: a pending/running row is mid-drain, and a
    ``done`` row's extracted questions stay in the bank regardless (the FK is
    SET_NULL), so deleting it would only orphan provenance.
    """
    try:
        job = IngestionJob.objects.get(pk=job_id, school=request.user.school)
    except IngestionJob.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)

    if request.method == "DELETE":
        if job.status != IngestionJobStatus.FAILED:
            return Response(
                {"detail": "Only a failed upload can be dismissed."},
                status=409,
            )
        job.delete()
        return Response(status=204)

    return Response(IngestionJobSerializer(job).data)


@api_view(["POST"])
@permission_classes([IsTeacher])
def ingest_retry(request, job_id):
    """Re-queue a failed ingestion job so the drainer extracts it again.

    Only a ``failed`` job is retryable. The ``thread_id`` is preserved, so
    extraction resumes from the last per-page checkpoint (ADR-0006) instead of
    re-billing pages already parsed (Rule 13). The paid work runs later in
    ``drain_ingestion_jobs`` — this view only flips the row to ``pending``.
    """
    try:
        job = IngestionJob.objects.get(pk=job_id, school=request.user.school)
    except IngestionJob.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)

    if job.status != IngestionJobStatus.FAILED:
        return Response({"detail": "Only a failed upload can be retried."}, status=409)
    job.status = IngestionJobStatus.PENDING
    job.error = ""
    job.save(update_fields=["status", "error", "updated_at"])
    return Response(IngestionJobSerializer(job).data, status=202)


@api_view(["GET"])
@permission_classes([IsTeacher])
def ingest_questions(request, job_id):
    """Return the questions a finished ingestion job added to the bank.

    Scoped to the teacher's school (a cross-school id is a 404, never a 403).
    Powers the upload status card's "what was parsed" list, so it mirrors the
    bank view's exclusion of structurally ``broken`` rows — only usable
    (clean/partial) questions the teacher could actually pick.
    """
    try:
        job = IngestionJob.objects.get(pk=job_id, school=request.user.school)
    except IngestionJob.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)
    questions_qs = (
        job.questions.filter(parse_quality__in=["clean", "partial"])
        .select_related("chapter")
        .order_by("section", "id")
    )
    return Response(BankQuestionSerializer(questions_qs, many=True).data)


@api_view(["GET", "POST"])
@permission_classes([IsTeacher])
def ingest_answers(request, job_id):
    """Queue or read optional generated answers for one completed upload."""
    if request.method == "POST":
        try:
            answer_job = queue_ingestion_answer_generation(request.user, job_id)
        except AnswerGenerationConflict as exc:
            return Response({"detail": exc.detail}, status=409)
        if answer_job is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(AnswerGenerationJobSerializer(answer_job).data, status=202)

    state = answer_generation_state(request.user, job_id)
    if state is None:
        return Response({"detail": "Not found."}, status=404)
    answer_job, answered_questions = state
    return Response(
        {
            "job": (
                AnswerGenerationJobSerializer(answer_job).data
                if answer_job is not None
                else None
            ),
            "answers": GeneratedAnswerSerializer(answered_questions, many=True).data,
        }
    )


QUESTIONS_PAGE_SIZE = 50
QUESTIONS_MAX_PAGE_SIZE = 200


def _int_param(request, key, default):
    """Parse a non-negative int query param, falling back to ``default``."""
    try:
        value = int(request.query_params.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


@api_view(["GET"])
@permission_classes([IsTeacher])
def questions(request):
    """List bank questions visible to the teacher, with filters + pagination.

    Tenancy: the global/seeded bank (``school IS NULL``) plus the teacher's own
    school. Optional filters: ``chapter`` (slug), ``section``, ``qtype``,
    ``source_type``, ``source`` (a specific paper's ``source_name``), and
    ``search`` (case-insensitive substring of the question
    text). Paginated with ``limit``/``offset``; the response carries ``count``
    so the client can page. Answers are never serialized (see serializers).
    """
    # Only usable rows: the picker draws from clean+partial and excludes
    # ``broken`` (structurally unusable — empty/fragment stems, bad enums). The
    # bank view promises "what's available", so it mirrors that exclusion.
    qs = (
        Question.objects.filter(Q(school__isnull=True) | Q(school=request.user.school))
        .filter(parse_quality__in=["clean", "partial"])
        .select_related("chapter")
    )

    chapter_slug = request.query_params.get("chapter")
    if chapter_slug:
        qs = qs.filter(chapter__slug=chapter_slug)
    section = request.query_params.get("section")
    if section:
        qs = qs.filter(section=section)
    qtype = request.query_params.get("qtype")
    if qtype:
        qs = qs.filter(qtype=qtype)
    source_type = request.query_params.get("source_type")
    if source_type:
        qs = qs.filter(source_type=source_type)
    source = request.query_params.get("source")
    if source:
        qs = qs.filter(source_name=source)
    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(text__icontains=search)

    qs = qs.order_by("-created_at", "-id")
    count = qs.count()

    limit = _int_param(request, "limit", QUESTIONS_PAGE_SIZE) or QUESTIONS_PAGE_SIZE
    limit = min(limit, QUESTIONS_MAX_PAGE_SIZE)
    offset = _int_param(request, "offset", 0)
    page = qs[offset : offset + limit]

    return Response(
        {
            "count": count,
            "limit": limit,
            "offset": offset,
            "results": BankQuestionSerializer(page, many=True).data,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsTeacher])
def generation_batches(request):
    """List the teacher's batch queue (GET) or enqueue a new batch (POST)."""
    if request.method == "GET":
        batches = list_generation_batches(request.user)
        return Response(GenerationBatchSerializer(batches, many=True).data)

    serializer = GenerationBatchCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        batch = queue_generation_batch(request.user, serializer.validated_data)
    except GenerationBatchConflict as exc:
        return Response({"detail": exc.detail}, status=409)

    return Response(GenerationBatchSerializer(batch).data, status=202)


@api_view(["POST"])
@permission_classes([IsTeacher])
def generation_batch_discard(request, batch_id):
    """Discard an owned batch so the teacher can start a fresh one."""
    try:
        batch = discard_generation_batch(request.user, batch_id)
    except GenerationBatchConflict as exc:
        return Response({"detail": exc.detail}, status=409)

    if batch is None:
        return Response({"detail": "Not found."}, status=404)
    return Response(GenerationBatchSerializer(batch).data)


@api_view(["POST"])
@permission_classes([IsTeacher])
def generation_batch_retry(request, batch_id):
    """Re-queue a failed owned batch so the drainer generates it again."""
    try:
        batch = requeue_generation_batch(request.user, batch_id)
    except GenerationBatchConflict as exc:
        return Response({"detail": exc.detail}, status=409)

    if batch is None:
        return Response({"detail": "Not found."}, status=404)
    return Response(GenerationBatchSerializer(batch).data, status=202)


@api_view(["GET"])
@permission_classes([IsTeacher])
def generation_batch_detail(request, batch_id):
    """Return one generation batch status, scoped to the creating teacher."""
    batch = get_owned_generation_batch(request.user, batch_id)
    if batch is None:
        return Response({"detail": "Not found."}, status=404)
    batch.expire_if_stale()
    return Response(GenerationBatchSerializer(batch).data)


@api_view(["GET"])
@permission_classes([IsTeacher])
def generation_batch_candidates(request, batch_id):
    """Return valid candidates for one owned generation batch."""
    batch = get_owned_generation_batch(request.user, batch_id)
    if batch is None:
        return Response({"detail": "Not found."}, status=404)
    batch.expire_if_stale()
    candidates = batch.candidates.all()
    return Response(GeneratedQuestionCandidateSerializer(candidates, many=True).data)


@api_view(["POST"])
@permission_classes([IsTeacher])
def generation_batch_accept(request, batch_id):
    """Import selected ready candidates and reject the rest of the batch."""
    serializer = GenerationBatchAcceptSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    accepted_candidate_ids = set(serializer.validated_data["accepted_candidate_ids"])

    try:
        batch = accept_generation_batch_selection(
            request.user,
            batch_id,
            accepted_candidate_ids,
        )
    except GenerationBatchBadSelection as exc:
        return Response({"detail": exc.detail}, status=400)
    except GenerationBatchConflict as exc:
        return Response({"detail": exc.detail}, status=409)

    if batch is None:
        return Response({"detail": "Not found."}, status=404)
    return Response(GenerationBatchSerializer(batch).data)
