"""Accounts for Nova Campus Tycoon (v12): e-mail and password, no game rules here.

Passwords are never stored: only a salted PBKDF2 hash. A login hands the browser a
random token; the database keeps only the token's SHA-256 hash, so a copy of the
database does not let anybody log in.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

PBKDF2_ITERATIONS = 200_000
MIN_PASSWORD = 8
MAX_PASSWORD = 128
SESSION_DAYS = 30
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class AuthError(Exception):
    """A message for the player: wrong password, e-mail taken, ..."""


def normalize_email(email: str) -> str:
    """One account per address: case and spaces around it do not make a new one."""
    return (email or "").strip().lower()


def check_email(email: str) -> str:
    email = normalize_email(email)
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise AuthError("Please enter a valid e-mail address.")
    return email


def check_password(password: str) -> str:
    password = password or ""
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"The password needs at least {MIN_PASSWORD} characters.")
    if len(password) > MAX_PASSWORD:
        raise AuthError(f"The password can have at most {MAX_PASSWORD} characters.")
    return password


def hash_password(password: str, salt: bytes | None = None) -> str:
    """'pbkdf2_sha256$iterations$salt$hash' (salt and hash in hex)."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        check = hashlib.pbkdf2_hmac("sha256", (password or "").encode(), bytes.fromhex(salt), int(iterations))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(check.hex(), digest)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode()).hexdigest()
