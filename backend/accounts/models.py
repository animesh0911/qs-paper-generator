"""Identity models — School (tenant) and User (email-based auth).

``School`` is the tenant. Both ``bank.Question`` and ``papers.Paper`` carry
an optional ``school`` FK so a future multi-tenant rollout can scope data
without a schema change.

``User`` overrides Django's default to use email as the username field and
to carry an optional ``school`` FK so teachers belong to a school.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class School(models.Model):
    """Tenancy seam.

    Single-tenant MVP: there is normally one row here. Core models carry a
    nullable FK to School so multi-tenancy can be introduced later as an
    additive change rather than a schema migration on a live table.
    """

    name = models.CharField(max_length=255)
    # Branding/config lives here (logo, header text) rather than in code.
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    """User manager keyed on email instead of username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Teacher account. Email is the login identifier; username is dropped."""

    username = None
    email = models.EmailField("email address", unique=True)
    school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
