"""DRF permissions for the bank app.

``IsTeacher`` gates the live HTTP ingest path. A teacher is any authenticated
user who belongs to a ``School`` — tenancy requires a school anyway, so a
user without one cannot scope an upload and is refused. No role field exists on
``User`` in V1; school membership is the teacher signal (see issue #104).
"""

from rest_framework.permissions import BasePermission


class IsTeacher(BasePermission):
    """Authenticated AND belongs to a school. Uploads scope to ``user.school``."""

    message = "Upload requires a teacher account linked to a school."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "school_id", None))
