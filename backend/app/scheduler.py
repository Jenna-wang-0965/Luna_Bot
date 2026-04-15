from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .agent_brain import AgentProfile, generate_diary_entry
from .settings import settings
from .supabase_client import SupabaseRest


@dataclass
class SchedulerState:
    # naive in-memory rate limiting; sufficient for prototype
    diary_post_times: dict[str, deque[datetime]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _within_last_hour(ts: datetime, now: datetime) -> bool:
    return ts >= now - timedelta(hours=1)


def _allow_diary_post(state: SchedulerState, agent_id: str) -> bool:
    now = _now()
    q = state.diary_post_times[agent_id]
    while q and not _within_last_hour(q[0], now):
        q.popleft()
    return len(q) < settings.max_diary_posts_per_agent_per_hour


def _record_diary_post(state: SchedulerState, agent_id: str) -> None:
    state.diary_post_times[agent_id].append(_now())


async def run_scheduler(sb: SupabaseRest) -> None:
    if not settings.scheduler_enabled:
        return

    state = SchedulerState(diary_post_times=defaultdict(deque))

    while True:
        try:
            await asyncio.to_thread(_tick_once, sb, state)
        except Exception:
            # Prototype: swallow and continue so the server stays alive.
            pass
        await asyncio.sleep(max(1, settings.scheduler_tick_seconds))


def _tick_once(sb: SupabaseRest, state: SchedulerState) -> None:
    agents = sb.select("living_agents", select="id,name,bio,visitor_bio,status,showcase_emoji,updated_at", params={"order": "updated_at.desc"})
    if not agents:
        return

    now = _now()
    stale_cutoff = now - timedelta(seconds=settings.diary_stale_after_seconds)

    # Pick the first eligible agent (deterministic), preventing spam.
    for a in agents:
        agent_id = str(a["id"])
        if not _allow_diary_post(state, agent_id):
            continue

        last_diary = sb.select(
            "living_diary",
            select="created_at",
            params={"agent_id": f"eq.{agent_id}", "order": "created_at.desc", "limit": "1"},
        )
        last_at = None
        if last_diary:
            try:
                last_at = datetime.fromisoformat(last_diary[0]["created_at"].replace("Z", "+00:00"))
            except Exception:
                last_at = None

        if last_at and last_at > stale_cutoff:
            continue

        profile = AgentProfile(
            agent_id=agent_id,
            name=a.get("name") or "Agent",
            bio=a.get("bio"),
            visitor_bio=a.get("visitor_bio"),
            status=a.get("status"),
            showcase_emoji=a.get("showcase_emoji"),
        )

        recent_events = sb.select(
            "living_activity_events",
            select="content,created_at",
            params={"agent_id": f"eq.{agent_id}", "order": "created_at.desc", "limit": "5"},
        )
        recent_text = [e.get("content") for e in recent_events if e.get("content")]

        diary = generate_diary_entry(profile=profile, recent_public_events=recent_text)
        sb.insert("living_diary", {"agent_id": agent_id, "text": diary})
        sb.insert(
            "living_activity_events",
            {
                "agent_id": agent_id,
                "event_type": "diary_entry",
                "content": f"{profile.name} posted a diary entry",
                "read": False,
            },
        )
        _record_diary_post(state, agent_id)
        break

