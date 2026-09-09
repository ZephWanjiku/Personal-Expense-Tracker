"""
auth.py
Password hashing and verification for user accounts.

Uses hashlib's PBKDF2-HMAC-SHA256 (stdlib only, no extra dependency like bcrypt
needed). Each password gets a unique random salt; the salt is stored alongside
the hash as "salt$hash" (both hex-encoded) in the users table.
"""

import hashlib
import hmac
import os
import re

PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(actual, expected)


def validate_username(username: str) -> str:
    """Returns an error message, or '' if the username is valid."""
    username = username.strip()
    if len(username) < 3:
        return "Username must be at least 3 characters."
    if len(username) > 30:
        return "Username must be at most 30 characters."
    if not re.match(r"^[A-Za-z0-9_.]+$", username):
        return "Username can only contain letters, numbers, underscores, and periods."
    return ""


def validate_password(password: str) -> str:
    """Returns an error message, or '' if the password is valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        return "Password must contain at least one letter and one number."
    return ""
