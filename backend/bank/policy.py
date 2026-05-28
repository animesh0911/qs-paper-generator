def answer_visible(user) -> bool:
    """Return True when the caller may see question answers.

    Staff accounts (teachers, admins) see answers; regular authenticated users
    do not. Gate answer-key endpoints on this function — not on serializer
    choice — so the rule lives in one place and is testable without HTTP.
    """
    return bool(user and user.is_authenticated and user.is_staff)
