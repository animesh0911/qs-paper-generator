"""Request/response shapes for the AI editor endpoints.

The poll serializer is the contract the frontend reads off ``GET
/api/ai/jobs/{jobId}/``; the request serializers validate the typed-intent /
chat / job-creating payloads. Internal ledger fields (``request_payload``,
``created_by`` …) are never exposed.
"""

from rest_framework import serializers

from .models import AIJob


class AIJobSerializer(serializers.ModelSerializer):
    """Job status shape the frontend polls.

    ``jobId``/``baseRevision`` are camelCased to match the PRD contract; the
    stored request payload is never returned.
    """

    # camelCase to match the PRD #30 JSON contract the frontend reads.
    jobId = serializers.IntegerField(source="id", read_only=True)  # noqa: N815
    baseRevision = serializers.IntegerField(  # noqa: N815
        source="base_revision", read_only=True
    )

    class Meta:
        model = AIJob
        fields = ["jobId", "kind", "status", "baseRevision", "result", "error"]


class TypedTextSerializer(serializers.Serializer):
    """Body for the sync intent/chat endpoints."""

    text = serializers.CharField()
    paperId = serializers.IntegerField()  # noqa: N815


class JobRequestSerializer(serializers.Serializer):
    """Body for the async job-creating endpoints.

    ``instruction`` is optional for summary/review (button actions need no text)
    and carries the edit/refine instruction for editor-edit/refine.
    """

    paperId = serializers.IntegerField()  # noqa: N815
    instruction = serializers.CharField(required=False, allow_blank=True, default="")
