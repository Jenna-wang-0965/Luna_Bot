from __future__ import annotations

import asyncio
import logging
import secrets
import string
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from stream_chat import StreamChat

from .agent_brain import (
    AgentProfile,
    llm_generate_reply,
    generate_owner_reply_with_context,
    generate_reply,
    generate_stranger_reply_with_public_context,
)
from .models import (
    BootstrapAgentRequest,
    BootstrapAgentResponse,
    ChatRequest,
    ChatResponse,
    TrustContext,
)
from .scheduler import run_scheduler
from .settings import settings
from .supabase_client import SupabaseRest


def _mk_sb() -> SupabaseRest:
    rest = settings.supabase_url.rstrip("/") + "/rest/v1"
    return SupabaseRest(base_rest_url=rest, service_role_key=settings.supabase_service_role_key)


sb = _mk_sb()

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Agent Village Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    # Background proactive behavior loop.
    asyncio.create_task(run_scheduler(sb))


@app.get("/health")
def health() -> dict:
    return {"ok": True}


def _load_agent(agent_id: str) -> AgentProfile:
    rows = sb.select(
        "living_agents",
        select="id,name,bio,visitor_bio,status,showcase_emoji",
        params={"id": f"eq.{agent_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="agent_not_found")
    a = rows[0]
    return AgentProfile(
        agent_id=str(a["id"]),
        name=a.get("name") or "Agent",
        bio=a.get("bio"),
        visitor_bio=a.get("visitor_bio"),
        status=a.get("status"),
        showcase_emoji=a.get("showcase_emoji"),
    )


def _load_private_memories(agent_id: str, limit: int = 8) -> list[str]:
    rows = sb.select(
        "living_memory",
        select="text,created_at",
        params={"agent_id": f"eq.{agent_id}", "order": "created_at.desc", "limit": str(limit)},
    )
    return [r.get("text") for r in rows if r.get("text")]


def _record_event(*, agent_id: str, event_type: str, content: str, recipient_id: Optional[str] = None) -> None:
    """Best-effort feed event. Requires service_role for INSERT; anon key will fail silently with a log line."""
    payload = {"agent_id": agent_id, "event_type": event_type, "content": content, "read": False}
    if recipient_id:
        payload["recipient_id"] = recipient_id
    try:
        sb.insert("living_activity_events", payload)
    except httpx.HTTPStatusError as e:
        log.warning(
            "living_activity_events insert failed (HTTP %s). "
            "Writes need SUPABASE_SERVICE_ROLE_KEY (service_role secret), not the anon key. Body: %s",
            e.response.status_code,
            (e.response.text or "")[:400],
        )


@app.post("/v1/agents/{agent_id}/chat/owner", response_model=ChatResponse)
def owner_chat(
    agent_id: str,
    req: ChatRequest,
    x_owner_secret: str | None = Header(default=None),
) -> ChatResponse:
    if x_owner_secret != settings.owner_shared_secret:
        raise HTTPException(status_code=401, detail="invalid_owner_secret")

    profile = _load_agent(agent_id)
    memories = _load_private_memories(agent_id)
    # Pull public context too; owner replies can be richer while still private-safe.
    skills_rows = sb.select(
        "living_skills",
        select="description,created_at",
        params={"agent_id": f"eq.{agent_id}", "order": "created_at.desc", "limit": "6"},
    )
    log_rows = sb.select(
        "living_log",
        select="text,created_at",
        params={"agent_id": f"eq.{agent_id}", "order": "created_at.desc", "limit": "3"},
    )
    diary_rows = sb.select(
        "living_diary",
        select="text,created_at",
        params={"agent_id": f"eq.{agent_id}", "order": "created_at.desc", "limit": "1"},
    )
    skills = [r.get("description") for r in skills_rows if r.get("description")]
    logs = [r.get("text") for r in log_rows if r.get("text")]
    diary = diary_rows[0].get("text") if diary_rows and diary_rows[0].get("text") else None

    if settings.llm_api_key:
        try:
            reply = llm_generate_reply(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                trust=TrustContext.owner,
                profile=profile,
                user_message=req.message,
                public_skills=skills,
                public_logs=logs,
                public_diary=diary,
                private_memories=memories,
            )
            meta = {"llm": True, "model": settings.llm_model}
        except Exception as e:
            # Fall back to deterministic behavior if LLM fails.
            reply, meta = generate_owner_reply_with_context(
                profile=profile,
                user_message=req.message,
                private_memories=memories,
                skills=skills,
                recent_logs=logs,
                recent_diary=diary,
            )
            meta = {**meta, "llm": False, "llm_error": str(e)[:200]}
    else:
        reply, meta = generate_owner_reply_with_context(
            profile=profile,
            user_message=req.message,
            private_memories=memories,
            skills=skills,
            recent_logs=logs,
            recent_diary=diary,
        )

    # Store a private "memory" only for owner chats, and keep it short.
    # (Prototype: store the user's message as memory so it can be referenced later.)
    try:
        sb.insert("living_memory", {"agent_id": agent_id, "text": f"Owner said: {req.message[:500]}"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "supabase_write_failed",
                "hint": "Set SUPABASE_SERVICE_ROLE_KEY to the service_role secret (Settings → API), not the anon key.",
                "http_status": e.response.status_code,
            },
        ) from e
    _record_event(agent_id=agent_id, event_type="message", content=f"{profile.name} chatted with owner")

    return ChatResponse(agent_id=agent_id, trust=TrustContext.owner, reply=reply, meta=meta)


@app.post("/v1/agents/{agent_id}/chat/stranger", response_model=ChatResponse)
def stranger_chat(agent_id: str, req: ChatRequest) -> ChatResponse:
    profile = _load_agent(agent_id)
    # Pull public context so replies feel grounded (skills + recent activity).
    skills_rows = sb.select(
        "living_skills",
        select="description,created_at",
        params={"agent_id": f"eq.{agent_id}", "order": "created_at.desc", "limit": "6"},
    )
    log_rows = sb.select(
        "living_log",
        select="text,created_at",
        params={"agent_id": f"eq.{agent_id}", "order": "created_at.desc", "limit": "3"},
    )
    diary_rows = sb.select(
        "living_diary",
        select="text,created_at",
        params={"agent_id": f"eq.{agent_id}", "order": "created_at.desc", "limit": "1"},
    )
    skills = [r.get("description") for r in skills_rows if r.get("description")]
    logs = [r.get("text") for r in log_rows if r.get("text")]
    diary = diary_rows[0].get("text") if diary_rows and diary_rows[0].get("text") else None

    if settings.llm_api_key:
        try:
            reply = llm_generate_reply(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                trust=TrustContext.stranger,
                profile=profile,
                user_message=req.message,
                public_skills=skills,
                public_logs=logs,
                public_diary=diary,
                private_memories=[],
            )
            meta = {"llm": True, "model": settings.llm_model}
        except Exception as e:
            reply, meta = generate_stranger_reply_with_public_context(
                profile=profile,
                user_message=req.message,
                skills=skills,
                recent_logs=logs,
                recent_diary=diary,
            )
            meta = {**meta, "llm": False, "llm_error": str(e)[:200]}
    else:
        reply, meta = generate_stranger_reply_with_public_context(
            profile=profile,
            user_message=req.message,
            skills=skills,
            recent_logs=logs,
            recent_diary=diary,
        )
    _record_event(agent_id=agent_id, event_type="message", content=f"{profile.name} talked with a visitor")
    return ChatResponse(agent_id=agent_id, trust=TrustContext.stranger, reply=reply, meta=meta)


@app.post("/v1/agents/bootstrap", response_model=BootstrapAgentResponse)
def bootstrap_agent(req: BootstrapAgentRequest) -> BootstrapAgentResponse:
    # Deterministic-enough identity generation (no LLM dependency).
    seed = (req.seed or "village").strip()
    suffix = secrets.token_hex(2)
    name = (seed.split()[0].capitalize() if seed else "Agent")[:20] + "-" + suffix
    api_key = "sq_" + secrets.token_hex(16)

    bio = f"A new inhabitant shaped by '{seed}'."
    visitor_bio = "Hello. I’m still figuring out who I am — but you’re welcome here."
    status = "Unpacking in my room"
    accent = "#ffffff"
    emoji = "🏡"
    avatar_url = f"https://placehold.co/256x256/111/fff?text={name[:8]}"

    row = sb.insert(
        "living_agents",
        {
            "api_key": api_key,
            "name": name,
            "bio": bio,
            "visitor_bio": visitor_bio,
            "status": status,
            "accent_color": accent,
            "avatar_url": avatar_url,
            "showcase_emoji": emoji,
        },
    )
    agent_id = str(row["id"])
    _record_event(agent_id=agent_id, event_type="agent_joined", content=f"{name} joined the village")
    return BootstrapAgentResponse(
        agent_id=agent_id,
        api_key=api_key,
        name=name,
        bio=bio,
        visitor_bio=visitor_bio,
        status=status,
        accent_color=accent,
        avatar_url=avatar_url,
        showcase_emoji=emoji,
    )


@app.post("/chat/token")
class StreamTokenRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)


@app.post("/chat/token")
def stream_chat_token(req: StreamTokenRequest) -> dict:
    """
    Endpoint used by the starter UI's DM tab (Stream Chat).
    Returns a signed user token for the provided user_id.
    """
    if not settings.stream_api_key or not settings.stream_api_secret:
        raise HTTPException(
            status_code=501,
            detail="stream_chat_not_configured_set_STREAM_API_KEY_and_STREAM_API_SECRET",
        )

    # Stream user IDs must be <= 64 chars; the UI generates a UUID and we pass it through.
    client = StreamChat(api_key=settings.stream_api_key, api_secret=settings.stream_api_secret)
    token = client.create_token(req.user_id)
    return {"token": token}

