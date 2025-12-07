import base64
import secrets
import typing as t
from datetime import timedelta
from hashlib import sha256

import peewee as pw

from .base import BaseModel
from .user import User


def generate_session_token() -> str:
    """Generate 256-bit cryptographically secure session token (URL-safe, no padding)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


class Session(BaseModel):
    token = pw.CharField(
        max_length=43,
        unique=True,
        index=True,
        default=generate_session_token,
        help_text="Opaque session identifier sent to client",
    )
    created_at = pw.DateTimeField(default=pw.utcnow, index=True)  # type: ignore
    expires_at = pw.DateTimeField(index=True)  # absolute expiry
    last_seen_at = pw.DateTimeField(default=pw.utcnow, index=True)  # type: ignore
    ip_address = pw.IPField(null=True)
    user_agent_hash = pw.CharField(max_length=64, index=True)
    user = pw.ForeignKeyField(User, backref="sessions", on_delete="CASCADE")
    revoked = pw.BooleanField(default=False, index=True)

    class Meta:
        table_name = "session"
        indexes = (
            # Speed up cleanup job
            (("expires_at", "revoked"), False),
            # Speed up "list my active sessions"
            (("user", "revoked"), False),
        )

    @classmethod
    def create_for_user(
        cls,
        user: User,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
        remember: bool = True,  # long-lived session?
    ) -> t.Self:
        lifetime = timedelta(days=60) if remember else timedelta(hours=24)
        user_agent_hash = sha256(user_agent.encode("utf-8")).hexdigest() if user_agent else ""
        return cls.create(
            user=user,
            ip_address=ip_address,
            user_agent_hash=user_agent_hash,
            expires_at=pw.utcnow() + lifetime,  # type: ignore
        )

    @classmethod
    def find_by_token(cls, token: str) -> t.Self | None:
        return (
            cls.select()
            .where(
                cls.token == token,
                cls.revoked == False,  # noqa: E712
                cls.expires_at > pw.utcnow(),  # type: ignore
            )
            .first()
        )

    def touch(self):
        self.last_seen_at = pw.utcnow()  # type: ignore
        self.save(only=[self.last_seen_at])

    def revoke(self) -> None:
        self.revoked = True
        self.save(only=[self.revoked])

    def is_valid(self) -> bool:
        return not self.revoked and self.expires_at > pw.utcnow()  # type: ignore
