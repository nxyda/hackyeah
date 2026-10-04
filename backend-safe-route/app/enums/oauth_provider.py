"""Obsługiwani dostawcy tożsamości OAuth."""

from enum import Enum


class OAuthProvider(str, Enum):
    GOOGLE = "google"
    FACEBOOK = "facebook"
