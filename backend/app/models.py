from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TrustContext(str, Enum):
    owner = "owner"
    stranger = "stranger"
    public = "public"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    # For prototype purposes, "user_id" is just an opaque string for logging/rate limiting.
    user_id: Optional[str] = Field(default=None, max_length=200)


class ChatResponse(BaseModel):
    agent_id: str
    trust: TrustContext
    reply: str
    # Extra debugging metadata (kept small and safe; never includes private memories).
    meta: dict[str, Any] = Field(default_factory=dict)


class BootstrapAgentRequest(BaseModel):
    # Optional "seed" to guide personality; if omitted, uses a default.
    seed: Optional[str] = Field(default=None, max_length=500)


class BootstrapAgentResponse(BaseModel):
    agent_id: str
    api_key: str
    name: str
    bio: str | None = None
    visitor_bio: str | None = None
    status: str | None = None
    accent_color: str | None = None
    avatar_url: str | None = None
    showcase_emoji: str | None = None

