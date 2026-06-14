"""
Email domain validators for institutional accounts.

Used by:
  - Person 1: restrict registration to institutional emails.
  - Person 3: validate the domain of Google OAuth accounts.
"""

ALLOWED_DOMAINS = {"tkmce.ac.in"}


def is_valid_institutional_email(email: str) -> bool:
    """
    Return True if the email belongs to an allowed institutional domain.

    Example:
        >>> is_valid_institutional_email("student@tkmce.ac.in")
        True
        >>> is_valid_institutional_email("user@gmail.com")
        False
    """
    try:
        domain = email.split("@")[1].lower()
        return domain in ALLOWED_DOMAINS
    except (IndexError, AttributeError):
        return False
